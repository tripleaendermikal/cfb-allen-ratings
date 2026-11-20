#!/usr/bin/env python3
"""Historical conference lookup."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cfb_historical_conferences as hist


class TestHistoricalConferences(unittest.TestCase):
    def test_conference_for_season_uses_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "historical_team_conferences.json"
            path.write_text(
                json.dumps(
                    {
                        "seasons": {
                            "2021": {"201": "Big 12"},
                            "2024": {"201": "SEC"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(hist, "HISTORICAL_JSON", path):
                hist._load_historical.cache_clear()
                self.assertEqual(
                    hist.conference_for_season("201", "SEC", 2021),
                    "Big 12",
                )
                self.assertEqual(
                    hist.conference_for_season("201", "Big 12", 2024),
                    "SEC",
                )
                hist._load_historical.cache_clear()


if __name__ == "__main__":
    unittest.main()