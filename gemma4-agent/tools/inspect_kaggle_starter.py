#!/usr/bin/env python3
"""Read public starter-notebook API metadata without running the notebook.

This diagnostic uses the Kaggle CLI configured by GitHub Actions. It only pulls
metadata and notebook source into a temporary directory; it does not launch a
Kaggle session or consume GPU quota.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

KERNEL_REF = "ryanholbrook/getting-started-gemma-4-developer-agent"
FIELDS = (
    "id",
    "title",
    "code_file",
    "language",
    "kernel_type",
    "is_private",
    "enable_gpu",
    "enable_tpu",
    "enable_internet",
    "machine_shape",
    "dataset_sources",
    "competition_sources",
    "kernel_sources",
    "model_sources",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    result: dict[str, object] = {
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kernel_ref": KERNEL_REF,
        "notebook_executed": False,
        "gpu_quota_used": False,
    }

    with tempfile.TemporaryDirectory(prefix="gemma-starter-metadata-") as temporary:
        command = [
            sys.executable,
            "-m",
            "kaggle",
            "kernels",
            "pull",
            KERNEL_REF,
            "--path",
            temporary,
            "--metadata",
        ]
        try:
            pulled = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["status"] = "pull_failed"
            result["error"] = f"Kaggle CLI process failed ({type(exc).__name__}); details omitted."
        else:
            metadata_path = Path(temporary) / "kernel-metadata.json"
            if pulled.returncode != 0:
                result["status"] = "pull_failed"
                result["error"] = (
                    f"Kaggle CLI pull failed with exit code {pulled.returncode}; "
                    "captured output omitted."
                )
            elif not metadata_path.is_file():
                result["status"] = "metadata_missing"
                result["error"] = "Kaggle CLI returned success but did not write kernel-metadata.json."
            else:
                try:
                    raw = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    result["status"] = "metadata_invalid"
                    result["error"] = f"Metadata could not be parsed ({type(exc).__name__})."
                else:
                    result["status"] = "ok"
                    result["metadata"] = {key: raw.get(key) for key in FIELDS if key in raw}

    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # Print only this redacted, allow-listed metadata summary to the Actions log.
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
