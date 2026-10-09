#!/usr/bin/env python3
"""Run a bounded set of explicit pytest file or node-id targets."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


def repository_root() -> Path:
    configured = os.environ.get("WORKSPACE", "/workspace")
    candidate = Path(configured)
    if candidate.is_dir() and (candidate / ".git").exists():
        return candidate.resolve()

    current = Path.cwd().resolve()
    for parent in (current, *current.parents):
        if (parent / ".git").exists():
            return parent

    raise RuntimeError("Could not find the task repository Git root or /workspace.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run explicit pytest file/node-id targets only; this helper refuses "
            "the repository root and directories to avoid accidental full-suite runs."
        )
    )
    parser.add_argument(
        "targets",
        nargs="+",
        help="pytest file paths or node IDs, relative to the task repository root",
    )
    args = parser.parse_args()

    if len(args.targets) > 12:
        parser.error("Pass at most 12 focused targets; narrow the selection first.")

    try:
        root = repository_root()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for target in args.targets:
        if not target or target.startswith("-"):
            parser.error(f"Not a pytest path/node ID: {target!r}")
        file_part = target.split("::", 1)[0]
        relative = Path(file_part)
        if relative.is_absolute() or ".." in relative.parts:
            parser.error(f"Target must stay inside the repository: {target!r}")
        resolved = (root / relative).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            parser.error(f"Target escapes the repository: {target!r}")
        if not resolved.is_file():
            parser.error(
                f"Target must name an existing test file (not a directory): {target!r}"
            )

    timeout_seconds = 180
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        *args.targets,
    ]
    print(f"Repository: {root}")
    print(f"Running {len(args.targets)} focused pytest target(s), timeout={timeout_seconds}s")
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run(
            command,
            cwd=root,
            check=False,
            timeout=timeout_seconds,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        print(
            f"ERROR: pytest exceeded the {timeout_seconds}s skill timeout.",
            file=sys.stderr,
        )
        return 124
    except OSError as exc:
        print(f"ERROR: could not start pytest: {exc}", file=sys.stderr)
        return 127

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
