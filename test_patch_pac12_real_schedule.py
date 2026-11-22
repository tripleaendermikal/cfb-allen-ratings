#!/usr/bin/env python3
"""Pac-12 flex patch when ESPN Week 13 matchups exist."""

import unittest

from patch_pac12_week13_flex import has_real_week13_matchup


class RealWeek13MatchupTests(unittest.TestCase):
    def test_detects_espn_matchup(self) -> None:
        rows = [
            {
                "week": "13",
                "team_id": "36",
                "opponent_id": "68",
                "opponent_name": "Boise State Broncos",
            }
        ]
        self.assertTrue(has_real_week13_matchup(rows, "36"))
        self.assertFalse(has_real_week13_matchup(rows, "278"))


if __name__ == "__main__":
    unittest.main()