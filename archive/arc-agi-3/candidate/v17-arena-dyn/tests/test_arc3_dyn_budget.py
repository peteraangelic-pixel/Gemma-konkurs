"""Offline tests for the v13.2 adaptive level budget (patch 0007).

Pure logic only: no harness, no GPU, no engine, no Kaggle slot - the same
discipline as tests/test_arc3_level_budget.py for patch 0004.

Run:  python3 -m unittest tests.test_arc3_dyn_budget -v
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MODULE = _HERE.parent / "src" / "arc3_level_budget_v13_2.py"

_spec = importlib.util.spec_from_file_location("arc3_level_budget_v13_2", _MODULE)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["arc3_level_budget_v13_2"] = _mod
_spec.loader.exec_module(_mod)  # noqa: B005

LevelBudget = _mod.LevelBudget
KEEP_GOING = _mod.KEEP_GOING
RESET_LEVEL = _mod.RESET_LEVEL
ABANDON = _mod.ABANDON


def _clean_env():
    saved = {}
    for key in list(os.environ):
        if key.startswith("ARC3_"):
            saved[key] = os.environ.pop(key)
    return saved


class _Env:
    """Context manager restoring ARC3_* env."""

    def __enter__(self):
        self.saved = _clean_env()
        return os.environ

    def __exit__(self, *exc):
        _clean_env()
        os.environ.update(self.saved)
        return False


class DisabledTests(unittest.TestCase):
    def test_cap_zero_is_stock_behaviour(self):
        with _Env():
            lb = LevelBudget(level_token_cap=0)
            self.assertFalse(lb.enabled)
            for gt in (0, 10_000, 500_000):
                self.assertEqual(lb.peek(gt, 0), KEEP_GOING)
                self.assertEqual(lb.step(gt, 0), KEEP_GOING)

    def test_dyn_off_with_cap_zero_never_arms(self):
        with _Env():
            os.environ["ARC3_DYN_CAP"] = "1"
            lb = LevelBudget(level_token_cap=0)
            self.assertFalse(lb.enabled)
            self.assertEqual(lb.peek(999_999, 0), KEEP_GOING)


class StaticFallbackTests(unittest.TestCase):
    """ARC3_DYN_CAP=0 must reproduce patch 0004 decisions exactly."""

    def _static(self, min_done=0, resets=1, cap=45_000):
        with _Env():
            os.environ["ARC3_DYN_CAP"] = "0"
            os.environ["ARC3_LEVEL_MIN_DONE"] = str(min_done)
            os.environ["ARC3_LEVEL_RESETS_MAX"] = str(resets)
            os.environ["ARC3_LEVEL_TOKEN_CAP"] = str(cap)
            return LevelBudget.from_env(), None

    def test_reset_then_abandon(self):
        lb, _ = self._static()
        self.assertEqual(lb.step(44_999, 0), KEEP_GOING)
        self.assertEqual(lb.step(45_000, 0), RESET_LEVEL)
        # after the reset the counter restarts from the reset point
        self.assertEqual(lb.step(60_000, 0), KEEP_GOING)
        self.assertEqual(lb.step(90_000, 0), ABANDON)

    def test_min_done_protects_from_abandon(self):
        lb, _ = self._static(min_done=2)
        lb.step(45_000, 0)          # RESET
        self.assertEqual(lb.step(90_000, 0), KEEP_GOING)  # protected
        self.assertEqual(lb.step(120_000, 2), KEEP_GOING)  # turn of progress: never capped
        self.assertEqual(lb.step(165_000, 2), RESET_LEVEL)  # completion replenished resets
        self.assertEqual(lb.step(230_000, 2), ABANDON)      # spent 65k, resets exhausted

    def test_progress_replenishes_resets(self):
        lb, _ = self._static()
        lb.step(45_000, 0)                    # RESET (resets_used=1)
        self.assertEqual(lb.step(50_000, 1), KEEP_GOING)  # level done: fresh budget
        self.assertEqual(lb.step(95_001, 1), RESET_LEVEL)  # resets back to 0 -> reset again


class DynamicTests(unittest.TestCase):
    def _dyn(self, cap=60_000, resets=1, min_done=0, **env):
        with _Env():
            os.environ["ARC3_DYN_CAP"] = "1"
            os.environ["ARC3_LEVEL_RESETS_MAX"] = str(resets)
            os.environ["ARC3_LEVEL_MIN_DONE"] = str(min_done)
            os.environ["ARC3_LEVEL_TOKEN_CAP"] = str(cap)
            for key, value in env.items():
                os.environ[key] = str(value)
            return LevelBudget.from_env()

    def test_arming_cap_is_the_floor_before_samples(self):
        lb = self._dyn(cap=60_000)
        self.assertEqual(lb._current_cap(), 60_000)
        lb.step(60_000, 0)                    # RESET at floor cap
        self.assertEqual(lb._current_cap(), int(60_000 * 1.5))  # ladder

    def test_expensive_game_earns_bigger_cap(self):
        lb = self._dyn(cap=60_000, **{"ARC3_DYN_CAP_MIN": "30000"})
        # complete two levels at ~100k each (level done at those counters)
        lb.step(100_000, 1)
        lb.step(200_000, 2)
        self.assertEqual(lb._level_costs, [100_000, 100_000])
        self.assertEqual(lb._current_cap(), 150_000)  # 4*100k clamped to max

    def test_level_just_completed_is_never_capped(self):
        lb = self._dyn(cap=60_000, **{"ARC3_DYN_CAP_MIN": "30000"})
        lb.step(60_000, 0)                    # RESET fires at 60k...
        # ...but the very same turn the level completed: peek must KEEP
        self.assertEqual(lb.peek(60_000, 1), KEEP_GOING)

    def test_abandon_needs_patience_zone(self):
        lb = self._dyn(cap=60_000, resets=1)
        lb.step(60_000, 0)                    # RESET -> ladder cap 90k
        self.assertEqual(lb.step(89_999, 0), KEEP_GOING)   # still inside the 90k cap
        self.assertEqual(lb.step(149_999, 0), KEEP_GOING)  # spent 90k: below 90k*1.5
        self.assertEqual(lb.step(195_001, 0), ABANDON)     # spent 135_001 >= 135k

    def test_min_done_protects_in_dyn_mode_too(self):
        lb = self._dyn(cap=60_000, resets=0, min_done=2, **{"ARC3_DYN_ABANDON_MULT": "1.0"})
        self.assertEqual(lb.step(60_001, 0), KEEP_GOING)   # protected below min_done
        self.assertEqual(lb.step(60_001, 2), KEEP_GOING)   # turn of progress: never capped
        self.assertEqual(lb.step(200_000, 2), ABANDON)     # spent 140k, resets=0, min_done ok

    def test_history_caps_at_max(self):
        lb = self._dyn(cap=60_000, **{"ARC3_DYN_HISTORY": "3"})
        for i, gt in enumerate((10_000, 30_000, 45_000, 70_000, 90_000), start=1):
            lb.step(gt, i)
        self.assertEqual(lb._level_costs, [15_000, 25_000, 20_000])

    def test_peek_is_pure(self):
        lb = self._dyn(cap=60_000)
        before = (lb.resets_used, list(lb._level_costs), lb.level_start_tokens, lb.level_start_levels)
        for gt in (0, 30_000, 59_999, 60_000, 500_000):
            lb.peek(gt, 0)
        after = (lb.resets_used, list(lb._level_costs), lb.level_start_tokens, lb.level_start_levels)
        self.assertEqual(before, after)

    def test_reset_replenished_on_completion(self):
        lb = self._dyn(cap=60_000, resets=1)
        lb.step(60_000, 0)                    # RESET (resets_used=1)
        lb.step(70_000, 1)                    # level completed
        self.assertEqual(lb.resets_used, 0)


class EnvParsingTests(unittest.TestCase):
    def test_from_env_reads_all_knobs(self):
        with _Env():
            os.environ["ARC3_LEVEL_TOKEN_CAP"] = "60000"
            os.environ["ARC3_LEVEL_RESETS_MAX"] = "2"
            os.environ["ARC3_LEVEL_MIN_DONE"] = "1"
            os.environ["ARC3_DYN_CAP"] = "1"
            os.environ["ARC3_DYN_CAP_MULT"] = "3.5"
            os.environ["ARC3_DYN_CAP_MIN"] = "30000"
            os.environ["ARC3_DYN_CAP_MAX"] = "120000"
            os.environ["ARC3_DYN_CAP_LADDER"] = "2"
            os.environ["ARC3_DYN_ABANDON_MULT"] = "1.25"
            os.environ["ARC3_DYN_HISTORY"] = "4"
            lb = LevelBudget.from_env()
            self.assertTrue(lb.enabled and lb.dyn_enabled)
            self.assertEqual((lb.max_resets, lb.min_done), (2, 1))
            self.assertEqual((lb.cap_mult, lb.cap_min, lb.cap_max), (3.5, 30000, 120000))
            self.assertEqual((lb.ladder, lb.abandon_mult, lb.history_max), (2.0, 1.25, 4))

    def test_garbage_env_falls_back_to_defaults(self):
        with _Env():
            os.environ["ARC3_LEVEL_TOKEN_CAP"] = "abc"
            os.environ["ARC3_DYN_CAP_MULT"] = "NaN?"
            lb = LevelBudget.from_env()
            self.assertEqual(lb.static_cap, 0)
            self.assertFalse(lb.enabled)
            self.assertEqual(lb.cap_mult, 4.0)


class DescribeTests(unittest.TestCase):
    def test_describe_both_modes_smoke(self):
        with _Env():
            lb = LevelBudget(level_token_cap=60_000)
            self.assertIn("DynLevelBudget", lb.describe())
            os.environ["ARC3_DYN_CAP"] = "0"
            lb2 = LevelBudget(level_token_cap=45_000)
            self.assertIn("LevelBudget(cap=45000", lb2.describe())


if __name__ == "__main__":
    unittest.main()
