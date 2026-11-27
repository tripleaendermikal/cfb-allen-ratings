import unittest

from cfb_rating.rating_algorithm import GameRecord
from cfb_team_sos import compute_team_sos_from_games


class TeamSosTests(unittest.TestCase):
    def test_home_away_adjustment(self) -> None:
        margins = {"h": 10.0, "a": 4.0}
        games = [
            GameRecord(
                home_team_id="h",
                away_team_id="a",
                home_score=1,
                away_score=0,
                home_yards=1,
                away_yards=1,
            )
        ]
        sos = compute_team_sos_from_games(games, margins)
        self.assertAlmostEqual(sos["h"], 1.0)  # away opp 4.0 − 3.0
        self.assertAlmostEqual(sos["a"], 13.0)  # home opp 10.0 + 3.0


if __name__ == "__main__":
    unittest.main()