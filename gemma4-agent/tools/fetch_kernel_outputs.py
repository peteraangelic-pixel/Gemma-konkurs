#!/usr/bin/env python3
"""Wait for an already-pushed Kaggle kernel and fetch its outputs (read-only, no GPU work).

Why this exists: on 2026-10-14 the V6.5 and V6.6 benchmark workflows pushed their kernels
successfully (`push_exit_code: 0`) and then died at the status-polling step - "Five consecutive
Kaggle status API calls failed" - because the polling gave up after 5 transient API failures while
two workflows polled at the same time. The kernels themselves were never affected; the GPU work
kept running. This tool re-attaches to a kernel by reference, waits patiently, and only then
downloads.

Read-only with respect to Kaggle: `kernels status` and `kernels output` neither start nor stop a
kernel and never create a competition submission. Credentials come from the standard Kaggle CLI
file; the token is never read, printed or written by this script.

Exit code 0 when the outputs were fetched; 2 when the kernel reported a failure status; 3 when the
wait timed out. In every case a record is written to <outdir>/run.json so the state is auditable.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Kaggle prints e.g. 'petersharps/<kernel> has status "KernelWorkerStatus.RUNNING"'. The prefix
# matters: matching a bare "ERROR" anywhere in the output treated a CLI *error message* as a
# finished-with-failure kernel and aborted a 3-hour wait after one second (2026-10-14 bug).
STATE_RE = re.compile(r"KernelWorkerStatus\.(\w+)", re.IGNORECASE)
TERMINAL_OK = ("COMPLETE",)
TERMINAL_BAD = ("ERROR", "CANCELED", "CANCELLED", "FAILED")
MAX_TRANSIENT_FAILURES = 12  # the reason this tool exists: 5 was too few


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def kaggle(args: list[str], timeout: int = 180) -> tuple[int | None, str, str]:
    try:
        completed = subprocess.run([sys.executable, "-m", "kaggle", *args],
                                   capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None, "", "timeout"
    except OSError as exc:
        return None, "", type(exc).__name__
    return completed.returncode, completed.stdout, completed.stderr


LAST_RAW = {"text": ""}


def kernel_state(ref: str) -> str:
    """Return a normalised state, or API_FAIL when the call itself failed.

    Only text of the form KernelWorkerStatus.<STATE> counts as a state; anything else from a
    non-zero exit is an API failure to retry, and anything else from a zero exit is UNKNOWN
    (still retried, with the raw text kept for the audit trail).
    """
    code, stdout, stderr = kaggle(["kernels", "status", ref], timeout=90)
    text = f"{stdout}\n{stderr}".strip()
    LAST_RAW["text"] = text[:400]
    match = STATE_RE.search(text)
    if match:
        return match.group(1).upper()
    # 404 / "Permission 'kernels.get' was denied" means the reference does not resolve right now.
    # That is not API flakiness and must not consume the transient-failure budget: on 2026-10-14
    # five such answers were counted as "status API failures" and produced a misleading record.
    if "404" in text or "Not Found" in text or "kernels.get" in text:
        return "NOT_FOUND"
    return "UNKNOWN" if code == 0 else "API_FAIL"


def files_probe(ref: str) -> tuple[int, str]:
    """Ask the data endpoint, not the status endpoint, whether the kernel is reachable.

    The two endpoints disagree in practice: on 2026-10-14 `kernels status` answered 404 for a
    reference whose `kernels files` replied normally (empty, but with exit 0). Transfer endpoints
    are therefore the better liveness probe.
    """
    code, stdout, stderr = kaggle(["kernels", "files", ref], timeout=90)
    return code, f"{stdout}\n{stderr}".strip()


def read_record(outdir: Path) -> dict:
    path = outdir / "run.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def write_record(outdir: Path, record: dict) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "run.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kernel-ref", default="", help="defaults to run.json's kernel_ref in --outdir")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--workdir", type=Path, required=True, help="where kernel outputs are downloaded")
    ap.add_argument("--max-wait-minutes", type=int, default=210)
    ap.add_argument("--poll-interval-seconds", type=int, default=90)
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    record = read_record(args.outdir)
    ref = args.kernel_ref or str(record.get("kernel_ref") or "")
    if not ref:
        print("no kernel reference: pass --kernel-ref or keep kernel_ref in run.json", file=sys.stderr)
        return 2

    record.update({"kernel_ref": ref, "fetch_tool": "fetch_kernel_outputs.py",
                   "fetch_started_utc": utc_now(), "submission_created": False})
    deadline = time.monotonic() + args.max_wait_minutes * 60
    failures = 0
    not_found = 0
    last_state = "UNKNOWN"
    NOT_FOUND_LIMIT = 6  # six polls x the interval: patient enough for a push race, not for hours

    while time.monotonic() < deadline:
        state = kernel_state(ref)
        if state == "API_FAIL":
            failures += 1
            print(f"[{utc_now()}] status API failure {failures}/{MAX_TRANSIENT_FAILURES}")
            print(f"    raw: {LAST_RAW['text'][:200]!r}")
            if failures >= MAX_TRANSIENT_FAILURES:
                record.update({"status": "fetch_status_api_failed", "kaggle_status": last_state,
                               "detail": f"{failures} consecutive status API failures",
                               "last_raw_cli_output": LAST_RAW["text"]})
                write_record(args.outdir, record)
                return 3
            time.sleep(min(300, args.poll_interval_seconds * failures))  # back off
            continue
        failures = 0
        if state == "NOT_FOUND":
            not_found += 1
            code, files_text = files_probe(ref)
            print(f"[{utc_now()}] status 404 ({not_found}/{NOT_FOUND_LIMIT}); files probe exit={code} "
                  f"output={files_text[:120]!r}")
            if code == 0 and files_text:
                print("    the data endpoint answered: downloading without a status reading")
                last_state = "UNKNOWN_BUT_REACHABLE"
                break
            if not_found >= NOT_FOUND_LIMIT:
                record.update({"status": "kernel_never_appeared", "kaggle_status": "NOT_FOUND",
                               "detail": ("the reference never resolved: status answered 404 and the "
                                          "files endpoint returned nothing for it"),
                               "last_raw_cli_output": LAST_RAW["text"], "fetched_utc": utc_now()})
                write_record(args.outdir, record)
                print("kernel reference never appeared; nothing to fetch", file=sys.stderr)
                return 3
            time.sleep(max(30, args.poll_interval_seconds))
            continue
        if state != last_state:
            print(f"[{utc_now()}] kernel state: {state}")
            print(f"    raw: {LAST_RAW['text'][:200]!r}")
            last_state = state
        if state in TERMINAL_OK:
            break
        if state in TERMINAL_BAD:
            record.update({"status": "kernel_failed", "kaggle_status": state, "fetched_utc": utc_now(),
                           "last_raw_cli_output": LAST_RAW["text"]})
            write_record(args.outdir, record)
            print(f"kernel reported {state}; nothing to download", file=sys.stderr)
            return 2
        time.sleep(max(30, args.poll_interval_seconds))
    else:
        record.update({"status": "fetch_timeout", "kaggle_status": last_state,
                       "waited_minutes": args.max_wait_minutes, "fetched_utc": utc_now(),
                       "last_raw_cli_output": LAST_RAW["text"]})
        write_record(args.outdir, record)
        print(f"timed out after {args.max_wait_minutes} min in state {last_state}", file=sys.stderr)
        return 3

    # Download outputs (read-only transfer).
    target = args.workdir / ref.split("/")[-1]
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    code, stdout, stderr = kaggle(["kernels", "output", ref, "-p", str(target), "--force"], timeout=900)
    if code != 0:
        record.update({"status": "output_download_failed", "kaggle_status": last_state,
                       "detail": (stderr or stdout or "unknown error").strip()[:300],
                       "fetched_utc": utc_now()})
        write_record(args.outdir, record)
        print(f"`kaggle kernels output` failed: {(stderr or stdout).strip()[:200]}", file=sys.stderr)
        return 3

    downloaded = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    print(f"downloaded {len(downloaded)} files:")
    for name in downloaded[:40]:
        print(f"   {name}")

    result_files = [p for p in target.rglob("agent_benchmark_result.json")]
    if not result_files:
        record.update({"status": "result_file_missing", "kaggle_status": "COMPLETE",
                       "downloaded": downloaded[:40], "fetched_utc": utc_now()})
        write_record(args.outdir, record)
        print("no agent_benchmark_result.json in the kernel outputs", file=sys.stderr)
        return 3

    shutil.copy2(result_files[0], args.outdir / "agent_benchmark_result.json")
    result = json.loads(result_files[0].read_text(encoding="utf-8"))
    record.update({
        "status": "complete",
        "kaggle_status": "COMPLETE",
        "fetched_utc": utc_now(),
        "resolved_count": result.get("resolved_count"),
        "task_count_selected": result.get("task_count_selected"),
        "score_estimate": result.get("score_estimate"),
        "score_ci95_wilson": result.get("score_ci95_wilson"),
        "downloaded_file_count": len(downloaded),
    })
    write_record(args.outdir, record)
    print(f"fetched: resolved {result.get('resolved_count')}/{result.get('task_count_selected')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
