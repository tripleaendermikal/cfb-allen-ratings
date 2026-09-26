"""Team page rank/margins should match the rankings leaderboard for the current week."""

from __future__ import annotations

import unittest
from pathlib import Path

from app import DataStore


class TeamPageRankingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DataStore(Path(__file__).resolve().parent / "data")

    def test_tennessee_rank_matches_leaderboard_for_current_week(self) -> None:
        week = int(self.store.meta.get("current_week") or 0)
        team_id = "2633"
        leaderboard_row = next(
            row
            for row in self.store.leaderboard_for_week(week, ranking_mode="overall")
            if row["team_id"] == team_id
        )
        team_row = self.store.team_row_for_week(team_id, week=week)
        self.assertEqual(
            team_row.get("display_rank"),
            leaderboard_row.get("display_rank"),
        )
        self.assertEqual(
            team_row.get("overall_margin"),
            leaderboard_row.get("overall_margin"),
        )
        self.assertNotEqual(
            self.store.lb_by_id[team_id].get("rank"),
            leaderboard_row.get("display_rank"),
            "stale leaderboard.json rank should differ from current-week rank",
        )


if __name__ == "__main__":
    unittest.main()
