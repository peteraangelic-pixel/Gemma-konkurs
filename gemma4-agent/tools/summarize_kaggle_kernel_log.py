#!/usr/bin/env python3
"""Print short, error-focused Kaggle notebook log annotations for GitHub Actions."""
from __future__ import annotations

import argparse
from pathlib import Path


MARKERS = (
    "traceback",
    "error:",
    "exception:",
    "failure:",
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    args = parser.parse_args()

    if not args.log.is_file():
        print(
            "::warning title=Kaggle kernel log::Log file was not retrieved; "
            "see the fetch step for status."
        )
        return 0

    matches: list[str] = []
    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        cleaned = " ".join(line.split())[:350]
        lowered = cleaned.casefold()
        if cleaned and any(marker in lowered for marker in MARKERS):
            matches.append(cleaned)

    if not matches:
        print(
            "::notice title=Kaggle kernel log::No traceback, exception, CUDA, timeout, "
            "or worker-error marker found in the retrieved log."
        )
        return 0

    for index, message in enumerate(matches[-24:], start=1):
        escaped = message.replace("%", "%25").replace(chr(13), "%0D").replace(chr(10), "%0A")
        print(f"::notice title=Kaggle kernel diagnostic {index}::{escaped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
