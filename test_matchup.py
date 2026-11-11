"""Tests for matchup projection helpers."""

from __future__ import annotations

import math

from cfb_matchup import (
    find_scheduled_games,
    game_matches_requested_site,
    pick_game_for_site,
    project_from_ratings,
)
from simulate_cfb_games_preseason_simulation import win_probability


def _sample_games() -> dict:
    return {
        "g1": {
            "game_id": "g1",
            "home_team_id": "10",
            "away_team_id": "20",
            "neutral_site": False,
            "home_win_pct": 62.0,
            "avg_margin": 5.5,
            "completed": False,
        },
        "g2": {
            "game_id": "g2",
            "home_team_id": "20",
            "away_team_id": "10",
            "neutral_site": True,
            "home_win_pct": 48.0,
            "avg_margin": -1.0,
            "completed": False,
        },
    }


def test_find_scheduled_games_both_directions():
    games = _sample_games()
    found = find_scheduled_games(games, "10", "20")
    assert len(found) == 2
    assert find_scheduled_games(games, "10", "10") == []


def test_game_matches_requested_site():
    g_home = _sample_games()["g1"]
    g_neutral = _sample_games()["g2"]
    assert game_matches_requested_site(g_home, "10", neutral=False)
    assert not game_matches_requested_site(g_home, "20", neutral=False)
    assert game_matches_requested_site(g_neutral, "20", neutral=True)
    assert not game_matches_requested_site(g_neutral, "20", neutral=False)


def test_pick_game_for_site_prefers_match():
    games = list(_sample_games().values())
    picked = pick_game_for_site(games, "10", neutral=False)
    assert picked["game_id"] == "g1"
    picked_n = pick_game_for_site(games, "20", neutral=True)
    assert picked_n["game_id"] == "g2"


def test_project_from_ratings_neutral_equal_teams():
    proj = project_from_ratings(10.0, 10.0, neutral=True)
    assert proj["home_win_pct"] == 50.0
    assert proj["avg_margin"] == 0.0
    assert proj["method"] == "ratings"


def test_project_from_ratings_home_field_adds_three_to_margin():
    proj = project_from_ratings(10.0, 10.0, neutral=False)
    assert proj["avg_margin"] == 3.0
    p_home = win_probability(0.0, 1.0)
    assert proj["home_win_pct"] == round(p_home * 100, 2)


def test_home_advantage_roughly_three_point_win_pct_swing():
    """Equal ratings: home ~5–6 pts better than away in win % (logistic + 3pt margin display)."""
    home = project_from_ratings(15.0, 15.0, neutral=False)
    neutral = project_from_ratings(15.0, 15.0, neutral=True)
    assert home["home_win_pct"] > neutral["home_win_pct"]
    assert home["home_win_pct"] - neutral["home_win_pct"] > 3.0
    assert math.isclose(home["avg_margin"] - neutral["avg_margin"], 3.0, abs_tol=0.01)
