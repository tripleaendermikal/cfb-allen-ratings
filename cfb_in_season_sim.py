"""Shared helpers for in-season CFB Monte Carlo simulations."""

from __future__ import annotations

import math
from typing import Mapping, Sequence, Set

from cfb_rating.season_data import load_fbs_team_ids

IN_SEASON_PREFIX = "cfb_2026_in_season"


def load_fbs_ids() -> Set[str]:
    """Return ESPN team_ids for FBS teams."""
    return set(load_fbs_team_ids().keys())


def is_completed(row: Mapping[str, str]) -> bool:
    """Return True when ``game_completed`` marks a finished game."""
    value = (row.get("game_completed") or "").strip().lower()
    return value in ("true", "1", "yes")


def parse_score(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def actual_team_win(row: Mapping[str, str]) -> str | None:
    """Return ``1`` or ``0`` from scores, or ``None`` if unavailable.

    Ties return ``0`` for both teams (negligible in CFB).
    """
    team_score = parse_score(row.get("team_score"))
    opponent_score = parse_score(row.get("opponent_score"))
    if team_score is None or opponent_score is None:
        return None
    if team_score > opponent_score:
        return "1"
    if team_score < opponent_score:
        return "0"
    return "0"


def is_fbs_vs_fbs_row(row: Mapping[str, str], fbs_ids: Set[str]) -> bool:
    team_id = (row.get("team_id") or "").strip()
    opponent_id = (row.get("opponent_id") or "").strip()
    return team_id in fbs_ids and opponent_id in fbs_ids


def count_completed_fbs_games(
    rows: Sequence[Mapping[str, str]],
    fbs_ids: Set[str] | None = None,
) -> dict[str, int]:
    """Count completed FBS-vs-FBS games per team."""
    if fbs_ids is None:
        fbs_ids = load_fbs_ids()
    counts: dict[str, int] = {}
    for row in rows:
        if not is_completed(row):
            continue
        if not is_fbs_vs_fbs_row(row, fbs_ids):
            continue
        team_id = (row.get("team_id") or "").strip()
        if not team_id:
            continue
        counts[team_id] = counts.get(team_id, 0) + 1
    return counts


def per_team_sigma(base_sigma: float, games_played: int) -> float:
    """Shrink draw std dev as more FBS games are completed."""
    if base_sigma <= 0:
        raise ValueError("base_sigma must be positive")
    games = max(games_played, 0)
    return base_sigma / (1.0 + math.sqrt(games))


def count_completed_fbs_game_pairs(rows: Sequence[Mapping[str, str]]) -> int:
    """Count unique completed FBS-vs-FBS games (one per game_id)."""
    fbs_ids = load_fbs_ids()
    seen: set[str] = set()
    for row in rows:
        if not is_completed(row):
            continue
        if not is_fbs_vs_fbs_row(row, fbs_ids):
            continue
        game_id = (row.get("game_id") or "").strip()
        if game_id and game_id not in seen:
            seen.add(game_id)
    return len(seen)
