#!/usr/bin/env python3
"""Guard against documentation drifting from the measured JSON artifacts.

This exists because of a real review finding: analysis.md quoted a CI95 of [11%, 30%] for
V6.2 while the result JSON carried the correct Wilson interval [16.7%, 47.9%]. Prose numbers
must never be hand-copied.

The check is deliberately narrow and strict:
  * every percent pair quoted next to "CI95" / "CI 95" / "przedział Wilsona" in any tracked
    markdown must match, within tolerance, the Wilson interval of one of the recorded
    screenings (recomputed here from the JSON, which is also cross-checked against the
    interval stored in the file);
  * the screening history table must list every candidate folder that has results.

Usage:
    python3 gemma4-agent/tools/check_docs_consistency.py
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "gemma4-agent" / "kaggle_results"
CANDIDATES = [("V3", "v3-benchmark"), ("V4", "v4-benchmark"), ("V5", "v5-benchmark"),
              ("V6.1", "v6-1-benchmark"), ("V6.2", "v6-benchmark"),
              ("V6.3-mini", "v6-3-miniscreen"), ("V6.3", "v6-3-benchmark")]
# prose rounds intervals to one decimal place (19.23 -> "19.2"), so allow half of the
# last digit plus epsilon; candidates differ by >= 1 pp, so this stays discriminating.
TOLERANCE = 0.06  # percentage points

# The connector between the label and the brackets may contain digits ("CI95 dla 9/30 to
# [16.7 %, 47.9 %]"), which an earlier version of this regex excluded - the exact blind spot
# that let a wrong interval ship.
PAIR_RE = re.compile(
    r"(?:CI\s?95|przedzia[łl]\w*\s+Wilsona)[^\[\]]{0,60}"
    r"\[\s*([0-9]+(?:[.,][0-9]+)?)\s*%\s*,\s*([0-9]+(?:[.,][0-9]+)?)\s*%",
    re.IGNORECASE,
)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 1.0
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def screening_intervals() -> dict[str, tuple[float, float]]:
    intervals: dict[str, tuple[float, float]] = {}
    for tag, folder in CANDIDATES:
        path = RESULTS / folder / "agent_benchmark_result.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        k, n = data["resolved_count"], len(data["tasks"])
        low, high = wilson(k, n)
        stored = data.get("score_ci95_wilson")
        if stored and (abs(stored[0] - low) > 0.002 or abs(stored[1] - high) > 0.002):
            raise SystemExit(f"{tag}: stored interval {stored} disagrees with recomputed "
                             f"[{low:.4f}, {high:.4f}]")
        intervals[tag] = (low, high)
    return intervals


def markdown_files() -> list[Path]:
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "*.md"], check=True, capture_output=True, text=True
    ).stdout.split()
    return [ROOT / name for name in listing]


def main() -> int:
    intervals = screening_intervals()
    if not intervals:
        raise SystemExit("No screening results found to validate against.")

    problems: list[str] = []
    checked = 0
    for path in markdown_files():
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for match in PAIR_RE.finditer(text):
            low = float(match.group(1).replace(",", "."))
            high = float(match.group(2).replace(",", "."))
            checked += 1
            matches = [tag for tag, (a, b) in intervals.items()
                       if abs(a * 100 - low) <= TOLERANCE and abs(b * 100 - high) <= TOLERANCE]
            if not matches:
                line = text[:match.start()].count("\n") + 1
                problems.append(
                    f"{path.relative_to(ROOT)}:{line} quotes [{low}%, {high}%] next to CI95, "
                    f"which matches no recorded screening. Valid intervals: "
                    + "; ".join(f"{tag} [{a * 100:.1f}%, {b * 100:.1f}%]"
                                for tag, (a, b) in sorted(intervals.items())))

    history = RESULTS / "screening_history.md"
    if history.is_file():
        text = history.read_text(encoding="utf-8")
        for tag, _ in CANDIDATES:
            if tag in intervals and f"| {tag} |" not in text:
                problems.append(f"screening_history.md is missing the row for {tag}")

    if problems:
        print("Documentation consistency check FAILED:")
        for problem in problems:
            print("  -", problem)
        return 1

    print(f"Documentation consistency check passed: {checked} quoted interval(s) verified "
          f"against {len(intervals)} recorded screening(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
