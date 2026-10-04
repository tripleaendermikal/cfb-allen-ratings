#!/usr/bin/env python3
"""Export helpers for Pac-12 Week 13 flex games."""

import unittest

import export_sim_data as esd
from pac12_week13 import FLEX_FLAG_COL, FLEX_FLAG_VALUE, PAC12_FLEX_OPPONENT_ID


class DedupeScheduleFlexTests(unittest.TestCase):
    def test_prefers_real_flex_row_over_placeholder_mirror(self) -> None:
        schedule = [
            {
                "game_id": "401879005",
                "team_id": PAC12_FLEX_OPPONENT_ID,
                "home_away": "home",
                "win_pct": 0.0,
                FLEX_FLAG_COL: "",
            },
            {
                "game_id": "401879005",
                "team_id": "68",
                "home_away": "away",
                "win_pct": 87.2,
                FLEX_FLAG_COL: FLEX_FLAG_VALUE,
            },
        ]
        out = esd.dedupe_schedule(schedule)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["team_id"], "68")
        self.assertAlmostEqual(float(out[0]["win_pct"]), 87.2)


class BuildGamesFlexTests(unittest.TestCase):
    def test_away_flex_team_win_pct_from_team_perspective(self) -> None:
        schedule = [
            {
                "game_id": "401879005",
                "game_date": "",
                "week": 13,
                "team_id": "68",
                "team_name": "Boise State Broncos",
                "conference": "Pac-12",
                "home_away": "away",
                "neutral_site": "False",
                "opponent_id": PAC12_FLEX_OPPONENT_ID,
                "opponent_name": "Pac-12 flex",
                "team_fpi": 9.5,
                "opponent_fpi": None,
                "win_pct": 87.2,
                "avg_margin": 6.5,
                FLEX_FLAG_COL: FLEX_FLAG_VALUE,
            }
        ]
        games = esd.build_games(schedule, {"68": "Pac-12"}, {})
        game = games["401879005"]
        self.assertEqual(game["away_team_id"], "68")
        self.assertEqual(game["home_team_name"], "Pac-12 flex")
        self.assertAlmostEqual(float(game["home_win_pct"]), 12.8)
        self.assertTrue(game["is_pac12_flex"])


if __name__ == "__main__":
    unittest.main()
