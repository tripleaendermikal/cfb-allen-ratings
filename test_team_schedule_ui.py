#!/usr/bin/env python3
"""Team schedule: CCG badge data and opponent overall ranks."""

from __future__ import annotations

import unittest

from app import DataStore, create_app
from cfb_conf_championship import infer_conference_championship_game_ids


class TestTeamScheduleUi(unittest.TestCase):
    def test_infer_conference_championship_game_ids(self) -> None:
        games = {
            "g1": {
                "game_id": "g1",
                "week": 14,
                "home_team_id": "68",
                "away_team_id": "254",
                "home_conference": "Pac-12",
                "away_conference": "Pac-12",
            },
            "g2": {
                "game_id": "g2",
                "week": 12,
                "home_team_id": "1",
                "away_team_id": "2",
                "home_conference": "SEC",
                "away_conference": "SEC",
            },
        }
        self.assertEqual(infer_conference_championship_game_ids(games), frozenset({"g1"}))

    def test_team_schedule_includes_opponent_rank(self) -> None:
        from pathlib import Path

        store = DataStore(Path(__file__).resolve().parent / "data")
        team_id = "87"
        ranks = store.overall_rank_by_team_id()
        sched = store.team_schedule(team_id, opponent_ranks=ranks)
        self.assertTrue(sched)
        opponents_with_rank = [
            g for g in sched if g.get("opponent_rank") is not None
        ]
        self.assertTrue(opponents_with_rank)
        for g in opponents_with_rank:
            self.assertIsInstance(g["opponent_rank"], int)
            opp_row = store.team_row_for_week(g["opponent_id"])
            if opp_row.get("display_rank"):
                self.assertEqual(g["opponent_rank"], opp_row["display_rank"])

    def test_team_page_shows_opponent_rank(self) -> None:
        from pathlib import Path

        store = DataStore(Path(__file__).resolve().parent / "data")
        team_id = "87"
        client = create_app().test_client()
        response = client.get(f"/team/{team_id}")
        self.assertEqual(response.status_code, 200)
        body = response.data.decode()
        sched = store.team_schedule(team_id, opponent_ranks=store.overall_rank_by_team_id())
        ranked = next((g for g in sched if g.get("opponent_rank")), None)
        if ranked:
            self.assertIn(f"#{ranked['opponent_rank']}", body)


if __name__ == "__main__":
    unittest.main()