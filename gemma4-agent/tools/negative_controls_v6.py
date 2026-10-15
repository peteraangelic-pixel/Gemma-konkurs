#!/usr/bin/env python3
"""Prove that the V6 packer's guards actually fire: mutate one phrase at a time in a throwaway
copy of a variant tree and require the build to fail (exit 1).

Why this exists: the packer's checks are the only thing standing between "the prompt claims a
lever" and "the prompt still contains it". The V6.4/V6.6 controls were run by hand and recorded in
GATES_V6_4.md / GATES_V6_6.md; this makes them repeatable, so a future variant cannot be built on
guards nobody re-tested.

    python3 gemma4-agent/tools/negative_controls_v6.py --variant v67

Positive control: the untouched copy must build, and its sha256 must equal the committed archive.
Each negative control: exactly one phrase is removed or replaced, and the build must exit non-zero
with an ERROR line on stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "gemma4-agent"
PACKER = AGENT / "build_submission_v6.py"

# (name, anchor that must exist, replacement)
CONTROLS: dict[str, list[tuple[str, str, str]]] = {
    "v69": [
        ("V6.9 guard: framing lever present",
         "make it even if you are not yet certain it is the right file", "make the edit"),
        ("V6.9 guard: inline locator justification present",
         "four sessions wrote `/tmp/locate.py`", "some sessions wrote a script"),
        ("V6.9 guard: V6.7-contract text must be absent",
         "The only exception is an issue that is explicitly about the documentation itself.",
         "The only exception is an issue that is explicitly about the documentation itself. "
         "On the last run two sessions reached call 31 with the tree untouched and the answer to "
         "their first `edit_file` was `Tool call budget exhausted (30 calls)`."),
        ("V6.9 guard: V6.8 text must be absent",
         "top 3 for 66% of them, in the top 5 for 73%",
         "top 3 for 67% of them, in the top 5 for 74%"),
    ],
    "v610": [
        ("V6.10 guard: contract rule (ceiling)",
         "Tool call budget exhausted (30 calls)", "the tool call ceiling"),
        ("V6.10 guard: contract rule (write_file scope)",
         "Path traversal detected: '/tmp/repro.py' escapes workspace root.", "the path is rejected"),
        ("V6.10 guard: evolved locator recall line",
         "top 3 for 67% of them, in the top 5 for 74%", "top 3 for 66% of them, in the top 5 for 73%"),
        ("V6.10 guard: the embedded script is the evolved one",
         "# EVOLVED 2026", "# hand-tuned"),
        ("V6.10 guard: inline delivery",
         "python3 -c \"$(cat <<'LOCATE_PY'", "python3 -c loc.py", "all"),
        ("V6.10 guard: V6.5 framing must be absent",
         "never create a dummy edit merely to satisfy the deadline",
         "never create a dummy edit merely to satisfy the deadline. The first intended edit must be "
         "on disk by tool call 4 - make it even if you are not yet certain it is the right file."),
    ],
    "v611": [
        ("V6.11 guard: budget statement matches eval_config",
         "this run is wider than the last one: an 8-minute window and 45 calls", "a wider budget"),
        ("V6.11 guard: finish-early rule",
         "**Finish as soon as your intended edit is on disk**", "**Finish when you can**"),
        ("V6.11 guard: no-empty-tree rescue",
         "If by call 8 the tree still has no intended edit", "If you are unsure what to edit"),
        ("V6.11 guard: the rescue rule's closing requirement",
         "No session ends with an empty tree.", "Try to end with an edit."),
        ("V6.11 guard: edit-parser measurement",
         "mandatory input parameters are not present", "a rejected edit call"),
        # the two budget guards live in eval_config.yaml, so these controls mutate that file
        ("V6.11 guard: the measured 8.0-minute window",
         "  max_time_minutes: 8.0", "  max_time_minutes: 5.25", "eval_config.yaml"),
        ("V6.11 guard: V5's 45-call budget restored",
         "  max_tool_calls: 45", "  max_tool_calls: 30", "eval_config.yaml"),
        ("V6.11 guard: contract rule (ceiling)",
         "Tool call budget exhausted (30 calls)", "the tool call ceiling"),
        ("V6.11 guard: the embedded script is the evolved one",
         "# EVOLVED 2026", "# hand-tuned"),
        ("V6.11 guard: non-inline locator form must be rejected",
         "cd /workspace && python3 -c",
         "cd /workspace && python3 /tmp/locate.py --root . --top 8 && python3 -c"),
        ("V6.11 guard: V6.5 framing must be absent",
         "never create a dummy edit merely to satisfy the deadline",
         "never create a dummy edit merely to satisfy the deadline. The first intended edit must be "
         "on disk by tool call 4 - make it even if you are not yet certain it is the right file."),
    ],
    "v68": [
        ("V6.8 guard: dev recall of the evolved locator",
         "top 3 for 67% of them, in the top 5 for 74%", "top 3 for 66% of them, in the top 5 for 73%"),
        ("V6.8 guard: held-out validation set",
         "104 tasks from four repositories", "some tasks from other repositories"),
        ("V6.8 guard: the validation statement",
         "the recall improvement is not a tuning artefact", "the script is better"),
        ("V6.8 guard: updated read-narrowly recall",
         "covers 56% of tasks, the top two 59%, the top three 67%",
         "covers 48% of tasks, the top two 52%, the top three 66%"),
        ("V6.8 guard: stale 188-task figure",
         "and on 104 tasks", "and on 188 tasks"),
        ("V6.8 guard: the embedded script must be the evolved one",
         "# EVOLVED 2026", "# hand-tuned"),
        ("V6.8 guard: locator form borrowed from another variant",
         "cd /workspace && cat > /tmp/locate.py <<'LOCATE_PY'",
         "cd /workspace && python3 -c \"$(cat <<'LOCATE_PY'"),
    ],
    "v67": [
        ("V6.7 guard: ceiling refusal",
         "Tool call budget exhausted (30 calls)", "the tool call ceiling"),
        ("V6.7 guard: comment-only commands",
         "Thirty-two calls across that run", "Some calls across that run"),
        ("V6.7 guard: finish the issue",
         "**Finish the issue, not the search.**", "**Keep going.**"),
        ("V6.7 guard: write_file outside the workspace",
         "Path traversal detected: '/tmp/repro.py' escapes workspace root.", "the path is rejected"),
        ("V6.7 guard: guessed line ranges",
         "lines 4470-4520", "some line range"),
        ("V6.7 guard: discarded files survive the tool call",
         "the tool confirmed both with a diff", "the tool confirmed both"),
        ("V6.4 guard: M4 measurement",
         "279.8 s", "a long session"),
        ("V6.4 guard: dummy-edit ban",
         "never create a dummy edit", "never create a placeholder edit"),
        ("V6.2 plumbing: bare-filename warning",
         "Never let a bare filename like", "Never let a scratch name like"),
        ("variant mixing: V6.6-only text injected into the V6.7 tree",
         "The only exception is an issue that is explicitly about the documentation itself.",
         "The only exception is an issue that is explicitly about the documentation itself. "
         "Measured on the last run: four sessions wrote `/tmp/locate.py` and then never edited the "
         "repository at all."),
    ],
}


def build(source: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PACKER), "--source-dir", str(source), "--output", str(output)],
        capture_output=True, text=True, cwd=ROOT,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="v67", choices=sorted(CONTROLS))
    args = parser.parse_args()
    variant = args.variant
    # variant id -> the directory suffix (v610 cannot be derived from its last character)
    suffix = {"v67": "6.7", "v68": "6.8", "v69": "6.9", "v610": "6.10",
              "v611": "6.11"}[variant]
    source = AGENT / f"submission-v{suffix}"
    archive = AGENT / f"submission-v{suffix}.zip"
    if not source.is_dir():
        print(f"missing source tree: {source}", file=sys.stderr)
        return 1

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # positive control
        positive = tmp_path / source.name
        shutil.copytree(source, positive)
        out = tmp_path / "positive.zip"
        result = build(positive, out)
        if result.returncode != 0:
            print("POSITIVE CONTROL FAILED: the untouched tree does not build\n" + result.stderr)
            return 1
        sha = hashlib.sha256(out.read_bytes()).hexdigest()
        print(f"positive control: builds, sha256 {sha}")
        if archive.exists():
            committed = hashlib.sha256(archive.read_bytes()).hexdigest()
            if committed != sha:
                failures.append(f"rebuilt archive differs from {archive.name}: {sha} != {committed}")
            else:
                print(f"positive control: sha256 matches {archive.name}")
        else:
            failures.append(f"no committed archive to compare against: {archive}")

        # negative controls
        for index, control in enumerate(CONTROLS[variant], start=1):
            label, anchor, replacement = control[0], control[1], control[2]
            replace_all = len(control) > 3 and control[3] == "all"
            # V6.11 added budget guards that live in eval_config.yaml, so a control may name the
            # file it mutates as a 4th element (a plain 4th element of "all" keeps meaning
            # "replace every occurrence in prompts/system.md").
            target_rel = "prompts/system.md"
            if len(control) > 3 and control[3] not in ("all",):
                target_rel = str(control[3])
            copy = tmp_path / f"{source.name}-mut{index}"
            shutil.copytree(source, copy)
            prompt = copy / target_rel
            if not prompt.is_file():
                failures.append(f"{label}: control target does not exist: {target_rel}")
                continue
            text = prompt.read_text(encoding="utf-8")
            if anchor not in text:
                failures.append(f"{label}: anchor not found, control is stale: {anchor!r}")
                continue
            mutated = text.replace(anchor, replacement) if replace_all else text.replace(anchor, replacement, 1)
            prompt.write_text(mutated, encoding="utf-8")
            result = build(copy, tmp_path / f"mut{index}.zip")
            ok = result.returncode != 0 and "ERROR:" in result.stderr
            print(f"negative control {index:2}: {'fires' if ok else 'DOES NOT FIRE'} - {label}")
            if not ok:
                failures.append(f"{label}: build did not fail (exit {result.returncode})")

    if failures:
        print("\nCONTROL FAILURES:", file=sys.stderr)
        for item in failures:
            print("  - " + item, file=sys.stderr)
        return 1
    print(f"\nall controls passed for {variant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
