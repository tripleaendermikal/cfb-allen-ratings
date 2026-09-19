#!/usr/bin/env python3
"""Tests for real yardage loading in the 2026 schedule path."""

from __future__ import annotations

from cfb_paths import data_root

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cfb_game_corrections import apply_yard_corrections
from cfb_rating.season_data import load_fbs_schedule_games

TEAMS_CSV = data_root() / "espn_cfb_teams_conferences.csv"


def _write_schedule_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "game_id",
        "season_year",
        "week",
        "team_id",
        "opponent_id",
        "home_away",
        "team_score",
        "opponent_score",
        "game_completed",
        "team_yards",
        "opponent_yards",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestSeasonDataYards(unittest.TestCase):
    def test_loader_uses_csv_yards_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            games_path = Path(tmp) / "games.csv"
            _write_schedule_csv(
                games_path,
                [
                    {
                        "game_id": "999",
                        "season_year": "2026",
                        "week": "1",
                        "team_id": "130",
                        "opponent_id": "2711",
                        "home_away": "home",
                        "team_score": "7",
                        "opponent_score": "12",
                        "game_completed": "True",
                        "team_yards": "229",
                        "opponent_yards": "221",
                    },
                    {
                        "game_id": "999",
                        "season_year": "2026",
                        "week": "1",
                        "team_id": "2711",
                        "opponent_id": "130",
                        "home_away": "away",
                        "team_score": "12",
                        "opponent_score": "7",
                        "game_completed": "True",
                        "team_yards": "221",
                        "opponent_yards": "229",
                    },
                ],
            )
            with patch("cfb_rating.season_data.load_corrections", return_value={}):
                games = load_fbs_schedule_games(
                    games_path,
                    teams_path=TEAMS_CSV,
                )
            self.assertEqual(len(games), 1)
            game = games[0]
            self.assertEqual(game.home_yards, 229.0)
            self.assertEqual(game.away_yards, 221.0)

    def test_loader_falls_back_to_estimate_when_yards_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            games_path = Path(tmp) / "games.csv"
            _write_schedule_csv(
                games_path,
                [
                    {
                        "game_id": "999",
                        "season_year": "2026",
                        "week": "1",
                        "team_id": "130",
                        "opponent_id": "2711",
                        "home_away": "home",
                        "team_score": "7",
                        "opponent_score": "12",
                        "game_completed": "True",
                        "team_yards": "",
                        "opponent_yards": "",
                    },
                ],
            )
            with patch("cfb_rating.season_data.load_corrections", return_value={}):
                games = load_fbs_schedule_games(
                    games_path,
                    teams_path=TEAMS_CSV,
                )
            game = games[0]
            self.assertEqual(game.home_yards, 7.0 * 15.5)
            self.assertEqual(game.away_yards, 12.0 * 15.5)

    def test_loader_applies_yard_corrections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            games_path = Path(tmp) / "games.csv"
            _write_schedule_csv(
                games_path,
                [
                    {
                        "game_id": "401858428",
                        "season_year": "2026",
                        "week": "1",
                        "team_id": "130",
                        "opponent_id": "2711",
                        "home_away": "home",
                        "team_score": "7",
                        "opponent_score": "12",
                        "game_completed": "True",
                        "team_yards": "276",
                        "opponent_yards": "221",
                    },
                ],
            )
            corrections = {
                "401858428": {"home_yards": 229, "away_yards": 221},
            }
            with patch(
                "cfb_rating.season_data.load_corrections",
                return_value=corrections,
            ):
                games = load_fbs_schedule_games(
                    games_path,
                    teams_path=TEAMS_CSV,
                )
            game = games[0]
            self.assertEqual(game.home_yards, 229.0)
            self.assertEqual(game.away_yards, 221.0)

    def test_apply_yard_corrections_maps_home_and_away_rows(self) -> None:
        rows = [
            {
                "game_id": "401858428",
                "home_away": "home",
                "team_yards": "276",
                "opponent_yards": "221",
            },
            {
                "game_id": "401858428",
                "home_away": "away",
                "team_yards": "221",
                "opponent_yards": "276",
            },
        ]
        corrections = {"401858428": {"home_yards": 229, "away_yards": 221}}
        applied = apply_yard_corrections(rows, corrections)
        self.assertEqual(applied, ["401858428"])
        self.assertEqual(rows[0]["team_yards"], "229")
        self.assertEqual(rows[0]["opponent_yards"], "221")
        self.assertEqual(rows[1]["team_yards"], "221")
        self.assertEqual(rows[1]["opponent_yards"], "229")


if __name__ == "__main__":
    unittest.main()
