#!/usr/bin/env python3
"""Ask Kaggle's competition image - on CPU, for free - whether the SFT path is possible at all.

The smoke kernel proved the dataset builder works (4 train / 2 holdout examples, locator top-1
0.33) and then died at `AutoConfig.from_pretrained` with

    ValueError: The checkpoint ... has model type `gemma4` but Transformers does not recognize
    this architecture

with transformers 5.0.0 and no internet to upgrade. That single fact decides whether LoRA is a real
option or a dead end, and it can be answered without a GPU:

  * does anything in the competition wheelhouse teach transformers about `gemma4`?
  * is `trl` available at all (the smoke run reported "not importable")?
  * which versions of transformers / peft / vllm / swegemma / adk_submission are installed?
  * can vLLM load the model and apply an adapter, even if transformers cannot?

A CPU kernel costs no GPU quota, so this runs before any more training time is spent.

Usage:
    python3 gemma4-agent/tools/diagnose_gemma4_env.py --outdir gemma4-agent/kaggle_results/gemma4-env
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

COMPETITION = "gemma-4-developer-agent"
MODEL_SOURCE = "google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2"
WHEELHOUSE = "metric/gemma-4-developer-agent-wheelhouse"
IMAGE = (
    "gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461"
)

DIAGNOSE = r'''# --- environment report: no GPU, no training, just facts --------------------------------
import glob, json, os, subprocess, sys, zipfile
from pathlib import Path

WH = Path("/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse")
MODEL = "/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2"

# Every version check runs in a SUBPROCESS. Importing transformers or safetensors here, before the
# wheelhouse is installed, poisons this interpreter: pip replaces the files but not sys.modules, and
# safetensors cannot even be re-imported afterwards (PyO3 refuses a second initialisation).
VERSIONS = (
    "import importlib, json\n"
    "out = {}\n"
    "for mod in ('torch', 'transformers', 'peft', 'trl', 'vllm', 'swegemma', 'adk_submission',\n"
    "            'accelerate', 'datasets', 'bitsandbytes', 'safetensors', 'compressed_tensors'):\n"
    "    try:\n"
    "        m = importlib.import_module(mod)\n"
    "        out[mod] = getattr(m, '__version__', 'imported-no-version')\n"
    "    except Exception as exc:\n"
    "        out[mod] = 'NOT IMPORTABLE (' + type(exc).__name__ + ')'\n"
    "print(json.dumps(out))\n"
)


def versions():
    proc = subprocess.run([sys.executable, "-c", VERSIONS], capture_output=True, text=True)
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"error": (proc.stdout + proc.stderr)[-600:]}


report = {"python": sys.version.split()[0]}
report["wheelhouse_mounted"] = WH.is_dir()
report["wheel_count"] = len(list(WH.glob("*.whl")))
report["wheels"] = sorted(p.name for p in WH.glob("*.whl"))
report["before_install"] = versions()

# install the wheelhouse exactly as the scored harness does, before anything imports it
tmp = Path("/tmp/wheelhouse"); tmp.mkdir(parents=True, exist_ok=True)
for wheel in WH.glob("*.whl"):
    if "cutlass" in wheel.name.lower():
        continue
    name = wheel.name.replace("cu128", "+cu128") if ("cu128" in wheel.name and "+" not in wheel.name) else wheel.name
    target = tmp / name
    if not target.exists():
        os.symlink(wheel, target)
wheels = sorted(str(p) for p in tmp.glob("*.whl"))
if wheels:
    proc = subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps",
                           "--force-reinstall", *wheels], capture_output=True, text=True)
    report["install_returncode"] = proc.returncode
    report["install_stdout_tail"] = proc.stdout[-1200:]
    report["install_stderr_tail"] = proc.stderr[-1200:]
report["after_install"] = versions()

# the decisive question: can anything read the model config?
report["model_dir"] = Path(MODEL).is_dir()
try:
    report["model_files"] = sorted(p.name for p in Path(MODEL).iterdir())[:20]
except Exception as exc:
    report["model_files"] = ["error: " + str(exc)]
try:
    raw = json.loads((Path(MODEL) / "config.json").read_text())
    report["config_model_type"] = raw.get("model_type")
    report["config_architectures"] = raw.get("architectures")
    report["config_keys"] = sorted(raw.keys())[:25]
except Exception as exc:
    report["config_error"] = type(exc).__name__ + ": " + str(exc)

import transformers
cfg = None
try:
    cfg = transformers.AutoConfig.from_pretrained(MODEL)
    report["autoconfig_plain"] = "OK (" + type(cfg).__name__ + ")"
except Exception as exc:
    report["autoconfig_plain"] = type(exc).__name__ + ": " + str(exc)[:200]
try:
    models_dir = Path(transformers.__file__).parent / "models"
    report["transformers_gemma_dirs"] = sorted(p.name for p in models_dir.glob("gemma*"))
    report["transformers_version_loaded"] = transformers.__version__
except Exception as exc:
    report["transformers_gemma_dirs"] = "error: " + str(exc)

report["transformers_like_wheels"] = [w for w in report.get("wheels", [])
                                      if any(k in w.lower() for k in ("transformers", "trl", "swegemma", "adk", "peft"))]

print(json.dumps(report, indent=2)[:12000])
Path("/kaggle/working/env_report.json").write_text(json.dumps(report, indent=2))
'''


TRAIN_PROBE = '# --- can the 31B W4A16 checkpoint load and take a LoRA on CPU? --------------------------------\n# Free counterpart of the GPU canary: if peft cannot wrap compressed-tensors layers, no amount of\n# GPU time will help, and if it can, the GPU run is mostly a matter of memory.\nimport gc, json, struct, time, traceback\n\nfrom pathlib import Path\n\nMODEL = "/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2"\nout = {"model_dir": Path(MODEL).is_dir()}\n\n# 1. what does the checkpoint declare, and what do its tensors look like?\ncfg = None\ntry:\n    from transformers import AutoConfig\n    cfg = AutoConfig.from_pretrained(MODEL)\n    qc = getattr(cfg, "quantization_config", None)\n    if isinstance(qc, dict):\n        group = next(iter((qc.get("config_groups") or {}).values()), {}) or {}\n        weights = group.get("weights") or {}\n        out["quantization"] = {"quant_method": qc.get("quant_method"),\n                               "format": qc.get("format"),\n                               "num_bits": weights.get("num_bits"),\n                               "group_size": weights.get("group_size"),\n                               "ignore_count": len(qc.get("ignore") or [])}\n    else:\n        out["quantization"] = str(qc)[:200]\n    print("config read", flush=True)\n    text = getattr(cfg, "text_config", cfg)\n    out["geometry"] = {k: getattr(text, k, None) for k in\n                       ("num_hidden_layers", "hidden_size", "num_attention_heads", "num_key_value_heads")}\nexcept Exception:\n    out["config_error"] = traceback.format_exc()[-1200:]\n\ntry:\n    with open(Path(MODEL) / "model.safetensors", "rb") as fh:\n        n = struct.unpack("<Q", fh.read(8))[0]\n        header = json.loads(fh.read(n))\n    keys = [k for k in header if k != "__metadata__"]\n    out["tensor_count"] = len(keys)\n    out["tensor_examples"] = keys[:14]\n    out["has_compressed"] = sum("weight_scale" in k or "weight_packed" in k for k in keys)\nexcept Exception:\n    out["safetensors_error"] = traceback.format_exc()[-800:]\n\n# 2. which auto class is supposed to hold it?\nfor name in ("AutoModelForCausalLM", "AutoModelForImageTextToText", "AutoModel"):\n    try:\n        import transformers\n        auto = getattr(transformers, name)\n        cls = auto._model_mapping.get(type(cfg)) if cfg is not None else None\n        out["auto_" + name] = getattr(cls, "__name__", repr(cls))\n    except Exception as exc:\n        out["auto_" + name] = repr(exc)\n\n# 3. load it for real, on CPU, then attach LoRA and run one step\nt0 = time.time()\nmodel = None\ntry:\n    import torch\n    from transformers import AutoModelForImageTextToText\n    torch.set_num_threads(4)\n    print("loading", flush=True)\n    model = AutoModelForImageTextToText.from_pretrained(MODEL, device_map="cpu")\n    print("loaded", flush=True)\n    out["loaded"] = True\n    out["load_seconds"] = round(time.time() - t0, 1)\n    out["dtype"] = str(next(model.parameters()).dtype)\n    classes = {}\n    for name, mod in model.named_modules():\n        classes[type(mod).__name__] = classes.get(type(mod).__name__, 0) + 1\n    out["module_classes"] = dict(sorted(classes.items(), key=lambda kv: -kv[1])[:12])\nexcept Exception:\n    out["load_error"] = traceback.format_exc()[-2500:]\n\nif model is not None:\n    try:\n        from peft import LoraConfig, get_peft_model\n        lora = LoraConfig(r=8, lora_alpha=16, lora_dropout=0.0, bias="none",\n                          target_modules=["q_proj", "k_proj", "v_proj", "o_proj"])\n        model = get_peft_model(model, lora)\n        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)\n        total = sum(p.numel() for p in model.parameters())\n        out["lora_attached"] = True\n        out["trainable_params"] = trainable\n        out["trainable_share"] = round(trainable / max(total, 1), 8)\n        out["lora_layer_types"] = sorted({type(m).__name__ for m in model.modules()\n                                          if "lora" in type(m).__name__.lower()})\n    except Exception:\n        out["lora_error"] = traceback.format_exc()[-2000:]\n\n    if out.get("lora_attached"):\n        try:\n            import torch\n            from transformers import AutoTokenizer\n            tok = AutoTokenizer.from_pretrained(MODEL)\n            ids = tok("def add(a, b):\\n    return ", return_tensors="pt").input_ids\n            model.train()\n            step = time.time()\n            loss = model(input_ids=ids, labels=ids).loss\n            loss.backward()\n            grads = [p.grad.abs().sum().item() for p in model.parameters()\n                     if p.requires_grad and p.grad is not None]\n            out["loss"] = float(loss.detach())\n            out["grad_tensors"] = len(grads)\n            out["grad_sum"] = float(sum(grads))\n            out["step_seconds"] = round(time.time() - step, 1)\n        except Exception:\n            out["step_error"] = traceback.format_exc()[-2500:]\n\n    del model\n    gc.collect()\n\nPath("/kaggle/working/train_probe.json").write_text(json.dumps(out, indent=2, default=str))\nprint(json.dumps(out, indent=2, default=str), flush=True)\n'

ADAPTER_CONTRACT = '# --- adapter contract: can a submission declare a LoRA adapter? --------------------------------\n# The schema field exists, so the question is whether discovery and validation accept a real\n# adapters/<name>/ directory. Everything here runs on CPU.\nimport inspect, json, shutil, textwrap\nfrom pathlib import Path\n\ncontract = {}\nsub = Path("/kaggle/working/fake_submission")\nshutil.rmtree(sub, ignore_errors=True)\n(sub / "adapters" / "main_lora").mkdir(parents=True)\n(sub / "prompts").mkdir()\n(sub / "prompts" / "system.md").write_text("probe system prompt\\n")\n(sub / "agent.yaml").write_text(textwrap.dedent("""\n    agent_class: LlmAgent\n    name: probe_agent\n    model: gemma-4-31b-it-qat-w4a16-ct\n    adapter: main_lora\n    instruction: !include prompts/system.md\n    tools:\n      - run_command\n"""))\n\nimport torch\nfrom safetensors.torch import save_file\nsave_file({\n    "base_model.model.model.language_model.layers.0.self_attn.q_proj.lora_A.weight": torch.zeros(8, 16),\n    "base_model.model.model.language_model.layers.0.self_attn.q_proj.lora_B.weight": torch.zeros(16, 8),\n}, str(sub / "adapters" / "main_lora" / "adapter_model.safetensors"))\n(sub / "adapters" / "main_lora" / "adapter_config.json").write_text(json.dumps({\n    "peft_type": "LORA", "task_type": "CAUSAL_LM", "r": 8, "lora_alpha": 16,\n    "lora_dropout": 0.0, "bias": "none", "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],\n    "base_model_name_or_path": "gemma-4-31b-it-qat-w4a16-ct",\n}, indent=2))\n\nfrom adk_submission import discovery\ncontract["signature_discover_adapters"] = str(inspect.signature(discovery.discover_adapters))\ntry:\n    manifest = discovery.discover_adapters(sub)\n    contract["adapters"] = {name: {"path": str(info.path), "rank": getattr(info, "rank", None)}\n                            for name, info in manifest.adapters.items()}\n    contract["manifest_type"] = type(manifest).__name__\nexcept Exception as exc:\n    contract["discover_adapters_error"] = repr(exc)\n\ntry:\n    validator = getattr(discovery, "validate_directory", None)\n    contract["signature_validate_directory"] = str(inspect.signature(validator)) if validator else None\n    if validator:\n        contract["validate_directory"] = str(validator(sub))\nexcept Exception as exc:\n    contract["validate_directory_error"] = repr(exc)\n\ntry:\n    from adk_submission.yaml_loader import load_yaml\n    data = load_yaml(sub / "agent.yaml", sub)\n    contract["agent_yaml_loaded"] = bool(data)\n    contract["agent_yaml_keys"] = sorted(data or {})\n    from adk_submission.schema import SandboxedLlmAgentConfig\n    contract["schema_fields"] = sorted(getattr(SandboxedLlmAgentConfig, "model_fields", {}))\n    cfg = SandboxedLlmAgentConfig(**data)\n    contract["adapter_resolved"] = getattr(cfg, "adapter", "<missing>")\nexcept Exception as exc:\n    contract["schema_error"] = repr(exc)\n\ntry:\n    from adk_submission import server\n    contract["server_functions"] = [n for n, _ in inspect.getmembers(server, inspect.isfunction)]\n    contract["server_classes"] = [n for n, _ in inspect.getmembers(server, inspect.isclass)]\n    src = Path(server.__file__).read_text(encoding="utf-8")\n    Path("/kaggle/working/adk_server_source.txt").write_text(src)\n    for flag in ("enable_lora", "lora_modules", "max_lora_rank", "max_loras",\n                 "quantization", "compressed", "gemma-4"):\n        at = src.find(flag)\n        if at >= 0:\n            contract["server_" + flag] = src[max(0, at - 120):at + 240]\nexcept Exception as exc:\n    contract["server_error"] = repr(exc)\n\nPath("/kaggle/working/adapter_contract.json").write_text(json.dumps(contract, indent=2))\nprint(json.dumps(contract, indent=2)[:8000])\n'


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--owner", default=os.environ.get("KAGGLE_USERNAME", ""))
    parser.add_argument("--max-wait-minutes", type=int, default=40)
    parser.add_argument("--phase", choices=("env", "train"), default="env",
                        help="train = load the checkpoint on CPU and take one LoRA step")
    parser.add_argument("--image", choices=("default", "competition"), default="default",
                        help="competition = the private BYOD image the scored harness uses")
    args = parser.parse_args()
    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    if not args.owner:
        raise SystemExit("set KAGGLE_USERNAME")

    run_tag = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    kernel_ref = f"{args.owner}/gemma4-env-diagnose-{run_tag}"
    cells = [
        {"cell_type": "markdown", "id": "c0", "metadata": {},
         "source": ["# Gemma 4 environment diagnosis (CPU only, no training)\n"]},
        {"cell_type": "code", "id": "c1", "execution_count": None, "metadata": {}, "outputs": [],
         "source": DIAGNOSE.splitlines(keepends=True)},
        {"cell_type": "code", "id": "c2", "execution_count": None, "metadata": {}, "outputs": [],
         "source": ADAPTER_CONTRACT.splitlines(keepends=True)},
    ]
    if args.phase == "train":
        cells = cells[:2] + [
            {"cell_type": "code", "id": "c3", "execution_count": None, "metadata": {},
             "outputs": [], "source": TRAIN_PROBE.splitlines(keepends=True)},
        ]
    notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                            "language_info": {"name": "python", "version": "3.12"}},
                "nbformat": 4, "nbformat_minor": 5}
    state = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "status": "preparing", "kernel_ref": kernel_ref, "cpu_only": True,
             "image": args.image,
             "competition_submission_created": False}
    write_json(outdir / "run.json", state)

    with tempfile.TemporaryDirectory(prefix="gemma-env-") as temporary:
        kernel_dir = Path(temporary)
        (kernel_dir / "diagnose.ipynb").write_text(json.dumps(notebook, ensure_ascii=False), encoding="utf-8")
        metadata = {
            "id": kernel_ref,
            "title": f"Gemma4 env diagnose {run_tag}",
            "code_file": "diagnose.ipynb",
            "language": "python",
            "kernel_type": "notebook",
            "is_private": True,
            "enable_gpu": False,
            "enable_tpu": False,
            "enable_internet": False,
            "dataset_sources": [WHEELHOUSE],
            "competition_sources": [COMPETITION],
            "kernel_sources": [],
            "model_sources": [MODEL_SOURCE],
        }
        if args.image == "competition":
            metadata["docker_image"] = IMAGE
            metadata["docker_image_pinning_type"] = "original"
        (kernel_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n",
                                                         encoding="utf-8")
        pushed = subprocess.run(["kaggle", "kernels", "push", "--path", str(kernel_dir),
                                 "--timeout", str(args.max_wait_minutes * 60)],
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
            with tempfile.TemporaryDirectory(prefix="gemma-env-out-") as temporary:
                subprocess.run(["kaggle", "kernels", "output", kernel_ref, "--path", temporary, "--force"],
                               capture_output=True, text=True)
                for path in Path(temporary).rglob("*"):
                    if path.is_file():
                        target = outdir / path.relative_to(temporary)
                        target.parent.mkdir(parents=True, exist_ok=True)
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
