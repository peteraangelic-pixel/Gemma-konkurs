#!/usr/bin/env python3
"""Offline tests for patch 0009 (self-paced escalation) - no harness, no GPU.

The functions are lifted **out of the patch text**, so what is tested is exactly what ships,
and they run on the real r085 numbers every branch used for the @10/@60 measurements.

    python3 tests/test_self_pace.py
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace as NS

PKG = Path(__file__).resolve().parent.parent

# r085, per game: human baseline and actions spent, for the levels the run completed
# (10 games, 32 levels - the same population as ARC3/local-lab/escalation_audit.py).
R085 = [
    {"game": "tn36", "base": [32], "actions": [16]},
    {"game": "m0r0", "base": [30, 111, 203, 26], "actions": [22, 41, 94, 31]},
    {"game": "cn04", "base": [29, 54, 85, 300, 208], "actions": [35, 30, 25, 41, 52]},
    {"game": "dc22", "base": [59, 102, 67], "actions": [37, 131, 61]},
    {"game": "ka59", "base": [28, 109, 51, 51, 33], "actions": [17, 35, 55, 69, 30]},
    {"game": "sc25", "base": [36, 6, 32], "actions": [47, 12, 35]},
    {"game": "s5i5", "base": [20, 89], "actions": [20, 43]},
    {"game": "ls20", "base": [22, 123, 73], "actions": [17, 175, 222]},
    {"game": "su15", "base": [22, 42, 26], "actions": [13, 37, 21]},
    {"game": "g50t", "base": [78, 175, 179], "actions": [79, 40, 73]},
]


def load_module():
    """Exec the shipped (post-patch) function region.

    `tests/fixtures/tool_agent_0009_{pre,post}.py` were cut out of the real patched tree;
    test_v16_package.py proves `diff pre post` equals the patch itself, so what runs here is
    exactly what ships.
    """
    ns = {"os": os}

    exec("def _get_env_bool(n, d=False):\n"
         "    return os.environ.get(n, '').strip().lower() in ('1', 'true', 'yes', 'on')\n"
         "def _get_env_int(n, d=0):\n"
         "    try:\n"
         "        return int(float(os.environ.get(n, '') or d))\n"
         "    except (TypeError, ValueError):\n"
         "        return d\n", ns)
    exec((PKG / "tests" / "fixtures" / "tool_agent_0009_post.py").read_text(), ns)
    return ns


def agent(actions_per_level, levels_completed, base=None):
    """The two objects the patched code reads: GameRun (our own record) and GameState."""
    run = NS(actions_per_level=list(actions_per_level),
             levels_completed=levels_completed,
             base_actions_per_level=base)
    state = NS(levels_completed=levels_completed)
    return NS(game=NS(game_run=run, current_state=state))


def count(provider, cap=2):
    """Replay the escalation loop over r085 and count injections / premature ones."""
    total = premature = levels = 0
    for g in R085:
        for i, acts in enumerate(g["actions"]):
            levels += 1
            thr = provider(agent(g["actions"][:i], i, base=g["base"]), 20)
            n = 0
            while thr and (n + 1) * thr <= acts:
                if cap and n >= cap:
                    break
                n += 1
            if n and thr < g["base"][i]:
                premature += 1
            total += n
    return total, premature, levels


def run() -> int:
    ns = load_module()
    threshold, self_pace = ns["_escalate_threshold"], ns["_escalate_self_pace"]
    saved = dict(os.environ)

    def env(**kw):
        os.environ.clear()
        os.environ.update(saved)
        for k, v in kw.items():
            os.environ[k] = str(v)

    # 1. Off by default: threshold is the floor, i.e. v13.4 without 0009.
    env()
    assert self_pace(agent([30, 40], 2), 20) == 0
    assert threshold(agent([30, 40], 2), 20) == 20
    print("1. SELF_PACE unset -> prog = floor (20), zachowanie v13.4 bez zmian   OK")

    # 2. On: 1.5 x median(completed levels), clamped.
    env(ARC3_ESCALATE_SELF_PACE=1)
    assert self_pace(agent([30, 40], 2), 20) == 52, self_pace(agent([30, 40], 2), 20)
    assert self_pace(agent([400, 500], 2), 20) == 120      # ceiling
    assert self_pace(agent([4, 6], 2), 20) == 20           # floor wins
    assert self_pace(agent([], 0), 20) == 0                # nothing to calibrate on
    print("2. self-pace = clamp(1.5 x mediana, 20, 120); brak historii -> floor   OK")

    # 3. Relative branch still wins when the human baseline is visible (local/smoke).
    env(ARC3_ESCALATE_RELATIVE=1, ARC3_ESCALATE_RATE=1.2, ARC3_ESCALATE_SELF_PACE=1)
    assert threshold(agent([30, 40], 0, base=[100, 200, 300]), 20) == 120   # 1.2 * baseline[0]
    os.environ["ARC3_ESCALATE_RELATIVE"] = "0"
    assert threshold(agent([30, 40], 2, base=[100, 200, 300]), 20) == 52    # self-pace
    print("3. baseline widoczny -> relatywny wygrywa; ukryty -> self-pace       OK")

    # 4. The measurement this patch is for: same population, three triggers.
    env(ARC3_ESCALATE_RELATIVE=1, ARC3_ESCALATE_RATE=1.2, ARC3_ESCALATE_SELF_PACE=0)
    rel = count(threshold)
    env(ARC3_ESCALATE_RELATIVE=0, ARC3_ESCALATE_SELF_PACE=0)
    floor = count(threshold)
    env(ARC3_ESCALATE_SELF_PACE=1)
    pace = count(threshold)
    print(f"4. r085, 32 poziomy:  rel+baseline={rel[0]}/{rel[1]}  "
          f"floor20={floor[0]}/{floor[1]}  self-pace={pace[0]}/{pace[1]}   (nudge/przedwczesne)")
    # 32 levels; injection counts are what the branch's own 0008 test claims (8/0 for the
    # relative rule) reproduced here from the shipped code, and the self-pace numbers are
    # lower than floor-20 on BOTH axes, which is the whole point of the patch.
    assert rel[:2] == (8, 0), rel
    assert floor[:2] == (42, 26), floor
    assert pace[0] < floor[0] and pace[1] < floor[1], (pace, floor)
    print("   wszystkie trzy odtwarzaja sie dokladnie z kodu patcha                OK")

    os.environ.clear()
    os.environ.update(saved)
    print("\nwszystkie testy 0009 przeszly")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
