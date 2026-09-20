"""Opponent-adjusted in-season margins (Opp Adj middle Overall component)."""

from __future__ import annotations

import math
import statistics
from typing import Dict, Mapping, Optional, Sequence

from cfb_rating.rating_algorithm import GameRecord

# Maps preseason/FPI margin units to per-game margin units for residual comparison.
FPI_MARGIN_SCALE = 8.0
YARDS_PER_POINT = 15.5
OPP_ADJ_TARGET_STDEV = 12.0
OPP_ADJ_SHRINK_MIN_GAMES = 1
OPP_ADJ_SHRINK_FULL_GAMES = 10


def home_field_adjustment(neutral_site: bool, home_away: str) -> float:
    """+3 home, -3 away, 0 neutral (matches export_sim_data)."""
    if neutral_site:
        return 0.0
    if home_away == "home":
        return 3.0
    if home_away == "away":
        return -3.0
    return 0.0


def anchor_preseason_weight(fbs_games_played: int) -> float:
    """Preseason share for stable opponent strength: 1.0 at 0 games -> 0.4 at 6+."""
    n = min(max(fbs_games_played, 0), 6)
    return max(0.4, (6 - n) / 6)


def compute_pilot_overall(
    preseason_margin: Optional[float],
    algorithm_margin: float,
    games_played: int,
) -> float:
    """Overall blend omitting Opp Adj to avoid circularity."""
    from cfb_rating.in_season import overall_component_weights

    w_pre, _w_some, w_algo = overall_component_weights(games_played)
    pre = preseason_margin if preseason_margin is not None else algorithm_margin
    return w_pre * pre + w_algo * algorithm_margin


def stable_opponent_strength(
    team_id: str,
    preseason_margins: Mapping[str, float],
    pilot_overall_margins: Mapping[str, float],
    games_played: Mapping[str, int],
) -> float:
    """Preseason-heavy strength estimate for opponent quality."""
    n = games_played.get(team_id, 0)
    anchor = anchor_preseason_weight(n)
    preseason = preseason_margins.get(team_id)
    pilot = pilot_overall_margins.get(team_id, 0.0)
    if preseason is None:
        return pilot
    return anchor * preseason + (1.0 - anchor) * pilot


def game_actual_margin(
    home_score: float,
    away_score: float,
    home_yards: float,
    away_yards: float,
    *,
    for_home_team: bool,
) -> float:
    """Point margin (+ yard bonus) on the same scale as expected FPI margins."""
    if for_home_team:
        point_margin = home_score - away_score
        yard_margin = home_yards - away_yards
    else:
        point_margin = away_score - home_score
        yard_margin = away_yards - home_yards
    return (point_margin + 0.25 * yard_margin / YARDS_PER_POINT) / FPI_MARGIN_SCALE


def sample_shrinkage_weight(fbs_games_played: int) -> float:
    """Shrink Opp Adj toward 0: 10% at 1 game -> 100% at 10+ games."""
    n = min(max(fbs_games_played, OPP_ADJ_SHRINK_MIN_GAMES), OPP_ADJ_SHRINK_FULL_GAMES)
    return 0.1 + 0.9 * (n - 1) / 9


def normalize_opp_adj_margins(
    raw_margins: Mapping[str, float],
    games_played: Mapping[str, int],
    preseason_margins: Mapping[str, float],
    team_ids: Sequence[str],
) -> Dict[str, float]:
    """Z-score raw residuals, rescale to FPI-like spread, then shrink by sample size."""
    result: Dict[str, float] = {}
    pool: list[tuple[str, float]] = []

    for team_id in team_ids:
        n = games_played.get(team_id, 0)
        if n <= 0:
            fallback = preseason_margins.get(team_id)
            result[team_id] = fallback if fallback is not None else 0.0
            continue
        pool.append((team_id, raw_margins[team_id]))

    if len(pool) < 2:
        for team_id, raw in pool:
            shrink = sample_shrinkage_weight(games_played[team_id])
            result[team_id] = shrink * raw
        return result

    raw_vals = [raw for _, raw in pool]
    weights = [
        sample_shrinkage_weight(games_played[team_id]) for team_id, _ in pool
    ]
    weight_sum = sum(weights)
    mean = sum(weight * raw for weight, raw in zip(weights, raw_vals)) / weight_sum
    variance = sum(
        weight * (raw - mean) ** 2 for weight, raw in zip(weights, raw_vals)
    ) / weight_sum
    stdev = math.sqrt(variance)
    if stdev < 1e-9:
        for team_id, raw in pool:
            shrink = sample_shrinkage_weight(games_played[team_id])
            result[team_id] = shrink * raw
        return result

    for team_id, raw in pool:
        z = (raw - mean) / stdev
        scaled = z * OPP_ADJ_TARGET_STDEV
        shrink = sample_shrinkage_weight(games_played[team_id])
        result[team_id] = shrink * scaled
    return result


def game_residual(
    game: GameRecord,
    team_id: str,
    stable_strength: Mapping[str, float],
    *,
    neutral_site: bool = False,
) -> float:
    """Performance vs expectation for one team in one game."""
    if team_id == game.home_team_id:
        actual = game_actual_margin(
            game.home_score,
            game.away_score,
            game.home_yards,
            game.away_yards,
            for_home_team=True,
        )
        opp_id = game.away_team_id
        hfa = home_field_adjustment(neutral_site, "home")
    elif team_id == game.away_team_id:
        actual = game_actual_margin(
            game.home_score,
            game.away_score,
            game.home_yards,
            game.away_yards,
            for_home_team=False,
        )
        opp_id = game.home_team_id
        hfa = home_field_adjustment(neutral_site, "away")
    else:
        raise ValueError(f"team {team_id} not in game")

    team_strength = stable_strength[team_id]
    opp_strength = stable_strength[opp_id]
    expected = (team_strength - opp_strength + hfa) / FPI_MARGIN_SCALE
    return actual - expected


def compute_opponent_adjusted_margins(
    games: Sequence[GameRecord],
    team_ids: Sequence[str],
    preseason_margins: Mapping[str, float],
    algorithm_margins: Mapping[str, float],
    games_played: Mapping[str, int],
) -> Dict[str, float]:
    """Mean per-game residual vs expectation (stored as some_preseason_margin)."""
    pilot_overall = {
        team_id: compute_pilot_overall(
            preseason_margins.get(team_id),
            algorithm_margins.get(team_id, 0.0),
            games_played.get(team_id, 0),
        )
        for team_id in team_ids
    }
    stable = {
        team_id: stable_opponent_strength(
            team_id,
            preseason_margins,
            pilot_overall,
            games_played,
        )
        for team_id in team_ids
    }

    residuals: Dict[str, list[float]] = {team_id: [] for team_id in team_ids}
    for game in games:
        for team_id in (game.home_team_id, game.away_team_id):
            if team_id not in residuals:
                continue
            residuals[team_id].append(
                game_residual(game, team_id, stable, neutral_site=False)
            )

    raw_margins: Dict[str, float] = {}
    for team_id in team_ids:
        team_residuals = residuals[team_id]
        if not team_residuals:
            raw_margins[team_id] = 0.0
            continue
        raw_margins[team_id] = sum(team_residuals) / len(team_residuals)

    return normalize_opp_adj_margins(
        raw_margins,
        games_played,
        preseason_margins,
        team_ids,
    )
