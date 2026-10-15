#!/usr/bin/env python3
"""Build a supervised-fine-tuning dataset for the Gemma 4 Developer Agent competition.

Why this exists (RESEARCH_2026-10-15_EXTERNAL.md, GATES_V6_11.md): every public measurement we
could find says prompt/scaffold work plateaus around 0.10-0.14 - the score we already have - and
that the entries above 0.18 are the ones that post-trained the model. The competition allows PEFT
LoRA adapters inside the submission (`adapters/<name>/`), and the host confirmed on 2026-10-15
(discussion 749528) that adapters ARE applied in the scoring forward pass; the sample adapter only
looked inert because it touches layer 0 of 60.

This script runs on CPU, inside a Kaggle notebook that has the competition data attached, and turns
the 129 public tasks into chat-format examples that match what the agent actually has to do:

    system   - the shipped V6.11 prompt (short form; the notebook substitutes the real one)
    user     - the problem statement + the k candidates our shipped locator ranks highest
    assistant- the reference patch restricted to the files it touches

Targeting "produce this diff given the issue and the top candidates" trains exactly the step our
measurements say is broken: the agent finds the file (top-1 55.5% dev / 51% holdout, better than
any public benchmark) and then fails to convert that into an edit (V6.4: 11/30 empty trees, 5 of 11
basket-N sessions had the gold file at rank 1 and still never edited).

Usage (Kaggle, CPU is enough):

    python3 build_sft_dataset.py \
        --tasks /kaggle/input/gemma-4-developer-agent/tasks.jsonl \
        --snapshots /kaggle/input/gemma-4-developer-agent/snapshots \
        --locator /kaggle/working/repo/gemma4-agent/submission-v6.11/tools/locate.py \
        --outdir /kaggle/working/sft

Outputs: sft_train.jsonl, sft_holdout.jsonl, sft_summary.json (+ the candidates kept per task).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

MAX_CANDIDATES = 3
MAX_FILE_CHARS = 8_000
MAX_ISSUE_CHARS = 12_000
HOLDOUT_EVERY = 5  # sha1(instance_id) % 5 == 0 -> holdout, deterministic and repo-agnostic

DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+?)\s*$", re.MULTILINE)
DIFF_HEADER_RE = re.compile(r"^diff --git ", re.MULTILINE)


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def split_of(instance_id: str) -> str:
    return "holdout" if int(sha1(instance_id)[:8], 16) % HOLDOUT_EVERY == 0 else "train"


def patch_files(patch: str) -> list[str]:
    """Files the reference patch touches, in patch order, de-duplicated."""
    seen: list[str] = []
    for name in DIFF_FILE_RE.findall(patch or ""):
        if name not in seen:
            seen.append(name)
    return seen


def patch_for_files(patch: str, wanted: list[str]) -> str:
    """Keep only the per-file diff blocks whose file is in `wanted`."""
    if not patch:
        return ""
    blocks = [b for b in re.split(r"(?=^diff --git )", patch, flags=re.MULTILINE) if b.strip()]
    kept: list[str] = []
    for block in blocks:
        match = DIFF_FILE_RE.search(block)
        if match and match.group(1) in wanted:
            kept.append(block.rstrip("\n"))
    return "\n".join(kept)


def extract_snapshot(tar_path: Path, dest: Path) -> Path | None:
    """Extract a snapshot tarball and return the directory that holds the repository root."""
    if not tar_path.is_file():
        return None
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(tar_path) as archive:
            archive.extractall(dest)  # noqa: S202 - the archive is the organisers' own dataset
    except (tarfile.TarError, OSError):
        return None
    # Snapshots may nest the repo root one or two levels down; pick the shallowest directory that
    # carries a project marker. `dest` itself must be a candidate: the competition tarballs put the
    # repository at the archive root, and forgetting that once made the locator scan a `src/`
    # subdirectory and return paths relative to it, so every gold rank came back as a miss.
    candidates = [dest, *sorted((p for p in dest.rglob("*") if p.is_dir()), key=lambda p: len(p.parts))]
    for marker in ("pyproject.toml", "setup.py", "setup.cfg", "src"):
        for path in candidates:
            if (path / marker).exists():
                return path
    return candidates[0] if candidates else None


def rank_files(locator: Path, root: Path, issue: str, top: int) -> list[str]:
    """Run the shipped locator exactly as the agent does (issue on stdin) and parse the ranking."""
    try:
        result = subprocess.run(
            [sys.executable, str(locator), "--root", ".", "--top", str(top)],
            input=issue[:MAX_ISSUE_CHARS], capture_output=True, text=True, cwd=root, timeout=120,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    names: list[str] = []
    for line in result.stdout.splitlines():
        match = re.match(r"\s*\d+\.\s+(\S+)", line)
        if match:
            names.append(match.group(1))
    return names


def read_candidate(root: Path, name: str) -> str:
    path = (root / name).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return ""
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > MAX_FILE_CHARS:
        text = text[:MAX_FILE_CHARS] + f"\n... [truncated at {MAX_FILE_CHARS} characters]\n"
    return text


SYSTEM = (
    "You are a Python maintainer fixing one real issue in a repository checked out in /workspace. "
    "The graded artefact is the working-tree diff, and an empty patch scores zero. Locate the "
    "source file that must change, then write the minimal edit that fixes the reported behaviour. "
    "Never edit tests."
)


def build_example(task: dict, snapshot_root: Path, locator: Path) -> tuple[dict | None, dict]:
    instance_id = str(task.get("instance_id", ""))
    issue_parts = [str(task.get("problem_statement", "")).strip()]
    hints = str(task.get("hints_text", "") or "").strip()
    if hints:
        issue_parts.append("Hints from the issue thread:\n" + hints)
    issue = "\n\n".join(p for p in issue_parts if p)[:MAX_ISSUE_CHARS]
    gold = patch_files(str(task.get("patch", "") or ""))
    if not issue or not gold or snapshot_root is None:
        return None, {"instance_id": instance_id, "skipped": "missing issue, patch or snapshot"}

    ranked = rank_files(locator, snapshot_root, issue, MAX_CANDIDATES)
    # always show the gold file even when the locator missed it, so the target is reachable
    shown = list(ranked)
    for name in gold:
        if name not in shown:
            shown.append(name)
    blocks = []
    for name in shown[: MAX_CANDIDATES + 1]:
        body = read_candidate(snapshot_root, name)
        if body:
            blocks.append(f"### {name}\n```python\n{body}\n```")
    target = patch_for_files(str(task.get("patch", "") or ""), gold)
    if not blocks or not target:
        return None, {"instance_id": instance_id, "skipped": "no readable candidate or empty target"}
    user = (
        f"Issue:\n{issue}\n\n"
        f"The locator ranks these files highest for this issue:\n\n" + "\n\n".join(blocks) + "\n\n"
        "Write the patch that fixes the issue."
    )
    rank_of_first_gold = next((i + 1 for i, n in enumerate(ranked) if n in gold), None)
    example = {
        "instance_id": instance_id,
        "repo": task.get("repo", ""),
        "split": split_of(instance_id),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": target},
        ],
    }
    meta = {
        "instance_id": instance_id,
        "repo": task.get("repo", ""),
        "gold_files": gold,
        "ranked": ranked,
        "rank_of_first_gold": rank_of_first_gold,
        "shown": shown[: MAX_CANDIDATES + 1],
        "target_chars": len(target),
        "user_chars": len(user),
    }
    return example, meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--snapshots", type=Path, required=True)
    parser.add_argument("--locator", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="0 = all tasks (useful for a smoke run)")
    args = parser.parse_args()

    if not args.tasks.is_file():
        print(f"tasks file not found: {args.tasks}", file=sys.stderr)
        return 1
    if not args.locator.is_file():
        print(f"locator not found: {args.locator}", file=sys.stderr)
        return 1
    args.outdir.mkdir(parents=True, exist_ok=True)

    tasks = [json.loads(line) for line in args.tasks.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        tasks = tasks[: args.limit]
    print(f"tasks: {len(tasks)}")

    train_path = args.outdir / "sft_train.jsonl"
    holdout_path = args.outdir / "sft_holdout.jsonl"
    meta_path = args.outdir / "sft_meta.jsonl"
    counts = {"train": 0, "holdout": 0, "skipped": 0}
    top1 = top3 = total = 0

    with tempfile.TemporaryDirectory() as tmp, \
            train_path.open("w", encoding="utf-8") as train_out, \
            holdout_path.open("w", encoding="utf-8") as holdout_out, \
            meta_path.open("w", encoding="utf-8") as meta_out:
        for index, task in enumerate(tasks, start=1):
            instance_id = str(task.get("instance_id", ""))
            snapshot_tar = args.snapshots / f"{instance_id}.tgz"
            root = extract_snapshot(snapshot_tar, Path(tmp) / instance_id)
            example, meta = build_example(task, root, args.locator)
            if example is None:
                counts["skipped"] += 1
                print(f"  [{index}/{len(tasks)}] {instance_id}: skipped ({meta.get('skipped')})")
            else:
                total += 1
                counts[example["split"]] += 1
                rank = meta.get("rank_of_first_gold")
                top1 += 1 if rank == 1 else 0
                top3 += 1 if rank in (1, 2, 3) else 0
                (train_out if example["split"] == "train" else holdout_out).write(
                    json.dumps(example, ensure_ascii=False) + "\n"
                )
                print(f"  [{index}/{len(tasks)}] {instance_id}: {example['split']}, "
                      f"gold rank {rank}, {meta['target_chars']} target chars")
            meta_out.write(json.dumps(meta, ensure_ascii=False) + "\n")

    summary = {
        "tasks": len(tasks),
        "examples": counts,
        "locator_gold_rank": {
            "top1_share": round(top1 / total, 4) if total else None,
            "top3_share": round(top3 / total, 4) if total else None,
            "measured_on": "the candidates the shipped locator returns for each task",
        },
        "settings": {
            "max_candidates": MAX_CANDIDATES,
            "max_file_chars": MAX_FILE_CHARS,
            "holdout_every": HOLDOUT_EVERY,
            "target": "reference patch restricted to the files it touches",
        },
    }
    (args.outdir / "sft_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
