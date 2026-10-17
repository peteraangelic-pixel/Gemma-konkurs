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
import glob, importlib, json, os, subprocess, sys
from pathlib import Path

report = {"python": sys.version.split()[0]}
WH = Path("/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse")
report["wheelhouse_mounted"] = WH.is_dir()
try:
    report["wheels"] = sorted(p.name for p in WH.glob("*.whl"))[:60]
    report["wheel_count"] = len(list(WH.glob("*.whl")))
except Exception as exc:
    report["wheels"] = [f"error: {exc}"]

def versions():
    out = {}
    for mod in ("torch", "transformers", "peft", "trl", "vllm", "swegemma", "adk_submission",
                "accelerate", "datasets", "bitsandbytes", "safetensors"):
        try:
            m = importlib.import_module(mod)
            out[mod] = getattr(m, "__version__", "imported-no-version")
        except Exception as exc:
            out[mod] = f"NOT IMPORTABLE ({type(exc).__name__})"
    return out

report["before_install"] = versions()

# install the wheelhouse exactly as the scored harness does
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
    report["install_stdout_tail"] = proc.stdout[-1500:]
    report["install_stderr_tail"] = proc.stderr[-1500:]
importlib.invalidate_caches()
# The kernel's own preflight already imported transformers 5.0.0, and pip installing 5.13.1 does
# not replace a module that is already in sys.modules - that is the entire "gemma4 unsupported"
# wall. Purge it and import again.
for _name in [m for m in list(sys.modules) if m == "transformers" or m.startswith("transformers.")]:
    del sys.modules[_name]
report["purged_modules"] = True
report["after_install"] = versions()

# the decisive question: can anything read the model config?
MODEL = "/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2"
report["model_dir"] = Path(MODEL).is_dir()
try:
    report["model_files"] = sorted(p.name for p in Path(MODEL).iterdir())[:20]
except Exception as exc:
    report["model_files"] = [f"error: {exc}"]
try:
    raw = json.loads((Path(MODEL) / "config.json").read_text())
    report["config_model_type"] = raw.get("model_type")
    report["config_architectures"] = raw.get("architectures")
    report["config_keys"] = sorted(raw.keys())[:25]
except Exception as exc:
    report["config_error"] = f"{type(exc).__name__}: {exc}"

for label, attempt in (("plain", lambda: __import__("transformers").AutoConfig.from_pretrained(MODEL)),
                       ("after_swegemma", lambda: (__import__("swegemma"), __import__("transformers").AutoConfig.from_pretrained(MODEL))[1])):
    try:
        cfg = attempt()
        report[f"autoconfig_{label}"] = f"OK ({type(cfg).__name__})"
    except Exception as exc:
        report[f"autoconfig_{label}"] = f"{type(exc).__name__}: {str(exc)[:200]}"

# does any transformers module register gemma4?
try:
    import transformers
    models_dir = Path(transformers.__file__).parent / "models"
    report["transformers_gemma_dirs"] = sorted(p.name for p in models_dir.glob("gemma*"))
except Exception as exc:
    report["transformers_gemma_dirs"] = f"error: {exc}"

# what do the wheel filenames say about a transformers fork?
report["transformers_like_wheels"] = [w for w in report.get("wheels", [])
                                      if any(k in w.lower() for k in ("transformers", "trl", "swegemma", "adk", "peft"))]

# --- what the competition packages actually say -------------------------------------------
import re, zipfile
KEY = ("lora", "adapter", "peft", "vllm", "compressed", "quantiz", "max_time_minutes",
       "timeout_seconds", "max_turns", "max_tool_calls", "adapter_path", "submission")
probe = {"mounted": str(WH)}
interfaces = {}


def zip_text(wheel, predicate, limit=400000):
    parts, total = [], 0
    with zipfile.ZipFile(wheel) as zf:
        for name in zf.namelist():
            if not name.endswith(".py") or not predicate(name):
                continue
            body = zf.read(name).decode("utf-8", "replace")
            parts.append("\n\n### FILE " + name + "\n" + body)
            total += len(body)
            if total > limit:
                break
    return "".join(parts)


for wheel in sorted(WH.glob("*.whl")):
    if not any(k in wheel.name.lower() for k in ("swegemma", "adk_submission", "adk_eval_core", "transformers")):
        continue
    entry = {"size": wheel.stat().st_size}
    try:
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
        entry["file_count"] = len(names)
        entry["files"] = [n for n in names if n.endswith(".py")][:120]
        if wheel.name.startswith("transformers"):
            entry["gemma4_files"] = [n for n in names if "models/gemma4/" in n][:20]
            meta = [n for n in names if n.endswith("METADATA")]
            if meta:
                entry["metadata_head"] = zf.read(meta[0]).decode("utf-8", "replace")[:300]
    except Exception as exc:
        entry["error"] = str(exc)
    interfaces[wheel.name] = entry

hits = {}
for wheel in sorted(WH.glob("*.whl")):
    if not any(k in wheel.name.lower() for k in ("swegemma", "adk_submission", "adk_eval_core")):
        continue
    per_wheel = []
    try:
        with zipfile.ZipFile(wheel) as zf:
            for name in zf.namelist():
                if not name.endswith((".py", ".yaml", ".json", ".md", ".jinja")):
                    continue
                body = zf.read(name).decode("utf-8", "replace")
                low = body.lower()
                for key in KEY:
                    at = low.find(key)
                    if at >= 0:
                        per_wheel.append({"file": name, "key": key,
                                          "context": body[max(0, at - 200):at + 260]})
    except Exception as exc:
        per_wheel.append({"error": str(exc)})
    hits[wheel.name] = per_wheel[:160]
probe["interfaces"] = interfaces
probe["keyword_hits"] = hits
Path("/kaggle/working/wheel_probe.json").write_text(json.dumps(probe, indent=2))

swegemma = [w for w in WH.glob("swegemma-*.whl")]
text = ""
if swegemma:
    text = zip_text(swegemma[0], lambda n: True, limit=600000)
Path("/kaggle/working/swegemma_source.txt").write_text(text)

print(json.dumps(report, indent=2)[:12000])
print("WHEEL PROBE written:", len(json.dumps(probe)))
print("SWEGEMMA SOURCE bytes:", len(text))
Path("/kaggle/working/env_report.json").write_text(json.dumps(report, indent=2))
'''


ADAPTER_CONTRACT = '# --- adapter contract: can a submission declare a LoRA adapter? --------------------------------\n# The schema field exists, so the question is whether discovery and validation accept a real\n# adapters/<name>/ directory. Everything here runs on CPU.\nimport inspect, json, shutil, textwrap\nfrom pathlib import Path\n\ncontract = {}\nsub = Path("/kaggle/working/fake_submission")\nshutil.rmtree(sub, ignore_errors=True)\n(sub / "adapters" / "main_lora").mkdir(parents=True)\n(sub / "prompts").mkdir()\n(sub / "prompts" / "system.md").write_text("probe system prompt\\n")\n(sub / "agent.yaml").write_text(textwrap.dedent("""\n    agent_class: LlmAgent\n    name: probe_agent\n    model: gemma-4-31b-it-qat-w4a16-ct\n    adapter: main_lora\n    instruction: !include prompts/system.md\n    tools:\n      - run_command\n"""))\n\nimport torch\nfrom safetensors.torch import save_file\nsave_file({\n    "base_model.model.model.language_model.layers.0.self_attn.q_proj.lora_A.weight": torch.zeros(8, 16),\n    "base_model.model.model.language_model.layers.0.self_attn.q_proj.lora_B.weight": torch.zeros(16, 8),\n}, str(sub / "adapters" / "main_lora" / "adapter_model.safetensors"))\n(sub / "adapters" / "main_lora" / "adapter_config.json").write_text(json.dumps({\n    "peft_type": "LORA", "task_type": "CAUSAL_LM", "r": 8, "lora_alpha": 16,\n    "lora_dropout": 0.0, "bias": "none", "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],\n    "base_model_name_or_path": "gemma-4-31b-it-qat-w4a16-ct",\n}, indent=2))\n\nfrom adk_submission import discovery\ncontract["signature_discover_adapters"] = str(inspect.signature(discovery.discover_adapters))\ntry:\n    manifest = discovery.discover_adapters(sub)\n    contract["adapters"] = {name: {"path": str(info.path), "rank": getattr(info, "rank", None)}\n                            for name, info in manifest.adapters.items()}\n    contract["manifest_type"] = type(manifest).__name__\nexcept Exception as exc:\n    contract["discover_adapters_error"] = repr(exc)\n\ntry:\n    validator = getattr(discovery, "validate_directory", None)\n    contract["signature_validate_directory"] = str(inspect.signature(validator)) if validator else None\n    if validator:\n        contract["validate_directory"] = str(validator(sub))\nexcept Exception as exc:\n    contract["validate_directory_error"] = repr(exc)\n\ntry:\n    from adk_submission.yaml_loader import load_yaml\n    data = load_yaml(sub / "agent.yaml", sub)\n    contract["agent_yaml_loaded"] = bool(data)\n    contract["agent_yaml_keys"] = sorted(data or {})\n    from adk_submission.schema import SandboxedLlmAgentConfig\n    contract["schema_fields"] = sorted(getattr(SandboxedLlmAgentConfig, "model_fields", {}))\n    cfg = SandboxedLlmAgentConfig(**data)\n    contract["adapter_resolved"] = getattr(cfg, "adapter", "<missing>")\nexcept Exception as exc:\n    contract["schema_error"] = repr(exc)\n\ntry:\n    from adk_submission import server\n    contract["server_functions"] = [n for n, _ in inspect.getmembers(server, inspect.isfunction)]\n    contract["server_classes"] = [n for n, _ in inspect.getmembers(server, inspect.isclass)]\n    src = Path(server.__file__).read_text(encoding="utf-8")\n    Path("/kaggle/working/adk_server_source.txt").write_text(src)\n    for flag in ("enable_lora", "lora_modules", "max_lora_rank", "max_loras",\n                 "quantization", "compressed", "gemma-4"):\n        at = src.find(flag)\n        if at >= 0:\n            contract["server_" + flag] = src[max(0, at - 120):at + 240]\nexcept Exception as exc:\n    contract["server_error"] = repr(exc)\n\nPath("/kaggle/working/adapter_contract.json").write_text(json.dumps(contract, indent=2))\nprint(json.dumps(contract, indent=2)[:8000])\n'


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--owner", default=os.environ.get("KAGGLE_USERNAME", ""))
    parser.add_argument("--max-wait-minutes", type=int, default=40)
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
