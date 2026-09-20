#!/usr/bin/env python3
"""Tests for opponent-adjusted margins (Opp Adj / some_preseason_margin)."""

from __future__ import annotations

import logging
import unittest
from pathlib import Path

from cfb_paths import data_root
from cfb_rating.in_season import (
    compute_in_season_rankings_for_week,
    load_preseason_margins,
)
from cfb_rating.opp_adjust import (
    anchor_preseason_weight,
    compute_opponent_adjusted_margins,
    compute_pilot_overall,
    stable_opponent_strength,
)
from cfb_rating.rating_algorithm import GameRecord
from cfb_rating.season_data import load_fbs_schedule_games, load_fbs_team_ids

TEAMS_CSV = data_root() / "espn_cfb_teams_conferences.csv"
GAMES_CSV = data_root() / "cfb_2026_fbs_games_with_fpi.csv"

logging.getLogger("cfb_rating.season_data").setLevel(logging.ERROR)


def _week3_rankings():
    if not GAMES_CSV.is_file() or not TEAMS_CSV.is_file():
        raise unittest.SkipTest("CFB_DATA_ROOT CSVs not available")
    games = load_fbs_schedule_games(GAMES_CSV, teams_path=TEAMS_CSV, completed_only=True)
    preseason = load_preseason_margins(teams_path=TEAMS_CSV)
    team_info = load_fbs_team_ids(TEAMS_CSV)
    team_ids = sorted(team_info.keys())
    return compute_in_season_rankings_for_week(
        games, 3, team_ids, preseason, team_info=team_info
    )


def _row(rows, team_id: str):
    return next(r for r in rows if r.team_id == team_id)


class AnchorPreseasonWeightTests(unittest.TestCase):
    def test_zero_games_full_preseason(self) -> None:
        self.assertEqual(anchor_preseason_weight(0), 1.0)

    def test_six_plus_games_floor(self) -> None:
        self.assertEqual(anchor_preseason_weight(6), 0.4)
        self.assertEqual(anchor_preseason_weight(10), 0.4)


class StableStrengthTests(unittest.TestCase):
    def test_zero_games_equals_preseason(self) -> None:
        preseason = {"1": 20.0, "2": 10.0}
        pilot = {"1": 5.0, "2": 15.0}
        games_played = {"1": 0, "2": 0}
        self.assertAlmostEqual(
            stable_opponent_strength("1", preseason, pilot, games_played),
            20.0,
        )

    def test_six_games_blends_pilot(self) -> None:
        preseason = {"1": 20.0}
        pilot = {"1": 10.0}
        games_played = {"1": 6}
        expected = 0.4 * 20.0 + 0.6 * 10.0
        self.assertAlmostEqual(
            stable_opponent_strength("1", preseason, pilot, games_played),
            expected,
        )


class ZeroGamesFallbackTests(unittest.TestCase):
    def test_no_games_uses_preseason(self) -> None:
        preseason = {"1": 12.5, "2": 8.0}
        margins = compute_opponent_adjusted_margins(
            [],
            ["1", "2"],
            preseason,
            {"1": 0.0, "2": 0.0},
            {"1": 0, "2": 0},
        )
        self.assertAlmostEqual(margins["1"], 12.5)
        self.assertAlmostEqual(margins["2"], 8.0)


class SyntheticResidualTests(unittest.TestCase):
    def test_blowout_vs_weak_opponent_modest_residual(self) -> None:
        """Alabama-style: big win over weak opponent should not explode Opp Adj."""
        preseason = {
            "bama": 17.5,
            "ecu": -8.0,
        }
        games = [
            GameRecord(
                home_team_id="bama",
                away_team_id="ecu",
                home_score=48,
                away_score=10,
                home_yards=487,
                away_yards=162,
            ),
        ]
        algo = {"bama": 5.0, "ecu": -20.0}
        played = {"bama": 1, "ecu": 1}
        margins = compute_opponent_adjusted_margins(
            games, ["bama", "ecu"], preseason, algo, played
        )
        self.assertLess(margins["bama"], 20.0)
        self.assertGreater(margins["bama"], -5.0)

    def test_road_win_vs_strong_opponent_positive_residual(self) -> None:
        """Kentucky-style: road win over preseason-strong opponent."""
        preseason = {
            "uk": 3.7,
            "tam": 17.6,
        }
        games = [
            GameRecord(
                home_team_id="tam",
                away_team_id="uk",
                home_score=21,
                away_score=31,
                home_yards=423,
                away_yards=408,
            ),
        ]
        algo = {"uk": -10.0, "tam": -5.0}
        played = {"uk": 1, "tam": 1}
        margins = compute_opponent_adjusted_margins(
            games, ["uk", "tam"], preseason, algo, played
        )
        self.assertGreater(margins["uk"], 2.0)

    def test_loss_to_strong_opponent_negative_residual(self) -> None:
        """Ohio State-style: close road loss to strong opponent."""
        preseason = {
            "osu": 29.1,
            "tex": 21.2,
        }
        games = [
            GameRecord(
                home_team_id="tex",
                away_team_id="osu",
                home_score=24,
                away_score=23,
                home_yards=336,
                away_yards=372,
            ),
        ]
        algo = {"osu": 15.0, "tex": 18.0}
        played = {"osu": 1, "tex": 1}
        margins = compute_opponent_adjusted_margins(
            games, ["osu", "tex"], preseason, algo, played
        )
        self.assertLess(margins["osu"], 0.0)


class Week3IntegrationTests(unittest.TestCase):
    def test_kentucky_opp_adj_positive(self) -> None:
        rows = _week3_rankings()
        uk = _row(rows, "96")
        self.assertGreater(uk.some_preseason_margin, 0.0)
        self.assertGreater(uk.overall_margin, -0.5)

    def test_alabama_opp_adj_modest(self) -> None:
        rows = _week3_rankings()
        bama = _row(rows, "333")
        self.assertLess(barm := bama.some_preseason_margin, 15.0)
        self.assertGreater(barm, -10.0)

    def test_south_carolina_opp_adj_below_old_ceiling(self) -> None:
        rows = _week3_rankings()
        sc = _row(rows, "2579")
        self.assertLess(sc.some_preseason_margin, 25.0)

    def test_some_preseason_top25_not_mac_heavy(self) -> None:
        rows = _week3_rankings()
        top = sorted(rows, key=lambda r: -r.some_preseason_margin)[:25]
        mac_count = sum(1 for r in top if r.conference == "MAC")
        self.assertLessEqual(mac_count, 2)


if __name__ == "__main__":
    unittest.main()
