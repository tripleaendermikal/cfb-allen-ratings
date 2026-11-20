#!/usr/bin/env python3
"""Postseason week renumbering in bootstrap_prior_season_data."""

import unittest

from bootstrap_prior_season_data import renumber_postseason_weeks


class TestPostseasonWeekRenumber(unittest.TestCase):
    def test_january_games_placed_after_regular_season(self) -> None:
        games = {
            "a": {
                "game_id": "a",
                "game_date_utc": "2025-09-01",
                "week": "1",
            },
            "b": {
                "game_id": "b",
                "game_date_utc": "2025-12-07",
                "week": "15",
            },
            "c": {
                "game_id": "c",
                "game_date_utc": "2026-01-10",
                "week": "1",
            },
        }
        n = renumber_postseason_weeks(games, 2025)
        self.assertEqual(n, 1)
        self.assertEqual(int(games["c"]["week"]), 16)
        self.assertEqual(int(games["b"]["week"]), 15)

    def test_multiple_postseason_games_share_one_week(self) -> None:
        games = {
            "a": {
                "game_id": "a",
                "game_date_utc": "2025-12-07",
                "week": "15",
            },
            "b": {
                "game_id": "b",
                "game_date_utc": "2026-01-10",
                "week": "1",
            },
            "c": {
                "game_id": "c",
                "game_date_utc": "2026-01-20",
                "week": "1",
            },
        }
        n = renumber_postseason_weeks(games, 2025)
        self.assertEqual(n, 2)
        self.assertEqual(int(games["b"]["week"]), 16)
        self.assertEqual(int(games["c"]["week"]), 16)


if __name__ == "__main__":
    unittest.main()