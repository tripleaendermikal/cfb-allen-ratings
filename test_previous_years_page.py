#!/usr/bin/env python3
"""Previous Years tab HTTP tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app import create_app


class PreviousYearsPageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        data_dir = Path(self.tmp.name)
        (data_dir / "meta.json").write_text(
            json.dumps({"season_year": 2026, "current_week": 1, "sim_count": 100}),
            encoding="utf-8",
        )
        for name in (
            "leaderboard.json",
            "teams.json",
            "eligibility.json",
            "field_analysis.json",
            "conferences.json",
        ):
            (data_dir / name).write_text("[]", encoding="utf-8")

        (data_dir / "previous_years.json").write_text(
            json.dumps(
                {
                    "seasons": {
                        "2025": {
                            "season_year": 2025,
                            "final_week": 1,
                            "weeks": [1],
                            "by_week": {
                                "1": [
                                    {
                                        "team_id": "194",
                                        "team_name": "Ohio State Buckeyes",
                                        "conference": "Big Ten",
                                        "overall_margin": 25.0,
                                        "resume_margin": 20.0,
                                        "record": "1-0",
                                    }
                                ]
                            },
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        import app as app_module

        self._orig = app_module.DATA_DIR
        app_module.DATA_DIR = data_dir
        self.app = create_app()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        import app as app_module

        app_module.DATA_DIR = self._orig
        self.tmp.cleanup()

    def test_previous_years_renders_200(self) -> None:
        resp = self.client.get("/previous-years?season=2025&week=1")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Ohio State Buckeyes", resp.data)
        self.assertIn(b"Previous Years", resp.data)


if __name__ == "__main__":
    unittest.main()