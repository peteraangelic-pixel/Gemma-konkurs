"""CLI: python -m arc3_local_candidate.audit_benchmark benchmark.json"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .scorecard import audit_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute ARC-AGI-3 scores from benchmark.json")
    parser.add_argument("benchmark", type=Path, help="Path to a local benchmark.json")
    parser.add_argument("--per-game", action="store_true", help="Print each game's score row")
    args = parser.parse_args()

    try:
        document = json.loads(args.benchmark.read_text(encoding="utf-8"))
    except OSError as exc:
        parser.error(str(exc))
    except json.JSONDecodeError as exc:
        parser.error(f"invalid JSON: {exc}")

    result = audit_benchmark(document)
    print(f"label:                  {result['label']}")
    print(f"games:                  {result['games']}")
    print(f"mean score (recomputed): {result['mean_score_recomputed']:.6f}")
    if result["mean_score_reported"] is not None:
        print(f"mean score (reported):   {result['mean_score_reported']:.6f}")
    print(f"score mismatches:        {result['score_mismatch_count']}")
    print(f"completed levels:        {result['completed_levels']}/{result['total_levels']}")
    print(f"wins:                    {result['wins']}")
    print(f"actions:                 {result['actions']}")
    print(f"generated tokens:        {result['generated_tokens']}")
    print(f"max game wallclock:      {result['wallclock_seconds_max']:.1f}s")

    if args.per_game:
        for game in result["per_game"]:
            print(
                f"{game['game_id']:<24} score={game['score']:.6f} "
                f"levels={game['levels_completed']}/{game['total_levels']} "
                f"actions={game['actions']} tokens={game['generated_tokens']} "
                f"state={game['state']}"
            )
    return 2 if result["score_mismatch_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
