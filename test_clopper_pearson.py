"""Tests for Clopper–Pearson confidence intervals."""

from __future__ import annotations

import math
import unittest

from cfb_rating.clopper_pearson import (
    clopper_pearson,
    clopper_pearson_midpoint,
)


class ClopperPearsonTests(unittest.TestCase):
    def test_perfect_record_50_percent_midpoint(self) -> None:
        mid = clopper_pearson_midpoint(10, 10, confidence=0.5)
        lower = 0.25**0.1
        self.assertAlmostEqual(mid, (lower + 1.0) / 2, places=10)

    def test_perfect_record_50_percent(self) -> None:
        ci = clopper_pearson(10, 10, confidence=0.5)
        expected_lower = 0.25**0.1
        self.assertAlmostEqual(ci.lower, expected_lower, places=10)
        self.assertEqual(ci.upper, 1.0)

    def test_zero_successes_95(self) -> None:
        ci = clopper_pearson(0, 10, confidence=0.95)
        self.assertEqual(ci.lower, 0.0)
        self.assertLess(ci.upper, 0.5)

    def test_symmetry_half_successes(self) -> None:
        ci = clopper_pearson(5, 10, confidence=0.95)
        self.assertAlmostEqual(ci.point_estimate, 0.5)
        self.assertLess(ci.lower, 0.5)
        self.assertGreater(ci.upper, 0.5)

    def test_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            clopper_pearson(11, 10, confidence=0.95)
        with self.assertRaises(ValueError):
            clopper_pearson(1, 10, confidence=1.0)


if __name__ == "__main__":
    unittest.main()