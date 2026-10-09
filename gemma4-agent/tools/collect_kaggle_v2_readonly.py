#!/usr/bin/env python3
"""Collect status, log diagnostics, and completed results for an existing Kaggle kernel.

This tool is intentionally read-only: it never pushes, edits, deletes, or executes a
Kaggle kernel. Raw logs stay in the temporary Actions artifact directory; only a
small diagnostic/result summary is written into the repository.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

COMPLETED_STATUSES = {"COMPLETE", "COMPLETED", "SUCCESS", "SUCCEEDED"}
TERMINAL_STATUSES = COMPLETED_STATUSES | {"ERROR", "FAILED", "FAILURE", "CANCELED", "CANCELLED"}
DIAGNOSTIC_MARKERS = (
    "traceback",
    "error",
    "exception",
    "failure",
    "cuda",
    "out of memory",
    "oom",
    "timed out",
    "timeout",
    "killed",
    "module not found",
    "importerror",
    "worker error",
    "kernelworkerstatus",
    "permission denied",
    "exit code",
    "segmentation fault",
    "failed",
    "could not",
    "no matching distribution",
    "not a supported wheel",
    "not compatible",
    "requires-python",
    "subprocess-exited-with-error",
    "invalid wheel",
)
STATUS_RE = re.compile(r"has status\s+[\"']([^\"']+)[\"']", re.IGNORECASE)
WORKER_STATUS_RE = re.compile(r"KernelWorkerStatus\.([A-Z_]+)", re.IGNORECASE)
GENERIC_STATUS_RE = re.compile(
    r"\b(COMPLETE|COMPLETED|SUCCESS|SUCCEEDED|ERROR|FAILED|FAILURE|CANCELLED|CANCELED|"
    r"QUEUED|PENDING|RUNNING|CREATED|INITIALIZING)\b",
    re.IGNORECASE,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_kaggle(args: list[str], timeout: int) -> tuple[int | None, str, str, str | None]:
    command = [sys.executable, "-m", "kaggle", *args]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, "", "", "timeout"
    except OSError as exc:
        return None, "", "", type(exc).__name__
    return result.returncode, result.stdout, result.stderr, None


def parse_status(text: str) -> tuple[str | None, str | None]:
    match = STATUS_RE.search(text)
    if match:
        raw = match.group(1).strip()
        return raw, raw.rsplit(".", 1)[-1].upper()
    match = WORKER_STATUS_RE.search(text)
    if match:
        value = match.group(1).upper()
        return f"KernelWorkerStatus.{value}", value
    match = GENERIC_STATUS_RE.search(text)
    if match:
        value = match.group(1).upper()
        return value, value
    return None, None


def diagnostic_lines(log_text: str, limit: int = 32) -> list[str]:
    matches: list[str] = []
    for line in log_text.splitlines():
        cleaned = " ".join(line.split())
        lowered = cleaned.casefold()
        if cleaned and any(marker in lowered for marker in DIAGNOSTIC_MARKERS):
            matches.append(cleaned[:500])
    return matches[-limit:]


def task_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Keep task outcomes and concise errors; never copy agent patches into Git."""
    result: dict[str, Any] = {}
    for key in (
        "task_id",
        "repo",
        "resolved",
        "test_exit_code",
        "tool_calls",
        "duration_seconds",
    ):
        if key in row:
            result[key] = row[key]
    if row.get("error"):
        result["error"] = " ".join(str(row["error"]).split())[:500]
    return result


def markdown_report(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Read-only Kaggle V2 benchmark check",
        "",
        f"- Collected (UTC): `{snapshot['collected_utc']}`",
        f"- Kernel: [`{snapshot['kernel_ref']}`]({snapshot.get('kernel_url', '')})",
        f"- Kaggle status: **{snapshot.get('status', 'UNKNOWN')}**",
        "- Collection mode: read-only; no kernel was started, changed, or stopped.",
        "",
        "## Log diagnostics",
        "",
    ]
    log = snapshot.get("log_fetch", {})
    if log.get("status") == "ok":
        lines.append(
            f"Fetched {log.get('line_count', 0)} log lines; "
            f"{log.get('diagnostic_line_count', 0)} matched diagnostic markers."
        )
        excerpts = log.get("diagnostics", [])
        if excerpts:
            lines.append("")
            lines.extend(f"- `{line}`" for line in excerpts)
        else:
            lines.extend(["", "No error/timeout/CUDA/worker diagnostic markers were found."])
    else:
        lines.append(f"Log fetch: `{log.get('status', 'not_attempted')}`.")
        if log.get("error"):
            lines.append(f"Details: {log['error']}")

    output = snapshot.get("output_fetch", {})
    lines.extend(["", "## Benchmark output", ""])
    result = snapshot.get("benchmark_result")
    if result:
        lines.extend(
            [
                f"- Tasks completed/failed: {result.get('tasks_completed_or_failed', 'unknown')} / "
                f"{result.get('task_count_selected', 'unknown')}",
                f"- Resolved: {result.get('resolved_count', 'unknown')}",
                f"- Sample estimate (not a Kaggle leaderboard score): `{result.get('score_estimate', 'unknown')}`",
                f"- 95% Wilson interval: `{result.get('score_ci95_wilson', 'unknown')}`",
                f"- Benchmark wall time: `{result.get('benchmark_wall_seconds', 'unknown')}` seconds",
            ]
        )
        task_rows = result.get("tasks", [])
        if task_rows:
            lines.extend(["", "### Per-task summary", "", "| Task | Repo | Resolved | Tool calls | Error |", "|---|---|---:|---:|---|"])
            for task in task_rows:
                error = str(task.get("error", "")).replace("|", "\\|").replace("\n", " ")[:240]
                resolved = task.get("resolved", "")
                lines.append(
                    f"| {task.get('task_id', '')} | {task.get('repo', '')} | "
                    f"{resolved} | {task.get('tool_calls', '')} | {error} |"
                )
    else:
        lines.append(f"No result JSON was collected (`{output.get('status', 'not_available')}`).")
        if output.get("error"):
            lines.append(f"Details: {output['error']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-json", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--summary-md", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    args = parser.parse_args()

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    snapshot: dict[str, Any] = {
        "collected_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "read_only",
        "status": "UNKNOWN",
        "log_fetch": {"status": "not_attempted"},
        "output_fetch": {"status": "not_attempted"},
    }
    try:
        run = json.loads(args.run_json.read_text(encoding="utf-8"))
        kernel_ref = str(run.get("kernel_ref", "")).strip()
        if not kernel_ref or "/" not in kernel_ref:
            raise ValueError("The recorded run has no valid Kaggle kernel reference.")
        snapshot["kernel_ref"] = kernel_ref
        snapshot["kernel_url"] = str(run.get("kernel_url") or f"https://www.kaggle.com/code/{kernel_ref}")
        snapshot["submission_sha256"] = run.get("submission_sha256")
        snapshot["run_status_at_last_poll"] = run.get("kaggle_status")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        snapshot["collection_error"] = f"{type(exc).__name__}: {exc}"
        write_json(args.summary_json, snapshot)
        args.summary_md.parent.mkdir(parents=True, exist_ok=True)
        args.summary_md.write_text(markdown_report(snapshot), encoding="utf-8")
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        return 2

    code, stdout, stderr, error = run_kaggle(["kernels", "status", kernel_ref], timeout=90)
    raw_status, normalized = parse_status(f"{stdout}\n{stderr}")
    snapshot["kaggle_status_raw"] = raw_status
    snapshot["status"] = normalized or "UNKNOWN"
    snapshot["status_probe"] = {
        "exit_code": code,
        "error_type": error,
    }
    if code not in (None, 0) or not normalized:
        # Avoid saving raw CLI output: it is unnecessary for diagnosis and may
        # contain account-specific details. Keep just a short, non-secret error.
        detail = " ".join((stderr or stdout).split())[:400]
        if detail:
            snapshot["status_probe"]["detail"] = detail

    status_name = str(snapshot["status"]).upper()
    log_path = args.raw_dir / "kernel.log"
    log_code, log_stdout, log_stderr, log_error = run_kaggle(
        ["kernels", "logs", kernel_ref], timeout=180
    )
    if log_stdout:
        log_path.write_text(log_stdout, encoding="utf-8", errors="replace")
    if log_code == 0 and log_error is None:
        matches = diagnostic_lines(log_stdout)
        snapshot["log_fetch"] = {
            "status": "ok",
            "line_count": len(log_stdout.splitlines()),
            "diagnostic_line_count": sum(
                1
                for line in log_stdout.splitlines()
                if any(marker in " ".join(line.split()).casefold() for marker in DIAGNOSTIC_MARKERS)
            ),
            "diagnostics": matches,
            "raw_log_artifact_path": str(log_path) if log_path.is_file() else None,
        }
    else:
        detail = " ".join((log_stderr or log_stdout).split())[:400]
        snapshot["log_fetch"] = {
            "status": "failed",
            "exit_code": log_code,
            "error_type": log_error,
            "error": detail or "Kaggle CLI could not retrieve the kernel log.",
        }

    if status_name in TERMINAL_STATUSES:
        with tempfile.TemporaryDirectory(prefix="gemma-v2-kaggle-output-") as temporary:
            output_code, output_stdout, output_stderr, output_error = run_kaggle(
                ["kernels", "output", kernel_ref, "--path", temporary, "--force"],
                timeout=300,
            )
            if output_code == 0 and output_error is None:
                result_paths = sorted(Path(temporary).rglob("agent_benchmark_result.json"))
                if result_paths:
                    try:
                        raw_result = json.loads(result_paths[0].read_text(encoding="utf-8"))
                        result = {
                            key: raw_result.get(key)
                            for key in (
                                "task_count_requested",
                                "task_count_selected",
                                "tasks_completed_or_failed",
                                "resolved_count",
                                "score_estimate",
                                "score_ci95_wilson",
                                "per_task_max_time_minutes",
                                "mean_task_duration_seconds",
                                "total_task_duration_seconds",
                                "benchmark_wall_seconds",
                                "model",
                                "visible_gpu_count",
                                "sample_seed",
                                "repo_counts",
                                "task_ids",
                            )
                            if key in raw_result
                        }
                        task_rows = raw_result.get("tasks", [])
                        if isinstance(task_rows, list):
                            result["tasks"] = [task_summary(row) for row in task_rows if isinstance(row, dict)]
                        snapshot["benchmark_result"] = result
                        snapshot["output_fetch"] = {"status": "ok", "result_file_found": True}
                    except (OSError, json.JSONDecodeError) as exc:
                        snapshot["output_fetch"] = {
                            "status": "failed",
                            "error": f"Could not parse benchmark result: {type(exc).__name__}.",
                        }
                else:
                    snapshot["output_fetch"] = {
                        "status": "no_result_file",
                        "error": "Kaggle output was retrieved, but agent_benchmark_result.json was absent.",
                    }
            else:
                detail = " ".join((output_stderr or output_stdout).split())[:400]
                snapshot["output_fetch"] = {
                    "status": "failed",
                    "exit_code": output_code,
                    "error_type": output_error,
                    "error": detail or "Kaggle CLI could not retrieve kernel output.",
                }
    else:
        snapshot["output_fetch"] = {
            "status": "not_ready",
            "message": "Kernel is not in a terminal state; output retrieval was not attempted.",
        }

    write_json(args.summary_json, snapshot)
    args.summary_md.parent.mkdir(parents=True, exist_ok=True)
    args.summary_md.write_text(markdown_report(snapshot), encoding="utf-8")
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
