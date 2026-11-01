#!/usr/bin/env python3
"""Tests for mean sim forecast resume."""

import unittest

from cfb_rating.forecast_resume_enrich import mean_sim_forecast_resume_for_overall
from cfb_rating.sim_resume import build_sim_season_games


class TestMeanSimForecastResume(unittest.TestCase):
    def test_averages_per_sim_resume(self):
        game_rows = [
            {
                "game_id": "g1",
                "team_id": "1",
                "opponent_id": "2",
                "home_away": "home",
                "sim_0001": "1",
                "sim_0002": "0",
            },
            {
                "game_id": "g2",
                "team_id": "2",
                "opponent_id": "1",
                "home_away": "away",
                "sim_0001": "0",
                "sim_0002": "1",
            },
        ]
        overall = {"1": 10.0, "2": 0.0}
        sim_cols = ["sim_0001", "sim_0002"]
        season_by_col = {
            col: build_sim_season_games(game_rows, col) for col in sim_cols
        }
        margins = mean_sim_forecast_resume_for_overall(
            season_by_col, sim_cols, ["1", "2"], overall
        )
        self.assertEqual(set(margins.keys()), {"1", "2"})
        # Team 1 wins sim_0001 and loses sim_0002; mean resume should sit between extremes.
        self.assertGreater(margins["1"], overall["2"])
        self.assertLess(margins["1"], overall["1"] + 5.0)


if __name__ == "__main__":
    unittest.main()
