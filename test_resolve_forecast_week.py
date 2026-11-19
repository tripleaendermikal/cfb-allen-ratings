#!/usr/bin/env python3
"""Forecast week resolution for augment_weekly_rankings_forecast_resume."""

import unittest

from augment_weekly_rankings_forecast_resume import resolve_forecast_week


class TestResolveForecastWeek(unittest.TestCase):
    def test_explicit_overrides_inference(self) -> None:
        rows = [{"week": "12", "game_completed": "true"}]
        self.assertEqual(resolve_forecast_week(11, games_fpi_rows=rows), 11)

    def test_infers_from_completed_games_not_stale_meta(self) -> None:
        rows = [
            {"week": "11", "game_completed": "true"},
            {"week": "12", "game_completed": "true"},
            {"week": "13", "game_completed": "false"},
        ]
        self.assertEqual(resolve_forecast_week(None, games_fpi_rows=rows), 12)

    def test_empty_games_returns_none(self) -> None:
        self.assertIsNone(resolve_forecast_week(None, games_fpi_rows=None))


if __name__ == "__main__":
    unittest.main()