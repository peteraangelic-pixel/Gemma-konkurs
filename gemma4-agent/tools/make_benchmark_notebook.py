#!/usr/bin/env python3
"""Regenerate the private Kaggle benchmark notebook with a different submission ZIP.

The notebook in commit c0256ba embeds its candidate archive as base64 and asserts its
SHA-256 before extracting it, then runs the real `swegemma` Evaluator on a deterministic
30-task stratified sample (seed 20261009, fixed task fastapi_15588) - the same sample V2,
V3 and V4 were measured on. This script swaps only those two constants so a new candidate
(V5) is measured on exactly the same tasks as its predecessors.

Usage:
    python gemma4-agent/tools/make_benchmark_notebook.py \
        --zip gemma4-agent/submission-v5.zip \
        --output gemma4-agent/kaggle_smoke/gemma-agent-benchmark-v5.ipynb
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_REV = "c0256ba"
DEFAULT_TEMPLATE_PATH = "gemma-agent-benchmark-3543c4f6-20261010-120912.ipynb"
TASK_SELECTION = {"task_count": 30, "seed": 20261009, "task_id": "fastapi_15588"}


def read_template(args: argparse.Namespace) -> str:
    if args.template is not None:
        return Path(args.template).read_text(encoding="utf-8")
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{args.template_rev}:{args.template_path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(
            "ERROR: could not read the template notebook from git: "
            + (completed.stderr.strip() or "unknown error")
        )
    return completed.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True, help="candidate submission archive")
    parser.add_argument("--output", type=Path, required=True, help="notebook to write")
    parser.add_argument("--template", type=Path, default=None, help="template .ipynb path")
    parser.add_argument("--template-rev", default=DEFAULT_TEMPLATE_REV)
    parser.add_argument("--template-path", default=DEFAULT_TEMPLATE_PATH)
    args = parser.parse_args()

    archive = args.zip if args.zip.is_absolute() else (REPO_ROOT / args.zip).resolve()
    output = args.output if args.output.is_absolute() else (REPO_ROOT / args.output).resolve()
    if not archive.is_file():
        raise SystemExit(f"ERROR: submission archive not found: {archive}")

    raw = archive.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    payload = base64.b64encode(raw).decode("ascii")

    notebook = read_template(args)
    text = json.loads(notebook)

    replaced_zip = replaced_sha = replaced_selection = False
    for cell in text.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        new_source, count_zip = re.subn(
            r'SUBMISSION_ZIP_B64 = "[A-Za-z0-9+/=]*"',
            f'SUBMISSION_ZIP_B64 = "{payload}"',
            source,
        )
        new_source, count_sha = re.subn(
            r"EXPECTED_SUBMISSION_SHA256 = '[0-9a-f]{64}'",
            f"EXPECTED_SUBMISSION_SHA256 = '{digest}'",
            new_source,
        )
        new_source, count_selection = re.subn(
            r'TASK_SELECTION = json\.loads\("(?:[^"\\]|\\.)*"\)',
            "TASK_SELECTION = json.loads(" + json.dumps(json.dumps(TASK_SELECTION)) + ")",
            new_source,
        )
        replaced_zip |= count_zip == 1
        replaced_sha |= count_sha == 1
        replaced_selection |= count_selection == 1
        if count_zip or count_sha or count_selection:
            cell["source"] = new_source.splitlines(keepends=True)

    if not (replaced_zip and replaced_sha and replaced_selection):
        raise SystemExit(
            "ERROR: template notebook did not contain the expected constants "
            f"(zip={replaced_zip}, sha={replaced_sha}, selection={replaced_selection})."
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(text, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    # Re-verify what we just wrote: decode the embedded payload and compare hashes.
    written = json.loads(output.read_text(encoding="utf-8"))
    for cell in written["cells"]:
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        match = re.search(r'SUBMISSION_ZIP_B64 = "([A-Za-z0-9+/=]*)"', source)
        if not match:
            continue
        decoded = base64.b64decode(match.group(1), validate=True)
        if hashlib.sha256(decoded).hexdigest() != digest:
            raise SystemExit("ERROR: embedded payload does not match the archive hash.")
        if decoded != raw:
            raise SystemExit("ERROR: embedded payload differs from the archive bytes.")
        break

    print(f"Wrote: {output}")
    print(f"Embedded submission: {archive.name} ({len(raw):,} bytes)")
    print(f"SHA-256: {digest}")
    print(
        "Task sample: "
        f"{TASK_SELECTION['task_count']} tasks, seed {TASK_SELECTION['seed']}, "
        f"fixed task {TASK_SELECTION['task_id']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
