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
    proc = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps",
                           "--force-reinstall", *wheels], capture_output=True, text=True)
    report["install_returncode"] = proc.returncode
    report["install_stderr_tail"] = proc.stderr[-800:]
importlib.invalidate_caches()
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

print(json.dumps(report, indent=2)[:12000])
Path("/kaggle/working/env_report.json").write_text(json.dumps(report, indent=2))
'''


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--owner", default=os.environ.get("KAGGLE_USERNAME", ""))
    parser.add_argument("--max-wait-minutes", type=int, default=40)
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
    ]
    notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                            "language_info": {"name": "python", "version": "3.12"}},
                "nbformat": 4, "nbformat_minor": 5}
    state = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "status": "preparing", "kernel_ref": kernel_ref, "cpu_only": True,
             "competition_submission_created": False}
    write_json(outdir / "run.json", state)

    with tempfile.TemporaryDirectory(prefix="gemma-env-") as temporary:
        kernel_dir = Path(temporary)
        (kernel_dir / "diagnose.ipynb").write_text(json.dumps(notebook, ensure_ascii=False), encoding="utf-8")
        (kernel_dir / "kernel-metadata.json").write_text(json.dumps({
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
        }, indent=2) + "\n", encoding="utf-8")
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
