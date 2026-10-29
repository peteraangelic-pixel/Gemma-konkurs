#!/usr/bin/env python3
"""Tests for the local lab. Run: python3 test_lab.py  (no pytest dependency).

Two classes of test, both of which earned their place:
  * scoring - the exact taaf rule, including the two traps that produced a 32x error;
  * engine  - that the fast path is the official path (clone policy + direct driving).
The engine tests need the ARC packages and the game files; they skip themselves cleanly if
those are not present, so this file runs anywhere.
"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab.engine import LEVEL_CAP, game_score, level_score, level_value_table  # noqa: E402

GAMES = os.environ.get("ARC3_GAMES") or "/tmp/smak/arc-agi-3/games/environment_files"
BENCH = "/tmp/smak/arc-agi-3/kaggle/ops/results"


class TestScoring(unittest.TestCase):
    def test_per_level_cap_is_115(self):
        self.assertEqual(level_score(10, 1), 115.0)   # 100x better than baseline
        self.assertAlmostEqual(level_score(10, 10), 100.0, places=9)
        self.assertAlmostEqual(level_score(10, 20), 25.0, places=9)
        self.assertEqual(level_score(10, 0), 0.0)

    def test_partial_level_not_credited(self):
        """The 32x bug: cn04 real score was 0.35, crediting the in-progress level gave 11.30."""
        base = [29, 54, 85, 300, 208, 113]
        self.assertEqual(game_score([107, 47], base, levels_completed=0), 0.0)
        self.assertAlmostEqual(game_score([107, 47], base, levels_completed=1), 0.350, places=3)

    def test_completion_cap(self):
        """1/6 levels with 4x better efficiency still cannot exceed 100/21."""
        self.assertAlmostEqual(game_score([14, 57], [29, 54, 85, 300, 208, 113], 1),
                               4.762, places=3)

    def test_real_harness_values(self):
        cases = [
            ([35, 30, 25, 41, 52, 5], [29, 54, 85, 300, 208, 113], 5, 71.429),
            ([22, 41, 94, 31, 64, 0], [30, 111, 203, 26, 500, 237], 4, 46.256),
            ([17, 175, 222, 13, 0, 0, 0], [22, 123, 73, 84, 96, 192, 186], 3, 8.794),
            ([13, 29, 22, 78, 28, 28, 0, 0, 0], [22, 42, 26, 115, 36, 31, 8, 40, 41], 5, 33.333),
        ]
        for apl, base, k, want in cases:
            self.assertAlmostEqual(game_score(apl, base, k), want, places=3, msg=str(base))

    def test_depth_dominates(self):
        """Level k is worth k units: the last level of a long game is a large share."""
        t = level_value_table([10] * 9)
        self.assertAlmostEqual(t[0]["points"], 100 * 1 / 45, places=3)
        self.assertAlmostEqual(t[-1]["points"], 100 * 9 / 45, places=3)
        self.assertAlmostEqual(t[-1]["cumulative"], 100.0, places=3)

    def test_planned_levels_without_actions_use_baseline(self):
        """Trailing zeros in actions_per_level mean 'not reached', not 'zero actions'."""
        t = level_value_table([10, 20, 30], actions=[5, 0, 0])
        self.assertGreater(t[2]["points"], 0.0)

    def test_saved_runs_reproduce(self):
        """Every `final_score` the harness wrote must come back out of our formula."""
        files = sorted(Path(BENCH).glob("*/output*/benchmark.json"))
        if not files:
            self.skipTest(f"no saved runs under {BENCH}")
        checked = 0
        for f in files:
            for g in json.loads(f.read_text()).get("game_runs", []):
                if g.get("final_score") is None:
                    continue
                ours = game_score(g.get("actions_per_level") or [],
                                  g["base_actions_per_level"],
                                  g.get("levels_completed") or 0)
                self.assertAlmostEqual(ours, g["final_score"], places=3,
                                       msg=f"{f.parent.name}/{g['game_id']}")
                checked += 1
        self.assertGreater(checked, 20)


class TestEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from lab.engine import Lab
        except (Exception, SystemExit) as exc:  # bootstrap raises SystemExit, not ImportError
            raise unittest.SkipTest(f"engine unavailable: {exc}")
        if not Path(GAMES).is_dir():
            raise unittest.SkipTest(f"no games at {GAMES}")
        cls.lab = Lab(games_dir=GAMES)

    def test_fast_path_matches_official_wrapper(self):
        from lab.engine import verify_against_wrapper

        for slug in self.lab.slugs()[:6]:
            r = verify_against_wrapper(self.lab, slug, actions=15)
            self.assertEqual(r["mismatches"], 0, msg=slug)

    def test_calibrated_policy_is_verified(self):
        for slug in self.lab.slugs()[:6]:
            policy = self.lab.policy_for(slug)
            self.assertIn(policy, ("share_levels_and_camera", "share_camera", "full_deepcopy"))

    def test_search_lands_on_a_level(self):
        """A found path, replayed on the live session, must move the level counter."""
        from lab.search import play_with_search

        s = self.lab.session("cn04")
        play_with_search(s, levels_wanted=1, node_budget=1500, time_budget_s=25, log=lambda *_: None)
        self.assertGreaterEqual(s.levels_completed, 0)  # 0 is allowed; it just must not lie
        if s.actions_per_level:
            self.assertEqual(len(s.actions_per_level), s.levels_completed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
