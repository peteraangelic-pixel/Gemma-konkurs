#!/usr/bin/env python3
"""Regenerate the private Kaggle benchmark notebook with a different submission ZIP.

The notebook in commit c0256ba embeds its candidate archive as base64 and asserts its
SHA-256 before extracting it, then runs the real `swegemma` Evaluator on a deterministic
30-task stratified sample (seed 20261009, fixed task fastapi_15588) - the same sample V2,
V3 and V4 were measured on. This script swaps only those two constants so a new candidate
(V5, V6, ...) is measured on exactly the same tasks as its predecessors.

Usage:
    python gemma4-agent/tools/make_benchmark_notebook.py \
        --zip gemma4-agent/submission-v6.zip \
        --output gemma4-agent/kaggle_smoke/gemma-agent-benchmark-v6.ipynb
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

# The review notebook must stay byte-compatible with what run_kaggle_v1_smoke.py pushes,
# which now records per-task localization diagnostics: which files the agent patch touched,
# the gold files of that task, and whether the patch touched a fixable gold file. Kaggle
# never reports per-task failures, so this is the only end-to-end localization evidence.
DIAGNOSTICS_HELPERS = """
def _patch_paths(patch_text):
    paths = []
    for _line in patch_text.splitlines():
        if _line.startswith('+++ '):
            _raw = _line[4:].strip()
            if _raw.startswith('b/'):
                _raw = _raw[2:]
            if _raw and _raw != '/dev/null':
                paths.append(_raw.split('\\t')[0])
    return sorted(set(paths))


def _is_test_path(path):
    return '_test' in path or path.startswith('tests/') or '/tests/' in path


def _is_fixable_path(path):
    return (path.endswith(('.py', '.pyi')) and not _is_test_path(path)
            and not path.startswith(('docs/', 'docs_src/', 'scripts/')))


GOLD_BY_TASK = {}
try:
    for _line in (DATA_DIR / 'tasks.jsonl').read_text(encoding='utf-8').splitlines():
        if not _line.strip():
            continue
        _row = json.loads(_line)
        _gold = _patch_paths(_row.get('patch') or '')
        GOLD_BY_TASK[_row.get('instance_id')] = {
            'all': _gold,
            'fixable': [p for p in _gold if _is_fixable_path(p)],
        }
    print(f'Diagnostics: gold map loaded for {len(GOLD_BY_TASK)} published tasks')
except Exception as _exc:
    print(f'Diagnostics: gold map unavailable ({type(_exc).__name__}: {_exc})')


"""

DIAGNOSTICS_LOOP_ANCHOR = "for task_index, task in enumerate(selected_tasks, start=1):"
DIAGNOSTICS_ROW_ANCHOR = """            'tool_calls': int(result.tool_calls or 0),
            'duration_seconds': float(result.duration_seconds),
        }"""
DIAGNOSTICS_ROW_EXTRA = DIAGNOSTICS_ROW_ANCHOR + """
        touched = _patch_paths(patch)
        gold = GOLD_BY_TASK.get(task.instance_id, {})
        gold_fixable = gold.get('fixable') or gold.get('all') or []
        row['touched_files'] = touched[:12]
        row['touched_tests'] = any(_is_test_path(item) for item in touched)
        row['gold_fixable_files'] = gold_fixable[:12]
        row['localized'] = bool(set(touched) & set(gold_fixable))"""
DIAGNOSTICS_SUMMARY_ANCHOR = """        'tasks': per_task_results,
        'official_submission': False,"""
DIAGNOSTICS_SUMMARY_EXTRA = """        'tasks': per_task_results,
        'localization_hits': sum(1 for item in per_task_results if item.get('localized')),
        'tasks_with_empty_patch': sum(1 for item in per_task_results if item.get('patch_chars', 0) == 0),
        'tasks_touching_tests': sum(1 for item in per_task_results if item.get('touched_tests')),
        'official_submission': False,"""


def apply_diagnostics(source: str) -> str:
    """Add the same per-task localization diagnostics the runner injects at run time."""
    if "GOLD_BY_TASK" in source:
        return source
    if DIAGNOSTICS_LOOP_ANCHOR not in source:
        return source
    source = source.replace(DIAGNOSTICS_LOOP_ANCHOR, DIAGNOSTICS_HELPERS + DIAGNOSTICS_LOOP_ANCHOR, 1)
    source = source.replace(DIAGNOSTICS_ROW_ANCHOR, DIAGNOSTICS_ROW_EXTRA, 1)
    source = source.replace(DIAGNOSTICS_SUMMARY_ANCHOR, DIAGNOSTICS_SUMMARY_EXTRA, 1)
    return source



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
        new_source = apply_diagnostics(new_source)
        replaced_zip |= count_zip == 1
        replaced_sha |= count_sha == 1
        replaced_selection |= count_selection == 1
        diagnostics_added = "GOLD_BY_TASK" in new_source and "GOLD_BY_TASK" not in source
        if count_zip or count_sha or count_selection or diagnostics_added:
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
