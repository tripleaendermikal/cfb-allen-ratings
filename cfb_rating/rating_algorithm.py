"""Iterative team rating algorithm from game evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from cfb_rating.game_eval import evaluate_game

INITIAL_RATING = 0.5
REVERSION_RATING = 0.5
TARGET_MEAN_RATING = 0.5
DEFAULT_ITERATIONS = 1000


@dataclass(frozen=True)
class GameRecord:
    home_team_id: str
    away_team_id: str
    home_score: float
    away_score: float
    home_yards: float
    away_yards: float
    game_id: Optional[str] = None
    week: Optional[int] = None
    season: Optional[int] = None


def _collect_team_ids(games: Sequence[GameRecord]) -> list[str]:
    team_ids: set[str] = set()
    for game in games:
        team_ids.add(game.home_team_id)
        team_ids.add(game.away_team_id)
    return sorted(team_ids)


def _normalize_to_target_mean(
    ratings: dict[str, float], target_mean: float = TARGET_MEAN_RATING
) -> None:
    if not ratings:
        return
    mean_rating = sum(ratings.values()) / len(ratings)
    if mean_rating == 0:
        return
    factor = target_mean / mean_rating
    if factor != 1.0:
        for team_id in ratings:
            ratings[team_id] *= factor


def _resolve_initial_ratings(
    team_ids: Sequence[str],
    *,
    initial_rating: float,
    initial_ratings: Optional[Mapping[str, float]] = None,
) -> dict[str, float]:
    if initial_ratings is None:
        return {team_id: initial_rating for team_id in team_ids}
    return {
        team_id: initial_ratings.get(team_id, initial_rating)
        for team_id in team_ids
    }


def compute_team_ratings(
    games: Sequence[GameRecord],
    team_ids: Optional[Sequence[str]] = None,
    *,
    iterations: int = DEFAULT_ITERATIONS,
    initial_rating: float = INITIAL_RATING,
    initial_ratings: Optional[Mapping[str, float]] = None,
    target_mean: float = TARGET_MEAN_RATING,
) -> dict[str, float]:
    """Run the iterative rating algorithm to convergence.

    1. Initialize every team at ``initial_rating`` (default 0.5), or at
       per-team values from ``initial_ratings`` when provided.
    2. Evaluate each game using current team ratings.
    3. Set each team's rating to the average of its per-game scores (after
       avail_points scaling).
    4. Rescale all ratings by a constant factor so the league average equals
       ``target_mean`` (0.5). Reversion to the mean applies to the group, not
       to individual teams.
    5. Repeat for ``iterations`` passes (default 1000).

    Teams with no games keep their initial rating instead of reverting to the
    global ``initial_rating`` when ``initial_ratings`` is supplied.
    """
    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    all_team_ids = list(team_ids) if team_ids is not None else _collect_team_ids(games)
    baseline_ratings = _resolve_initial_ratings(
        all_team_ids,
        initial_rating=initial_rating,
        initial_ratings=initial_ratings,
    )
    ratings = dict(baseline_ratings)

    for _ in range(iterations):
        game_scores: dict[str, list[float]] = {team_id: [] for team_id in all_team_ids}

        for game in games:
            home_rating = ratings[game.home_team_id]
            away_rating = ratings[game.away_team_id]
            result = evaluate_game(
                game.home_score,
                game.away_score,
                game.home_yards,
                game.away_yards,
                home_rating,
                away_rating,
            )
            game_scores[game.home_team_id].append(result.home_game_score)
            game_scores[game.away_team_id].append(result.away_game_score)

        for team_id in all_team_ids:
            scores = game_scores[team_id]
            if scores:
                ratings[team_id] = sum(scores) / len(scores)
            else:
                ratings[team_id] = baseline_ratings[team_id]

        _normalize_to_target_mean(ratings, target_mean)

    return ratings


def ratings_mean(ratings: Mapping[str, float]) -> float:
    if not ratings:
        return 0.0
    return sum(ratings.values()) / len(ratings)
