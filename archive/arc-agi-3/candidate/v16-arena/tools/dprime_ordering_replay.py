#!/usr/bin/env python3
"""Offline diagnostic: would D' have ranked the recorded games differently?

This does **not** re-run anything, does not produce a score, and cannot: the
recorded run made its own allocation decisions, and changing them changes the
outcome. What it answers is narrower and still useful before spending a slot:

    at every sampled moment of a recorded run, does the shipped priority and
    D' disagree about which game should get the next model slot?

If they never disagree, the switch is inert and the candidate is not worth a
submission. If they disagree, the direction of the disagreement says which
games D' favours (deeper? cheaper per cleared level?) — and that is what the
live meters then confirm or refute.

Input is any `benchmark.json` saved by the harness (public games only). The
reconstruction is deliberately conservative:

  * a game is only ranked once it has been served at least once;
  * level boundaries come from the recorded `actions_per_level` (one action per
    history entry in the runs used here; entries are counted, not assumed);
  * the measured pace is generated tokens on levels already cleared, exactly
    the quantity patch 0009 accumulates.

    python3 tools/dprime_ordering_replay.py path/to/benchmark.json [--step 60]

Reference scheduler: `src/priority_scheduler_v16.py`, a byte-for-byte copy of
the file the notebook's patch 0009 produces (verify_v16.py re-checks that).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def load_scheduler():
    path = PKG / "src" / "priority_scheduler_v16.py"
    spec = importlib.util.spec_from_file_location("priority_scheduler_v16", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["priority_scheduler_v16"] = module  # dataclasses need this
    spec.loader.exec_module(module)
    return module


def game_timeline(run: dict) -> list[dict]:
    """Per-turn snapshots: elapsed, level, actions on level, tokens on level."""
    per_level = [int(x or 0) for x in (run.get("actions_per_level") or [])]
    timeline: list[dict] = []
    level, actions_on_level, tokens_on_level = 1, 0, 0
    cleared_tokens, cleared_levels = 0.0, 0
    boundary = per_level[0] if per_level else 0
    level_tokens_start = 0.0
    total_tokens = 0.0
    for turn in run.get("history") or []:
        tokens = float(turn.get("generated_tokens") or 0)
        total_tokens += tokens
        elapsed = float(turn.get("wallclock_seconds") or 0.0)
        actions_on_level += 1
        tokens_on_level += tokens
        if boundary and actions_on_level >= boundary and level <= len(per_level):
            # the recorded level boundary: bank this level's tokens as pace
            cleared_tokens += total_tokens - level_tokens_start
            cleared_levels += 1
            level_tokens_start = total_tokens
            level += 1
            actions_on_level, tokens_on_level = 0, 0
            boundary = per_level[level - 1] if level <= len(per_level) else 0
        timeline.append({
            "elapsed": elapsed,
            "level": min(level, max(1, int(run.get("number_of_levels") or level))),
            "actions": actions_on_level,
            "tokens": tokens_on_level,
            "pace": cleared_tokens / cleared_levels if cleared_levels else 0.0,
        })
    return timeline


def snapshot_at(timeline: list[dict], t: float) -> dict | None:
    seen = None
    for row in timeline:
        if row["elapsed"] <= t:
            seen = row
        else:
            break
    return seen


def rank(module, states, *, dprime: bool, tail_fraction: float):
    scored = []
    for game_id, state in states:
        snap = module.PrioritySnapshot(
            level=state["level"], actions=state["actions"], tokens=state["tokens"],
            total_levels=state["total_levels"],
            mean_tokens_per_cleared_level=state["pace"],
        )
        if dprime:
            value = module.dprime_priority(snap, tail_fraction=tail_fraction)
        else:
            value = module.priority_value(
                snap, normalize_score=True, tail_lookup="remaining",
                tail_fraction=tail_fraction,
            )
        scored.append((game_id, value))
    scored.sort(key=lambda item: -item[1])
    return [game_id for game_id, _ in scored], dict(scored)


def spearman(a: list[float], b: list[float]) -> float | None:
    """Rank correlation without scipy; None when a ranking is degenerate."""
    n = len(a)
    if n < 3:
        return None
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            average = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = average
            i = j + 1
        return out
    ra, rb = ranks(a), ranks(b)
    if len(set(ra)) < 2 or len(set(rb)) < 2:
        return None
    mean_a, mean_b = sum(ra) / n, sum(rb) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(ra, rb))
    var_a = sum((x - mean_a) ** 2 for x in ra) ** 0.5
    var_b = sum((y - mean_b) ** 2 for y in rb) ** 0.5
    return cov / (var_a * var_b) if var_a and var_b else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("benchmark")
    ap.add_argument("--step", type=float, default=300.0,
                    help="sampling step in seconds of run time (default 300)")
    ap.add_argument("--top", type=int, default=3,
                    help="size of the slot set compared at each sample (default 3)")
    ap.add_argument("--json", default="", help="write the full report here")
    args = ap.parse_args()

    module = load_scheduler()
    data = json.loads(Path(args.benchmark).read_text())
    runs = data.get("game_runs") or []
    if not runs:
        print("no game_runs in this benchmark file", file=sys.stderr)
        return 2

    timelines = {}
    totals = {}
    for run in runs:
        gid = str(run.get("game_id") or "?")
        timelines[gid] = game_timeline(run)
        totals[gid] = int(run.get("number_of_levels") or 10)

    horizon = max((tl[-1]["elapsed"] for tl in timelines.values() if tl), default=0.0)
    samples = []
    t = args.step
    while t <= horizon:
        states = []
        for gid, timeline in timelines.items():
            seen = snapshot_at(timeline, t)
            if seen is None:
                continue  # not served yet: no basis for ranking
            states.append((gid, {**seen, "total_levels": totals[gid]}))
        if len(states) >= 2:
            before, before_scores = rank(module, states, dprime=False, tail_fraction=1.0)
            after, after_scores = rank(module, states, dprime=True, tail_fraction=1.0)
            top_before, top_after = before[:args.top], after[:args.top]
            samples.append({
                "t_s": round(t, 1),
                "games": len(states),
                "same_top": top_before == top_after,
                "same_order": before == after,
                "top_before": top_before,
                "top_after": top_after,
                "moved_into_top": [g for g in top_after if g not in top_before],
                "moved_out_of_top": [g for g in top_before if g not in top_after],
                "scores_before": before_scores,
                "scores_after": after_scores,
            })
        t += args.step

    if not samples:
        print("not enough served games over time to compare rankings", file=sys.stderr)
        return 2

    # Diagnostic only: does the priority at time t line up with the score the
    # run actually ended with? The games' outcomes were produced under the old
    # allocation, so this is a directional sanity check, not a forecast.
    final = {str(r.get("game_id") or "?"): float(r.get("final_score") or 0.0) for r in runs}
    rho_legacy, rho_dprime = [], []
    for sample in samples:
        ids = list(sample["scores_before"])
        realized = [final.get(gid, 0.0) for gid in ids]
        legacy = spearman([sample["scores_before"][g] for g in ids], realized)
        dprime = spearman([sample["scores_after"][g] for g in ids], realized)
        if legacy is not None:
            rho_legacy.append(legacy)
        if dprime is not None:
            rho_dprime.append(dprime)

    same_top = sum(1 for s in samples if s["same_top"])
    same_order = sum(1 for s in samples if s["same_order"])
    swaps = {}
    for sample in samples:
        for gid in sample["moved_into_top"]:
            swaps[gid] = swaps.get(gid, 0) + 1
    print(f"benchmark: {Path(args.benchmark).name}  games={len(runs)}  "
          f"horizon={horizon / 60:.0f} min  samples={len(samples)} step={args.step / 60:.0f} min")
    print(f"identical top-{args.top} set: {same_top}/{len(samples)} "
          f"({100 * same_top / len(samples):.0f}%)")
    print(f"identical full order:  {same_order}/{len(samples)} "
          f"({100 * same_order / len(samples):.0f}%)")
    if swaps:
        print("games D' pulls into the top set (samples, not points): "
              + ", ".join(f"{gid}×{n}" for gid, n in sorted(swaps.items(), key=lambda kv: -kv[1])))
    else:
        print("D' never changed the top set: on this recording the switch is inert")
    if rho_legacy and rho_dprime:
        print(f"rank corr. with the run's realised final score: "
              f"legacy {sum(rho_legacy) / len(rho_legacy):+.2f} (n={len(rho_legacy)})  "
              f"D' {sum(rho_dprime) / len(rho_dprime):+.2f} (n={len(rho_dprime)})")
    print("NOTE: ranking disagreement is not a score. It says the variable is live, "
          "not that the live run would score higher.")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "benchmark": str(args.benchmark),
            "samples": len(samples),
            "step_s": args.step,
            "top": args.top,
            "identical_top": same_top,
            "identical_order": same_order,
            "swaps_into_top": swaps,
            "mean_rank_corr_legacy": round(sum(rho_legacy) / len(rho_legacy), 3) if rho_legacy else None,
            "mean_rank_corr_dprime": round(sum(rho_dprime) / len(rho_dprime), 3) if rho_dprime else None,
            "detail": samples,
        }, indent=1))
        print(f"report: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
