"""Team page rank/margins should match the rankings leaderboard for the current week."""

from __future__ import annotations

import unittest
from pathlib import Path

from app import (
    DataStore,
    _leaderboard_playoff_pct,
    _leaderboard_title_pct,
    create_app,
)


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
        self.assertEqual(
            self.store.lb_by_id[team_id].get("rank"),
            leaderboard_row.get("display_rank"),
        )

    def test_playoff_title_odds_match_overall_leaderboard(self) -> None:
        week = int(self.store.meta.get("current_week") or 0)
        team_id = "87"
        leaderboard_row = next(
            row
            for row in self.store.leaderboard_for_week(week, ranking_mode="overall")
            if row["team_id"] == team_id
        )
        lb_base = self.store.lb_by_id[team_id]
        self.assertEqual(
            _leaderboard_playoff_pct(lb_base, "overall"),
            leaderboard_row["display_playoff_pct"],
        )
        self.assertEqual(
            _leaderboard_title_pct(lb_base, "overall"),
            leaderboard_row["display_title_pct"],
        )

    def test_team_detail_page_renders(self) -> None:
        team_id = "87"
        client = create_app().test_client()
        response = client.get(f"/team/{team_id}")
        self.assertEqual(response.status_code, 200)
        body = response.data.decode()
        self.assertIn("Resume", body)
        self.assertNotIn("UndefinedError", body)
        season_n = int(self.store.season_sim_count)
        self.assertIn(f"Win distribution ({season_n} sims)", body)
        if int(self.store.meta.get("sim_count", season_n)) != season_n:
            self.assertNotIn(
                f"Win distribution ({self.store.meta.get('sim_count')} sims)", body
            )

    def test_conference_detail_sim_lookup_uses_season_sim_count(self) -> None:
        season_n = int(self.store.season_sim_count)
        client = create_app().test_client()
        response = client.get("/conferences?conference=SEC")
        self.assertEqual(response.status_code, 200)
        body = response.data.decode()
        self.assertIn(f'max="{season_n}"', body)
        self.assertIn(f"1–{season_n}", body)
        total = int(self.store.meta.get("sim_count", season_n))
        if total != season_n:
            self.assertNotIn(f'max="{total}"', body)
        summary = self.store.conference_summaries.get("summaries", {}).get("SEC", {}).get(
            "summary", ""
        )
        if summary:
            self.assertNotIn("2000 simulations", summary)
            self.assertIn(f"{season_n} simulations", summary)


if __name__ == "__main__":
    unittest.main()
