"""Resume margin: calibrate Overall to Bayesian win% via sim win probabilities."""

from __future__ import annotations

from typing import Mapping, Sequence

from cfb_rating.rating_algorithm import GameRecord
from cfb_rating.win_prob import team_win_probability

RESUME_STEP = 0.01
MAX_RESUME_ITERATIONS = 1000
WIN_PCT_TOLERANCE = 0.01
FORECAST_SEASON_GAMES = 12


def bayesian_win_pct(wins: int, games: int) -> float:
    return (wins + 1) / (games + 2)


def forecast_target_win_pct(projected_wins: float) -> float:
    """Season projected wins as a win rate (12-game regular season)."""
    return projected_wins / FORECAST_SEASON_GAMES


def team_record_from_games(
    games: Sequence[GameRecord], team_id: str
) -> tuple[int, int]:
    wins = 0
    games_played = 0
    for game in games:
        if team_id == game.home_team_id:
            games_played += 1
            if game.home_score > game.away_score:
                wins += 1
            elif game.home_score == game.away_score:
                wins += 0
        elif team_id == game.away_team_id:
            games_played += 1
            if game.away_score > game.home_score:
                wins += 1
    return wins, games_played


def _rating_for_side(
    team_id: str,
    subject_id: str,
    subject_resume: float,
    overall_by_team: Mapping[str, float],
) -> float:
    if team_id == subject_id:
        return subject_resume
    return overall_by_team[team_id]


def expected_win_pct(
    team_id: str,
    resume_rating: float,
    overall_by_team: Mapping[str, float],
    games: Sequence[GameRecord],
) -> float:
    probs: list[float] = []
    for game in games:
        if team_id not in (game.home_team_id, game.away_team_id):
            continue
        home_r = _rating_for_side(
            game.home_team_id, team_id, resume_rating, overall_by_team
        )
        away_r = _rating_for_side(
            game.away_team_id, team_id, resume_rating, overall_by_team
        )
        probs.append(
            team_win_probability(
                team_id,
                game.home_team_id,
                game.away_team_id,
                home_r,
                away_r,
                neutral_site=game.neutral_site,
            )
        )
    if not probs:
        return 0.0
    return sum(probs) / len(probs)


def calibrate_resume_to_target(
    team_id: str,
    overall_margin: float,
    target_win_pct: float,
    overall_by_team: Mapping[str, float],
    week_games: Sequence[GameRecord],
) -> float:
    team_games = [
        g for g in week_games if team_id in (g.home_team_id, g.away_team_id)
    ]
    if not team_games:
        return overall_margin

    resume = overall_margin
    for _ in range(MAX_RESUME_ITERATIONS):
        expected = expected_win_pct(team_id, resume, overall_by_team, team_games)
        if abs(expected - target_win_pct) <= WIN_PCT_TOLERANCE:
            break
        if expected > target_win_pct:
            resume -= RESUME_STEP
        else:
            resume += RESUME_STEP

    return resume


def calibrate_resume_rating(
    team_id: str,
    overall_margin: float,
    wins: int,
    games_played: int,
    overall_by_team: Mapping[str, float],
    week_games: Sequence[GameRecord],
) -> float:
    if games_played <= 0:
        return overall_margin

    target = bayesian_win_pct(wins, games_played)
    return calibrate_resume_to_target(
        team_id,
        overall_margin,
        target,
        overall_by_team,
        week_games,
    )


def compute_resume_margins(
    team_ids: Sequence[str],
    week_games: Sequence[GameRecord],
    overall_by_team: Mapping[str, float],
) -> dict[str, float]:
    out: dict[str, float] = {}
    for team_id in team_ids:
        wins, gp = team_record_from_games(week_games, team_id)
        overall = overall_by_team[team_id]
        out[team_id] = calibrate_resume_rating(
            team_id,
            overall,
            wins,
            gp,
            overall_by_team,
            week_games,
        )
    return out


def compute_forecast_resume_margins(
    team_ids: Sequence[str],
    week_games: Sequence[GameRecord],
    overall_by_team: Mapping[str, float],
    projected_wins_by_team: Mapping[str, float],
) -> dict[str, float]:
    """Resume calibration with target win% = projected season wins / 12."""
    out: dict[str, float] = {}
    for team_id in team_ids:
        if team_id not in overall_by_team:
            continue
        overall = overall_by_team[team_id]
        wins, gp = team_record_from_games(week_games, team_id)
        if gp <= 0:
            out[team_id] = overall
            continue
        projected = projected_wins_by_team.get(team_id)
        if projected is None:
            out[team_id] = overall
            continue
        target = forecast_target_win_pct(float(projected))
        out[team_id] = calibrate_resume_to_target(
            team_id,
            overall,
            target,
            overall_by_team,
            week_games,
        )
    return out
