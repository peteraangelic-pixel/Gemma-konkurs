#!/usr/bin/env python3
"""Check a task repo's pending Git patch without staging file contents."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def find_git_root() -> Path | None:
    configured = Path(os.environ.get("WORKSPACE", "/workspace"))
    starts = [configured] if configured.is_dir() else []
    starts.append(Path.cwd())
    for start in starts:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    return None


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    root = find_git_root()
    if root is None:
        print("ERROR: this skill must run inside the task's Git repository.", file=sys.stderr)
        return 2

    # Match submit_patch's treatment of new files without staging their contents.
    intent = run_git(root, "add", "-N", "--", ".")
    if intent.returncode != 0:
        print(intent.stderr.strip() or "ERROR: git add -N failed.", file=sys.stderr)
        return intent.returncode

    diff = run_git(root, "diff", "--quiet", "HEAD", "--")
    if diff.returncode == 0:
        print("ERROR: no patch changes found relative to HEAD.", file=sys.stderr)
        return 1
    if diff.returncode != 1:
        print(diff.stderr.strip() or "ERROR: could not inspect the Git diff.", file=sys.stderr)
        return diff.returncode

    check = run_git(root, "diff", "--check", "HEAD", "--")
    if check.returncode != 0:
        print("ERROR: git diff --check found patch issues:", file=sys.stderr)
        print(check.stdout, end="", file=sys.stderr)
        print(check.stderr, end="", file=sys.stderr)
        return check.returncode

    names = run_git(root, "diff", "--name-only", "HEAD", "--")
    if names.returncode != 0:
        print(names.stderr.strip() or "ERROR: could not list changed files.", file=sys.stderr)
        return names.returncode
    changed = [line for line in names.stdout.splitlines() if line]
    generated_markers = {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "build",
        "dist",
    }
    generated = [
        path
        for path in changed
        if any(part in generated_markers for part in Path(path).parts)
        or path.endswith((".pyc", ".pyo", ".coverage"))
    ]
    if generated:
        print("ERROR: generated test/build artifacts are present in the patch:", file=sys.stderr)
        for path in generated:
            print(f"  - {path}", file=sys.stderr)
        print("Remove only artifacts created by this run, then validate again.", file=sys.stderr)
        return 1

    stat = run_git(root, "diff", "--stat", "HEAD", "--")
    print(f"Repository: {root}")
    print("Patch: non-empty")
    print("Whitespace check: clean")
    print("Changed files:")
    for path in changed:
        print(f"  - {path}")
    if stat.stdout.strip():
        print("Diff stat:")
        print(stat.stdout.rstrip())
    print("Review this list, then submit only after the targeted tests have run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
