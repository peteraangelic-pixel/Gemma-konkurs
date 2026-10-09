#!/usr/bin/env python3
"""Inspect the current Kaggle harness wheel versions without starting a kernel."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
import tempfile

WHEELHOUSE = "metric/gemma-4-developer-agent-wheelhouse"


def run_cli(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "kaggle", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def write_summary(path: Path, summary: dict[str, object]) -> None:
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if summary.get("status") == "inspected":
        print(
            "::notice title=Kaggle wheelhouse::"
            f"swegemma {summary.get('swegemma_version')}; "
            f"swegemma.models.discovery present={summary.get('models_discovery_module_present')}"
        )
        for wheel in summary.get("harness_wheels", []):
            print(f"::notice title=Harness wheel::{wheel}")
    else:
        print(f"::warning title=Kaggle wheelhouse inspection::{summary.get('status')}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, object] = {
        "inspected_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": WHEELHOUSE,
        "status": "failed",
    }
    try:
        listing = run_cli(["datasets", "files", WHEELHOUSE, "--page-size", "200", "--csv"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        summary["error_type"] = type(exc).__name__
        write_summary(args.output_dir / "wheelhouse-summary.json", summary)
        return 1

    if listing.returncode != 0:
        summary["list_exit_code"] = listing.returncode
        summary["raw_cli_output_saved"] = False
        write_summary(args.output_dir / "wheelhouse-summary.json", summary)
        return 1

    (args.output_dir / "wheelhouse-files.csv").write_text(listing.stdout, encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(listing.stdout)))
    names = [
        str(row.get("name") or row.get("fileName") or row.get("filename") or "").strip()
        for row in rows
    ]
    names = [name for name in names if name]
    package_prefixes = ("swegemma-", "adk_submission-", "adk_eval_core-", "google_adk-")
    relevant = sorted(name for name in names if name.lower().startswith(package_prefixes))
    summary.update({"status": "listed", "file_count": len(names), "harness_wheels": relevant})

    swegemma_wheels = [name for name in relevant if name.lower().startswith("swegemma-") and name.endswith(".whl")]
    if len(swegemma_wheels) != 1:
        summary["swegemma_inspection"] = "expected exactly one swegemma wheel in the file list"
        write_summary(args.output_dir / "wheelhouse-summary.json", summary)
        return 0

    download_dir = Path(tempfile.mkdtemp(prefix="kaggle-wheelhouse-inspect-"))
    wheel_name = swegemma_wheels[0]
    try:
        download = run_cli(
            [
                "datasets",
                "download",
                WHEELHOUSE,
                "--file",
                wheel_name,
                "--path",
                str(download_dir),
                "--unzip",
                "--force",
            ],
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        summary.update({"swegemma_wheel": wheel_name, "download_error_type": type(exc).__name__})
        write_summary(args.output_dir / "wheelhouse-summary.json", summary)
        return 1

    wheel_paths = list(download_dir.rglob("swegemma-*.whl"))
    if download.returncode != 0 or not wheel_paths:
        summary.update(
            {
                "swegemma_wheel": wheel_name,
                "download_exit_code": download.returncode,
                "downloaded_wheel_found": bool(wheel_paths),
            }
        )
        write_summary(args.output_dir / "wheelhouse-summary.json", summary)
        return 1

    wheel_path = wheel_paths[0]
    with zipfile.ZipFile(wheel_path) as wheel:
        members = wheel.namelist()
        metadata_paths = [name for name in members if name.endswith(".dist-info/METADATA")]
        metadata = wheel.read(metadata_paths[0]).decode("utf-8", errors="replace") if metadata_paths else ""
    package_version = next(
        (line.partition(":")[2].strip() for line in metadata.splitlines() if line.startswith("Version:")),
        "unknown",
    )
    discovery_paths = [
        name
        for name in members
        if name.endswith("swegemma/models/discovery.py")
        or name.endswith("swegemma/models/discovery/__init__.py")
    ]
    summary.update(
        {
            "status": "inspected",
            "swegemma_wheel": wheel_name,
            "swegemma_version": package_version,
            "models_discovery_module_present": bool(discovery_paths),
            "models_discovery_module_paths": discovery_paths,
        }
    )
    write_summary(args.output_dir / "wheelhouse-summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
