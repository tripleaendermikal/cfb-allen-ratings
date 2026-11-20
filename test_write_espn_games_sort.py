#!/usr/bin/env python3
"""Bootstrap ESPN games CSV sort key."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bootstrap_prior_season_data import write_espn_games


class TestWriteEspnGamesSort(unittest.TestCase):
    def test_sort_handles_string_and_int_weeks(self) -> None:
        games = {
            "a": {
                "game_id": "a",
                "season": "2013",
                "week": "2",
                "game_date_utc": "2013-09-07",
                "neutral_site": False,
                "home_team_id": "1",
                "home_team": "A",
                "home_points": 21,
                "home_total_yards": 400,
                "away_team_id": "2",
                "away_team": "B",
                "away_points": 14,
                "away_total_yards": 350,
            },
            "b": {
                "game_id": "b",
                "season": "2013",
                "week": 10,
                "game_date_utc": "2013-11-01",
                "neutral_site": False,
                "home_team_id": "1",
                "home_team": "A",
                "home_points": 7,
                "home_total_yards": 300,
                "away_team_id": "2",
                "away_team": "B",
                "away_points": 3,
                "away_total_yards": 280,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "games.csv"
            n = write_espn_games(path, games)
            self.assertEqual(n, 2)


if __name__ == "__main__":
    unittest.main()