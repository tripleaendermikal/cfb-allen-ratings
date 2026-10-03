#!/usr/bin/env python3
"""Tests for No Preseason (algorithm) margin clamping."""

import unittest

from cfb_rating.in_season import clamp_algorithm_margin


class ClampAlgorithmMarginTests(unittest.TestCase):
    def test_no_upper_cap_by_default(self) -> None:
        self.assertEqual(clamp_algorithm_margin(55.0), 55.0)
        self.assertEqual(clamp_algorithm_margin(100.0), 100.0)

    def test_floor_at_negative_forty(self) -> None:
        self.assertEqual(clamp_algorithm_margin(-50.0), -40.0)

    def test_optional_max_margin_override(self) -> None:
        self.assertEqual(clamp_algorithm_margin(50.0, max_margin=40.0), 40.0)


if __name__ == "__main__":
    unittest.main()
