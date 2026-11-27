import math
import unittest

from cfb_rating.rating_algorithm import GameRecord
from cfb_rating.win_prob import equivalent_opponent_margin, team_win_probability
from cfb_team_sos import (
    compute_equivalent_sos_from_game_records,
    compute_equivalent_sos_from_schedule,
)


class TeamSosTests(unittest.TestCase):
    def test_inversion_roundtrip_neutral(self) -> None:
        team_m = 12.0
        opp_m = 8.0
        p = team_win_probability("a", "a", "b", team_m, opp_m, neutral_site=True)
        back = equivalent_opponent_margin(team_m, p)
        self.assertAlmostEqual(back, opp_m, places=2)

    def test_harder_schedule_raises_sos(self) -> None:
        easy = [
            GameRecord("t", "w", 1, 0, 1, 1, neutral_site=True),  # t vs weak w=-20
        ]
        hard = [
            GameRecord("t", "s", 0, 1, 1, 1, neutral_site=True),  # t vs strong s=15
        ]
        ratings = {"t": 5.0, "w": -20.0, "s": 15.0}
        sos_easy = compute_equivalent_sos_from_game_records(easy, ratings)["t"]
        sos_hard = compute_equivalent_sos_from_game_records(hard, ratings)["t"]
        self.assertGreater(sos_hard, sos_easy)

    def test_schedule_rows_match_game_records(self) -> None:
        games = [
            GameRecord("h", "a", 1, 0, 1, 1, neutral_site=False),
        ]
        ratings = {"h": 10.0, "a": 4.0}
        from_g = compute_equivalent_sos_from_game_records(games, ratings)
        sched = [
            {
                "team_id": "h",
                "opponent_id": "a",
                "home_away": "home",
                "neutral_site": "False",
                "team_fpi": 10.0,
                "opponent_fpi": 4.0,
            },
            {
                "team_id": "a",
                "opponent_id": "h",
                "home_away": "away",
                "neutral_site": "False",
                "team_fpi": 4.0,
                "opponent_fpi": 10.0,
            },
        ]
        from_s = compute_equivalent_sos_from_schedule(sched, ratings)
        self.assertAlmostEqual(from_g["h"], from_s["h"], places=2)


if __name__ == "__main__":
    unittest.main()