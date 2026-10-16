#!/usr/bin/env python3
"""Poll a Kaggle benchmark kernel started earlier, until it finishes, then fetch its result.

Why this exists: a long screen (30 tasks at a raised per-task clock) does not fit inside one
GitHub-hosted job - the wait for the weekly GPU quota reset plus a 4-5 hour kernel exceeds the
6-hour job limit. So the launching job starts the kernel and leaves (see the `timeout` wrapper in
gemma-kaggle-v7c-clock-screen.yml), and this tool does the waiting in a second job, which gets a
fresh 6-hour budget. It reads the kernel reference the launcher already recorded in `run.json`.

It never prints raw authenticated CLI output, only parsed statuses.

Usage:
    python3 gemma4-agent/tools/poll_kernel_until_done.py \\
        --run-json gemma4-agent/kaggle_results/v7-c-benchmark/run.json \\
        --max-wait-minutes 340 --poll-interval-seconds 90
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

FINISHED_OK = "COMPLETE"
FINISHED_BAD = {"ERROR", "CANCELED", "CANCELLED"}
RESULT_NAME = "agent_benchmark_result.json"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def kaggle(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(["kaggle", *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def parse_status(text: str) -> str | None:
    """`kaggle kernels status` prints e.g. '... has status "KernelWorkerStatus.RUNNING"'."""
    for token in ("COMPLETE", "RUNNING", "QUEUED", "ERROR", "CANCELED", "CANCELLED"):
        if f"KernelWorkerStatus.{token}" in text:
            return token
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-json", type=Path, required=True)
    parser.add_argument("--max-wait-minutes", type=int, default=340)
    parser.add_argument("--poll-interval-seconds", type=int, default=90)
    args = parser.parse_args()

    run_json = args.run_json
    if not run_json.is_file():
        print(f"No run record at {run_json}; nothing to poll.")
        return 2
    state = json.loads(run_json.read_text(encoding="utf-8"))
    kernel_ref = state.get("kernel_ref")
    if not kernel_ref:
        print("run.json carries no kernel_ref; the launcher never got as far as creating a kernel.")
        return 2
    outdir = run_json.parent
    print(f"Polling {kernel_ref} for up to {args.max_wait_minutes} min.")

    deadline = time.monotonic() + max(1, args.max_wait_minutes) * 60
    last_status = "UNKNOWN"
    consecutive_errors = 0
    while time.monotonic() < deadline:
        result = kaggle(["kernels", "status", kernel_ref], timeout=90)
        if result is None or result.returncode != 0:
            consecutive_errors += 1
            if consecutive_errors >= 5:
                state.update({"status": "status_poll_failed", "poll_checked_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
                write_json(run_json, state)
                print("Five consecutive status calls failed; giving up without touching the kernel.")
                return 3
        else:
            consecutive_errors = 0
            last_status = parse_status(result.stdout + "\n" + result.stderr) or "UNPARSED"
            state["kaggle_status"] = last_status
            state["poll_checked_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            write_json(run_json, state)
            print(f"  status: {last_status}")
            if last_status == FINISHED_OK:
                with tempfile.TemporaryDirectory(prefix="gemma-kernel-output-") as temporary:
                    fetched = kaggle(["kernels", "output", kernel_ref, "--path", temporary, "--force"], timeout=600)
                    if fetched is None or fetched.returncode != 0:
                        state.update({"status": "output_download_failed", "error": "kaggle kernels output failed"})
                        write_json(run_json, state)
                        return 4
                    source = None
                    for candidate in Path(temporary).rglob(RESULT_NAME):
                        source = candidate
                        break
                    if source is None:
                        state.update(
                            {
                                "status": "output_download_failed",
                                "error": f"the kernel ran, but no {RESULT_NAME} appeared in its output",
                            }
                        )
                        write_json(run_json, state)
                        return 4
                    shutil.copyfile(source, outdir / RESULT_NAME)
                payload = json.loads((outdir / RESULT_NAME).read_text(encoding="utf-8"))
                state.update(
                    {
                        "status": "complete",
                        "result": {
                            key: payload.get(key)
                            for key in (
                                "tasks_completed_or_failed",
                                "task_count_selected",
                                "resolved_count",
                                "score_estimate",
                                "score_ci95_wilson",
                                "mean_task_duration_seconds",
                                "total_task_duration_seconds",
                                "benchmark_wall_seconds",
                                "per_task_max_time_minutes",
                                "submission_sha256",
                            )
                        },
                        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    }
                )
                write_json(run_json, state)
                print(
                    "DONE: resolved {}/{} at a {} min clock, mean task {} s".format(
                        payload.get("resolved_count"),
                        payload.get("task_count_selected"),
                        payload.get("per_task_max_time_minutes"),
                        round(payload.get("mean_task_duration_seconds") or 0),
                    )
                )
                return 0
            if last_status in FINISHED_BAD:
                state.update({"status": last_status.lower(), "error": "the kernel ended without a result"})
                write_json(run_json, state)
                print(f"The kernel ended as {last_status}; no result to fetch.")
                return 5
        time.sleep(max(30, args.poll_interval_seconds))

    state.update(
        {
            "status": "still_running_at_deadline",
            "error": f"the kernel was still {last_status} when the {args.max_wait_minutes}-minute window closed",
        }
    )
    write_json(run_json, state)
    print("The waiting window closed with the kernel unfinished; nothing was cancelled on Kaggle.")
    return 6


if __name__ == "__main__":
    raise SystemExit(main())
