#!/usr/bin/env python3
"""Single postseason week normalization."""

from __future__ import annotations

import unittest

from cfb_rating.season_data import normalize_espn_rows_single_postseason


class TestSeasonPostseasonWeek(unittest.TestCase):
    def test_december_and_january_bowls_share_postseason_week(self) -> None:
        rows = [
            {"game_date_utc": "2025-12-07", "week": "15"},
            {"game_date_utc": "2025-12-31", "week": "1"},
            {"game_date_utc": "2026-01-10", "week": "1"},
            {"game_date_utc": "2026-01-20", "week": "1"},
        ]
        reg_max, post_week = normalize_espn_rows_single_postseason(rows, 2025)
        self.assertEqual(reg_max, 15)
        self.assertEqual(post_week, 16)
        for row in rows[1:]:
            self.assertEqual(int(row["week"]), 16)


if __name__ == "__main__":
    unittest.main()