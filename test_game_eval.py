#!/usr/bin/env python3
"""Tests for pace-adjusted game evaluation."""

from __future__ import annotations

import unittest
from math import exp, log

from cfb_rating.constants import (
    POINTS_EXPONENT,
    POINTS_INTERCEPT,
    POINTS_LN_COEFF,
    POINTS_MULTIPLIER,
    POINTS_WEIGHT,
    YARDS_EXPONENT,
    YARDS_INTERCEPT,
    YARDS_LN_COEFF,
    YARDS_MULTIPLIER,
    YARDS_WEIGHT,
)
from cfb_rating.game_eval import evaluate_game, evaluate_points_margin, evaluate_yards_margin


class EvaluatePointsMarginTests(unittest.TestCase):
    def test_tie_game_splits_weight_evenly(self) -> None:
        result = evaluate_points_margin(21, 21)
        self.assertAlmostEqual(result.adj_margin, 0.0)
        self.assertAlmostEqual(result.home_point_score_ratio, 0.5)
        self.assertAlmostEqual(result.home_point_score, 0.5 * POINTS_WEIGHT)

    def test_blowout_pushes_home_ratio_high(self) -> None:
        result = evaluate_points_margin(48, 10)
        self.assertGreater(result.home_point_score_ratio, 0.98)
        self.assertLess(result.away_point_score_ratio, 0.02)

    def test_multiplier_affects_sigmoid(self) -> None:
        home_score, away_score = 35, 14
        total = home_score + away_score
        pace = POINTS_LN_COEFF * log(total) - POINTS_INTERCEPT
        adj_margin = (home_score - away_score) / pace

        with_multiplier = evaluate_points_margin(home_score, away_score)
        unscaled_exp = exp(POINTS_EXPONENT * adj_margin * 2)
        unscaled_ratio = unscaled_exp / (1 + unscaled_exp)

        self.assertGreater(with_multiplier.home_point_score_ratio, unscaled_ratio)


class EvaluateYardsMarginTests(unittest.TestCase):
    def test_tie_game_splits_weight_evenly(self) -> None:
        result = evaluate_yards_margin(400, 400)
        self.assertAlmostEqual(result.adj_yards_margin, 0.0)
        self.assertAlmostEqual(result.home_yards_score_ratio, 0.5)
        self.assertAlmostEqual(result.home_yards_score, 0.5 * YARDS_WEIGHT)

    def test_multiplier_affects_sigmoid(self) -> None:
        home_yards, away_yards = 500, 250
        total = home_yards + away_yards
        pace = YARDS_LN_COEFF * log(total) - YARDS_INTERCEPT
        adj_yards_margin = (home_yards - away_yards) / pace

        with_multiplier = evaluate_yards_margin(home_yards, away_yards)
        unscaled_exp = exp(YARDS_EXPONENT * adj_yards_margin * 2)
        unscaled_ratio = unscaled_exp / (1 + unscaled_exp)

        self.assertGreater(with_multiplier.home_yards_score_ratio, unscaled_ratio)


class EvaluateGameTests(unittest.TestCase):
    def test_stronger_team_gets_higher_game_score(self) -> None:
        result = evaluate_game(35, 10, 500, 300, 0.6, 0.4)
        self.assertGreater(result.home_game_score, result.away_game_score)

    def test_avail_points_scales_combined_score(self) -> None:
        low = evaluate_game(28, 21, 450, 400, 0.25, 0.25)
        high = evaluate_game(28, 21, 450, 400, 0.5, 0.5)
        self.assertAlmostEqual(high.home_game_score, low.home_game_score * 2.0)


if __name__ == "__main__":
    unittest.main()
