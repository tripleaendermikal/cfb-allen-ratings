#!/usr/bin/env python3
"""Tests that in-season static FPI columns are patched to Overall margins."""

from __future__ import annotations

import unittest

from add_fpi_sim_columns import apply_overall_to_rows


class ApplyOverallToRowsTests(unittest.TestCase):
    def test_patches_team_and_opponent_fpi(self) -> None:
        rows = [
            {
                "team_id": "194",
                "opponent_id": "87",
                "team_fpi": "29.131",
                "opponent_fpi": "24.636",
            },
            {
                "team_id": "87",
                "opponent_id": "194",
                "team_fpi": "24.636",
                "opponent_fpi": "29.131",
            },
        ]
        overall = {"194": 28.2115824753, "87": 24.636}
        changed = apply_overall_to_rows(rows, overall)
        self.assertEqual(changed, 1)
        self.assertAlmostEqual(float(rows[0]["team_fpi"]), 28.212, places=3)
        self.assertAlmostEqual(float(rows[0]["opponent_fpi"]), 24.636, places=3)
        self.assertAlmostEqual(float(rows[1]["team_fpi"]), 24.636, places=3)
        self.assertAlmostEqual(float(rows[1]["opponent_fpi"]), 28.212, places=3)

    def test_leaves_unknown_opponent_unchanged(self) -> None:
        rows = [
            {
                "team_id": "194",
                "opponent_id": "-3",
                "team_fpi": "29.131",
                "opponent_fpi": "",
            },
        ]
        overall = {"194": 28.2115824753}
        apply_overall_to_rows(rows, overall)
        self.assertAlmostEqual(float(rows[0]["team_fpi"]), 28.212, places=3)
        self.assertEqual(rows[0]["opponent_fpi"], "")


if __name__ == "__main__":
    unittest.main()
