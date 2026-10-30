from __future__ import annotations

import unittest

from arc3_local_candidate.scorecard import audit_benchmark, game_score, level_score


class ScorecardTests(unittest.TestCase):
    def test_incomplete_level_scores_zero(self) -> None:
        self.assertEqual(level_score(20, 1, completed=False), 0.0)

    def test_completed_level_uses_squared_action_efficiency(self) -> None:
        self.assertEqual(level_score(15, 30, completed=True), 25.0)

    def test_completed_level_is_capped_at_115(self) -> None:
        self.assertEqual(level_score(30, 1, completed=True), 115.0)

    def test_game_score_is_level_weighted_and_completion_capped(self) -> None:
        score = game_score([10, 20], [10, 0], levels_completed=1)
        self.assertAlmostEqual(score, 100.0 / 3.0)

    def test_full_completion_can_reach_100_but_not_exceed_it(self) -> None:
        score = game_score([100, 100], [1, 1], levels_completed=2)
        self.assertEqual(score, 100.0)

    def test_audit_recomputes_reported_scores_and_counts_tokens(self) -> None:
        document = {
            "label": "unit-test",
            "game_runs": [
                {
                    "game_id": "g1",
                    "number_of_levels": 2,
                    "base_actions_per_level": [10, 20],
                    "actions_per_level": [10, 0],
                    "levels_completed": 1,
                    "final_score": 100.0 / 3.0,
                    "state": "cancelled",
                    "final_wallclock_seconds": 12.5,
                    "history": [{"generated_tokens": 4}, {"generated_tokens": 6}],
                },
                {
                    "game_id": "g2",
                    "number_of_levels": 1,
                    "base_actions_per_level": [10],
                    "actions_per_level": [10],
                    "levels_completed": 1,
                    "final_score": 100.0,
                    "state": "won",
                    "final_wallclock_seconds": 5,
                    "history": [{"generated_tokens": 7}],
                },
            ],
        }
        result = audit_benchmark(document)
        self.assertEqual(result["games"], 2)
        self.assertAlmostEqual(result["mean_score_recomputed"], (100.0 / 3.0 + 100.0) / 2.0)
        self.assertEqual(result["score_mismatch_count"], 0)
        self.assertEqual(result["completed_levels"], 2)
        self.assertEqual(result["generated_tokens"], 17)
        self.assertEqual(result["wins"], 1)

    def test_score_mismatch_is_reported(self) -> None:
        result = audit_benchmark(
            {
                "game_runs": [
                    {
                        "game_id": "bad",
                        "number_of_levels": 1,
                        "base_actions_per_level": [10],
                        "actions_per_level": [10],
                        "levels_completed": 1,
                        "final_score": 0,
                    }
                ]
            }
        )
        self.assertEqual(result["score_mismatch_count"], 1)
        self.assertEqual(result["games_with_score_mismatch"], ["bad"])


if __name__ == "__main__":
    unittest.main()
