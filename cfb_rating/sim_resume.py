"""End-of-season resume margins for a single Monte Carlo sim column."""

from __future__ import annotations

from typing import Mapping, Sequence

from cfb_rating.rating_algorithm import GameRecord
from cfb_rating.resume import compute_resume_margins

DEFAULT_YARDS = 400.0


def build_sim_season_games(
    game_rows: Sequence[Mapping[str, str]],
    sim_col: str,
    fbs_team_ids: frozenset[str] | None = None,
) -> list[GameRecord]:
    """FBS-vs-FBS games with outcomes from one sim column (home rows only)."""
    seen: set[str] = set()
    games: list[GameRecord] = []
    for row in game_rows:
        if (row.get("home_away") or "").strip() != "home":
            continue
        game_id = (row.get("game_id") or "").strip()
        if not game_id or game_id in seen:
            continue
        home_id = (row.get("team_id") or "").strip()
        away_id = (row.get("opponent_id") or "").strip()
        if not home_id or not away_id:
            continue
        if fbs_team_ids is not None and (
            home_id not in fbs_team_ids or away_id not in fbs_team_ids
        ):
            continue
        result = (row.get(sim_col) or "").strip()
        if result not in ("0", "1"):
            continue
        home_win = result == "1"
        home_score = 35.0 if home_win else 14.0
        away_score = 14.0 if home_win else 35.0
        week_raw = (row.get("week") or "").strip()
        neutral_raw = (row.get("neutral_site") or "").strip().lower()
        games.append(
            GameRecord(
                home_team_id=home_id,
                away_team_id=away_id,
                home_score=home_score,
                away_score=away_score,
                home_yards=DEFAULT_YARDS,
                away_yards=DEFAULT_YARDS,
                game_id=game_id,
                week=int(week_raw) if week_raw.isdigit() else None,
                neutral_site=neutral_raw in ("true", "1", "yes"),
            )
        )
        seen.add(game_id)
    return games


def overall_margins_for_sim_col(
    sim_fpi_by_team_id: Mapping[str, Mapping[str, float]],
    sim_col: str,
    team_ids: Sequence[str],
) -> dict[str, float]:
    out: dict[str, float] = {}
    for team_id in team_ids:
        per_sim = sim_fpi_by_team_id.get(team_id) or {}
        value = per_sim.get(sim_col)
        if value is not None:
            out[team_id] = float(value)
    return out


def compute_sim_resume_margins(
    game_rows: Sequence[Mapping[str, str]],
    sim_col: str,
    team_ids: Sequence[str],
    overall_by_team: Mapping[str, float],
    *,
    fbs_team_ids: frozenset[str] | None = None,
) -> dict[str, float]:
    season_games = build_sim_season_games(
        game_rows, sim_col, fbs_team_ids=fbs_team_ids
    )
    ids = [tid for tid in team_ids if tid in overall_by_team]
    return compute_resume_margins(ids, season_games, overall_by_team)


def rank_team_ids_by_resume(
    resume_margins: Mapping[str, float],
    team_ids: Sequence[str],
) -> list[str]:
    return sorted(
        team_ids,
        key=lambda tid: (
            -(resume_margins.get(tid) if resume_margins.get(tid) is not None else -999.0),
            tid,
        ),
    )
