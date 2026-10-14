#!/usr/bin/env python3
"""Join the shipped locator's per-task ranking with the recorded benchmark outcomes.

Motivation (2026-10-14): the failure taxonomy of the full V6.4 run splits the 20 lost tasks into
11 "no edit at all" and 8 "edited a gold file and still failed", with only 1 "edited a wrong file".
That makes localization look unimportant - but the taxonomy field `localized` is defined as
"the agent's patch touched a gold fixable file", i.e. it is an outcome, not a cause. This tool
supplies the missing cause: for every task in a recorded run it recomputes the ranking with the
locator that actually shipped, and reports the rank of the first gold fixable file. Cross-tabulated
with the outcome bucket it answers the only question that matters for the next lever:

    do the sessions that never edit see a plausible candidate, or are they flying blind?

Read-only apart from cloning the four public repositories into ~/.cache/gemma-repos.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from locate_benchmark import checkout, gold_files, is_fixable, repo_worktree, tasks_from_git  # noqa: E402

RANK_BUCKETS = ("1", "2-3", "4-5", "6-10", ">10", "miss")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("audited_locator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def bucket_of(task: dict) -> str:
    if task.get("resolved"):
        return "P resolved"
    touched = [p.strip().lstrip("./") for p in (task.get("touched_files") or [])]
    gold = [p.strip().lstrip("./") for p in (task.get("gold_fixable_files") or [])]
    repo_touched = [p for p in touched if not p.startswith("/")]
    if int(task.get("patch_chars") or 0) == 0 and not repo_touched:
        return "N no edit"
    if set(repo_touched) & set(gold):
        return "R gold file edited, failed"
    return "W wrong file edited"


def rank_bucket(first_rank: int | None) -> str:
    if first_rank == 1:
        return "1"
    if first_rank is not None and first_rank <= 3:
        return "2-3"
    if first_rank is not None and first_rank <= 5:
        return "4-5"
    if first_rank is not None and first_rank <= 10:
        return "6-10"
    if first_rank is not None:
        return ">10"
    return "miss"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--locator", type=Path, required=True,
                    help="e.g. gemma4-agent/submission-v6.6/tools/locate.py")
    ap.add_argument("--result", type=Path, required=True,
                    help="agent_benchmark_result.json whose task_ids define the sample")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=None, help="markdown report path")
    args = ap.parse_args()

    module = load_module(args.locator)
    recorded = json.loads(args.result.read_text(encoding="utf-8"))
    wanted = list(recorded.get("task_ids") or [])
    by_id = {t.get("task_id"): t for t in (recorded.get("tasks") or [])}
    tasks = {t["instance_id"]: t for t in tasks_from_git(None, None) if t["instance_id"] in wanted}

    worktree = None
    current_repo = None
    rows = []
    table: dict[str, Counter] = {}
    for task_id in wanted:
        task = tasks.get(task_id)
        if task is None:
            rows.append({"task_id": task_id, "error": "not in tasks.jsonl"})
            continue
        code, tests = gold_files(task.get("patch") or "")
        gold = {p for p in (code or tests) if is_fixable(p)}
        if task["repo"] != current_repo:
            worktree = repo_worktree(task["repo"])
            current_repo = task["repo"]
        checkout(worktree, task["base_commit"])
        struct = module.collect(worktree)
        ranked = [name for _, name in module.rank(struct, module.build_query(task.get("problem_statement") or ""))[: args.top]] if struct else []
        first = next((i + 1 for i, name in enumerate(ranked) if name in gold), None)
        b = bucket_of(by_id.get(task_id, {}))
        rb = rank_bucket(first)
        table.setdefault(b, Counter())[rb] += 1
        rows.append({"task_id": task_id, "repo": task["repo"], "bucket": b, "gold_rank": first,
                     "rank_bucket": rb, "gold": sorted(gold)[:3], "top3": ranked[:3]})

    print(f"locator: {args.locator}")
    print(f"sample:  {len(wanted)} tasks from {args.result}")
    print()
    header = f"{'bucket':28}" + "".join(f"{b:>7}" for b in RANK_BUCKETS) + f"{'total':>7}"
    print(header)
    print("-" * len(header))
    for b in ("P resolved", "N no edit", "R gold file edited, failed", "W wrong file edited"):
        if b not in table:
            continue
        c = table[b]
        print(f"{b:28}" + "".join(f"{c.get(k, 0):>7}" for k in RANK_BUCKETS) + f"{sum(c.values()):>7}")
    print()
    print("per task:")
    print(f"{'task':16} {'bucket':28} {'gold_rank':>9}  top3 of the ranking")
    for r in rows:
        if "error" in r:
            print(f"{r['task_id']:16} {'?':28} {r['error']}")
            continue
        rank = r["gold_rank"] if r["gold_rank"] is not None else "-"
        print(f"{r['task_id']:16} {r['bucket']:28} {str(rank):>9}  {', '.join(r['top3'])}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "locator": str(args.locator),
            "sample_size": len(wanted),
            "table": {b: dict(c) for b, c in table.items()},
            "rows": rows,
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\njson: {args.out}")
    if args.report:
        lines = ["# Locator ranking vs recorded outcome (per task)", "",
                 f"Locator: `{args.locator}`. Sample: the {len(wanted)} tasks of `{args.result}`.", "",
                 "`gold_rank` = position of the first gold fixable file in the locator's ranking "
                 "(the list the agent is shown in step 2), `-` = the file is not in the top "
                 f"{args.top}.", "",
                 "| task | bucket | gold_rank | top-3 shown |", "| --- | --- | --- | --- |"]
        for r in rows:
            if "error" in r:
                lines.append(f"| {r['task_id']} | ? | {r['error']} | |")
                continue
            rank = r["gold_rank"] if r["gold_rank"] is not None else f"- (> {args.top})"
            lines.append(f"| {r['task_id']} | {r['bucket']} | {rank} | {', '.join(r['top3'])} |")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
