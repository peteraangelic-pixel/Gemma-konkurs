#!/usr/bin/env python3
"""Where does a recorded ARC-AGI-3 run lose its points: completion or actions?

RHAE multiplies two terms that are usually discussed as if they were one:

    level_score   = min(1.15, (human_actions / ai_actions)**2)
    game_score    = min( score on completed levels , completion cap )
    completion cap = (completions' level weights) / (all level weights) * 100

So a game score is approximately `efficiency × completion`. Two runs can have
the same score for opposite reasons, and the fix is opposite too: one needs
fewer actions per level, the other needs to finish levels at all.

This tool splits the recorded runs into those two terms and answers, for one
benchmark file:

    actual                                    what the run scored
    if efficiency were exactly human          same levels completed, human
      (same completion)                       action count on each of them
    if every level were completed             same measured efficiency, no
      (observed efficiency)                   unsolved level

Both counterfactuals are **upper bounds**: the first ignores that harder levels
may resist matching a human, the second assumes later levels cost what earlier
ones did. They are there to show which headroom is bigger, not to predict a
score. Offline only; reads the harness's own benchmark.json.

    python -m arc3_local_candidate.tools.score_decomposition benchmark.json
    python -m arc3_local_candidate.tools.score_decomposition a.json b.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from arc3_local_candidate.scorecard import LEVEL_SCORE_CAP, game_score  # noqa: E402
from arc3_local_candidate.tools.action_efficiency import load_runs  # noqa: E402


def game_terms(run: Mapping[str, Any]) -> dict[str, Any]:
    """Efficiency on completed levels, completion share, and both ceilings."""
    bases = [float(x or 0) for x in (run.get("base_actions_per_level") or [])]
    actions = [float(x or 0) for x in (run.get("actions_per_level") or [])]
    total_levels = int(run.get("number_of_levels") or len(bases) or 0)
    completed = max(0, min(int(run.get("levels_completed") or 0), total_levels))
    if total_levels <= 0:
        return {"game_id": str(run.get("game_id") or "?"), "usable": False}

    total_weight = total_levels * (total_levels + 1) / 2.0
    done_weight = completed * (completed + 1) / 2.0

    weighted = 0.0
    usable_levels = 0
    for index in range(min(completed, len(bases), len(actions))):
        baseline, spent = bases[index], actions[index]
        if baseline <= 0:
            continue
        usable_levels += 1
        if spent <= 0:
            weighted += LEVEL_SCORE_CAP * (index + 1)
        else:
            weighted += min(LEVEL_SCORE_CAP, (baseline / spent) ** 2 * 100.0) * (index + 1)

    if not any(base > 0 for base in bases):
        return {"game_id": str(run.get("game_id") or "?"), "usable": False,
                "reason": "no human baseline in this run"}
    # A game that finished nothing still belongs in the mean: it scores zero and
    # is usually the whole story, so dropping it would flatter the run.

    efficiency = weighted / done_weight if done_weight else 0.0   # percent, 0..115
    completion = done_weight / total_weight * 100.0               # percent, 0..100
    actual = game_score(bases, actions, levels_completed=completed)
    return {
        "game_id": str(run.get("game_id") or "?"),
        "usable": True,
        "levels_completed": completed,
        "number_of_levels": total_levels,
        "efficiency_pct": round(efficiency, 2),
        "completion_pct": round(completion, 2),
        "actual": round(actual, 3),
        # human-level actions on exactly the levels it did finish
        "ceiling_human_efficiency_same_completion": round(
            min(100.0 * completion / 100.0, completion), 3
        ),
        # every level finished, costing what its finished levels cost
        "ceiling_full_completion_observed_efficiency": round(min(efficiency, 100.0), 3),
    }


def decompose(document_runs: Sequence[Mapping[str, Any]], *, source: str = "") -> dict[str, Any]:
    games = [terms for terms in (game_terms(run) for run in document_runs) if terms["usable"]]
    skipped = len(document_runs) - len(games)
    if not games:
        return {"source": source, "games": [], "skipped_no_baseline": skipped,
                "error": "no run carried a human baseline"}
    summary = {
        "games": len(games),
        "skipped_no_baseline": skipped,
        "actual": round(mean(g["actual"] for g in games), 2),
        "efficiency_pct_mean": round(mean(g["efficiency_pct"] for g in games), 2),
        "completion_pct_mean": round(mean(g["completion_pct"] for g in games), 2),
        "ceiling_human_efficiency_same_completion": round(
            mean(g["ceiling_human_efficiency_same_completion"] for g in games), 2
        ),
        "ceiling_full_completion_observed_efficiency": round(
            mean(g["ceiling_full_completion_observed_efficiency"] for g in games), 2
        ),
    }
    summary["headroom_from_efficiency"] = round(
        summary["ceiling_human_efficiency_same_completion"] - summary["actual"], 2
    )
    summary["headroom_from_completion"] = round(
        summary["ceiling_full_completion_observed_efficiency"] - summary["actual"], 2
    )
    summary["binding_constraint"] = (
        "completion"
        if summary["headroom_from_completion"] > summary["headroom_from_efficiency"]
        else "action efficiency"
    )
    return {"source": source, "games": games, "summary": summary}


def report(path: str | Path) -> dict[str, Any]:
    return decompose(load_runs(path), source=str(path))


def render(result: dict[str, Any]) -> str:
    summary = result.get("summary")
    if not summary:
        return f"{result['source']}: {result.get('error', 'no data')}"
    lines = [f"source: {result['source']}"]
    lines.append(
        f"{'game':16s} {'done':>6s} {'effic.':>7s} {'complet.':>8s} {'actual':>7s} "
        f"{'if human':>8s} {'if finished':>11s}"
    )
    for game in result["games"]:
        lines.append(
            f"{game['game_id']:16s} "
            f"{game['levels_completed']:>3d}/{game['number_of_levels']:<2d} "
            f"{game['efficiency_pct']:>6.1f}% {game['completion_pct']:>7.1f}% "
            f"{game['actual']:>7.2f} "
            f"{game['ceiling_human_efficiency_same_completion']:>8.2f} "
            f"{game['ceiling_full_completion_observed_efficiency']:>11.2f}"
        )
    lines.append(
        f"mean: actual {summary['actual']:.2f} | efficiency {summary['efficiency_pct_mean']:.1f}% "
        f"| completion {summary['completion_pct_mean']:.1f}%"
    )
    lines.append(
        f"ceiling if every action matched a human (same levels): "
        f"{summary['ceiling_human_efficiency_same_completion']:.2f} "
        f"(+{summary['headroom_from_efficiency']:.2f})"
    )
    lines.append(
        f"ceiling if every level were finished (same efficiency): "
        f"{summary['ceiling_full_completion_observed_efficiency']:.2f} "
        f"(+{summary['headroom_from_completion']:.2f})"
    )
    lines.append(f"binding constraint: {summary['binding_constraint']}")
    lines.append("both ceilings are upper bounds, not predictions")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmarks", nargs="+")
    parser.add_argument("--json", default="")
    args = parser.parse_args(argv)
    results = [report(path) for path in args.benchmarks]
    print("\n\n".join(render(result) for result in results))
    if args.json:
        payload = results[0] if len(results) == 1 else {"benchmarks": results}
        Path(args.json).write_text(json.dumps(payload, indent=1) + "\n")
        print(f"\nreport: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
