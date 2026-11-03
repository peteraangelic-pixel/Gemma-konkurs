#!/usr/bin/env python3
"""Action-efficiency meter for recorded ARC-AGI-3 runs (offline, dependency-free).

The competition metric is RHAE: `level_score = min(1.15, (human/ai)**2)` with
the 1-indexed level number as weight, unsolved levels scoring zero, and the game
score capped by how much of the weight was actually completed. Everything in it
is a function of **actions per completed level**, so that is the number a patch
has to move. This tool reads what the harness already saves and reports it.

Two modes:

    # describe a run
    python -m arc3_local_candidate.tools.action_efficiency run benchmark.json

    # decide whether a change is worth a submission slot
    python -m arc3_local_candidate.tools.action_efficiency compare before.json after.json

`compare` exits 1 when the change should **not** be shipped: the score must go
up and completion must not fall. The median actions per completed level is
reported next to it because it is the mechanism-level signal — a score that
moves while the median does not is noise or luck, not efficiency.

No network, no Kaggle, no model. Reads only files the harness wrote.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from arc3_local_candidate.scorecard import LEVEL_SCORE_CAP, game_score  # noqa: E402


# --------------------------------------------------------------------------- io
def _int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default


def _floats(values: object) -> list[float]:
    if not isinstance(values, (list, tuple)):
        try:
            return [float(x) for x in list(values)]  # type: ignore[arg-type]
        except TypeError:
            return []
    out: list[float] = []
    for value in values:
        try:
            out.append(max(0.0, float(value)))  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError):
            out.append(0.0)
    return out


def load_runs(path: str | Path) -> list[Mapping[str, Any]]:
    document = json.loads(Path(path).read_text())
    runs = document.get("game_runs") if isinstance(document, Mapping) else None
    if runs is None and isinstance(document, list):
        runs = document
    if not isinstance(runs, list):
        raise ValueError(f"{path}: no 'game_runs' list")
    return [run for run in runs if isinstance(run, Mapping)]


# ------------------------------------------------------------------- per game
def game_report(run: Mapping[str, Any]) -> dict[str, Any]:
    """Per-level action accounting for one game, plus the RHAE score."""
    bases = _floats(run.get("base_actions_per_level") or [])
    actions = _floats(run.get("actions_per_level") or [])
    total_levels = _int(run.get("number_of_levels"), len(bases) or len(actions))
    completed = min(max(0, _int(run.get("levels_completed"))), total_levels)
    has_baseline = any(base > 0 for base in bases)

    levels: list[dict[str, Any]] = []
    for index in range(completed):
        spent = actions[index] if index < len(actions) else 0.0
        baseline = bases[index] if index < len(bases) else 0.0
        record = {
            "level": index + 1,
            "actions": spent,
            "human_baseline": baseline if baseline > 0 else None,
        }
        if baseline > 0 and spent > 0:
            record["ratio_human_to_ai"] = round(baseline / spent, 3)
            record["level_score"] = round(
                min(LEVEL_SCORE_CAP, (baseline / spent) ** 2 * 100.0), 2
            )
        elif baseline > 0:
            record["ratio_human_to_ai"] = None
            record["level_score"] = LEVEL_SCORE_CAP  # zero actions: capped ceiling
        else:
            record["ratio_human_to_ai"] = None
            record["level_score"] = None  # baseline hidden in submission mode
        levels.append(record)

    score = (
        game_score(bases, actions, levels_completed=completed)
        if has_baseline and completed
        else None
    )
    recorded = run.get("final_score")
    spent_actions = [level["actions"] for level in levels if level["actions"] > 0]
    return {
        "game_id": str(run.get("game_id") or "?"),
        "levels_completed": completed,
        "number_of_levels": total_levels,
        "actions_total": int(round(sum(actions) if actions else sum(spent_actions))),
        "actions_per_completed_level_median": (
            round(median(spent_actions), 1) if spent_actions else None
        ),
        "actions_per_completed_level_mean": (
            round(mean(spent_actions), 1) if spent_actions else None
        ),
        "has_human_baseline": has_baseline,
        "score_recomputed": None if score is None else round(score, 3),
        "score_recorded": None if recorded is None else round(float(recorded), 3),
        "score_recomputed_from_baseline": bool(has_baseline and completed),
        "levels": levels,
    }


def summarise(reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Pooled numbers over games. Medians pool every completed level."""
    pooled = [
        level["actions"]
        for report in reports
        for level in report["levels"]
        if level["actions"] > 0
    ]
    scores = [r["score_recomputed"] for r in reports if r["score_recomputed"] is not None]
    recorded = [r["score_recorded"] for r in reports if r["score_recorded"] is not None]
    ratios = [
        level["ratio_human_to_ai"]
        for report in reports
        for level in report["levels"]
        if level.get("ratio_human_to_ai")
    ]
    return {
        "games": len(reports),
        "completed_levels": sum(r["levels_completed"] for r in reports),
        "total_levels": sum(r["number_of_levels"] for r in reports),
        "actions_total": sum(r["actions_total"] for r in reports),
        "actions_per_completed_level_median": round(median(pooled), 1) if pooled else None,
        "actions_per_completed_level_mean": round(mean(pooled), 1) if pooled else None,
        "human_over_ai_ratio_median": round(median(ratios), 3) if ratios else None,
        "score_mean_recomputed": round(mean(scores), 2) if scores else None,
        "score_mean_recorded": round(mean(recorded), 2) if recorded else None,
        "games_with_baseline": sum(1 for r in reports if r["has_human_baseline"]),
    }


def run_report(path: str | Path) -> dict[str, Any]:
    reports = [game_report(run) for run in load_runs(path)]
    return {"source": str(path), "games": reports, "summary": summarise(reports)}


# ---------------------------------------------------------------- comparison
def compare(before_path: str | Path, after_path: str | Path) -> dict[str, Any]:
    """Does the change improve the metric without losing completion?"""
    before = run_report(before_path)
    after = run_report(after_path)
    b, a = before["summary"], after["summary"]

    def delta(key: str) -> float | None:
        if b.get(key) is None or a.get(key) is None:
            return None
        return round(a[key] - b[key], 3)

    score_delta = delta("score_mean_recomputed")
    level_delta = delta("completed_levels")
    median_delta = delta("actions_per_completed_level_median")

    reasons: list[str] = []
    if score_delta is None:
        reasons.append("score not comparable (a run lacks a human baseline)")
    elif score_delta <= 0:
        reasons.append(f"score did not improve ({score_delta:+.2f})")
    if level_delta is not None and level_delta < 0:
        reasons.append(f"fewer levels completed ({level_delta:+d})")
    if median_delta is not None and median_delta > 0:
        reasons.append(
            f"median actions per completed level went up ({median_delta:+.1f}): "
            "the mechanism moved the wrong way"
        )
    ship = not reasons

    return {
        "before": {"source": before["source"], **b},
        "after": {"source": after["source"], **a},
        "score_delta": score_delta,
        "completed_levels_delta": level_delta,
        "median_actions_delta": median_delta,
        "ship": ship,
        "verdict": "SHIP" if ship else "DO NOT SHIP",
        "reasons": reasons,
    }


# ---------------------------------------------------------------- rendering
def render_run(report: dict[str, Any]) -> str:
    lines = [f"source: {report['source']}"]
    lines.append(
        f"{'game':16s} {'done':>6s} {'acts':>6s} {'med/level':>9s} {'ratio':>6s} {'score':>7s}"
    )
    for game in report["games"]:
        per_level = game["actions_per_completed_level_median"]
        ratios = [lvl["ratio_human_to_ai"] for lvl in game["levels"]
                  if lvl.get("ratio_human_to_ai")]
        score = game["score_recomputed"]
        lines.append(
            f"{game['game_id']:16s} "
            f"{game['levels_completed']:>3d}/{game['number_of_levels']:<2d} "
            f"{game['actions_total']:>6d} "
            f"{('-' if per_level is None else format(per_level, '.0f')):>9s} "
            f"{('-' if not ratios else format(median(ratios), '.2f')):>6s} "
            f"{('-' if score is None else format(score, '.2f')):>7s}"
        )
    s = report["summary"]
    lines.append(
        f"pooled: {s['completed_levels']}/{s['total_levels']} levels, "
        f"{s['actions_total']} actions, median {s['actions_per_completed_level_median']} "
        f"actions per completed level, mean score {s['score_mean_recomputed']}"
        f" (recorded {s['score_mean_recorded']})"
    )
    return "\n".join(lines)


def render_compare(result: dict[str, Any]) -> str:
    lines = [
        f"before: {result['before']['source']}  score {result['before']['score_mean_recomputed']}  "
        f"levels {result['before']['completed_levels']}  "
        f"median/level {result['before']['actions_per_completed_level_median']}",
        f"after:  {result['after']['source']}  score {result['after']['score_mean_recomputed']}  "
        f"levels {result['after']['completed_levels']}  "
        f"median/level {result['after']['actions_per_completed_level_median']}",
        f"delta:  score {result['score_delta']:+}  levels {result['completed_levels_delta']:+}  "
        f"median/level {result['median_actions_delta']:+}",
        f"verdict: {result['verdict']}",
    ]
    lines.extend(f"  - {reason}" for reason in result["reasons"])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", default="", help="write the full report here")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("run", help="describe one recorded benchmark")
    one.add_argument("benchmark")
    two = sub.add_parser("compare", help="before/after ship gate")
    two.add_argument("before")
    two.add_argument("after")
    args = parser.parse_args(argv)

    if args.command == "run":
        report = run_report(args.benchmark)
        print(render_run(report))
        payload = report
    else:
        payload = compare(args.before, args.after)
        print(render_compare(payload))

    if args.json:
        Path(args.json).write_text(json.dumps(payload, indent=1) + "\n")
        print(f"report: {args.json}")
    return 0 if payload.get("ship", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
