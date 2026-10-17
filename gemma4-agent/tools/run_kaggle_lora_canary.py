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

TRAIN_CELL = '# --- 1-2. load the checkpoint, wrap the text attention layers, take a few steps ----------------\n# The CPU probe showed two things: the checkpoint loads as Gemma4ForConditionalGeneration, and the\n# first forward makes compressed-tensors decompress the packed weights to bf16. On a CPU kernel that\n# is a 62 GB allocation and it dies; on 4xL4 it fits. Everything is staged so a failure still writes\n# what it learned and still produces an adapter for the serving test.\nimport gc, json, math, os, time, traceback\nfrom pathlib import Path\n\n# The first GPU attempt died 442 MiB short inside compressed-tensors decompression, which\n# materialises every packed weight as bf16 on the first forward. Less fragmentation, and no vision\n# tower - text-only training never touches its 27 layers of bf16 weights.\nos.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")\n\nimport torch\nfrom torch import nn\n\nWORK = Path("/kaggle/working")\nMODEL = "/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2"\nout = {"stage": "load"}\n\n\ndef save():\n    Path(WORK / "canary_train.json").write_text(json.dumps(out, indent=2, default=str))\n\n\nclass LoraLinear(nn.Module):\n    def __init__(self, base, rank=8, alpha=16):\n        super().__init__()\n        self.base = base\n        self.rank = rank\n        self.scaling = alpha / rank\n        self.lora_A = None\n        self.lora_B = None\n\n    def forward(self, x):\n        y = self.base(x)\n        if self.lora_A is None:\n            width, depth = x.shape[-1], y.shape[-1]\n            self.lora_A = nn.Parameter(torch.empty(self.rank, width, dtype=x.dtype, device=x.device))\n            self.lora_B = nn.Parameter(torch.zeros(depth, self.rank, dtype=x.dtype, device=x.device))\n            nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))\n        return y + (x @ self.lora_A.T @ self.lora_B.T) * self.scaling\n\n\nmodel = None\ntok = None\nt0 = time.time()\ntry:\n    from transformers import AutoModelForImageTextToText, AutoTokenizer\n    print("loading", flush=True)\n    model = AutoModelForImageTextToText.from_pretrained(MODEL, device_map="auto")\n    tok = AutoTokenizer.from_pretrained(MODEL)\n    out["load_seconds"] = round(time.time() - t0, 1)\n    try:\n        vision = getattr(model.model, "vision_tower", None)\n        if vision is not None:\n            model.model.vision_tower = None\n            del vision\n            gc.collect(); torch.cuda.empty_cache()\n            out["vision_dropped"] = True\n    except Exception:\n        out["vision_dropped"] = False\n    out["gpu_count"] = torch.cuda.device_count()\n    out["allocated_gb"] = [round(torch.cuda.memory_allocated(i) / 2 ** 30, 2)\n                           for i in range(torch.cuda.device_count())]\n    save()\n    print("loaded", out["allocated_gb"], flush=True)\n\n    swapped = 0\n    for layer in model.model.language_model.layers:\n        for name in ("q_proj", "k_proj", "v_proj", "o_proj"):\n            setattr(layer.self_attn, name, LoraLinear(getattr(layer.self_attn, name)))\n            swapped += 1\n    out["swapped_modules"] = swapped\n    out["stage"] = "train"\n    save()\n\n    texts = [\n        "def add(a, b):\\n    return a - b\\n",\n        "# clamp returns the wrong bound\\ndef clamp(x, lo, hi):\\n    return max(hi, min(lo, x))\\n",\n        "class Pool:\\n    def __init__(self, size):\\n        self.size = size\\n",\n        "import json\\n\\ndef load(path):\\n    with open(path) as fh:\\n        return json.load(fh)\\n",\n    ]\n    params = [p for p in model.parameters() if p.requires_grad]\n    opt = torch.optim.AdamW(params, lr=1e-4)\n    model.train()\n    losses = []\n    for index, text in enumerate(texts):\n        step = time.time()\n        enc = tok(text, return_tensors="pt", truncation=True, max_length=128)\n        enc = {key: value.to(model.device) for key, value in enc.items()}\n        loss = model(**enc, labels=enc["input_ids"]).loss\n        loss.backward()\n        opt.step()\n        opt.zero_grad()\n        losses.append(round(float(loss.detach()), 4))\n        print("step", index, "loss", losses[-1], "s", round(time.time() - step, 1), flush=True)\n    out["losses"] = losses\n    out["trainable_tensors"] = len(params)\n    out["trainable_params"] = sum(p.numel() for p in params)\n    out["peak_gb"] = [round(torch.cuda.max_memory_allocated(i) / 2 ** 30, 2)\n                      for i in range(torch.cuda.device_count())]\nexcept Exception:\n    out["train_error"] = traceback.format_exc()[-2500:]\n\nout["stage"] = "save_adapter"\nadapter = WORK / "main_lora"\nadapter.mkdir(parents=True, exist_ok=True)\ntry:\n    state = {}\n    if model is not None and out.get("losses"):\n        for name, module in model.named_modules():\n            if isinstance(module, LoraLinear) and module.lora_A is not None:\n                key = "base_model.model." + name\n                state[key + ".lora_A.weight"] = module.lora_A.detach().half().cpu()\n                state[key + ".lora_B.weight"] = module.lora_B.detach().half().cpu()\n        out["adapter_source"] = "trained"\n    else:\n        dims = {"q_proj": (5376, 5376), "k_proj": (2688, 5376),\n                "v_proj": (2688, 5376), "o_proj": (5376, 5376)}\n        for layer in range(60):\n            for name, (depth, width) in dims.items():\n                key = "base_model.model.model.language_model.layers.%d.self_attn.%s" % (layer, name)\n                state[key + ".lora_A.weight"] = torch.zeros(8, width, dtype=torch.half)\n                state[key + ".lora_B.weight"] = torch.zeros(depth, 8, dtype=torch.half)\n        out["adapter_source"] = "random"\n    from safetensors.torch import save_file\n    save_file(state, str(adapter / "adapter_model.safetensors"))\n    (adapter / "adapter_config.json").write_text(json.dumps({\n        "peft_type": "LORA", "task_type": "CAUSAL_LM", "r": 8, "lora_alpha": 16,\n        "lora_dropout": 0.0, "bias": "none",\n        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],\n        "base_model_name_or_path": "gemma-4-31b-it-qat-w4a16-ct",\n    }, indent=2))\n    out["adapter_tensors"] = len(state)\n    out["adapter_bytes"] = sum(p.stat().st_size for p in adapter.rglob("*") if p.is_file())\n    out["adapter_keys_sample"] = sorted(state)[:3]\nexcept Exception:\n    out["save_error"] = traceback.format_exc()[-2000:]\n\nif model is not None:\n    del model\ngc.collect()\ntorch.cuda.empty_cache()\nout["stage"] = "freed"\nout["allocated_gb_after_free"] = [round(torch.cuda.memory_allocated(i) / 2 ** 30, 2)\n                                  for i in range(torch.cuda.device_count())]\nsave()\nprint(json.dumps(out, indent=2, default=str)[:4000])\n'

SERVE_CELL = '\n# --- 3. does the organisers\' vLLM server mount that adapter? ---------------------------------\nimport json\nfrom pathlib import Path\n\nWORK = Path("/kaggle/working")\nMODEL = "/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2"\nreport_path = WORK / "canary_train.json"\nout = json.loads(report_path.read_text()) if report_path.exists() else {"stage": "serve_only"}\nout["stage"] = "serve"\n\n# In serve mode no training cell ran, so make the adapter that the mount test needs. It is\n# deliberately zero-initialised: the question here is whether vLLM accepts the file layout, not\n# whether the model improved.\nadapter_dir = WORK / "main_lora"\nif not (adapter_dir / "adapter_model.safetensors").exists():\n    import json as _json\n    import torch as _torch\n    from safetensors.torch import save_file as _save_file\n    adapter_dir.mkdir(parents=True, exist_ok=True)\n    _state = {}\n    _dims = {"q_proj": (5376, 5376), "k_proj": (2688, 5376),\n             "v_proj": (2688, 5376), "o_proj": (5376, 5376)}\n    for _layer in range(60):\n        for _name, (_depth, _width) in _dims.items():\n            _key = "base_model.model.model.language_model.layers.%d.self_attn.%s" % (_layer, _name)\n            _state[_key + ".lora_A.weight"] = _torch.zeros(8, _width, dtype=_torch.half)\n            _state[_key + ".lora_B.weight"] = _torch.zeros(_depth, 8, dtype=_torch.half)\n    _save_file(_state, str(adapter_dir / "adapter_model.safetensors"))\n    (adapter_dir / "adapter_config.json").write_text(_json.dumps({\n        "peft_type": "LORA", "task_type": "CAUSAL_LM", "r": 8, "lora_alpha": 16,\n        "lora_dropout": 0.0, "bias": "none",\n        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],\n        "base_model_name_or_path": "gemma-4-31b-it-qat-w4a16-ct",\n    }, indent=2))\n    out["adapter_source"] = "random"\n    out["adapter_bytes"] = sum(p.stat().st_size for p in adapter_dir.rglob("*") if p.is_file())\n\ntry:\n    from adk_submission.server import VllmConfig, VllmServer\n\n    server = VllmServer(\n        # The first attempt died in CUDA-graph capture with 13 MiB free: the weights alone are\n        # ~17 GB of the 22 GB card. Shorter context, less KV cache reserved, no graphs, one adapter.\n        VllmConfig(model=MODEL, tensor_parallel_size=4, max_model_len=4096,\n                   gpu_memory_utilization=0.80, enable_lora=True, max_loras=1,\n                   extra_args=["--enforce-eager"]),\n        lora_modules={"main_lora": str(WORK / "main_lora")},\n    )\n    server.start()\n    out["server_started"] = True\n    out["base_url"] = server.base_url\nexcept Exception as exc:\n    out["server_error"] = type(exc).__name__ + ": " + str(exc)[:800]\n    Path(WORK / "canary_train.json").write_text(json.dumps(out, indent=2))\n    print(json.dumps(out, indent=2))\n    raise\n\nimport requests\n\nPROMPT = "Rewrite this function so it adds instead of subtracts. Reply with the code only.\\n\\ndef add(a, b):\\n    return a - b\\n"\n\n\ndef ask(model_name):\n    payload = {"model": model_name,\n               "messages": [{"role": "user", "content": PROMPT}],\n               "max_tokens": 48, "temperature": 0.0}\n    response = requests.post(server.base_url + "/v1/chat/completions", json=payload, timeout=240)\n    try:\n        body = response.json()\n        text = body["choices"][0]["message"].get("content", "")\n    except Exception:\n        text = response.text[:400]\n    return {"status": response.status_code, "text": text[:400]}\n\n\nout["base"] = ask(server.config.model)\nout["adapter"] = ask("main_lora")\nout["adapter_changed_output"] = out["base"]["text"] != out["adapter"]["text"]\nout["models_endpoint"] = requests.get(server.base_url + "/v1/models", timeout=60).text[:600]\nout["stage"] = "done"\ntry:\n    server.stop()\nexcept Exception:\n    pass\n\nPath(WORK / "canary_train.json").write_text(json.dumps(out, indent=2))\nprint(json.dumps({k: out[k] for k in ("stage", "base", "adapter", "adapter_changed_output")}, indent=2))\n'

TRAIN_CELL = TRAIN_CELL.replace("__MODEL_PATH__", MODEL_PATH)
SERVE_CELL = SERVE_CELL.replace("__MODEL_PATH__", MODEL_PATH)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--owner", default=os.environ.get("KAGGLE_USERNAME", ""))
    parser.add_argument("--mode", choices=("both", "train", "serve"), default="both",
                        help="serve skips training and mounts a random adapter; train skips vLLM")
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
    ]
    if args.mode in ("both", "train"):
        cells.append({"cell_type": "code", "id": "c2", "execution_count": None, "metadata": {},
                      "outputs": [], "source": TRAIN_CELL.splitlines(keepends=True)})
    if args.mode in ("both", "serve"):
        cells.append({"cell_type": "code", "id": "c3", "execution_count": None, "metadata": {},
                      "outputs": [], "source": SERVE_CELL.splitlines(keepends=True)})
    notebook = {
        "cells": cells,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python", "version": "3.12"}},
        "nbformat": 4, "nbformat_minor": 5,
    }
    state = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "status": "preparing", "kernel_ref": kernel_ref, "gpu": True, "mode": args.mode,
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
        if status in ("COMPLETE", "ERROR", "CANCELED"):
            logs = subprocess.run(["kaggle", "kernels", "logs", kernel_ref], capture_output=True, text=True)
            raw = (logs.stdout or "") + (logs.stderr or "")
            if raw.strip():
                (outdir / "kernel.log").write_text(raw, encoding="utf-8", errors="replace")
                (outdir / "kernel_log_tail.md").write_text(raw[-20000:], encoding="utf-8", errors="replace")
                print("kernel log saved:", len(raw), "chars", flush=True)
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
