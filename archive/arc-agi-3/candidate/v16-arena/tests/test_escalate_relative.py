#!/usr/bin/env python3
"""Offline tests for patch 0008 (relative escalation threshold). No harness, no GPU.

Imports the PATCHED inference.agent.tool_agent and exercises _escalate_threshold()
under every env combination the notebook can produce:

  ARC3_ESCALATE_RELATIVE unset/0  -> exact v14 behaviour (absolute floor)
  ARC3_ESCALATE_RELATIVE=1        -> max(floor, rate * baseline[level])
                                     falls back to the floor whenever the
                                     baseline is hidden (None / missing game /
                                     out-of-range level / zero baseline)
Run from the ARC3-Inference tree root:  python -m unittest tests.test_escalate_relative
"""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inference.agent import tool_agent as ta  # noqa: E402

FLOOR = 20


def agent_with(baseline=None, levels_completed=0, has_game=True):
    if not has_game:
        return NS()
    game_run = NS(base_actions_per_level=baseline)
    state = NS(levels_completed=levels_completed)
    game = NS(game_run=game_run, current_state=state)
    return NS(game=game)


class EscalateRelativeTests(unittest.TestCase):
    def setUp(self):
        self.old = dict(os.environ)
        for k in ("ARC3_ESCALATE_RELATIVE", "ARC3_ESCALATE_RATE",
                  "ARC3_ESCALATE_MAX_PER_LEVEL", "ARC3_ESCALATE_ACTIONS"):
            os.environ.pop(k, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)

    def test_unset_is_absolute_v14_behaviour(self):
        a = agent_with(baseline=[300, 208], levels_completed=0)
        self.assertEqual(ta._escalate_threshold(a, FLOOR), FLOOR)
        os.environ["ARC3_ESCALATE_RELATIVE"] = "0"
        self.assertEqual(ta._escalate_threshold(a, FLOOR), FLOOR)

    def test_relative_uses_rate_times_baseline(self):
        os.environ["ARC3_ESCALATE_RELATIVE"] = "1"
        a = agent_with(baseline=[300, 208], levels_completed=0)
        self.assertEqual(ta._escalate_threshold(a, FLOOR), 360)  # 1.2 * 300
        a2 = agent_with(baseline=[300, 208], levels_completed=1)
        self.assertEqual(ta._escalate_threshold(a2, FLOOR), 249)  # int(1.2*208)
        a3 = agent_with(baseline=[15], levels_completed=0)
        self.assertEqual(ta._escalate_threshold(a3, FLOOR), FLOOR)  # floor wins

    def test_rate_env_is_honoured(self):
        os.environ["ARC3_ESCALATE_RELATIVE"] = "1"
        os.environ["ARC3_ESCALATE_RATE"] = "1.5"
        a = agent_with(baseline=[100], levels_completed=0)
        self.assertEqual(ta._escalate_threshold(a, FLOOR), 150)
        os.environ["ARC3_ESCALATE_RATE"] = "garbage"
        self.assertEqual(ta._escalate_threshold(a, FLOOR), 120)  # fallback 1.2

    def test_missing_baseline_falls_back_to_floor(self):
        os.environ["ARC3_ESCALATE_RELATIVE"] = "1"
        self.assertEqual(ta._escalate_threshold(agent_with(baseline=None), FLOOR), FLOOR)
        self.assertEqual(ta._escalate_threshold(agent_with(has_game=False), FLOOR), FLOOR)
        self.assertEqual(ta._escalate_threshold(agent_with(baseline=[]), FLOOR), FLOOR)
        out_of_range = agent_with(baseline=[10, 10], levels_completed=5)
        self.assertEqual(ta._escalate_threshold(out_of_range, FLOOR), FLOOR)
        zero = agent_with(baseline=[0], levels_completed=0)
        self.assertEqual(ta._escalate_threshold(zero, FLOOR), FLOOR)

    def test_r085_reproduces_the_measured_trigger_set(self):
        """The trigger set that motivated patch 0008: 8 nudges on r085's
        completed levels, none before the human baseline (audit: Gemma
        b38b82e escalation_audit.py; independently recomputed by Arena)."""
        import json
        from pathlib import Path
        bench = Path(os.environ.get("R085_BENCH", ""))
        if not bench.exists():
            self.skipTest("r085 benchmark.json not available")
        os.environ["ARC3_ESCALATE_RELATIVE"] = "1"
        d = json.loads(bench.read_text())
        total, premature = 0, 0
        for g in d["game_runs"]:
            done = g.get("levels_completed") or 0
            base = g.get("base_actions_per_level") or []
            apl = g.get("actions_per_level") or []
            for i in range(min(done, len(base))):
                acts = apl[i] if i < len(apl) else 0
                if not acts:
                    continue
                a = agent_with(baseline=base, levels_completed=i)
                thr = ta._escalate_threshold(a, FLOOR)
                n = min(2, acts // thr) if acts >= thr else 0  # cap 2/level
                total += n
                premature += 1 if (n and thr < base[i]) else 0
        self.assertEqual(total, 8)
        self.assertEqual(premature, 0)


if __name__ == "__main__":
    unittest.main()
