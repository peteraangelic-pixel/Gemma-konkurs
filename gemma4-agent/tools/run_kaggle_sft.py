#!/usr/bin/env python3
"""Launch the LoRA/SFT notebook on Kaggle GPU, patched for the V5 base and the mounted model.

The notebook (kaggle_smoke/gemma-lora-sft-v1.ipynb) was written against the V6.11 tree and against
a bare model name. Both are wrong for tonight:

  * the base is now V5 (submission-v5) - the only configuration with a positive official score and
    the one the packaging step must mirror, so the adapter is trained on the prompt it will be
    served with;
  * a kernel sees the model mounted at /kaggle/input/models/..., not under its display name.

The launcher therefore patches the notebook JSON in memory, pushes it as a private kernel with GPU
and internet (training libraries), polls to completion and downloads the output. It refuses to push
if a patch does not apply, so a silent no-op cannot turn a "V5 + adapter" run into something else.

Nothing here submits to the competition: the notebook only builds the adapter and a local archive.

Usage:
    python3 gemma4-agent/tools/run_kaggle_sft.py --smoke --outdir gemma4-agent/kaggle_results/sft-smoke
    python3 gemma4-agent/tools/run_kaggle_sft.py --full  --outdir gemma4-agent/kaggle_results/sft-full
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

COMPETITION = "gemma-4-developer-agent"
MODEL_SOURCE = "google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2"
MODEL_PATH = "/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2"
MACHINE_SHAPE = "NvidiaL4"
DOCKER_IMAGE = (
    "gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461"
)
BASE_DIR_DEFAULT = "submission-v5"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def kaggle(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["kaggle", *args], capture_output=True, text=True, timeout=timeout)


def patch_notebook(nb: dict, *, smoke: bool, base_dir: str, locator_from: str = "submission-v6.11") -> dict:
    """Patch in place; every replacement must actually happen."""
    applied: dict[str, int] = {}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])

        if "SMOKE = True" in source or "SMOKE = False" in source:
            new = source.replace("SMOKE = True", f"SMOKE = {smoke}").replace("SMOKE = False", f"SMOKE = {smoke}")
            applied["SMOKE"] = applied.get("SMOKE", 0) + 1
            source = new

        if "submission-v6.11" in source:
            source = source.replace("submission-v6.11", base_dir)
            applied["base_dir"] = applied.get("base_dir", 0) + 1

        # V5 ships no locator (it greps), but the dataset builder needs one to rank candidate files.
        # Point that single argument at the evolved locator from another tree instead of letting the
        # base-dir patch produce a path that does not exist.
        if f"{base_dir}/tools/locate.py" in source:
            source = source.replace(f"{base_dir}/tools/locate.py", f"{locator_from}/tools/locate.py")
            applied["locator"] = applied.get("locator", 0) + 1

        if '"gemma-4-31b-it-qat-w4a16-ct"' in source:
            source = source.replace('"gemma-4-31b-it-qat-w4a16-ct"', f'"{MODEL_PATH}"')
            applied["model_path"] = applied.get("model_path", 0) + 1

        # The notebook hardcodes WORK/adapter packaging expectations; keep them but make the run tag
        # visible in the printed metadata.
        cell["source"] = source.splitlines(keepends=True)

    for key in ("SMOKE", "base_dir", "model_path", "locator"):
        if not applied.get(key):
            raise SystemExit(f"patch {key!r} did not apply - refusing to push a half-patched notebook")

    # Verification cell: prove the patches landed before anything expensive runs.
    expected_smoke = "True" if smoke else "False"
    guard = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "assert SMOKE is " + expected_smoke + ", SMOKE\n",
            "from pathlib import Path as _P\n",
            "_prompt = _P(REPO_DIR / 'gemma4-agent/" + base_dir + "/prompts/system.md')\n",
            "assert _prompt.is_file(), 'prompt missing: ' + str(_prompt)\n",
            "print('patched SMOKE=' + str(SMOKE) + ' base=" + base_dir + " prompt_chars=' + str(_prompt.stat().st_size))\n",
            "assert _P('" + MODEL_PATH + "').is_dir(), 'model not mounted'\n",
            "print('model mounted:', '" + MODEL_PATH + "')\n",
        ],
    }
    nb["cells"].insert(1, guard)
    return nb


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, default=Path("gemma4-agent/kaggle_smoke/gemma-lora-sft-v1.ipynb"))
    parser.add_argument("--smoke", action="store_true", help="6-task canary run (default if neither flag)")
    parser.add_argument("--full", action="store_true", help="full dataset and epochs")
    parser.add_argument("--base-dir", default=BASE_DIR_DEFAULT)
    parser.add_argument("--locator-from", default="submission-v6.11",
                        help="tree that supplies tools/locate.py for dataset construction only")
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--max-wait-minutes", type=int, default=300)
    parser.add_argument("--poll-interval-seconds", type=int, default=60)
    parser.add_argument("--owner", default=os.environ.get("KAGGLE_USERNAME", ""))
    args = parser.parse_args()

    smoke = not args.full
    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    notebook = json.loads(args.notebook.read_text(encoding="utf-8"))
    patched = patch_notebook(notebook, smoke=smoke, base_dir=args.base_dir, locator_from=args.locator_from)

    owner = args.owner
    if not owner:
        raise SystemExit("Set KAGGLE_USERNAME (the kernel must live under your account).")
    run_tag = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = f"gemma-4-sft-{'smoke' if smoke else 'full'}-{run_tag}"
    kernel_ref = f"{owner}/{slug}"

    state = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "preparing",
        "mode": "smoke" if smoke else "full",
        "base_dir": args.base_dir,
        "kernel_ref": kernel_ref,
        "model_path": MODEL_PATH,
        "competition_submission_created": False,
    }
    write_json(outdir / "run.json", state)

    with tempfile.TemporaryDirectory(prefix="gemma-sft-kernel-") as temporary:
        kernel_dir = Path(temporary)
        notebook_path = kernel_dir / "sft.ipynb"
        notebook_path.write_text(json.dumps(patched, ensure_ascii=False), encoding="utf-8")
        metadata = {
            "id": kernel_ref,
            "title": f"Gemma 4 SFT {'smoke' if smoke else 'full'} {run_tag}",
            "code_file": notebook_path.name,
            "language": "python",
            "kernel_type": "notebook",
            "is_private": True,
            "enable_gpu": True,
            "enable_tpu": False,
            # Training libraries are not guaranteed to be in the image; the run needs pip. This is a
            # training experiment, never the scored agent, so internet is acceptable here.
            "enable_internet": True,
            "machine_shape": MACHINE_SHAPE,
            "docker_image": DOCKER_IMAGE,
            "docker_image_pinning_type": "original",
            "dataset_sources": [],
            "competition_sources": [COMPETITION],
            "kernel_sources": [],
            "model_sources": [MODEL_SOURCE],
        }
        (kernel_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        state["status"] = "pushing"
        write_json(outdir / "run.json", state)
        pushed = kaggle(["kernels", "push", "--path", str(kernel_dir), "--timeout", str(args.max_wait_minutes * 60 + 900)])
        state["push_exit_code"] = pushed.returncode
        state["push_stdout_tail"] = (pushed.stdout or "")[-800:]
        write_json(outdir / "run.json", state)
        text = ((pushed.stdout or "") + "\n" + (pushed.stderr or "")).lower()
        if "quota" in text and "reached" in text:
            state.update({"status": "gpu_quota_exceeded", "error": "weekly GPU quota exhausted"})
            write_json(outdir / "run.json", state)
            return 7
        if "error" in text and "successfully pushed" not in text:
            state.update({"status": "push_failed", "error": "Kaggle refused the push; see push_stdout_tail"})
            write_json(outdir / "run.json", state)
            return 7

    state["status"] = "running"
    write_json(outdir / "run.json", state)
    deadline = time.monotonic() + max(1, args.max_wait_minutes) * 60
    last = "UNKNOWN"
    while time.monotonic() < deadline:
        probe = kaggle(["kernels", "status", kernel_ref], timeout=90)
        raw = ((probe.stdout or "") + "\n" + (probe.stderr or "")) if probe else ""
        last = next((s for s in ("COMPLETE", "RUNNING", "QUEUED", "ERROR", "CANCELED") if f"KernelWorkerStatus.{s}" in raw), last)
        state["kaggle_status"] = last
        write_json(outdir / "run.json", state)
        print(f"  status: {last}", flush=True)
        if last == "COMPLETE":
            with tempfile.TemporaryDirectory(prefix="gemma-sft-output-") as temporary:
                fetched = kaggle(["kernels", "output", kernel_ref, "--path", temporary, "--force"], timeout=900)
                if fetched is None or fetched.returncode != 0:
                    state.update({"status": "output_download_failed"})
                    write_json(outdir / "run.json", state)
                    return 4
                for path in Path(temporary).rglob("*"):
                    if not path.is_file():
                        continue
                    rel = path.relative_to(temporary)
                    target = outdir / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(path.read_bytes())
            state["status"] = "complete"
            write_json(outdir / "run.json", state)
            print(f"complete; output downloaded into {outdir}")
            return 0
        if last in {"ERROR", "CANCELED"}:
            state.update({"status": last.lower(), "error": "the kernel ended without producing a result"})
            write_json(outdir / "run.json", state)
            return 5
        time.sleep(max(30, args.poll_interval_seconds))

    state.update({"status": "still_running_at_deadline"})
    write_json(outdir / "run.json", state)
    print("the wait window closed with the kernel unfinished; nothing was cancelled")
    return 6


if __name__ == "__main__":
    raise SystemExit(main())
