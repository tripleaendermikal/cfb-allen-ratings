#!/usr/bin/env python3
"""Conference pages use overall playoff/title display odds."""

from __future__ import annotations

import unittest
from pathlib import Path

from app import DataStore, prepare_conference


class ConferenceOverallOddsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DataStore(Path(__file__).resolve().parent / "data")

    def test_conference_team_odds_match_overall_leaderboard(self) -> None:
        week = int(self.store.meta.get("current_week") or 0)
        lb_by_id = {
            row["team_id"]: row
            for row in self.store.leaderboard_for_week(week, ranking_mode="overall")
        }
        conf = next(c for c in self.store.conferences if c.get("teams"))
        prepared = prepare_conference(conf, self.store)
        for team in prepared["teams"]:
            tid = team["team_id"]
            lb_row = lb_by_id.get(tid)
            if not lb_row:
                continue
            self.assertEqual(team["playoff_field_pct"], lb_row["display_playoff_pct"])
            self.assertEqual(team["title_odds_pct"], lb_row["display_title_pct"])

    def test_total_title_odds_is_sum_of_team_display(self) -> None:
        conf = self.store.conferences[0]
        prepared = prepare_conference(conf, self.store)
        expected = round(
            sum(float(t.get("title_odds_pct") or 0) for t in prepared["teams"]),
            2,
        )
        self.assertEqual(prepared["total_title_odds_pct"], expected)


if __name__ == "__main__":
    unittest.main()
