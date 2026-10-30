"""Tests for the action-efficiency meter and the completion/efficiency split.

Both tools exist to answer one competition question — "did this change move the
number that is scored?" — so the tests pin the arithmetic against the scorecard
module and pin the ship gate, including the cases that must *refuse* to ship.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from arc3_local_candidate.scorecard import game_score
from arc3_local_candidate.tools.action_efficiency import (
    compare, game_report, run_report, summarise,
)
from arc3_local_candidate.tools.score_decomposition import decompose, game_terms


def run(game_id="ls20", bases=(10, 20, 40), actions=(10, 40, 0),
        completed=2, total=None, score=None):
    return {
        "game_id": game_id,
        "base_actions_per_level": list(bases),
        "actions_per_level": list(actions),
        "levels_completed": completed,
        "number_of_levels": total if total is not None else len(bases),
        "final_score": score,
    }


def write(tmp: Path, name: str, runs) -> Path:
    path = tmp / name
    path.write_text(json.dumps({"game_runs": runs}))
    return path


class ActionEfficiencyTests(unittest.TestCase):
    def test_per_level_ratio_and_score(self):
        report = game_report(run())
        levels = report["levels"]
        self.assertEqual([lvl["level"] for lvl in levels], [1, 2])
        self.assertAlmostEqual(levels[0]["ratio_human_to_ai"], 1.0)
        self.assertAlmostEqual(levels[1]["ratio_human_to_ai"], 0.5)
        # 0.5 ** 2 * 100 = 25
        self.assertAlmostEqual(levels[1]["level_score"], 25.0)
        self.assertAlmostEqual(report["score_recomputed"], game_score(
            [10, 20, 40], [10, 40, 0], levels_completed=2))

    def test_unsolved_levels_are_not_counted_as_levels(self):
        report = game_report(run())
        self.assertEqual(report["levels_completed"], 2)
        self.assertEqual(len(report["levels"]), 2)
        self.assertEqual(report["actions_per_completed_level_median"], 25.0)

    def test_hidden_baseline_leaves_the_score_unknown(self):
        report = game_report(run(bases=(), actions=(7,), completed=1, total=3))
        self.assertFalse(report["has_human_baseline"])
        self.assertIsNone(report["score_recomputed"])
        self.assertIsNone(report["levels"][0]["level_score"])
        self.assertEqual(report["actions_per_completed_level_median"], 7.0)

    def test_zero_actions_on_a_completed_level_hits_the_cap(self):
        report = game_report(run(bases=(10,), actions=(0,), completed=1, total=1))
        self.assertEqual(report["levels"][0]["level_score"], 115.0)

    def test_pooled_summary_matches_the_games(self):
        reports = [game_report(run("a", actions=(10, 20, 0), completed=2)),
                   game_report(run("b", actions=(60,), completed=1, bases=(10,)))]
        summary = summarise(reports)
        self.assertEqual(summary["games"], 2)
        self.assertEqual(summary["completed_levels"], 3)
        self.assertEqual(summary["actions_per_completed_level_median"], 20.0)
        self.assertEqual(summary["actions_total"], 90)

    def test_run_report_reads_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp), "b.json", [run()])
            report = run_report(path)
        self.assertEqual(report["summary"]["games"], 1)
        self.assertEqual(report["source"], str(path))


class ShipGateTests(unittest.TestCase):
    def test_refuses_when_the_score_does_not_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = write(Path(tmp), "before.json", [run()])
            after = write(Path(tmp), "after.json", [run()])
            result = compare(before, after)
        self.assertFalse(result["ship"])
        self.assertEqual(result["verdict"], "DO NOT SHIP")
        self.assertTrue(any("did not improve" in reason for reason in result["reasons"]))

    def test_refuses_when_more_actions_win_a_score_tie(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = write(Path(tmp), "before.json", [run(actions=(10, 20, 0), completed=2)])
            after = write(Path(tmp), "after.json", [run(actions=(30, 40, 0), completed=2)])
            result = compare(before, after)
        self.assertFalse(result["ship"])
        self.assertGreater(result["median_actions_delta"], 0)

    def test_ships_when_the_score_rises_and_completion_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = write(Path(tmp), "before.json", [run(actions=(40, 40, 0), completed=2)])
            after = write(Path(tmp), "after.json", [run(actions=(10, 20, 0), completed=2)])
            result = compare(before, after)
        self.assertTrue(result["ship"], result)
        self.assertEqual(result["verdict"], "SHIP")
        self.assertGreater(result["score_delta"], 0)
        self.assertLess(result["median_actions_delta"], 0)

    def test_refuses_when_completion_falls(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = write(Path(tmp), "before.json", [run(completed=2)])
            after = write(Path(tmp), "after.json", [run(completed=1)])
            result = compare(before, after)
        self.assertFalse(result["ship"])
        self.assertEqual(result["completed_levels_delta"], -1)

    def test_uncomparable_without_a_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = write(Path(tmp), "before.json", [run()])
            after = write(Path(tmp), "after.json",
                          [run(bases=(), actions=(10, 20, 0), completed=2)])
            result = compare(before, after)
        self.assertFalse(result["ship"])
        self.assertTrue(any("not comparable" in reason for reason in result["reasons"]))


class DecompositionTests(unittest.TestCase):
    def test_split_of_a_half_finished_game(self):
        terms = game_terms(run())
        self.assertTrue(terms["usable"])
        self.assertAlmostEqual(terms["completion_pct"], round(3 / 6 * 100, 2))
        # efficiency 100% on level 1 (weight 1), 25% on level 2 (weight 2)
        self.assertAlmostEqual(terms["efficiency_pct"], round((100 + 50) / 3, 2))
        self.assertAlmostEqual(terms["actual"], terms["efficiency_pct"] * 50 / 100, places=2)
        self.assertAlmostEqual(terms["ceiling_human_efficiency_same_completion"], 50.0)
        self.assertAlmostEqual(terms["ceiling_full_completion_observed_efficiency"], 50.0)

    def test_a_game_that_finished_nothing_still_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp), "b.json", [run("won", completed=2),
                                               run("lost", actions=(900, 900, 900), completed=0)])
            summary = decompose([r for r in json.loads(path.read_text())["game_runs"]] if False else
                                [run("won", completed=2), run("lost", actions=(900,) * 3, completed=0)])["summary"]
        self.assertEqual(summary["games"], 2)
        self.assertGreater(summary["ceiling_full_completion_observed_efficiency"], 0)
        # dropping the lost game would leave exactly the won game's score
        self.assertLess(summary["actual"], game_terms(run("won", completed=2))["actual"])

    def test_game_without_a_baseline_is_skipped(self):
        result = decompose([run("nobase", bases=(), actions=(5,), completed=1, total=3)])
        self.assertEqual(result["games"], [])
        self.assertEqual(result["skipped_no_baseline"], 1)
        self.assertIn("error", result)

    def test_completion_is_the_binding_constraint_on_a_stalling_run(self):
        result = decompose([run("a", bases=(10, 10, 10, 10), actions=(10, 30, 0, 0), completed=2)])
        summary = result["summary"]
        self.assertEqual(summary["binding_constraint"], "completion")
        self.assertGreater(summary["headroom_from_completion"], summary["headroom_from_efficiency"])

    def test_efficiency_is_binding_when_completion_is_nearly_full(self):
        result = decompose([run("a", bases=(10, 10, 20, 20),
                                actions=(200, 200, 400, 400), completed=4)])
        summary = result["summary"]
        self.assertEqual(summary["binding_constraint"], "action efficiency")
        self.assertGreater(summary["headroom_from_efficiency"], summary["headroom_from_completion"])

    def test_reported_score_is_reproduced(self):
        """The split must not invent its own arithmetic."""
        for bases, actions, completed in (
            ((10, 20, 40), (10, 40, 0), 2),
            ((10,), (5,), 1),
            ((30, 100, 200, 400), (90, 500, 0, 0), 2),
        ):
            terms = game_terms(run(bases=bases, actions=actions, completed=completed))
            expected = game_score(list(bases), list(actions), levels_completed=completed)
            self.assertAlmostEqual(terms["actual"], round(expected, 3), places=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
