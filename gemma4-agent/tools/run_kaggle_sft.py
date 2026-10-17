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
WHEELHOUSE = "metric/gemma-4-developer-agent-wheelhouse"
WHEELHOUSE_DIR = "/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse"
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



EMBED_FILES = (
    "gemma4-agent/tools/build_sft_dataset.py",
    "gemma4-agent/submission-v5/agent.yaml",
    "gemma4-agent/submission-v5/eval_config.yaml",
    "gemma4-agent/submission-v5/configs/sampling.yaml",
    "gemma4-agent/submission-v5/prompts/system.md",
    "gemma4-agent/submission-v6.11/tools/locate.py",
)


def embedded_repo_cell(root: Path) -> dict:
    """Materialise the files the notebook needs, so the kernel needs no internet for a clone."""
    import base64

    payload = {}
    for rel in EMBED_FILES:
        path = root / rel
        if not path.is_file():
            raise SystemExit(f"cannot embed {rel}: not present in the checkout")
        payload[rel] = base64.b64encode(path.read_bytes()).decode("ascii")
    blob = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    lines = [
        "# --- the repository files this run needs, embedded at push time ---------------------------\n",
        "# The kernel has no internet (Kaggle refused the push with it enabled), so the clone cell is\n",
        "# replaced by this: the exact bytes from the commit under test, sha256-printed for provenance.\n",
        "import base64 as _b64, json as _json, hashlib as _hashlib\n",
        f"_PAYLOAD = _b64.b64decode({blob!r})\n",
        "for _rel, _enc in _json.loads(_PAYLOAD).items():\n",
        "    _p = REPO_DIR / _rel\n",
        "    _p.parent.mkdir(parents=True, exist_ok=True)\n",
        "    _bytes = _b64.b64decode(_enc)\n",
        "    _p.write_bytes(_bytes)\n",
        "    print(f'{_rel:<52} {len(_bytes):>7} B  sha256 {_hashlib.sha256(_bytes).hexdigest()[:16]}')\n",
        "print('embedded files:', len(_json.loads(_PAYLOAD)))\n",
    ]
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": lines}


WHEELHOUSE_SETUP = """# --- install the competition wheelhouse first ------------------------------------------------
# The image's transformers does not know the `gemma4` architecture (ValueError on AutoConfig), and
# the kernel has no internet. The competition ships the exact wheels the scored harness uses, and
# the benchmark notebook installs them the same way - so the SFT run does too.
import glob, importlib, os, subprocess, sys
from pathlib import Path

os.environ["TRANSFORMERS_NO_TF"] = "1"
WH = Path("%s")
assert WH.is_dir(), f"Wheelhouse not mounted: {WH}"
for pattern in ("/usr/local/lib/python*/dist-packages/*cutlass*.pth",
                "/usr/local/lib/python*/site-packages/*cutlass*.pth"):
    for pth in glob.glob(pattern):
        try:
            os.unlink(pth)
        except OSError:
            pass
tmp = Path("/tmp/wheelhouse"); tmp.mkdir(parents=True, exist_ok=True)
for wheel in WH.glob("*.whl"):
    if "cutlass" in wheel.name.lower():
        continue
    name = wheel.name.replace("cu128", "+cu128") if ("cu128" in wheel.name and "+" not in wheel.name) else wheel.name
    target = tmp / name
    if not target.exists():
        os.symlink(wheel, target)
wheels = sorted(str(w) for w in tmp.glob("*.whl"))
print(f"installing {len(wheels)} offline wheels from the competition wheelhouse")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall", *wheels], check=True)
importlib.invalidate_caches()
import transformers
print("transformers", transformers.__version__)
print("gemma4 recognised:", "gemma4" in getattr(transformers.models, "__name__", "") or any("gemma4" in m for m in dir(transformers.models)))
""" % WHEELHOUSE_DIR


def normalize_notebook(nb: dict) -> dict:
    """Make the file nbformat-4.5 compliant, which Kaggle validates on SaveKernel.

    The committed notebook has nbformat 4.5 but no cell ids, and its code cells carry no
    execution_count/outputs. Kaggle answers SaveKernel with a bare HTTP 400 for that - which is how
    two pushes were lost before the metadata was compared with the launcher that does work.
    """
    for index, cell in enumerate(nb["cells"]):
        cell["id"] = f"cell-{index:03d}"
        if cell["cell_type"] == "code":
            cell.setdefault("execution_count", None)
            cell.setdefault("outputs", [])
        cell.setdefault("metadata", {})
    return nb


def patch_notebook(nb: dict, *, smoke: bool, base_dir: str, locator_from: str = "submission-v6.11",
                   repo_root: Path | None = None) -> dict:
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

        # The benchmark notebook mounts the competition data under /kaggle/input/competitions/...,
        # but this notebook was written against /kaggle/input/<competition>. Resolve both instead of
        # failing the build cell with MISSING.
        if 'DATA_DIR = Path("/kaggle/input/gemma-4-developer-agent")' in source:
            source = source.replace(
                'DATA_DIR = Path("/kaggle/input/gemma-4-developer-agent")',
                'DATA_DIR = next((p for p in (Path("/kaggle/input/competitions/gemma-4-developer-agent"),'
                ' Path("/kaggle/input/gemma-4-developer-agent")) if p.is_dir()),'
                ' Path("/kaggle/input/competitions/gemma-4-developer-agent"))'
            )
            applied["data_dir"] = applied.get("data_dir", 0) + 1

        if '"gemma-4-31b-it-qat-w4a16-ct"' in source:
            source = source.replace('"gemma-4-31b-it-qat-w4a16-ct"', f'"{MODEL_PATH}"')
            applied["model_path"] = applied.get("model_path", 0) + 1

        # The notebook hardcodes WORK/adapter packaging expectations; keep them but make the run tag
        # visible in the printed metadata.
        cell["source"] = source.splitlines(keepends=True)

    for key in ("SMOKE", "base_dir", "model_path", "locator", "data_dir"):
        if not applied.get(key):
            raise SystemExit(f"patch {key!r} did not apply - refusing to push a half-patched notebook")

    normalize_notebook(nb)

    # The wheelhouse install must be the FIRST code that touches transformers, so it goes right
    # after the configuration cell.
    install_index = None
    for index, cell in enumerate(nb["cells"]):
        source = "".join(cell["source"])
        if cell["cell_type"] == "code" and "SMOKE =" in source and "REPO_DIR" in source:
            install_index = index
            break
    if install_index is None:
        raise SystemExit("could not find the configuration cell for the wheelhouse install")
    nb["cells"].insert(install_index + 1, {
        "cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
        "source": WHEELHOUSE_SETUP.splitlines(keepends=True),
    })
    applied["wheelhouse"] = 1

    if repo_root is not None:
        # Replace the git-clone cell (the kernel has no internet) with the embedded-file cell.
        for index, cell in enumerate(nb["cells"]):
            source = "".join(cell["source"])
            if cell["cell_type"] == "code" and "git" in source and "clone" in source:
                nb["cells"][index] = embedded_repo_cell(repo_root)
                applied["embed"] = 1
                break
        if not applied.get("embed"):
            raise SystemExit("could not find the clone cell to replace - refusing to push")

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
    # Insert the guard AFTER the configuration cell. Putting it at index 1 made it run before
    # SMOKE/REPO_DIR existed and the kernel died with NameError - a fix that cost one GPU run.
    # It must also come AFTER the cell that materialises the repository files, because it asserts
    # that the prompt exists on disk.
    anchor_index = None
    for index, cell in enumerate(nb["cells"]):
        source = "".join(cell["source"])
        if cell["cell_type"] != "code":
            continue
        if "SMOKE =" in source and "REPO_DIR" in source:
            anchor_index = index
        if "embedded at push time" in source:
            anchor_index = index
    if anchor_index is None:
        raise SystemExit("could not find the configuration/embed cell; refusing to place the guard blindly")
    nb["cells"].insert(anchor_index + 1, guard)
    return normalize_notebook(nb)


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
    parser.add_argument("--embed-repo", dest="embed_repo", action="store_true", default=True,
                        help="write the repository files into the notebook (no internet needed)")
    parser.add_argument("--no-embed-repo", dest="embed_repo", action="store_false")
    parser.add_argument("--internet", action="store_true",
                        help="request internet for the kernel (Kaggle refused this with HTTP 400)")
    args = parser.parse_args()

    smoke = not args.full
    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    notebook = json.loads(args.notebook.read_text(encoding="utf-8"))
    repo_root = Path(".").resolve() if args.embed_repo else None
    patched = patch_notebook(notebook, smoke=smoke, base_dir=args.base_dir,
                             locator_from=args.locator_from, repo_root=repo_root)

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
        "internet": bool(args.internet),
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
            "enable_internet": bool(args.internet),
            "machine_shape": MACHINE_SHAPE,
            "docker_image": DOCKER_IMAGE,
            "docker_image_pinning_type": "original",
            "dataset_sources": [WHEELHOUSE],
            "competition_sources": [COMPETITION],
            "kernel_sources": [],
            "model_sources": [MODEL_SOURCE],
        }
        (kernel_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        state["status"] = "pushing"
        write_json(outdir / "run.json", state)
        pushed = kaggle(["kernels", "push", "--path", str(kernel_dir), "--timeout", str(args.max_wait_minutes * 60 + 900)])
        state["push_exit_code"] = pushed.returncode
        state["push_stdout_tail"] = (pushed.stdout or "")[-1200:]
        state["push_stderr_tail"] = (pushed.stderr or "")[-1200:]
        write_json(outdir / "run.json", state)
        text = ((pushed.stdout or "") + "\n" + (pushed.stderr or "")).lower()
        if "quota" in text and "reached" in text:
            state.update({"status": "gpu_quota_exceeded", "error": "weekly GPU quota exhausted"})
            write_json(outdir / "run.json", state)
            return 7
        if "successfully pushed" not in text:
            detail = ((pushed.stderr or "") or (pushed.stdout or "")).strip().splitlines()
            state.update({
                "status": "push_failed",
                "error": "Kaggle refused the push",
                "push_message": detail[-1] if detail else "no output from the CLI",
            })
            print("PUSH FAILED:", state["push_message"])
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
