#!/usr/bin/env python3
"""Held-out check: does the shipped locator transfer to repositories it never saw?

The hidden test split uses private repositories, which is exactly why V2-V4's
repo-specific hints collapsed from 11/30 public to 0.03 hidden. This script builds
proxy tasks from public repos that are NOT in the dev set (starlette, click, typer, ...):
each proxy task is a real merged pull request, the issue text is the PR title only
(the same shape as the published statements), and the target is the source .py file the
PR changed. It measures the *shipped* recipe, importing tools/locator.py directly.

Usage:
    python3 gemma4-agent/tools/locate_holdout.py --repo encode/starlette --repo pallets/click
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import locator  # noqa: E402  (the artifact we actually ship)

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE = Path.home() / ".cache" / "gemma-repos" / "holdout"
SKIP_PREFIXES = ("tests/", "docs/", "docs_src/", "scripts/", ".github/", "benchmarks/")


def git(repo_dir: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo_dir), *args],
                          check=True, capture_output=True, text=True).stdout


def ensure_repo(repo: str) -> Path:
    local = CACHE / repo.replace("/", "__")
    if not local.is_dir():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                        f"https://github.com/{repo}.git", str(local)],
                       check=True, capture_output=True, text=True)
    return local


def default_ref(repo_dir: Path) -> str:
    """Walk the default branch, not the detached HEAD left by the previous iteration."""
    for ref in ("origin/HEAD", "origin/main", "origin/master"):
        try:
            git(repo_dir, "rev-parse", "--verify", ref)
            return ref
        except subprocess.CalledProcessError:
            continue
    return "HEAD"


def candidate_tasks(repo_dir: Path, limit: int) -> list[dict]:
    """Merged PRs that look like SWE tasks: a title and 1-5 changed source files."""
    ref = default_ref(repo_dir)
    out = git(repo_dir, "log", ref, "--merges", "-n", str(limit * 6), "--format=%H%x1f%P%x1f%s")
    tasks: list[dict] = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        commit, parents, subject = parts
        parent_list = parents.split()
        if len(parent_list) != 2:
            continue
        title = subject.split("(#")[0].strip()
        if not title or len(title) > 200:
            continue
        changed = git(repo_dir, "diff", "--name-status", f"{parent_list[0]}..{commit}").splitlines()
        files = []
        for row in changed:
            fields = row.split("\t")
            if len(fields) < 2:
                continue
            status, path = fields[0], fields[1]
            if status.startswith("D") or not path.endswith(".py"):
                continue
            if path.startswith(SKIP_PREFIXES) or "_test" in path or "conftest" in path:
                continue
            files.append(path)
        if not 1 <= len(files) <= 5:
            continue
        tasks.append({"commit": commit, "base": parent_list[0], "title": title, "files": files})
        if len(tasks) >= limit:
            break
    return tasks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", action="append", required=True)
    parser.add_argument("--tasks-per-repo", type=int, default=40)
    parser.add_argument("--outdir", type=Path,
                        default=REPO_ROOT / "gemma4-agent" / "analysis" / "locate-holdout")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    results = {}
    aggregate = {1: 0, 5: 0, 10: 0}
    total = 0
    for repo in args.repo:
        repo_dir = ensure_repo(repo)
        tasks = candidate_tasks(repo_dir, args.tasks_per_repo)
        hits = {1: 0, 5: 0, 10: 0}
        rows = []
        for task in tasks:
            git(repo_dir, "checkout", "-q", "-f", task["base"])
            struct = locator.collect(repo_dir)
            if not struct:
                continue
            query = locator.build_query(task["title"])
            ranked = [name for _, name in locator.rank(struct, query)[: args.top]]
            gold = set(task["files"])
            row = {"title": task["title"], "gold": task["files"], "top5": ranked[:5]}
            for k in (1, 5, 10):
                if set(ranked[:k]) & gold:
                    hits[k] += 1
                    row[f"hit{k}"] = True
            rows.append(row)
        scored = len(rows)
        results[repo] = {
            "tasks": scored,
            "hit_rates": {f"top{k}": round(hits[k] / max(1, scored), 4) for k in (1, 5, 10)},
            "rows": rows,
        }
        for k in (1, 5, 10):
            aggregate[k] += hits[k]
        total += scored
        print(f"{repo}: {scored} tasks -> "
              + ", ".join(f"top{k} {hits[k] / max(1, scored):.1%}" for k in (1, 5, 10)), flush=True)

    summary = {
        "repos": list(results),
        "tasks_scored": total,
        "aggregate_hit_rates": {f"top{k}": round(aggregate[k] / max(1, total), 4) for k in (1, 5, 10)},
        "note": "issue text = PR title only; target = source .py changed by the merge; "
                "repos are outside the dev set, so this measures transfer, not tuning.",
        "per_repo": {repo: {"tasks": r["tasks"], "hit_rates": r["hit_rates"]} for repo, r in results.items()},
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "holdout_result.json").write_text(
        json.dumps({"summary": summary, "details": results}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps(summary["aggregate_hit_rates"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
