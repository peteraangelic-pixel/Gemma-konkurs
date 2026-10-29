#!/usr/bin/env python3
"""Diagnose a saved run, and compute what a target score actually requires.

Reads the harness's own `benchmark.json` (the format taaf writes) and answers the three
questions that decide the next submission:

1. **Where did the points go?** Per game: levels cleared, actions per level, tokens and
   wall clock, and the exact taaf score with the level-by-level contributions.
2. **What is the next level worth?** Marginal points per game = weight of the next level /
   sum of all weights, discounted by the efficiency the run actually shows. This ranks the
   games, and it is usually not the "hardest" games at the top but the *incomplete long*
   ones, because level k is worth k units.
3. **What does target T require?** Greedy on the marginal table: the cheapest set of extra
   levels that lifts the mean to T. That is the token allocation for the next run.

Usage:
    python3 analyze_run.py benchmark.json [--target 50] [--all bench1.json bench2.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lab.engine import level_score, level_value_table  # noqa: E402


def load(path):
    d = json.loads(Path(path).read_text())
    runs = d.get("game_runs") or d
    out = []
    for g in runs:
        hist = g.get("history") or []
        base = g.get("base_actions_per_level") or []
        apl = g.get("actions_per_level") or []
        lv = g.get("levels_completed") or 0
        out.append({
            "game": g["game_id"],
            "levels": lv,
            "n": len(base),
            "base": base,
            "apl": apl,
            "score": g.get("final_score"),
            "tokens": g.get("final_generated_tokens") or sum(h.get("generated_tokens", 0) for h in hist),
            "wall_min": (g.get("final_wallclock_seconds") or (hist[-1]["wallclock_seconds"] if hist else 0)) / 60,
            "actions": len(hist),
            "state": g.get("state"),
        })
    return out


def per_game(rows):
    for r in rows:
        tbl = level_value_table(r["base"], actions=r["apl"])
        r["table"] = tbl
        r["next_points"] = (tbl[r["levels"]]["points"] if r["levels"] < r["n"] else 0.0)
        # efficiency actually observed on cleared levels, vs baseline
        eff = [r["base"][i] / r["apl"][i] for i in range(min(r["levels"], len(r["apl"]))) if r["apl"][i]]
        r["eff_median"] = sorted(eff)[len(eff) // 2] if eff else None
        r["tok_per_action"] = r["tokens"] / r["actions"] if r["actions"] else 0
    return rows


def report(rows, target):
    rows = sorted(rows, key=lambda r: r["score"] or 0)
    print(f"{'game':16}{'lvl':>6}{'score':>8}{'next':>7}{'eff':>7}{'tok/act':>8}{'wall m':>8}  state")
    for r in rows:
        eff = f"{r['eff_median']:.2f}" if r["eff_median"] else "  -"
        print(f"{r['game']:16}{str(r['levels'])+'/'+str(r['n']):>6}{(r['score'] or 0):8.2f}"
              f"{r['next_points']:7.2f}{eff:>7}{r['tok_per_action']:8.0f}{r['wall_min']:8.1f}  {r['state']}")
    mean = sum((r["score"] or 0) for r in rows) / len(rows)
    print(f"\nmean over {len(rows)} games: {mean:.2f}   (this mean is the leaderboard statistic)")

    # ---- what the target costs, greedily on marginal points
    # work on copies: the greedy mutates depth, and every later section must see the run
    plan = [{"game": r["game"], "levels": r["levels"], "n": r["n"],
             "next_points": r["next_points"], "table": r["table"]} for r in rows]
    gain = [r["next_points"] for r in plan]
    order = sorted(range(len(plan)), key=lambda i: -gain[i])
    need = target - mean
    print(f"\nto reach {target:.0f}: need +{need:.2f} mean points")
    if need <= 0:
        print("  already there on this sample")
        return
    bought, projected = 0, mean
    print(f"  {'game':16}{'+lvl':>6}{'worth':>8}{'running mean':>14}  new depth")
    while projected < target and order:
        i = order.pop(0)
        r = plan[i]
        if r["levels"] >= r["n"]:
            continue
        add = r["next_points"]
        projected += add / len(rows)
        r["levels"] += 1
        bought += 1
        print(f"  {r['game']:16}{r['levels']:6}{add:8.2f}{projected:14.2f}  {r['levels']}/{r['n']}")
        if r["levels"] < r["n"]:
            r["next_points"] = r["table"][r["levels"]]["points"]
            order.append(i)
            order.sort(key=lambda j: -plan[j]["next_points"])
    print(f"  => {bought} extra levels")


def decompose(rows):
    """Split each game's missing points into "throttle" (efficiency) and "reach" (depth).

    Three numbers per game, all from the same formula:
      actual          - what the run scored
      same_depth_best - same levels cleared, but at baseline action counts (throttle fixed)
      full_depth      - every level cleared at the run's own median efficiency (reach fixed)
    A game's gap to 100 is depth + throttle, in that order of size only if the agent
    actually reaches the levels; on our runs throttle is the cheaper half.
    """
    print("\nloss decomposition (gap to 100 per game, points):")
    print(f"  {'game':16}{'actual':>8}{'throttle-fixed':>16}{'depth-fixed':>13}"
          f"{'lost to throttle':>18}{'lost to depth':>15}")
    tot = {"actual": 0.0, "same": 0.0, "full": 0.0}
    for r in rows:
        k, base = r["levels"], r["base"]
        actual = r["score"] or 0.0
        same = _score([base[i] for i in range(k)], base, k) if k else 0.0
        eff = r["eff_median"] or 1.0
        full_acts = [max(1, int(round(b / eff))) for b in base] if eff else base
        full = _score(full_acts, base, len(base))
        tot["actual"] += actual / len(rows)
        tot["same"] += same / len(rows)
        tot["full"] += full / len(rows)
        print(f"  {r['game']:16}{actual:8.1f}{same:16.1f}{full:13.1f}"
              f"{same-actual:18.1f}{100-same:15.1f}")
    print(f"  {'MEAN':16}{tot['actual']:8.2f}{tot['same']:16.2f}{tot['full']:13.2f}"
          f"{tot['same']-tot['actual']:18.2f}{100-tot['same']:15.2f}")
    return tot


def project_budget(rows, budgets=(200, 300, 400, 600, 800, 1200, 2000)):
    """Mean score as a function of how many *actions* one game is allowed.

    Model, fitted only on what the run itself showed:
      * a level costs `baseline_actions / eff` actions, where `eff` is the run's own median
        efficiency (baseline/actions) on the levels it did clear - i.e. we do not assume the
        agent becomes more efficient, only that it keeps going;
      * levels are attempted in order, and the budget is spent until it runs out.
    That is deliberately conservative: no new cleverness, only more time. If the curve
    plateaus below 50, the extra actions are not the lever and the agent has to change.

    It is also the honest way to read the saved runs: r085 used ~198 actions per game and
    scored 26.78; the competition gives ~2.2 h per game, which at the observed ~14 s per
    action is ~600 actions - three times what the dev run spent.
    """
    print("\naction-budget projection (same agent, same efficiency, only more actions):")
    print(f"  {'budget':>7}{'mean score':>12}{'levels':>8}  per-game depths")
    out = {}
    for budget in budgets:
        tot, lv_sum, depths = 0.0, 0, []
        for r in rows:
            eff = r["eff_median"] or 1.0
            base = r["base"]
            spent, k = 0, 0
            for i, b in enumerate(base):
                cost = max(1, int(round(b / eff)))
                if spent + cost > budget:
                    break
                spent += cost
                k += 1
            acts = [max(1, int(round(base[i] / eff))) for i in range(k)]
            tot += _score(acts, base, k)
            lv_sum += k
            depths.append(k)
        mean = tot / len(rows)
        out[budget] = mean
        if budget in (200, 400, 600):
            print(f"  {budget:7}{mean:12.2f}{lv_sum:8}  {depths}")
    for budget, mean in out.items():
        if budget not in (200, 400, 600):
            print(f"  {budget:7}{mean:12.2f}")
    return out


def efficiency_sensitivity(rows):
    """How much of the score is throttle, not reach? Recompute at 1x/1.5x/2x/3x baseline."""
    print("\nefficiency sensitivity (same levels cleared, actions = ratio x baseline):")
    print(f"  {'ratio':>6}{'mean score':>12}{'vs actual':>11}")
    actual = sum((r["score"] or 0) for r in rows) / len(rows)
    for ratio in (0.5, 1.0, 1.5, 2.0, 3.0):
        tot = 0.0
        for r in rows:
            k = r["levels"]
            if k == 0:
                continue
            acts = [max(1, int(round(r["base"][i] * ratio))) for i in range(k)]
            tot += _score(acts, r["base"], k)
        print(f"  {ratio:6.1f}{tot/len(rows):12.2f}{tot/len(rows)-actual:+11.2f}")


def _score(apl, base, k):
    from lab.engine import game_score  # noqa: PLC0415

    return game_score(apl, base, levels_completed=k)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("bench", nargs="+")
    ap.add_argument("--target", type=float, default=50.0)
    a = ap.parse_args(argv)
    for path in a.bench:
        print(f"\n=== {path}")
        rows = per_game(load(path))
        report(rows, a.target)
        decompose(rows)
        efficiency_sensitivity(rows)
        project_budget(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
