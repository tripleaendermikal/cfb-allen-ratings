#!/usr/bin/env python3
"""Historical WAC and legacy conference membership."""

from __future__ import annotations

import unittest

from build_historical_team_conferences import conference_from_standing, fetch_season_conferences


class TestWacHistoricalConferences(unittest.TestCase):
    def test_standing_summary_wac(self) -> None:
        self.assertEqual(conference_from_standing("1st in WAC"), "WAC")

    def test_boise_wac_2009(self) -> None:
        mapping = fetch_season_conferences(2009, sleep_s=0.05)
        self.assertEqual(mapping.get("68"), "WAC")


if __name__ == "__main__":
    unittest.main()