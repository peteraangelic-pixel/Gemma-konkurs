#!/usr/bin/env python3
"""Fetch logs for the latest private V1 smoke notebook without running it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    run = json.loads(args.run_json.read_text(encoding="utf-8"))
    kernel_ref = str(run.get("kernel_ref", "")).strip()
    if not kernel_ref or "/" not in kernel_ref:
        raise SystemExit("The recorded smoke run has no valid Kaggle kernel reference.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.output_dir / "kernel.log"
    command = [sys.executable, "-m", "kaggle", "kernels", "logs", kernel_ref]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        metadata = {
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kernel_ref": kernel_ref,
            "status": "fetch_failed",
            "error_type": type(exc).__name__,
            "raw_cli_output_saved": False,
        }
        (args.output_dir / "retrieval.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(metadata, indent=2))
        return 1

    # Keep the Kaggle log as a workflow artifact only; do not commit model output
    # or task traces into the repository.
    log_path.write_text(result.stdout, encoding="utf-8")
    metadata = {
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kernel_ref": kernel_ref,
        "status": "ok" if result.returncode == 0 else "fetch_failed",
        "cli_exit_code": result.returncode,
        "log_bytes": log_path.stat().st_size,
        "log_lines": len(result.stdout.splitlines()),
        "raw_stderr_saved": False,
    }
    (args.output_dir / "retrieval.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
