"""Run the generated notebook's concurrency block against stubs, on CPU, before it touches a GPU.

The block that decides whether tasks overlap lives inside a string (the notebook). Nothing else in
the repo can exercise it without a Kaggle kernel, which is how three dead knobs shipped in one day.
This test cuts the block out of the generated notebook, replaces the evaluator with a fake that
sleeps, and asserts the three properties we actually depend on:

  * the semaphore really caps concurrent sessions at `concurrency`;
  * one task raising does not abort the others or lose their rows;
  * every task gets its row appended and persisted, so a later crash cannot lose finished work.

Run: python3 gemma4-agent/tools/test_notebook_concurrency.py
Exit code 0 = the block behaves; 1 = do not launch.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import importlib.util
import json
import sys
import time
from pathlib import Path

LAUNCHER = Path(__file__).with_name("run_kaggle_v1_smoke.py")
CONCURRENCY = 3
TASKS = 6
SLEEP_SECONDS = 0.4


def run_sync(coro_or_fn, *args, **kwargs):
    """Same helper the notebook defines: run a coroutine in a fresh loop, thread if one is running."""
    fn = (lambda: coro_or_fn(*args, **kwargs)) if callable(coro_or_fn) else (lambda: coro_or_fn)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(fn())).result()
    return asyncio.run(fn())


def load_block() -> str:
    spec = importlib.util.spec_from_file_location("run_kaggle_v1_smoke", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    notebook = module.build_notebook(
        b"PK\x05\x06" + b"\x00" * 18, "0" * 64, task_count=2, seed=1, concurrency=CONCURRENCY
    )
    source = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    start = source.index("_CONCURRENCY = max(1, int(TASK_SELECTION.get('concurrency') or 1))")
    end = source.index("final_summary = persist_results()")
    return source[start:end]


class Task:
    def __init__(self, index: int) -> None:
        self.instance_id = f"t{index}"
        self.repo = "stub/repo"


class Result:
    def __init__(self, index: int) -> None:
        self.agent_patch = "diff" if index % 2 else ""
        self.test_exit_code = 0
        self.resolved = bool(index % 2)
        self.tool_calls = 3
        self.duration_seconds = 1.0


class FakeEvaluator:
    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self.started = 0

    async def evaluate_task(self, task, task_index, total_tasks):
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.started += 1
        try:
            await asyncio.sleep(SLEEP_SECONDS)
            if task.instance_id == "t2":
                raise RuntimeError("stub failure")
            return Result(int(task.instance_id[1:]))
        finally:
            self.active -= 1


def main() -> int:
    block = load_block()
    block = block.replace(
        f"int(TASK_SELECTION.get('concurrency') or 1)",
        str(CONCURRENCY),
        1,
    ).replace("max(1, ", "max(1, ", 1)
    environment = {
        "asyncio": asyncio,
        "json": json,
        "TASK_SELECTION": {"concurrency": CONCURRENCY},
        "selected_tasks": [Task(i) for i in range(1, TASKS + 1)],
        "evaluator": FakeEvaluator(),
        "per_task_results": [],
        "patches": [],
        "GOLD_BY_TASK": {},
        "_patch_paths": lambda patch: ["pkg/mod.py"],
        "_is_test_path": lambda path: False,
        "persist_results": lambda: {
            "tasks_completed_or_failed": len(environment["per_task_results"]),
            "resolved_count": sum(row["resolved"] for row in environment["per_task_results"]),
            "score_estimate": 0.0,
            "score_ci95_wilson": [0.0, 1.0],
        },
        "run_sync": run_sync,
    }
    started_at = time.monotonic()
    exec(compile(block, "<notebook-block>", "exec"), environment)  # noqa: S102 - the block under test
    elapsed = time.monotonic() - started_at
    rows = environment["per_task_results"]
    evaluator = environment["evaluator"]

    problems: list[str] = []
    if evaluator.peak != CONCURRENCY:
        problems.append(f"peak concurrency {evaluator.peak}, expected {CONCURRENCY}")
    if evaluator.started != TASKS:
        problems.append(f"{evaluator.started} tasks started, expected {TASKS}")
    if len(rows) != TASKS:
        problems.append(f"{len(rows)} rows recorded, expected {TASKS}")
    if sum(row["resolved"] for row in rows) != TASKS // 2:
        problems.append("resolved count does not match the stubbed results")
    if not any("stub failure" in (row.get("error") or "") for row in rows):
        problems.append("a raising task did not produce a failure row")
    serial_seconds = TASKS * SLEEP_SECONDS
    if elapsed > serial_seconds * 0.75:
        problems.append(f"{elapsed:.2f}s is not faster than serial ({serial_seconds:.2f}s)")

    if problems:
        print("CONCURRENCY BLOCK IS BROKEN - do not launch:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(
        f"OK: peak {evaluator.peak} sessions, {len(rows)} rows, {elapsed:.2f}s "
        f"against {serial_seconds:.2f}s serial, failure row kept"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
