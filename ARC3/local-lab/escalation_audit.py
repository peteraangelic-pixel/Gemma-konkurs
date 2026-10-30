#!/usr/bin/env python3
"""How often would the v13.x escalation directive fire, and on which levels?

`ESCALATE_ACTIONS` (v13.1: 60, v13.2: 10) controls one prompt line that tells the model to
stop probing and build an explicit model (`model_state`/`model_step` → `check_model()` →
`plan()` → `commit()`). It costs ~146 tokens per injection, but each injection *invites* a
multi-thousand-token modelling turn, so where it fires matters more than the directive cost.

This script replays a saved run's own action counts through the three candidate triggers and
reports, per level, whether the nudge would fire before the human baseline was reached —
i.e. whether the agent was told to change strategy while it was on pace.

    python3 escalation_audit.py benchmark.json [--rate 1.2] [--floor 20] [--cap 2]

Triggers compared:
  abs10 / abs60  - what v13.1 and v13.2 ship (plain action counts)
  baseline       - max(floor, rate * base_actions_per_level), optional per-level cap
                   (`base_actions_per_level` is already in the harness's GameRun, so this
                   needs no new plumbing)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DIRECTIVE_CHARS = 540          # len(plan_escalation_prompt) as shipped
CHARS_PER_TOKEN = 3.7          # conservative for English prompt text


def directive_tokens() -> int:
    return int(DIRECTIVE_CHARS / CHARS_PER_TOKEN)


def counts(actions: int, baseline: int, rate: float, floor: int, cap: int | None) -> dict:
    thr = max(floor, int(baseline * rate))
    rel = (actions // thr) if actions >= thr else 0
    if cap:
        rel = min(rel, cap)
    return {"abs10": actions // 10, "abs60": actions // 60, "baseline": rel}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("bench")
    ap.add_argument("--rate", type=float, default=1.2)
    ap.add_argument("--floor", type=int, default=20)
    ap.add_argument("--cap", type=int, default=2, help="max injections per level (0 = none)")
    ap.add_argument("--pool", type=int, default=146_000, help="tokens per game to % against")
    a = ap.parse_args(argv)
    cap = a.cap or None

    d = json.loads(Path(a.bench).read_text())
    tok = directive_tokens()
    totals = {"abs10": 0, "abs60": 0, "baseline": 0}
    early = {"abs10": 0, "abs60": 0, "baseline": 0}
    levels = 0
    rows = []
    for g in d.get("game_runs", []):
        done = g.get("levels_completed") or 0
        base = g.get("base_actions_per_level") or []
        for i, acts in enumerate((g.get("actions_per_level") or [])[:done]):
            if not acts or i >= len(base):
                continue
            levels += 1
            c = counts(acts, base[i], a.rate, a.floor, cap)
            first = {"abs10": 10, "abs60": 60,
                     "baseline": max(a.floor, int(base[i] * a.rate))}
            for k in totals:
                totals[k] += c[k]
                if c[k] and first[k] < base[i]:
                    early[k] += 1
            rows.append((f"{g['game_id'][:4]}/{i + 1}", acts, base[i], c))

    print(f"{'level':10}{'akcje':>7}{'baseline':>9}{'@10':>5}{'@60':>5}{'base*%.1f' % a.rate:>9}")
    for name, acts, base, c in rows:
        print(f"{name:10}{acts:7}{base:9}{c['abs10']:5}{c['abs60']:5}{c['baseline']:9}")

    print(f"\n{levels} completed levels")
    for k in ("abs10", "abs60", "baseline"):
        n, e = totals[k], early[k]
        print(f"  {k:9} {n:4} injections (~{n * tok:>6,} tokens = {100 * n * tok / a.pool:4.1f}% of pool)"
              f"   fired before baseline on {e}/{levels} levels")
    print("\nThe 'baseline' trigger is the one that fires only where the run is actually losing "
          "points; the absolute counters fire mostly while the agent is on pace.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
