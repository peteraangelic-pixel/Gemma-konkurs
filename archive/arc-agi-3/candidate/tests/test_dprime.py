from __future__ import annotations

import unittest

from arc3_local_candidate.dprime import (
    PrioritySnapshot,
    ProgressPace,
    dprime_priority,
    dprime_priority_adapter,
    dprime_value,
    priority_breakdown,
    rank_snapshots,
)


class DPrimeTests(unittest.TestCase):
    def test_fresh_ten_level_game_matches_reference_scale(self) -> None:
        state = PrioritySnapshot(level=1, total_levels=10)
        self.assertAlmostEqual(dprime_value(state), 17.0)
        self.assertEqual(dprime_priority(state), 17_000)

    def test_fresh_game_has_no_unconditional_queue_boost(self) -> None:
        fresh_six = PrioritySnapshot(level=1, total_levels=6)
        expected = int((55 / 21 + 16) * 1000)
        self.assertEqual(dprime_priority(fresh_six), expected)
        self.assertEqual(rank_snapshots([fresh_six]), [fresh_six])

    def test_progress_to_deeper_level_raises_priority(self) -> None:
        level_one = PrioritySnapshot(level=1, actions=0, tokens=0, total_levels=10)
        level_three = PrioritySnapshot(level=3, actions=0, tokens=0, total_levels=10)
        self.assertGreater(dprime_value(level_three), dprime_value(level_one))

    def test_more_actions_and_tokens_reduce_priority(self) -> None:
        fresh = PrioritySnapshot(level=2, total_levels=8)
        costly_actions = PrioritySnapshot(level=2, actions=115, total_levels=8)
        costly_tokens = PrioritySnapshot(level=2, tokens=225_000, total_levels=8)
        self.assertGreater(dprime_value(fresh), dprime_value(costly_actions))
        self.assertGreater(dprime_value(fresh), dprime_value(costly_tokens))

    def test_tail_fade_only_removes_growth_bonus(self) -> None:
        state = PrioritySnapshot(level=1, total_levels=10)
        full = priority_breakdown(state, tail_fraction=1.0)
        faded = priority_breakdown(state, tail_fraction=0.0)
        self.assertEqual(full.depth_efficiency, faded.depth_efficiency)
        self.assertEqual(full.patience, faded.patience)
        self.assertEqual(full.growth_bonus, 16.0)
        self.assertEqual(faded.value, faded.depth_efficiency * faded.patience)
        self.assertGreater(full.value, faded.value)

    def test_tail_fraction_is_clamped(self) -> None:
        state = PrioritySnapshot(level=1, total_levels=10)
        self.assertEqual(dprime_value(state, tail_fraction=7.0), dprime_value(state, tail_fraction=1.0))
        self.assertEqual(dprime_value(state, tail_fraction=-2.0), dprime_value(state, tail_fraction=0.0))

    def test_pace_changes_efficiency_and_patience_scale(self) -> None:
        base = PrioritySnapshot(level=2, total_levels=8)
        fast = PrioritySnapshot(level=2, total_levels=8, mean_tokens_per_cleared_level=15_000)
        slow = PrioritySnapshot(level=2, total_levels=8, mean_tokens_per_cleared_level=60_000)
        self.assertGreater(dprime_value(fast), dprime_value(base))
        self.assertLess(dprime_value(slow), dprime_value(base))

    def test_unknown_total_level_count_uses_ten_level_fallback(self) -> None:
        self.assertEqual(
            dprime_priority(PrioritySnapshot(level=1, total_levels=None)),
            dprime_priority(PrioritySnapshot(level=1, total_levels=10)),
        )

    def test_ranking_is_descending_and_stable_on_ties(self) -> None:
        low = PrioritySnapshot(level=1, actions=200, total_levels=10)
        high = PrioritySnapshot(level=4, actions=0, total_levels=10)
        tied_a = PrioritySnapshot(level=1, actions=0, total_levels=10)
        tied_b = PrioritySnapshot(level=1, actions=0, total_levels=10)
        ranked = rank_snapshots([low, tied_a, tied_b, high])
        self.assertIs(ranked[0], high)
        self.assertIs(ranked[-1], low)
        self.assertIs(ranked[1], tied_a)
        self.assertIs(ranked[2], tied_b)

    def test_runner_style_adapter_uses_cost_multiplier(self) -> None:
        class RunnerSnapshot:
            level = 2
            actions = 30
            tokens = 10_000
            total_levels = 8
            cost_multiplier = 20_000

        adapted = dprime_priority_adapter(RunnerSnapshot(), tail_fraction=0.5, ignored_flag=True)
        direct = dprime_priority(
            PrioritySnapshot(
                level=2,
                actions=30,
                tokens=10_000,
                total_levels=8,
                mean_tokens_per_cleared_level=20_000,
            ),
            tail_fraction=0.5,
        )
        self.assertEqual(adapted, direct)

    def test_progress_pace_tracks_mean_tokens_per_clear(self) -> None:
        pace = ProgressPace()
        self.assertEqual(pace.cost_multiplier(), 0.0)
        pace.record_completion(10_000)
        pace.record_completion(20_000, reference_tokens=50_000)
        self.assertEqual(pace.cost_multiplier(), 15_000.0)

    def test_bad_numbers_fall_back_safely(self) -> None:
        state = PrioritySnapshot(level=0, actions=float("nan"), tokens=float("inf"), total_levels=-1)
        self.assertGreaterEqual(dprime_priority(state), 1)
        self.assertTrue(0.0 <= priority_breakdown(state, tail_fraction=float("nan")).tail_fraction <= 1.0)


if __name__ == "__main__":
    unittest.main()
