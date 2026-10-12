#!/usr/bin/env python3
"""Verify that a locator script (e.g. the compact one embedded in the V6 prompt)
scores the same as the reference recipe on the dev set and on held-out repos.

    python3 gemma4-agent/tools/locate_verify.py --locator gemma4-agent/submission-v6/tools/locate.py --mode dev
    python3 gemma4-agent/tools/locate_verify.py --locator gemma4-agent/submission-v6/tools/locate.py --mode holdout
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from locate_benchmark import checkout, gold_files, is_fixable, repo_worktree, tasks_from_git  # noqa: E402
from locate_holdout import candidate_tasks, ensure_repo, git  # noqa: E402


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("candidate_locator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def measure(module, root: Path, issue: str, gold: set[str], top: int = 10) -> list[str]:
    struct = module.collect(root)
    if not struct:
        return []
    query = module.build_query(issue)
    return [name for _, name in module.rank(struct, query)[:top]]


def dev_mode(module) -> dict:
    tasks = tasks_from_git(None, None)
    hits = {1: 0, 5: 0, 10: 0}
    scored = 0
    worktree = None
    current = None
    for index, task in enumerate(tasks, start=1):
        code, tests = gold_files(task.get("patch") or "")
        targets = {p for p in (code or tests) if is_fixable(p)}
        if not targets:
            continue
        if task["repo"] != current:
            worktree = repo_worktree(task["repo"])
            current = task["repo"]
        checkout(worktree, task["base_commit"])
        ranked = measure(module, worktree, task.get("problem_statement") or "", targets)
        scored += 1
        for k in (1, 5, 10):
            if set(ranked[:k]) & targets:
                hits[k] += 1
        if index % 30 == 0:
            print(f"  {index}/{len(tasks)}", flush=True)
    return {"tasks": scored, "hit_rates": {f"top{k}": round(hits[k] / max(1, scored), 4) for k in (1, 5, 10)}}


def holdout_mode(module, repos: list[str], per_repo: int) -> dict:
    hits = {1: 0, 5: 0, 10: 0}
    scored = 0
    per_repo_rates = {}
    for repo in repos:
        repo_dir = ensure_repo(repo)
        repo_hits = {1: 0, 5: 0, 10: 0}
        rows = 0
        for task in candidate_tasks(repo_dir, per_repo):
            git(repo_dir, "checkout", "-q", "-f", task["base"])
            ranked = measure(module, repo_dir, task["title"], set(task["files"]))
            rows += 1
            for k in (1, 5, 10):
                if set(ranked[:k]) & set(task["files"]):
                    hits[k] += 1
                    repo_hits[k] += 1
        scored += rows
        per_repo_rates[repo] = {f"top{k}": round(repo_hits[k] / max(1, rows), 4) for k in (1, 5, 10)}
        print(f"  {repo}: {rows} tasks -> " + ", ".join(f"top{k} {repo_hits[k] / max(1, rows):.1%}"
                                                        for k in (1, 5, 10)), flush=True)
    return {"tasks": scored, "hit_rates": {f"top{k}": round(hits[k] / max(1, scored), 4) for k in (1, 5, 10)},
            "per_repo": per_repo_rates}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locator", type=Path, required=True)
    parser.add_argument("--mode", choices=["dev", "holdout"], default="dev")
    parser.add_argument("--repo", action="append",
                        default=["encode/starlette", "pallets/click"])
    parser.add_argument("--tasks-per-repo", type=int, default=30)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    module = load_module(args.locator)
    result = dev_mode(module) if args.mode == "dev" else holdout_mode(module, args.repo, args.tasks_per_repo)
    result["locator"] = str(args.locator)
    result["mode"] = args.mode
    print(json.dumps(result, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
