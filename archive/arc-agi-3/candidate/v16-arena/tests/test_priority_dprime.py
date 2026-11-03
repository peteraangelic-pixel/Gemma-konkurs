#!/usr/bin/env python3
"""Offline tests for patch 0009 (D' slot priority). No harness, no GPU, no model.

Three things are checked, in this order of importance:

1. **Nothing changes with the switch off.** `select_priority` must return the
   exact integer the shipped `priority_value` returns for every argument
   combination the notebook can produce, including the tail-fade and endgame
   paths. This is what makes the patch a single-variable experiment.
2. **D' is the published formula.** The patched implementation is compared
   against the repository reference (`arc3_local_candidate/dprime.py`, itself
   the module with the local unit tests) on a grid of snapshots. Same numbers,
   same integer scale.
3. **It degrades instead of raising.** NaN/inf/None/garbage inputs, an agent
   unpickled from a build without the new field, and a missing reference
   module all have defined behaviour.

Run from the ARC3-Inference tree root:  python -m unittest tests.test_priority_dprime
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inference.agent import priority_scheduler as ps  # noqa: E402

SWITCHES = (
    "ARC3_PRIORITY_DPRIME",
    "ARC3_PRIORITY_PACE",
    "ARC3_PRIORITY_TAIL_FADE",
)

# Every keyword the two call sites can pass (see tool_agent._game_priority and
# _PriorityGate._snapshot_priority).
LEGACY_KWARGS = (
    {},
    {"endgame": True},
    {"tail_fraction": 0.0},
    {"tail_fraction": 0.35},
    {"normalize_score": True},
    {"tail_lookup": True},
    {"tail_lookup": "remaining"},
    {"normalize_score": True, "tail_lookup": "remaining", "tail_fraction": 0.2},
    {"endgame": True, "tail_lookup": "remaining"},
    {"human_actions": 25.0, "action_scale": 115.0, "token_scale": 62000.0,
     "action_weight": 0.25, "tail_base": 6.0, "tail_cap": 6.0},
)

SNAPSHOTS = (
    ps.PrioritySnapshot(1, 0, 0.0),
    ps.PrioritySnapshot(1, 12, 3000.0, total_levels=6),
    ps.PrioritySnapshot(3, 40, 90000.0, total_levels=7,
                        mean_tokens_per_cleared_level=31000.0),
    ps.PrioritySnapshot(5, 226, 480000.0, 1.4, 10, 12000.0),
    ps.PrioritySnapshot(10, 0, 0.0, total_levels=10),
)


def reference_module():
    """The repository's standalone D' reference, if this checkout has it."""
    hinted = os.environ.get("ARC3_CANDIDATE_ROOT", "").strip()
    roots = ([Path(hinted)] if hinted else []) + list(Path(__file__).resolve().parents)
    for parent in roots:
        candidate = parent / "arc3_local_candidate" / "dprime.py"
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("_dprime_ref", candidate)
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            # dataclasses resolves annotations through sys.modules
            sys.modules["_dprime_ref"] = module
            spec.loader.exec_module(module)
            return module
    return None


class SwitchOffTests(unittest.TestCase):
    """The whole point of the patch: switch off == byte-identical behaviour."""

    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in SWITCHES}
        for key in SWITCHES:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_select_priority_equals_priority_value(self):
        checked = 0
        for state in SNAPSHOTS:
            for kwargs in LEGACY_KWARGS:
                want = ps.priority_value(state, **kwargs)
                got = ps.select_priority(state, **kwargs)
                self.assertEqual(got, want, (state, kwargs))
                self.assertIsInstance(got, int)
                checked += 1
        self.assertEqual(checked, len(SNAPSHOTS) * len(LEGACY_KWARGS))

    def test_switch_off_ignores_the_new_field(self):
        plain = ps.PrioritySnapshot(4, 30, 50000.0, total_levels=8)
        with_pace = ps.PrioritySnapshot(4, 30, 50000.0, total_levels=8,
                                        mean_tokens_per_cleared_level=250000.0)
        self.assertEqual(ps.select_priority(plain), ps.select_priority(with_pace))

    def test_explicit_zero_and_false_are_off(self):
        state = ps.PrioritySnapshot(2, 5, 1000.0)
        want = ps.priority_value(state)
        for raw in ("0", "false", "no", "off", "", " "):
            os.environ["ARC3_PRIORITY_DPRIME"] = raw
            self.assertEqual(ps.select_priority(state), want, raw)
        self.assertFalse(ps.dprime_enabled())

    def test_truthy_values_are_on(self):
        for raw in ("1", "true", "TRUE", "yes", "on", " On "):
            os.environ["ARC3_PRIORITY_DPRIME"] = raw
            self.assertTrue(ps.dprime_enabled(), raw)


class DPrimeFormulaTests(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in SWITCHES}
        os.environ["ARC3_PRIORITY_DPRIME"] = "1"

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_matches_the_repository_reference(self):
        ref = reference_module()
        if ref is None:
            self.skipTest("arc3_local_candidate/dprime.py not present in this checkout")
        for state in SNAPSHOTS:
            mirror = ref.PrioritySnapshot(
                level=state.level, actions=state.actions, tokens=state.tokens,
                total_levels=state.total_levels,
                mean_tokens_per_cleared_level=state.mean_tokens_per_cleared_level,
            )
            for phi in (0.0, 0.5, 1.0):
                self.assertAlmostEqual(
                    ps.dprime_value(state, tail_fraction=phi),
                    ref.dprime_value(mirror, tail_fraction=phi), places=12,
                    msg=(state, phi),
                )
                self.assertEqual(
                    ps.dprime_priority(state, tail_fraction=phi),
                    ref.dprime_priority(mirror, tail_fraction=phi), (state, phi),
                )
        from inference.agent import priority_scheduler as module
        self.assertTrue(module.dprime_enabled())

    def test_switch_off_vs_on_differs_on_a_realistic_snapshot(self):
        state = ps.PrioritySnapshot(3, 40, 90000.0, total_levels=7,
                                    mean_tokens_per_cleared_level=31000.0)
        on = ps.select_priority(state, tail_fraction=1.0)
        os.environ["ARC3_PRIORITY_DPRIME"] = "0"
        off = ps.select_priority(state, tail_fraction=1.0)
        self.assertNotEqual(on, off)
        self.assertGreater(on, 0)
        self.assertGreater(off, 0)

    def test_deeper_level_wins_at_identical_spend(self):
        shallow = ps.PrioritySnapshot(1, 20, 20000.0, total_levels=8,
                                      mean_tokens_per_cleared_level=30000.0)
        deep = ps.PrioritySnapshot(4, 20, 20000.0, total_levels=8,
                                   mean_tokens_per_cleared_level=30000.0)
        self.assertGreater(ps.dprime_priority(deep, tail_fraction=1.0),
                           ps.dprime_priority(shallow, tail_fraction=1.0))

    def test_cheaper_measured_pace_is_preferred(self):
        cheap = ps.PrioritySnapshot(2, 10, 5000.0, total_levels=8,
                                    mean_tokens_per_cleared_level=12000.0)
        pricey = ps.PrioritySnapshot(2, 10, 5000.0, total_levels=8,
                                     mean_tokens_per_cleared_level=180000.0)
        self.assertGreater(ps.dprime_priority(cheap, tail_fraction=1.0),
                           ps.dprime_priority(pricey, tail_fraction=1.0))

    def test_tail_fade_removes_the_growth_bonus_only(self):
        mid = ps.PrioritySnapshot(2, 0, 0.0, total_levels=9,
                                  mean_tokens_per_cleared_level=30000.0)
        open_phi = ps.dprime_value(mid, tail_fraction=1.0)
        closed_phi = ps.dprime_value(mid, tail_fraction=0.0)
        self.assertGreater(open_phi, closed_phi)
        self.assertAlmostEqual(open_phi - closed_phi, 16.0, places=9)

    def test_no_clock_endgame_drops_the_growth_bonus(self):
        state = ps.PrioritySnapshot(2, 0, 0.0, total_levels=9)
        running = ps.select_priority(state, tail_fraction=None, endgame=False)
        ending = ps.select_priority(state, tail_fraction=None, endgame=True)
        self.assertGreater(running, ending)

    def test_known_hand_computed_value(self):
        """One snapshot worked out by hand, so a silent formula drift fails."""
        state = ps.PrioritySnapshot(3, 40, 90000.0, total_levels=7,
                                    mean_tokens_per_cleared_level=31000.0)
        level, actions, tokens, pace = 3, 40.0, 90000.0, 31000.0
        norm = 55.0 / (7 * 8 / 2.0)
        depth = (1.0 + 0.5 * (level - 1)) * norm
        depth *= (300.0 / (300.0 + actions)) ** 2.5
        depth *= min(4.0, max(0.25, (30_000.0 / pace) ** 0.4))
        token_scale = 225_000.0 * min(2.0, max(0.5, pace / 30_000.0)) ** 0.5
        patience = (0.1 * max(0.1, 1.0 - actions / 115.0)
                    + 0.9 * max(0.1, 1.0 - tokens / token_scale))
        expected = depth * patience + 16.0
        self.assertAlmostEqual(ps.dprime_value(state, tail_fraction=1.0),
                               expected, places=9)
        self.assertEqual(ps.dprime_priority(state, tail_fraction=1.0),
                         max(1, int(expected * 1000.0)))


class GuardTests(unittest.TestCase):
    def test_garbage_inputs_never_raise(self):
        bad = float("nan")
        cases = [
            ps.PrioritySnapshot(0, -5, -1.0),
            ps.PrioritySnapshot(-3, 10 ** 9, bad),
            ps.PrioritySnapshot(2, 5, float("inf"), total_levels=0),
            ps.PrioritySnapshot(2, 5, 1.0, total_levels=-4),
            ps.PrioritySnapshot(2, 5, 1.0, total_levels=7.5),
            ps.PrioritySnapshot(2, 5, 1.0, mean_tokens_per_cleared_level=bad),
            ps.PrioritySnapshot(2, 5, 1.0, mean_tokens_per_cleared_level=-9.0),
            ps.PrioritySnapshot(2, 5, 1.0, total_levels=None),
        ]
        for state in cases:
            for phi in (None, 0.0, 1.0, bad, -1.0, 5.0):
                value = ps.dprime_priority(state, tail_fraction=phi)
                self.assertIsInstance(value, int)
                self.assertGreaterEqual(value, 1)
                self.assertNotIsInstance(value, bool)
                self.assertTrue(math.isfinite(ps.dprime_value(state, tail_fraction=phi)))

    def test_missing_pace_uses_the_reference_30000(self):
        state = ps.PrioritySnapshot(2, 10, 20000.0, total_levels=8)
        self.assertGreater(ps.dprime_priority(state, tail_fraction=1.0), 0)


class ProgressPaceTests(unittest.TestCase):
    def setUp(self):
        ps._DPRIME_LOGGED = False

    def test_zero_before_the_first_clear(self):
        pace = ps.ProgressPace()
        self.assertEqual(pace.mean_tokens_per_cleared_level(), 0.0)
        self.assertEqual(pace.cost_multiplier(), 1.0)

    def test_mean_of_cleared_levels(self):
        pace = ps.ProgressPace()
        pace.record_completion(30_000, 62_000)
        pace.record_completion(60_000, 62_000)
        self.assertAlmostEqual(pace.mean_tokens_per_cleared_level(), 45_000.0)
        self.assertEqual(pace.completed, 2)

    def test_garbage_tokens_do_not_poison_the_mean(self):
        pace = ps.ProgressPace()
        pace.record_completion(float("nan"), 1.0)
        pace.record_completion(-5, 1.0)
        pace.record_completion(1_000, 0.0)
        self.assertAlmostEqual(pace.mean_tokens_per_cleared_level(), 1000.0 / 3.0)

    def test_agent_pickled_before_the_field_existed(self):
        pace = ps.ProgressPace()
        del pace.total_tokens  # what unpickling an older agent gives us
        pace.record_completion(1_000, 62_000)
        self.assertAlmostEqual(pace.mean_tokens_per_cleared_level(), 1_000.0)

    def test_legacy_cost_multiplier_is_untouched(self):
        pace = ps.ProgressPace()
        pace.record_completion(124_000, 62_000)
        # confidence = 1/(1+3) = 0.25, log ratio = log 2 -> 2 ** 0.25
        self.assertAlmostEqual(pace.cost_multiplier(), 2.0 ** 0.25, places=12)


class ToolAgentWiringTests(unittest.TestCase):
    """The two call sites must reach D' — otherwise the switch is a no-op."""

    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in SWITCHES}
        try:
            from inference.agent import tool_agent
        except Exception as exc:  # requests/PIL/arcengine unavailable here
            os.environ.update({k: v for k, v in self.saved.items() if v is not None})
            self.skipTest(f"tool_agent unavailable: {exc!r}")
        self.ta = tool_agent

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_game_priority_routes_through_the_switch(self):
        for key in SWITCHES:
            os.environ.pop(key, None)
        legacy = self.ta._game_priority(3, 40, 90_000, total_levels=7)
        os.environ["ARC3_PRIORITY_DPRIME"] = "1"
        dprime = self.ta._game_priority(
            3, 40, 90_000, total_levels=7, mean_tokens_per_cleared_level=31_000.0,
        )
        self.assertGreater(dprime, legacy)  # 1000 scale beats the legacy 100 scale
        self.assertEqual(
            dprime,
            ps.dprime_priority(
                ps.PrioritySnapshot(3, 40, 90_000.0, total_levels=7,
                                    mean_tokens_per_cleared_level=31_000.0),
                tail_fraction=1.0,
            ),
        )

    def test_game_priority_keeps_the_legacy_kwarg_contract(self):
        for key in SWITCHES:
            os.environ.pop(key, None)
        self.assertEqual(
            self.ta._game_priority(2, 5, 1000), 
            self.ta._game_priority(2, 5, 1000, mean_tokens_per_cleared_level=99_000.0),
        )

    def test_source_wiring_present(self):
        import inspect
        src = inspect.getsource(self.ta)
        self.assertIn("mean_tokens_per_cleared_level=mean_tokens", src)
        self.assertIn("self._progress_pace.mean_tokens_per_cleared_level()", src)
        self.assertIn("or dprime_enabled()", src)
        self.assertEqual(src.count("select_priority("), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
