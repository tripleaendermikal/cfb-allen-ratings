#!/usr/bin/env python3
"""Tests for per-sim resume margin helpers."""

import unittest

from cfb_rating.sim_resume import build_sim_season_games, compute_sim_resume_margins


class TestSimResume(unittest.TestCase):
    def test_build_sim_season_games_home_rows_only(self):
        rows = [
            {
                "game_id": "g1",
                "team_id": "1",
                "opponent_id": "2",
                "home_away": "home",
                "neutral_site": "false",
                "week": "1",
                "sim_0001": "1",
            },
            {
                "game_id": "g1",
                "team_id": "2",
                "opponent_id": "1",
                "home_away": "away",
                "sim_0001": "0",
            },
        ]
        games = build_sim_season_games(rows, "sim_0001", fbs_team_ids=frozenset({"1", "2"}))
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].home_team_id, "1")
        self.assertGreater(games[0].home_score, games[0].away_score)

    def test_compute_sim_resume_moves_toward_record(self):
        rows = [
            {
                "game_id": "g1",
                "team_id": "1",
                "opponent_id": "2",
                "home_away": "home",
                "neutral_site": "true",
                "sim_0001": "1",
            },
            {
                "game_id": "g2",
                "team_id": "1",
                "opponent_id": "3",
                "home_away": "home",
                "neutral_site": "true",
                "sim_0001": "1",
            },
        ]
        overall = {"1": 5.0, "2": 0.0, "3": -5.0}
        margins = compute_sim_resume_margins(
            rows,
            "sim_0001",
            ["1", "2", "3"],
            overall,
            fbs_team_ids=frozenset({"1", "2", "3"}),
        )
        self.assertIn("1", margins)
        self.assertNotEqual(margins["1"], overall["1"])


if __name__ == "__main__":
    unittest.main()
