#!/usr/bin/env python3
"""Does the locator's excerpt actually contain the code a fix has to touch?

Lever L3 (V6.7) makes the locator print merged context windows for its top two candidates, so that
the first edit is constructible without the reading phase - measured on the full V6.4 run, sessions
spent a median of 176 s of their 315 s budget before their first edit, and the tasks that hit the
clock resolved only 26% of the time.

This tool measures the ceiling of that idea on the published dev tasks: when a gold fixable file is
in the top two, does the printed excerpt contain the lines the gold patch removes (i.e. the text an
edit must quote) and how much of the hunk does it cover? It also reports the total output size, so
the change cannot silently flood the tool result.

Read-only apart from cloning the four public repositories into ~/.cache/gemma-repos.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from locate_benchmark import checkout, gold_files, is_fixable, repo_worktree, tasks_from_git  # noqa: E402

# tasks.jsonl stores each gold patch as "--- a/<path>" / "+++ b/<path>" sections followed by
# unified-diff hunks; the first attempt at this tool only matched the "diff --git" form and so
# reported 0% coverage by construction. Both forms are handled now.
MINUS_FILE_RE = re.compile(r"^--- a/(?P<path>\S+)$")
PLUS_FILE_RE = re.compile(r"^\+\+\+ b/(?P<path>\S+)$")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("excerpt_locator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def anchor_lines(patch: str, target: str) -> tuple[list[str], int]:
    """Lines of the gold hunks for `target` that a fix must be able to anchor on.

    Returns (anchors, removed_count): anchors are the stripped hunk lines that exist in the file at
    the base commit - context lines and removed lines; pure insertions contribute only context.
    Removed lines are counted separately because they are what an edit quotes verbatim.
    """
    anchors: list[str] = []
    removed = 0
    current: str | None = None
    for line in patch.splitlines():
        minus = MINUS_FILE_RE.match(line)
        plus = PLUS_FILE_RE.match(line)
        if minus:
            current = minus.group("path")
            continue
        if plus:
            current = plus.group("path")
            continue
        if current is None or current != target:
            continue
        if line.startswith("@@") or line.startswith("diff ") or line.startswith("index "):
            continue
        if line.startswith("-"):
            removed += 1
            body = line[1:].strip()
        elif line.startswith(" "):
            body = line.strip()
        else:
            continue  # an added line does not exist in the repository yet
        if body:
            anchors.append(body)
    return anchors, removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--locator", type=Path, required=True)
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    module = load_module(args.locator)
    tasks = tasks_from_git(None, args.count)
    worktree = None
    current_repo = None
    rows = []
    for index, task in enumerate(tasks, start=1):
        code, tests = gold_files(task.get("patch") or "")
        gold = {p for p in (code or tests) if is_fixable(p)}
        if not gold:
            continue
        if task["repo"] != current_repo:
            worktree = repo_worktree(task["repo"])
            current_repo = task["repo"]
        checkout(worktree, task["base_commit"])
        issue = task.get("problem_statement") or ""
        struct = module.collect(worktree)
        query = module.build_query(issue)
        ranked = [name for _, name in module.rank(struct, query)[:8]]
        first = next((i + 1 for i, name in enumerate(ranked) if name in gold), None)
        # Rebuild the exact printed output to measure its size.
        needles = [t for t in query if len(t) >= 4][:20]
        import io
        import contextlib
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            if ranked:
                print("# locator: %d python files scanned, %d query terms" % (len(struct), len(query)))
                for position, name in enumerate(ranked, start=1):
                    print("%2d. %s" % (position, name))
                    if position <= getattr(module, "EXCERPT_CANDIDATES", 0):
                        for idx in module.excerpt(struct, name, needles):
                            print("    L%d: %s" % (idx + 1, struct[name]["text"].splitlines()[idx].rstrip()[:160]))
        out_size = len(buffer.getvalue())

        covered = total = None
        gold_in_excerpt = None
        if first is not None and first <= getattr(module, "EXCERPT_CANDIDATES", 2):
            target = ranked[first - 1]
            shown_lines = {struct[target]["text"].splitlines()[i].strip()
                           for i in module.excerpt(struct, target, needles)}
            wanted, removed_count = anchor_lines(task.get("patch") or "", target)
            total = len(wanted)
            covered = sum(1 for line in wanted if line in shown_lines)
            gold_in_excerpt = covered > 0
            rows_removed = removed_count
        rows.append({"instance_id": task["instance_id"], "repo": task["repo"], "gold_rank": first,
                     "out_chars": out_size, "anchor_lines": total, "covered": covered,
                     "gold_removed_lines": rows_removed if first is not None and first <= 2 else None,
                     "excerpt_edit_constructible": gold_in_excerpt,
                     "file": ranked[first - 1] if first else None})
        if index % 40 == 0:
            print(f"  {index}/{len(tasks)}", flush=True)

    scored = [r for r in rows if r["gold_rank"] is not None]
    top2 = [r for r in scored if r["gold_rank"] <= 2]
    covered = [r for r in top2 if r["excerpt_edit_constructible"]]
    print(f"\ntasks scored: {len(rows)}  (gold found in top-8: {len(scored)})")
    print(f"gold in top-2: {len(top2)}  of those with gold code visible in the excerpt: {len(covered)} "
          f"({len(covered) / max(1, len(top2)):.1%})")
    frac = [r["covered"] / r["anchor_lines"] for r in top2 if r["anchor_lines"]]
    if frac:
        print(f"share of the gold hunks' anchor lines present in the excerpt: "
              f"median {st.median(frac):.0%}, mean {st.mean(frac):.0%}")
    with_removed = [r for r in top2 if (r["gold_removed_lines"] or 0) > 0]
    if with_removed:
        complete = [r for r in with_removed if r["covered"] >= r["anchor_lines"]]
        print(f"tasks where the gold patch removes lines (edits quotable verbatim): {len(with_removed)}; "
              f"excerpt covers all anchor lines in {len(complete)} of them")
    sizes = [r["out_chars"] for r in rows]
    print(f"locator output size: median {st.median(sizes):.0f} chars, p90 "
          f"{sorted(sizes)[int(0.9 * len(sizes))]:.0f}, max {max(sizes)}")
    print(f"locator sha256: {hashlib.sha256(args.locator.read_bytes()).hexdigest()}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "locator": str(args.locator),
            "locator_sha256": hashlib.sha256(args.locator.read_bytes()).hexdigest(),
            "tasks_scored": len(rows), "gold_in_top2": len(top2),
            "excerpt_constructible": len(covered),
            "output_size_chars": {"median": st.median(sizes), "max": max(sizes)},
            "rows": rows,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"json: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
