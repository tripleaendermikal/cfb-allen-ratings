"""Game evaluation: pace-adjusted points and yards margins."""

from dataclasses import dataclass
from math import exp, log

from cfb_rating.constants import (
    POINTS_EXPONENT,
    POINTS_INTERCEPT,
    POINTS_LN_COEFF,
    POINTS_WEIGHT,
    YARDS_EXPONENT,
    YARDS_INTERCEPT,
    YARDS_LN_COEFF,
    YARDS_WEIGHT,
)


@dataclass(frozen=True)
class PointsMarginResult:
    total_score: float
    pace: float
    adj_margin: float
    home_point_score_ratio: float
    away_point_score_ratio: float
    home_point_score: float
    away_point_score: float


def evaluate_points_margin(home_score: float, away_score: float) -> PointsMarginResult:
    """Evaluate pace-adjusted points margins for a single game.

    Steps:
    1. total_score = home_score + away_score
    2. pace = points_ln_coeff * ln(total_score) - points_intercept
    3. adj_margin = (home_score - away_score) / pace
    4. home_point_score_ratio = exp(points_exponent * adj_margin * 2)
       / (1 + exp(points_exponent * adj_margin * 2))
    5. away_point_score_ratio = 1 - home_point_score_ratio
    6. Multiply both ratios by points_weight
    """
    total_score = home_score + away_score
    pace = POINTS_LN_COEFF * log(total_score) - POINTS_INTERCEPT
    adj_margin = (home_score - away_score) / pace

    exp_term = exp(POINTS_EXPONENT * adj_margin * 2)
    home_point_score_ratio = exp_term / (1 + exp_term)
    away_point_score_ratio = 1 - home_point_score_ratio

    return PointsMarginResult(
        total_score=total_score,
        pace=pace,
        adj_margin=adj_margin,
        home_point_score_ratio=home_point_score_ratio,
        away_point_score_ratio=away_point_score_ratio,
        home_point_score=home_point_score_ratio * POINTS_WEIGHT,
        away_point_score=away_point_score_ratio * POINTS_WEIGHT,
    )


@dataclass(frozen=True)
class YardsMarginResult:
    total_yards: float
    pace_yards: float
    adj_yards_margin: float
    home_yards_score_ratio: float
    away_yards_score_ratio: float
    home_yards_score: float
    away_yards_score: float


def evaluate_yards_margin(home_yards: float, away_yards: float) -> YardsMarginResult:
    """Evaluate pace-adjusted yards margins for a single game.

    Steps:
    1. total_yards = home_yards + away_yards
    2. pace_yards = yards_ln_coeff * ln(total_yards) - yards_intercept
    3. adj_yards_margin = (home_yards - away_yards) / pace_yards
    4. home_yards_score_ratio = exp(yards_exponent * adj_yards_margin * 2)
       / (1 + exp(yards_exponent * adj_yards_margin * 2))
    5. away_yards_score_ratio = 1 - home_yards_score_ratio
    6. Multiply both ratios by yards_weight
    """
    total_yards = home_yards + away_yards
    pace_yards = YARDS_LN_COEFF * log(total_yards) - YARDS_INTERCEPT
    adj_yards_margin = (home_yards - away_yards) / pace_yards

    exp_term = exp(YARDS_EXPONENT * adj_yards_margin * 2)
    home_yards_score_ratio = exp_term / (1 + exp_term)
    away_yards_score_ratio = 1 - home_yards_score_ratio

    return YardsMarginResult(
        total_yards=total_yards,
        pace_yards=pace_yards,
        adj_yards_margin=adj_yards_margin,
        home_yards_score_ratio=home_yards_score_ratio,
        away_yards_score_ratio=away_yards_score_ratio,
        home_yards_score=home_yards_score_ratio * YARDS_WEIGHT,
        away_yards_score=away_yards_score_ratio * YARDS_WEIGHT,
    )


@dataclass(frozen=True)
class GameEvaluationResult:
    points: PointsMarginResult
    yards: YardsMarginResult
    avail_points: float
    home_combined_score: float
    away_combined_score: float
    home_game_score: float
    away_game_score: float


def evaluate_game(
    home_score: float,
    away_score: float,
    home_yards: float,
    away_yards: float,
    home_rating: float,
    away_rating: float,
) -> GameEvaluationResult:
    """Evaluate a game by combining pace-adjusted points and yards margins.

    Combines weighted home/away points and yards scores, then multiplies each
    by avail_points (home_rating + away_rating).
    """
    points = evaluate_points_margin(home_score, away_score)
    yards = evaluate_yards_margin(home_yards, away_yards)

    avail_points = home_rating + away_rating
    home_combined_score = points.home_point_score + yards.home_yards_score
    away_combined_score = points.away_point_score + yards.away_yards_score

    return GameEvaluationResult(
        points=points,
        yards=yards,
        avail_points=avail_points,
        home_combined_score=home_combined_score,
        away_combined_score=away_combined_score,
        home_game_score=home_combined_score * avail_points,
        away_game_score=away_combined_score * avail_points,
    )
