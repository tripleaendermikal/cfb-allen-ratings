"""Win probability from rating margin (in-season sim logistic)."""

from __future__ import annotations

import math


def site_home_flag(neutral_site: bool, home_away: str) -> float:
    if neutral_site:
        return 0.0
    if home_away == "home":
        return 1.0
    if home_away == "away":
        return -1.0
    return 0.0


def win_probability_from_margin(margin: float, home_flag_val: float) -> float:
    """P(home win) from fitted preseason logistic (matches in-season sim)."""
    x = 0.175 * margin + 0.475 * home_flag_val
    return math.exp(x) / (1.0 + math.exp(x))


def team_win_probability(
    team_id: str,
    home_team_id: str,
    away_team_id: str,
    home_rating: float,
    away_rating: float,
    *,
    neutral_site: bool = False,
) -> float:
    """P(team_id wins) given home/away ratings on the game."""
    margin_home = home_rating - away_rating
    hf = site_home_flag(neutral_site, "home")
    p_home = win_probability_from_margin(margin_home, hf)
    if team_id == home_team_id:
        return p_home
    if team_id == away_team_id:
        return 1.0 - p_home
    raise ValueError(f"team {team_id} not in matchup")
