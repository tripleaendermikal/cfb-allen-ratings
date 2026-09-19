#!/usr/bin/env python3
"""Tests for Overall margin rating weights and blending."""

from __future__ import annotations

import unittest

from cfb_rating.in_season import (
    compute_overall_margin,
    compute_overall_margins_snapshot,
    overall_component_weights,
)


class OverallComponentWeightsTests(unittest.TestCase):
    def test_zero_games(self) -> None:
        self.assertEqual(overall_component_weights(0), (1.0, 0.0, 0.0))

    def test_one_game(self) -> None:
        self.assertAlmostEqual(overall_component_weights(1)[0], 0.85)
        self.assertAlmostEqual(overall_component_weights(1)[1], 0.10)
        self.assertAlmostEqual(overall_component_weights(1)[2], 0.05)

    def test_four_games(self) -> None:
        w_pre, w_some, w_algo = overall_component_weights(4)
        self.assertAlmostEqual(w_pre, 0.49375)
        self.assertAlmostEqual(w_some, 0.3375)
        self.assertAlmostEqual(w_algo, 0.16875)

    def test_six_games(self) -> None:
        w_pre, w_some, w_algo = overall_component_weights(6)
        self.assertAlmostEqual(w_pre, 0.0)
        self.assertAlmostEqual(w_some, 0.6203, places=3)
        self.assertAlmostEqual(w_algo, 0.3797, places=3)

    def test_seven_games(self) -> None:
        w_pre, w_some, w_algo = overall_component_weights(7)
        self.assertAlmostEqual(w_pre, 0.0)
        self.assertAlmostEqual(w_some, 0.4305, places=3)
        self.assertAlmostEqual(w_algo, 0.5695, places=3)

    def test_eight_games(self) -> None:
        w_pre, w_some, w_algo = overall_component_weights(8)
        self.assertAlmostEqual(w_pre, 0.0)
        self.assertAlmostEqual(w_some, 0.1457, places=3)
        self.assertAlmostEqual(w_algo, 0.8543, places=3)

    def test_nine_or_more_games(self) -> None:
        self.assertEqual(overall_component_weights(9), (0.0, 0.0, 1.0))
        self.assertEqual(overall_component_weights(15), (0.0, 0.0, 1.0))


class ComputeOverallMarginTests(unittest.TestCase):
    def test_zero_games_uses_preseason(self) -> None:
        self.assertAlmostEqual(
            compute_overall_margin(24.0, 0.0, 0.0, 0),
            24.0,
        )

    def test_one_game_blend(self) -> None:
        result = compute_overall_margin(30.0, 10.0, 20.0, 1)
        expected = 0.85 * 30.0 + 0.10 * 10.0 + 0.05 * 20.0
        self.assertAlmostEqual(result, expected)

    def test_six_game_blend(self) -> None:
        result = compute_overall_margin(30.0, 10.0, 20.0, 6)
        w_pre, w_some, w_algo = overall_component_weights(6)
        expected = w_pre * 30.0 + w_some * 10.0 + w_algo * 20.0
        self.assertAlmostEqual(result, expected)

    def test_seven_game_blend(self) -> None:
        result = compute_overall_margin(30.0, 10.0, 20.0, 7)
        w_pre, w_some, w_algo = overall_component_weights(7)
        expected = w_pre * 30.0 + w_some * 10.0 + w_algo * 20.0
        self.assertAlmostEqual(result, expected)

    def test_nine_plus_uses_algorithm_only(self) -> None:
        self.assertAlmostEqual(
            compute_overall_margin(30.0, 10.0, 20.0, 9),
            20.0,
        )


class OverallSnapshotTests(unittest.TestCase):
    def test_empty_games_equals_preseason(self) -> None:
        preseason = {"1": 25.0, "2": 15.0}
        margins = compute_overall_margins_snapshot(
            [],
            through_week=1,
            team_ids=["1", "2"],
            preseason_margins=preseason,
        )
        self.assertAlmostEqual(margins["1"], 25.0)
        self.assertAlmostEqual(margins["2"], 15.0)


if __name__ == "__main__":
    unittest.main()
