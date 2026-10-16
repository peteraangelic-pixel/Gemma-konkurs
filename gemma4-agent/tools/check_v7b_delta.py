#!/usr/bin/env python3
"""Gate for the V7-b archive: prove the delta against V5 is exactly one appended sentence.

V7-b is the first submission since the V6.12 result (0.08, five changes at once, unattributable)
built on the rule that a submission may move ONE lever. This script is the executable definition
of that claim:

  * three of the four files are byte-identical to the committed V5 files;
  * `prompts/system.md` is byte-identical to V5's prompt plus the one appended sentence;
  * the appended part carries none of the V6 pacing vocabulary that is suspected of causing the
    0.13 -> 0.08 regression (forced early edit, "finish as soon as", deadlines by call number);
  * the appended part is one sentence, not a list of rules.

`--mutate` rebuilds the tree with a deliberate defect per check and requires that check - by name -
to fire, so "the gate passes" cannot be a statement about a gate that never had teeth.

Usage:
    python3 gemma4-agent/tools/check_v7b_delta.py            # verify the real tree
    python3 gemma4-agent/tools/check_v7b_delta.py --mutate   # prove every check fires
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
V5_DIR = "gemma4-agent/submission-v5"
V7B_DIR = ROOT / "gemma4-agent" / "submission-v7b"
IDENTICAL_FILES = ("agent.yaml", "eval_config.yaml", "configs/sampling.yaml")
PROMPT = "prompts/system.md"
APPENDED = (
    "**Put the edit on disk before you verify**: in the last screen every session that scored zero "
    "died with an empty tree - five ran out of clock (298-325 s of the 315 s cap) and one spent 227 s "
    "inside a single command - so once you have read the definition you intend to change, making that "
    "change is the very next call you make, and keep every command you run bounded (`timeout 45`): an "
    "edit that has not been written yet cannot be graded, and an empty tree is the only guaranteed zero."
)
FORBIDDEN_IN_APPEND = (
    "finish as soon as",
    "finish early",
    "stop even with calls left",
    "be finished by call",
    "by call 4",
    "by call 14",
    "by call 18",
    "hard edit deadline",
    "stop searching by call",
    "no reading without writing",
)


def v5_file(rel: str) -> str:
    return subprocess.run(
        ["git", "show", f"HEAD:{V5_DIR}/{rel}"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def check_tree(root: Path, v5: dict[str, str]) -> list[str]:
    """Return the failures of the tree rooted at `root`, each tagged with its check name."""
    failures: list[str] = []
    if root.name != "submission-v7b":
        failures.append(f"NAME: unexpected source directory name {root.name!r}")
    for rel in IDENTICAL_FILES:
        path = root / rel
        if not path.is_file():
            failures.append(f"IDENT: {rel} is missing")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != v5[rel]:
            failures.append(f"IDENT: {rel} differs from V5 ({sha(v5[rel])} -> {sha(actual)})")

    prompt = root / PROMPT
    if not prompt.is_file():
        failures.append(f"IDENT: {PROMPT} is missing")
        return failures
    actual_prompt = prompt.read_text(encoding="utf-8")
    v5_prompt = v5[PROMPT]
    if not actual_prompt.startswith(v5_prompt.rstrip("\n")):
        failures.append(f"PREFIX: {PROMPT} modifies V5 text instead of appending to it")
    expected = v5_prompt.rstrip("\n") + "\n" + APPENDED + "\n"
    if actual_prompt != expected:
        failures.append(f"EQ: {PROMPT} is not 'V5 prompt + exactly the one appended sentence'")

    appended = actual_prompt[len(v5_prompt.rstrip("\n")):].strip()
    lowered = appended.lower()
    for phrase in FORBIDDEN_IN_APPEND:
        if phrase in lowered:
            failures.append(f"FORBIDDEN: appended part carries the pacing phrase {phrase!r}")
    body = appended.rstrip(".")
    if ". " in body or body.count(".") > 0:
        failures.append("SENTENCE: appended part is longer than one sentence")
    return failures


def mutate_tree(root: Path, mutation: str) -> None:
    if mutation == "identical-file":
        path = root / "agent.yaml"
        path.write_text(path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    elif mutation == "budget":
        path = root / "eval_config.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace("5.25", "8.0", 1), encoding="utf-8")
    elif mutation == "prefix":
        path = root / PROMPT
        path.write_text(path.read_text(encoding="utf-8").replace("## Budget and speed rules", "## Speed", 1), encoding="utf-8")
    elif mutation == "extra-sentence":
        path = root / PROMPT
        path.write_text(path.read_text(encoding="utf-8") + "Also: stop early.\n", encoding="utf-8")
    elif mutation == "pacing":
        path = root / PROMPT
        text = path.read_text(encoding="utf-8")
        cut = text.index("**Put the edit on disk before you verify**")
        path.write_text(text[:cut] + "**Finish as soon as your intended edit is on disk**.", encoding="utf-8")
    elif mutation == "name":
        pass  # handled by the caller, which renames the working copy
    else:  # pragma: no cover
        raise ValueError(mutation)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutate", action="store_true", help="prove every check fires")
    args = parser.parse_args()

    v5 = {rel: v5_file(rel) for rel in (*IDENTICAL_FILES, PROMPT)}
    failures = check_tree(V7B_DIR, v5)
    if failures:
        print("V7-b gate FAILED on the real tree:")
        for line in failures:
            print("  -", line)
        return 1
    print(
        f"V7-b tree OK: {len(IDENTICAL_FILES) + 1} files, {len(IDENTICAL_FILES)} byte-identical to V5, "
        f"prompt = V5 ({len(v5[PROMPT]):,} chars) + one appended sentence ({len(APPENDED)} chars)"
    )

    if not args.mutate:
        return 0

    # (mutation, check that must fire)
    mutations = [
        ("identical-file", "IDENT"),
        ("budget", "IDENT"),
        ("prefix", "PREFIX"),
        ("extra-sentence", "SENTENCE"),
        ("pacing", "FORBIDDEN"),
        ("name", "NAME"),
    ]
    missed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for mutation, expected_check in mutations:
            work = Path(tmp) / ("submission-v7b" if mutation != "name" else "submission-wrong-name")
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(V7B_DIR, work)
            mutate_tree(work, mutation)
            found = check_tree(work, v5)
            fired = any(line.startswith(expected_check + ":") for line in found)
            missed += 0 if fired else 1
            shown = next((line for line in found if line.startswith(expected_check + ":")), "CHECK DID NOT FIRE")
            print(f"  [{'fires' if fired else 'MISSED'}] {mutation} -> {expected_check}: {shown}")
    print(f"mutation selftest: {len(mutations) - missed}/{len(mutations)} checks exercised")
    return 0 if not missed else 1


if __name__ == "__main__":
    raise SystemExit(main())
