#!/usr/bin/env python3
"""Tests for No Preseason (algorithm) margin clamping."""

import unittest

from cfb_rating.in_season import (
    algorithm_margin_ceiling,
    clamp_algorithm_margin,
)


class ClampAlgorithmMarginTests(unittest.TestCase):
    def test_ceiling_grows_with_games_played(self) -> None:
        self.assertEqual(algorithm_margin_ceiling(0), 30.0)
        self.assertEqual(algorithm_margin_ceiling(4), 34.0)

    def test_upper_cap_by_games_played(self) -> None:
        self.assertEqual(clamp_algorithm_margin(55.0, fbs_games_played=4), 34.0)
        self.assertEqual(clamp_algorithm_margin(34.0, fbs_games_played=4), 34.0)

    def test_floor_at_negative_forty(self) -> None:
        self.assertEqual(clamp_algorithm_margin(-50.0), -40.0)

    def test_optional_max_margin_override(self) -> None:
        self.assertEqual(
            clamp_algorithm_margin(50.0, max_margin=40.0, fbs_games_played=10),
            40.0,
        )


if __name__ == "__main__":
    unittest.main()
