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
    source = AGENT / f"submission-v6.{variant[-1]}"
    if variant in ("v67", "v68"):
        source = AGENT / f"submission-v6.{variant[-1]}"
    archive = AGENT / f"submission-v6.{variant[-1]}.zip"
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
        for index, (label, anchor, replacement) in enumerate(CONTROLS[variant], start=1):
            copy = tmp_path / f"{source.name}-mut{index}"
            shutil.copytree(source, copy)
            prompt = copy / "prompts" / "system.md"
            text = prompt.read_text(encoding="utf-8")
            if anchor not in text:
                failures.append(f"{label}: anchor not found, control is stale: {anchor!r}")
                continue
            prompt.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")
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
