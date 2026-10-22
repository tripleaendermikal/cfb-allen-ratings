#!/usr/bin/env python3
"""Tests for forecast resume enrichment helpers."""

import unittest

from cfb_rating.forecast_resume_enrich import projected_games_from_sim_games


class TestProjectedGamesFromSims(unittest.TestCase):
    def test_counts_sim_results_per_team(self):
        game_rows = [
            {
                "team_id": "1",
                "sim_0001": "1",
                "sim_0002": "0",
            },
            {
                "team_id": "1",
                "sim_0001": "0",
                "sim_0002": "1",
            },
            {
                "team_id": "2",
                "sim_0001": "1",
                "sim_0002": "1",
            },
        ]
        sim_cols = ["sim_0001", "sim_0002"]
        games = projected_games_from_sim_games(game_rows, sim_cols)
        self.assertAlmostEqual(games["1"], 2.0)
        self.assertAlmostEqual(games["2"], 1.0)


if __name__ == "__main__":
    unittest.main()
