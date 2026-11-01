#!/usr/bin/env python3
"""Tests for resume margin calibration."""

import unittest

from cfb_rating.rating_algorithm import GameRecord
from cfb_rating.resume import (
    bayesian_win_pct,
    calibrate_resume_rating,
    calibrate_resume_to_target,
    expected_win_pct,
    forecast_target_win_pct,
    team_record_from_games,
)
from cfb_rating.win_prob import team_win_probability


def _game(
    home: str,
    away: str,
    home_score: float,
    away_score: float,
    *,
    neutral: bool = False,
) -> GameRecord:
    return GameRecord(
        home_team_id=home,
        away_team_id=away,
        home_score=home_score,
        away_score=away_score,
        home_yards=400.0,
        away_yards=400.0,
        neutral_site=neutral,
    )


class TestResumeRating(unittest.TestCase):
    def test_bayesian_win_pct(self):
        self.assertAlmostEqual(bayesian_win_pct(0, 0), 0.5)
        self.assertAlmostEqual(bayesian_win_pct(10, 12), 10.5 / 13)

    def test_team_record_from_games(self):
        games = [_game("1", "2", 28, 14), _game("3", "1", 21, 24)]
        self.assertEqual(team_record_from_games(games, "1"), (2, 2))

    def test_higher_resume_raises_expected_win_pct(self):
        games = [_game("1", "2", 0, 0)]  # unused scores; only structure matters
        games[0] = _game("1", "2", 35, 10)
        overall = {"1": 10.0, "2": 0.0}
        low = expected_win_pct("1", 5.0, overall, games)
        high = expected_win_pct("1", 20.0, overall, games)
        self.assertGreater(high, low)

    def test_team_win_probability_home_favorite(self):
        p = team_win_probability("h", "h", "a", 15.0, 0.0, neutral_site=False)
        self.assertGreater(p, 0.5)

    def test_zero_games_returns_overall(self):
        overall = {"1": 12.5}
        result = calibrate_resume_rating("1", 12.5, 0, 0, overall, [])
        self.assertEqual(result, 12.5)

    def test_forecast_target_win_pct(self):
        self.assertAlmostEqual(forecast_target_win_pct(9.0, 12.0), 9.5 / 13)
        self.assertAlmostEqual(forecast_target_win_pct(6.0, 12.0), 6.5 / 13)
        self.assertAlmostEqual(forecast_target_win_pct(9.0, 9.0), 9.5 / 10)

    def test_calibration_moves_toward_forecast_target(self):
        games = [_game("1", "2", 35, 7), _game("1", "3", 42, 0)]
        overall = {"1": 5.0, "2": 0.0, "3": -5.0}
        target = forecast_target_win_pct(10.5, 12.0)
        resume = calibrate_resume_to_target("1", 5.0, target, overall, games)
        expected = expected_win_pct("1", resume, overall, games)
        self.assertLessEqual(abs(expected - target), 0.011)

    def test_calibration_moves_toward_bayesian(self):
        games = [_game("1", "2", 35, 7), _game("1", "3", 42, 0)]
        overall = {"1": 5.0, "2": 0.0, "3": -5.0}
        wins, gp = team_record_from_games(games, "1")
        target = bayesian_win_pct(wins, gp)
        resume = calibrate_resume_rating("1", 5.0, wins, gp, overall, games)
        expected = expected_win_pct("1", resume, overall, games)
        self.assertLessEqual(abs(expected - target), 0.011)


if __name__ == "__main__":
    unittest.main()
