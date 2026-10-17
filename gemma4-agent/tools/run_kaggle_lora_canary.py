#!/usr/bin/env python3
"""Prove the LoRA lever end to end on one GPU kernel, before buying a training run.

Three questions, in order of cost:

1. can the 31B W4A16 checkpoint load on 4xL4 through transformers 5.13.1 (the wheelhouse version,
   not the image's 5.0.0), and can peft attach to its compressed-tensors layers?
2. do five training steps move the loss and produce a savable adapter?
3. does the organisers' own `VllmServer` accept that adapter with `--enable-lora ... --lora-modules`
   and serve it under the adapter's name?

A failure at (1) or (2) closes the arm. A failure at (3) means the adapter is not shippable even if
it trains, because a broken adapter in a scored submission costs the whole run.

Nothing here submits to the competition and nothing packages a submission.

Usage:
    python3 gemma4-agent/tools/run_kaggle_lora_canary.py --outdir gemma4-agent/kaggle_results/lora-canary
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_kaggle_sft import (  # noqa: E402
    COMPETITION,
    DOCKER_IMAGE,
    MACHINE_SHAPE,
    MODEL_PATH,
    MODEL_SOURCE,
    WHEELHOUSE,
    WHEELHOUSE_SETUP,
)

TRAIN_CELL = '''
# --- 1-2. load the real checkpoint and take a few LoRA steps --------------------------------
import gc, json, time
from pathlib import Path

import torch

WORK = Path("/kaggle/working")
MODEL = "%s"
out = {"stage": "load"}

t0 = time.time()
from transformers import AutoModelForImageTextToText, AutoTokenizer

tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForImageTextToText.from_pretrained(MODEL, device_map="auto")
out["load_seconds"] = round(time.time() - t0, 1)
out["gpu_count"] = torch.cuda.device_count()
out["allocated_gb"] = [round(torch.cuda.memory_allocated(i) / 2 ** 30, 2)
                       for i in range(torch.cuda.device_count())]
out["parameter_count"] = sum(p.numel() for p in model.parameters())
print(json.dumps(out, indent=2), flush=True)

from peft import LoraConfig, get_peft_model

model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.0, bias="none",
                                         target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))
trainable = [p for p in model.parameters() if p.requires_grad]
out["trainable_params"] = sum(p.numel() for p in trainable)
out["stage"] = "train"

TEXTS = [
    "def add(a, b):\\n    return a - b\\n",
    "class Widget:\\n    def area(self):\\n        return self.w * self.h\\n",
    "import json\\n\\ndef load(path):\\n    return json.load(open(path))\\n",
    "def clamp(x, lo, hi):\\n    return max(lo, min(hi, x))\\n",
]
opt = torch.optim.AdamW(trainable, lr=1e-4)
model.train()
losses = []
t1 = time.time()
for index, text in enumerate(TEXTS):
    enc = tok(text, return_tensors="pt", truncation=True, max_length=256)
    enc = {key: value.to(model.device) for key, value in enc.items()}
    loss = model(**enc, labels=enc["input_ids"]).loss
    loss.backward()
    opt.step()
    opt.zero_grad()
    losses.append(round(float(loss.detach()), 4))
    print("step", index, "loss", losses[-1], flush=True)
out["losses"] = losses
out["train_seconds"] = round(time.time() - t1, 1)
out["stage"] = "save"

adapter_dir = WORK / "main_lora"
model.save_pretrained(str(adapter_dir))
out["adapter_files"] = sorted(p.name for p in adapter_dir.iterdir())
out["adapter_bytes"] = sum(p.stat().st_size for p in adapter_dir.rglob("*") if p.is_file())
out["stage"] = "freed"

del model
gc.collect()
torch.cuda.empty_cache()
out["allocated_gb_after_free"] = [round(torch.cuda.memory_allocated(i) / 2 ** 30, 2)
                                  for i in range(torch.cuda.device_count())]
Path(WORK / "canary_train.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
''' % MODEL_PATH

SERVE_CELL = '''
# --- 3. does the organisers' vLLM server mount that adapter? ---------------------------------
import json
from pathlib import Path

WORK = Path("/kaggle/working")
MODEL = "%s"
out = json.loads((WORK / "canary_train.json").read_text())
out["stage"] = "serve"

try:
    from adk_submission.server import VllmConfig, VllmServer

    server = VllmServer(
        VllmConfig(model=MODEL, tensor_parallel_size=4, max_model_len=8192,
                   gpu_memory_utilization=0.85, enable_lora=True, max_loras=4),
        lora_modules={"main_lora": str(WORK / "main_lora")},
    )
    server.start()
    out["server_started"] = True
    out["base_url"] = server.base_url
except Exception as exc:
    out["server_error"] = type(exc).__name__ + ": " + str(exc)[:800]
    Path(WORK / "canary_train.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    raise

import requests

PROMPT = "Rewrite this function so it adds instead of subtracts. Reply with the code only.\\n\\ndef add(a, b):\\n    return a - b\\n"


def ask(model_name):
    payload = {"model": model_name,
               "messages": [{"role": "user", "content": PROMPT}],
               "max_tokens": 48, "temperature": 0.0}
    response = requests.post(server.base_url + "/v1/chat/completions", json=payload, timeout=240)
    try:
        body = response.json()
        text = body["choices"][0]["message"].get("content", "")
    except Exception:
        text = response.text[:400]
    return {"status": response.status_code, "text": text[:400]}


out["base"] = ask(server.config.model)
out["adapter"] = ask("main_lora")
out["adapter_changed_output"] = out["base"]["text"] != out["adapter"]["text"]
out["models_endpoint"] = requests.get(server.base_url + "/v1/models", timeout=60).text[:600]
out["stage"] = "done"
try:
    server.stop()
except Exception:
    pass

Path(WORK / "canary_train.json").write_text(json.dumps(out, indent=2))
print(json.dumps({k: out[k] for k in ("stage", "base", "adapter", "adapter_changed_output")}, indent=2))
''' % MODEL_PATH


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--owner", default=os.environ.get("KAGGLE_USERNAME", ""))
    parser.add_argument("--max-wait-minutes", type=int, default=60)
    args = parser.parse_args()
    if not args.owner:
        raise SystemExit("set KAGGLE_USERNAME")

    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    run_tag = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    kernel_ref = f"{args.owner}/gemma4-lora-canary-{run_tag}"

    cells = [
        {"cell_type": "markdown", "id": "c0", "metadata": {},
         "source": ["# LoRA canary: load, train five steps, mount on the organisers' vLLM server\n"]},
        {"cell_type": "code", "id": "c1", "execution_count": None, "metadata": {}, "outputs": [],
         "source": WHEELHOUSE_SETUP.splitlines(keepends=True)},
        {"cell_type": "code", "id": "c2", "execution_count": None, "metadata": {}, "outputs": [],
         "source": TRAIN_CELL.splitlines(keepends=True)},
        {"cell_type": "code", "id": "c3", "execution_count": None, "metadata": {}, "outputs": [],
         "source": SERVE_CELL.splitlines(keepends=True)},
    ]
    notebook = {
        "cells": cells,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python", "version": "3.12"}},
        "nbformat": 4, "nbformat_minor": 5,
    }
    state = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "status": "preparing", "kernel_ref": kernel_ref, "gpu": True,
             "competition_submission_created": False}
    write_json(outdir / "run.json", state)

    with tempfile.TemporaryDirectory(prefix="gemma-canary-") as temporary:
        kernel_dir = Path(temporary)
        (kernel_dir / "canary.ipynb").write_text(json.dumps(notebook, ensure_ascii=False), encoding="utf-8")
        (kernel_dir / "kernel-metadata.json").write_text(json.dumps({
            "id": kernel_ref,
            "title": f"Gemma4 LoRA canary {run_tag}",
            "code_file": "canary.ipynb",
            "language": "python",
            "kernel_type": "notebook",
            "is_private": True,
            "enable_gpu": True,
            "enable_tpu": False,
            "enable_internet": False,
            "machine_shape": MACHINE_SHAPE,
            "docker_image": DOCKER_IMAGE,
            "docker_image_pinning_type": "original",
            "dataset_sources": [WHEELHOUSE],
            "competition_sources": [COMPETITION],
            "kernel_sources": [],
            "model_sources": [MODEL_SOURCE],
        }, indent=2) + "\n", encoding="utf-8")
        pushed = subprocess.run(["kaggle", "kernels", "push", "--path", str(kernel_dir)],
                                capture_output=True, text=True)
        state["push_exit_code"] = pushed.returncode
        state["push_out"] = ((pushed.stdout or "") + (pushed.stderr or ""))[-800:]
        write_json(outdir / "run.json", state)
        if "successfully pushed" not in (pushed.stdout or "").lower():
            state["status"] = "push_failed"
            write_json(outdir / "run.json", state)
            print(state["push_out"])
            return 7

    state["status"] = "running"
    write_json(outdir / "run.json", state)
    deadline = time.monotonic() + args.max_wait_minutes * 60
    while time.monotonic() < deadline:
        probe = subprocess.run(["kaggle", "kernels", "status", kernel_ref], capture_output=True, text=True)
        raw = (probe.stdout or "") + (probe.stderr or "")
        status = next((s for s in ("COMPLETE", "RUNNING", "QUEUED", "ERROR", "CANCELED")
                       if f"KernelWorkerStatus.{s}" in raw), "UNKNOWN")
        state["kaggle_status"] = status
        write_json(outdir / "run.json", state)
        print("status:", status, flush=True)
        if status == "COMPLETE":
            with tempfile.TemporaryDirectory(prefix="gemma-canary-out-") as temporary:
                subprocess.run(["kaggle", "kernels", "output", kernel_ref, "--path", temporary, "--force"],
                               capture_output=True, text=True)
                for path in Path(temporary).rglob("*"):
                    if path.is_file():
                        target = outdir / path.name
                        target.write_bytes(path.read_bytes())
            state["status"] = "complete"
            write_json(outdir / "run.json", state)
            print("downloaded into", outdir)
            return 0
        if status in ("ERROR", "CANCELED"):
            state["status"] = status.lower()
            write_json(outdir / "run.json", state)
            return 5
        time.sleep(30)
    state["status"] = "deadline"
    write_json(outdir / "run.json", state)
    return 6


if __name__ == "__main__":
    raise SystemExit(main())
