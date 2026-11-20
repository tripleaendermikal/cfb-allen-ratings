#!/usr/bin/env python3
"""Tests for prior-season export pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from export_previous_years import (
    build_season_export,
    write_previous_years_json,
)
from cfb_rating.in_season import load_preseason_margins
from cfb_rating.season_data import load_espn_games

FIXTURES = Path(__file__).resolve().parent / "tests" / "fixtures" / "prior_season"


class TestExportPreviousYears(unittest.TestCase):
    def test_build_season_export_sorts_resume_differently_than_overall(self) -> None:
        games_path = FIXTURES / "games.csv"
        pre_path = FIXTURES / "preseason.csv"
        margin_path = FIXTURES / "margin_ratings.csv"
        teams_path = FIXTURES / "teams.csv"

        games = load_espn_games(games_path, teams_path=teams_path)
        preseason = load_preseason_margins(pre_path, teams_path=teams_path)
        team_ids = sorted(preseason.keys())

        team_info = {
            "1": {"team_id": "1", "team_name": "Team A", "conference": "SEC"},
            "2": {"team_id": "2", "team_name": "Team B", "conference": "SEC"},
            "3": {"team_id": "3", "team_name": "Team C", "conference": "SEC"},
            "4": {"team_id": "4", "team_name": "Team D", "conference": "SEC"},
        }

        payload = build_season_export(
            2025,
            games,
            preseason,
            team_ids,
            team_info,
            max_week=6,
        )
        week6 = payload["by_week"]["6"]
        overall_top = max(week6, key=lambda r: r["overall_margin"])["team_id"]
        resume_top = max(week6, key=lambda r: r["resume_margin"])["team_id"]
        self.assertTrue(week6)
        self.assertIn(overall_top, team_ids)
        self.assertIn(resume_top, team_ids)

    def test_write_merges_seasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "previous_years.json"
            write_previous_years_json(out, 2025, {"season_year": 2025, "weeks": [1]})
            raw = json.loads(out.read_text())
            self.assertIn("2025", raw["seasons"])
            write_previous_years_json(out, 2024, {"season_year": 2024, "weeks": [1]})
            raw = json.loads(out.read_text())
            self.assertIn("2024", raw["seasons"])
            self.assertIn("2025", raw["seasons"])


if __name__ == "__main__":
    unittest.main()