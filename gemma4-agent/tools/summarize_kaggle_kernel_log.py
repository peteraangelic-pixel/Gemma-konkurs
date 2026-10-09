#!/usr/bin/env python3
"""Print short, error-focused Kaggle notebook log annotations for GitHub Actions."""
from __future__ import annotations

import argparse
from pathlib import Path
import re


DIAGNOSTIC = re.compile(
    r"traceback|(?:[A-Za-z_][\w.]*(?:Error|Exception|Failure))\s*:|"
    r"cuda|out of memory|\boom\b|timed? ?out|timeout|killed|"
    r"module not found|importerror|worker.*error|kernelworkerstatus|"
    r"permission denied|exit code|segmentation fault",
    re.IGNORECASE,
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
        cleaned = "".join(ch if ch.isprintable() or ch == "\t" else " " for ch in line).strip()
        if cleaned and DIAGNOSTIC.search(cleaned):
            matches.append(cleaned[:350])

    if not matches:
        print(
            "::notice title=Kaggle kernel log::No traceback, exception, CUDA, timeout, "
            "or worker-error marker found in the retrieved log."
        )
        return 0

    for index, message in enumerate(matches[-12:], start=1):
        escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::notice title=Kaggle kernel diagnostic {index}::{escaped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
