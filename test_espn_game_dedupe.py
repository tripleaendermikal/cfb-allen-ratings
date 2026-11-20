#!/usr/bin/env python3
"""ESPN duplicate game row handling."""

from __future__ import annotations

import unittest

from cfb_rating.season_data import dedupe_espn_game_rows, load_espn_games
from export_previous_years import records_for_week


class TestEspnGameDedupe(unittest.TestCase):
    def test_dedupe_same_matchup_different_ids(self) -> None:
        rows = [
            {
                "game_id": "1",
                "game_date_utc": "2012-12-01",
                "home_team_id": "61",
                "away_team_id": "333",
                "home_points": "28",
                "away_points": "32",
                "week": "14",
                "home_total_yards": "350",
                "away_total_yards": "350",
            },
            {
                "game_id": "2",
                "game_date_utc": "2012-12-01",
                "home_team_id": "61",
                "away_team_id": "333",
                "home_points": "28",
                "away_points": "32",
                "week": "14",
                "home_total_yards": "350",
                "away_total_yards": "350",
            },
        ]
        self.assertEqual(len(dedupe_espn_game_rows(rows)), 1)

    def test_alabama_2012_postseason_record_after_dedupe(self) -> None:
        from pathlib import Path

        path = Path("/workspace/cfb_data/cfb_2012_espn_games.csv")
        if not path.is_file():
            self.skipTest("2012 games CSV not present locally")
        games = load_espn_games(
            path, fbs_only=False, season_year=2012, single_postseason_week=True
        )
        rec = records_for_week(games, ["333"], 16, record_cap_week=16)["333"]
        self.assertEqual(rec["wins"], 13)
        self.assertEqual(rec["losses"], 1)


if __name__ == "__main__":
    unittest.main()