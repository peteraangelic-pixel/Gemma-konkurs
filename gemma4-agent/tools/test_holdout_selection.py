"""Exercise the notebook's repository-holdout selector on CPU, with stub tasks.

A leave-one-repo-out screen is worthless if the held-out repository leaks back in through the
reserved reference task (`fastapi_15588` is reserved on every stratified draw) or through an explicit
task id. Both paths exist in the generated cell, both were written after the holdout flag, and
neither can be tested against the real task list from here - the task list lives inside the Kaggle
dataset. So the selector is cut out of the generated notebook and run against a stub distribution
shaped like the real one (fastapi 16, rich 10, requests 3, httpx 1 out of 30).

Run: python3 gemma4-agent/tools/test_holdout_selection.py
Exit code 0 = selection behaves; 1 = do not launch a holdout screen.
"""
from __future__ import annotations

import importlib.util
import math
import random
import sys
from pathlib import Path

LAUNCHER = Path(__file__).with_name("run_kaggle_v1_smoke.py")

# Shape of the public development split, inferred from the 30-task draw that used it:
# fastapi 16/30, rich 10/30, requests 3/30, httpx 1/30.
STUB_COUNTS = {
    "fastapi/fastapi": 16,
    "Textualize/rich": 10,
    "psf/requests": 3,
    "encode/httpx": 1,
}
REFERENCE_ID = "fastapi_15588"
REFERENCES = {"fastapi/fastapi": REFERENCE_ID}


class Task:
    def __init__(self, instance_id: str, repo: str) -> None:
        self.instance_id = instance_id
        self.repo = repo


def stub_tasks() -> list[Task]:
    tasks: list[Task] = []
    for repo, count in STUB_COUNTS.items():
        prefix = repo.split("/")[1].replace("-", "_")
        for index in range(count):
            instance_id = REFERENCES.get(repo) if index == 0 and repo in REFERENCES else None
            tasks.append(Task(instance_id or f"{prefix}_{1000 + index}", repo))
    return tasks


def load_selector() -> str:
    spec = importlib.util.spec_from_file_location("run_kaggle_v1_smoke", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    notebook = module.build_notebook(
        b"PK\x05\x06" + b"\x00" * 18, "0" * 64, task_count=30, seed=20261009, concurrency=1
    )
    source = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    start = source.index("all_tasks = load_tasks(TASKS_PATH)")
    end = source.index("repo_counts = {}")
    return source[start:end]


def select(block: str, tasks, *, task_count=30, excluded=(), explicit=(), seed=20261009,
           reference=REFERENCE_ID):
    environment = {
        "math": math,
        "random": random,
        "load_tasks": lambda path: list(tasks),
        "TASKS_PATH": "stub",
        "TASK_SELECTION": {
            "task_count": task_count,
            "seed": seed,
            "task_id": reference,
            "excluded_repos": list(excluded),
            "task_ids": list(explicit),
        },
        "_excluded": sorted(excluded),
        "len": len,
        "min": min,
        "max": max,
        "sorted": sorted,
        "sum": sum,
        "print": lambda *a, **k: None,
    }
    exec(compile(block, "<selector>", "exec"), environment)
    return [task.instance_id for task in environment["selected_tasks"]], environment


def main() -> int:
    block = load_selector()
    tasks = stub_tasks()
    all_ids = {task.instance_id for task in tasks}
    by_id = {task.instance_id: task for task in tasks}
    problems: list[str] = []

    for repo in STUB_COUNTS:
        ids, env = select(block, tasks, excluded=[repo])
        leaked = [item for item in ids if by_id[item].repo == repo]
        if leaked:
            problems.append(f"holdout {repo}: leaked {leaked}")
        if repo == "fastapi/fastapi" and REFERENCE_ID in ids:
            problems.append("holdout fastapi/fastapi: the reserved reference task survived")
        if len(ids) != len(set(ids)):
            problems.append(f"holdout {repo}: duplicate task ids")
        if not ids:
            problems.append(f"holdout {repo}: empty selection")
        if env["selected_tasks"] and len(ids) != env["requested_count"]:
            problems.append(f"holdout {repo}: {len(ids)} selected, {env['requested_count']} requested")

    # The two small repositories force the request below the surviving task count.
    ids, _ = select(block, tasks, task_count=29, excluded=["encode/httpx"])
    if len(ids) != 29:
        problems.append(f"request 29 with one task held out yielded {len(ids)}")

    ids, _ = select(block, tasks, task_count=30, excluded=["fastapi/fastapi"])
    # 30 - 16 fastapi = 14 survivors; the request is capped to them rather than failing.
    if len(ids) != 14:
        problems.append(f"holdout fastapi should sample all 14 survivors, got {len(ids)}")

    # Determinism: the same seed must give the same set, a different seed a different one.
    first, _ = select(block, tasks, excluded=["Textualize/rich"])
    second, _ = select(block, tasks, excluded=["Textualize/rich"])
    if first != second:
        problems.append("the same seed produced two different samples")
    other, _ = select(block, tasks, excluded=["Textualize/rich"], seed=7)
    if other == first:
        problems.append("a different seed produced the same sample (seed is not wired)")

    # An explicit id from a held-out repository must fail loudly, not slip through.
    try:
        select(block, tasks, excluded=["psf/requests"], explicit=["requests_1000"])
    except AssertionError as exc:
        if "held-out" not in str(exc):
            problems.append(f"explicit-id leak raised the wrong assertion: {exc}")
    else:
        problems.append("an explicit task id from a held-out repository was accepted")

    if problems:
        print("HOLDOUT SELECTOR IS BROKEN - do not launch:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    sizes = {repo: len(select(block, tasks, task_count=30, excluded=[repo])[0]) for repo in STUB_COUNTS}
    print(f"OK: holdout sizes {sizes}, reference task dropped when fastapi is held out, "
          "explicit leaks refused, seed wired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
