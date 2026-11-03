"""Dependency-free ARC-AGI-3 RHAE score recomputation and log auditing.

This implements the public scorecard description used by the ARC-AGI-3
competition and is intended to verify local benchmark artifacts. It does not
predict leaderboard performance or score hidden games.
"""
from __future__ import annotations

from math import isfinite
from statistics import mean
from typing import Any, Mapping, Sequence


LEVEL_SCORE_CAP = 115.0


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _as_nonnegative_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not isfinite(result):
        return default
    return max(0.0, result)


def level_score(
    human_baseline_actions: float,
    agent_actions: float,
    *,
    completed: bool,
) -> float:
    """Score one level: capped squared action-efficiency, or zero if incomplete."""
    if not completed:
        return 0.0
    baseline = _as_nonnegative_float(human_baseline_actions)
    if baseline <= 0.0:
        raise ValueError("human_baseline_actions must be positive for a completed level")
    actions = _as_nonnegative_float(agent_actions)
    if actions <= 0.0:
        # The mathematical ratio is unbounded; the official per-level cap applies.
        return LEVEL_SCORE_CAP
    return min(LEVEL_SCORE_CAP, (baseline / actions) ** 2 * 100.0)


def game_score(
    human_baseline_actions: Sequence[float],
    agent_actions_per_level: Sequence[float],
    *,
    levels_completed: int,
) -> float:
    """Compute the level-weighted RHAE score for a single game.

    Level i has weight i (1-based). The final score is capped by the weighted
    fraction of levels completed, as in the competition scorecard.
    """
    total_levels = len(human_baseline_actions)
    if total_levels == 0:
        return 0.0

    completed = min(total_levels, max(0, _as_int(levels_completed)))
    total_weight = total_levels * (total_levels + 1) / 2.0
    weighted_score = 0.0
    completed_weight = 0.0

    for index in range(total_levels):
        weight = float(index + 1)
        if index < completed:
            actions = agent_actions_per_level[index] if index < len(agent_actions_per_level) else 0.0
            weighted_score += weight * level_score(
                human_baseline_actions[index], actions, completed=True
            )
            completed_weight += weight

    weighted_score /= total_weight
    completion_cap = completed_weight / total_weight * 100.0
    return min(weighted_score, completion_cap)


def _sum_history_tokens(history: object) -> int:
    if not isinstance(history, list):
        return 0
    return sum(_as_int(item.get("generated_tokens", 0)) for item in history if isinstance(item, Mapping))


def audit_benchmark(document: Mapping[str, Any], *, tolerance: float = 1e-6) -> dict[str, Any]:
    """Recompute scores and return compact totals plus per-game diagnostics."""
    runs = document.get("game_runs", [])
    if not isinstance(runs, list):
        raise ValueError("benchmark['game_runs'] must be a list")

    per_game: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run, Mapping):
            continue
        bases = run.get("base_actions_per_level") or []
        if not isinstance(bases, list):
            bases = list(bases)
        total_levels = _as_int(run.get("number_of_levels"), len(bases))
        if total_levels <= 0:
            total_levels = len(bases)
        bases = (list(bases) + [0.0] * total_levels)[:total_levels]

        actions = run.get("actions_per_level") or []
        if not isinstance(actions, list):
            actions = list(actions)
        actions = list(actions)[:total_levels]
        completed = min(total_levels, max(0, _as_int(run.get("levels_completed"))))
        score = game_score(bases, actions, levels_completed=completed)
        recorded = run.get("final_score")
        recorded_score = None if recorded is None else _as_nonnegative_float(recorded)
        difference = None if recorded_score is None else score - recorded_score

        per_game.append(
            {
                "game_id": str(run.get("game_id", "?")),
                "score": score,
                "recorded_score": recorded_score,
                "score_difference": difference,
                "score_matches": difference is None or abs(difference) <= tolerance,
                "levels_completed": completed,
                "total_levels": total_levels,
                "actions": sum(_as_int(value) for value in actions),
                "generated_tokens": _sum_history_tokens(run.get("history")),
                "wallclock_seconds": _as_nonnegative_float(run.get("final_wallclock_seconds")),
                "state": str(run.get("state", "")),
            }
        )

    computed_scores = [entry["score"] for entry in per_game]
    recorded_scores = [entry["recorded_score"] for entry in per_game if entry["recorded_score"] is not None]
    mismatches = [entry["game_id"] for entry in per_game if not entry["score_matches"]]

    return {
        "label": str(document.get("label", "")),
        "games": len(per_game),
        "mean_score_recomputed": mean(computed_scores) if computed_scores else 0.0,
        "mean_score_reported": mean(recorded_scores) if recorded_scores else None,
        "score_mismatch_count": len(mismatches),
        "games_with_score_mismatch": mismatches,
        "completed_levels": sum(entry["levels_completed"] for entry in per_game),
        "total_levels": sum(entry["total_levels"] for entry in per_game),
        "wins": sum(entry["state"].lower() == "won" for entry in per_game),
        "actions": sum(entry["actions"] for entry in per_game),
        "generated_tokens": sum(entry["generated_tokens"] for entry in per_game),
        "wallclock_seconds_max": max((entry["wallclock_seconds"] for entry in per_game), default=0.0),
        "per_game": per_game,
    }
