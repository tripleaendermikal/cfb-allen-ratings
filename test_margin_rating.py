#!/usr/bin/env python3
"""Tests for margin rating (No Preseason pre-standardization)."""

from __future__ import annotations

import math
import unittest

from cfb_rating.margin_rating import compute_margin_ratings, compute_r


class ComputeRTests(unittest.TestCase):
    def test_median_game_score_is_zero(self) -> None:
        self.assertEqual(compute_r(0.5), 0.0)

    def test_above_median(self) -> None:
        self.assertAlmostEqual(compute_r(1.0), 1.0 / 3.0)

    def test_below_median(self) -> None:
        self.assertAlmostEqual(compute_r(0.25), -0.25 / 0.75)


class ComputeMarginRatingsTests(unittest.TestCase):
    def test_all_teams_at_median_yield_zero_margin(self) -> None:
        ratings = {"a": 0.5, "b": 0.5, "c": 0.5}
        results = compute_margin_ratings(ratings)
        for row in results.values():
            self.assertEqual(row.r, 0.0)
            self.assertEqual(row.rs, 0.0)
            self.assertEqual(row.margin_rating, 0.0)

    def test_two_team_standardization(self) -> None:
        ratings = {"high": 1.0, "low": 0.25}
        results = compute_margin_ratings(ratings)
        r_high = compute_r(1.0)
        r_low = compute_r(0.25)
        r_mean = (r_high + r_low) / 2
        r_std = math.sqrt(
            ((r_high - r_mean) ** 2 + (r_low - r_mean) ** 2) / 2
        )
        self.assertAlmostEqual(results["high"].r, r_high)
        self.assertAlmostEqual(results["low"].r, r_low)
        self.assertAlmostEqual(results["high"].rs, r_high / r_std)
        self.assertAlmostEqual(results["low"].rs, r_low / r_std)
        self.assertAlmostEqual(results["high"].margin_rating, results["high"].rs * 14.0)


if __name__ == "__main__":
    unittest.main()
