#!/usr/bin/env python3
"""Leaderboard playoff/title % by ranking mode."""

from __future__ import annotations

import unittest

from app import (
    _avg_playoff_metric,
    _leaderboard_playoff_pct,
    _leaderboard_title_pct,
)


class LeaderboardPlayoffDisplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.row = {
            "eligibility_pct": 84.1,
            "resume_playoff_eligibility_pct": 63.7,
            "title_odds_pct": 11.78,
            "resume_title_odds_pct": 8.83,
        }

    def test_avg_both(self) -> None:
        self.assertEqual(_avg_playoff_metric(10.0, 20.0), 15.0)

    def test_avg_one_side(self) -> None:
        self.assertEqual(_avg_playoff_metric(10.0, None), 10.0)

    def test_overall_averages_traditional_and_resume(self) -> None:
        self.assertEqual(_leaderboard_playoff_pct(self.row, "overall"), 73.9)
        self.assertEqual(_leaderboard_title_pct(self.row, "overall"), 10.3)

    def test_resume_modes_use_resume_metrics(self) -> None:
        for mode in ("resume", "forecast_resume"):
            self.assertEqual(_leaderboard_playoff_pct(self.row, mode), 63.7)
            self.assertEqual(_leaderboard_title_pct(self.row, mode), 8.83)

    def test_algorithm_uses_traditional(self) -> None:
        self.assertEqual(_leaderboard_playoff_pct(self.row, "algorithm"), 84.1)
        self.assertEqual(_leaderboard_title_pct(self.row, "algorithm"), 11.78)


if __name__ == "__main__":
    unittest.main()
