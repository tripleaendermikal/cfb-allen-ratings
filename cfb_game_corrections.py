"""Manual game score and yard corrections applied after ESPN refresh."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cfb_paths import REPO_ROOT, data_root

DEFAULT_CORRECTIONS_PATH = REPO_ROOT / "cfb_game_corrections.json"


def load_corrections(path: Path | None = None) -> Dict[str, dict]:
    """Load game corrections keyed by game_id."""
    path = path or DEFAULT_CORRECTIONS_PATH
    if not path.is_file():
        fallback = data_root() / "cfb_game_corrections.json"
        path = fallback if fallback.is_file() else path
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Corrections file must be a JSON object: {path}")
    return {str(game_id): correction for game_id, correction in data.items()}


def apply_score_corrections(
    rows: List[dict],
    corrections: Dict[str, dict],
) -> List[str]:
    """Apply score overrides to schedule CSV rows. Returns corrected game_ids."""
    if not corrections:
        return []

    applied: List[str] = []
    for game_id, correction in corrections.items():
        home_score = correction.get("home_score")
        away_score = correction.get("away_score")
        if home_score is None or away_score is None:
            continue

        home_score_str = str(int(home_score))
        away_score_str = str(int(away_score))
        matched = False

        for row in rows:
            if (row.get("game_id") or "").strip() != game_id:
                continue
            matched = True
            if row.get("home_away") == "home":
                row["team_score"] = home_score_str
                row["opponent_score"] = away_score_str
            elif row.get("home_away") == "away":
                row["team_score"] = away_score_str
                row["opponent_score"] = home_score_str

        if matched:
            applied.append(game_id)

    return applied


def get_yard_overrides(
    corrections: Dict[str, dict],
    game_id: str,
) -> Tuple[Optional[float], Optional[float]]:
    """Return optional (home_yards, away_yards) overrides for a game."""
    correction = corrections.get(game_id)
    if not correction:
        return None, None

    home_yards = correction.get("home_yards")
    away_yards = correction.get("away_yards")
    home = float(home_yards) if home_yards is not None else None
    away = float(away_yards) if away_yards is not None else None
    return home, away


def apply_yard_corrections(
    rows: List[dict],
    corrections: Dict[str, dict],
) -> List[str]:
    """Apply yard overrides to schedule CSV rows. Returns corrected game_ids."""
    if not corrections:
        return []

    applied: List[str] = []
    for game_id, correction in corrections.items():
        home_yards = correction.get("home_yards")
        away_yards = correction.get("away_yards")
        if home_yards is None and away_yards is None:
            continue

        home_yards_str = str(int(home_yards)) if home_yards is not None else None
        away_yards_str = str(int(away_yards)) if away_yards is not None else None
        matched = False

        for row in rows:
            if (row.get("game_id") or "").strip() != game_id:
                continue
            matched = True
            if row.get("home_away") == "home":
                if home_yards_str is not None:
                    row["team_yards"] = home_yards_str
                if away_yards_str is not None:
                    row["opponent_yards"] = away_yards_str
            elif row.get("home_away") == "away":
                if away_yards_str is not None:
                    row["team_yards"] = away_yards_str
                if home_yards_str is not None:
                    row["opponent_yards"] = home_yards_str

        if matched:
            applied.append(game_id)

    return applied


def get_score_overrides(
    corrections: Dict[str, dict],
    game_id: str,
) -> Tuple[Optional[float], Optional[float]]:
    """Return optional (home_score, away_score) overrides for a game."""
    correction = corrections.get(game_id)
    if not correction:
        return None, None

    home_score = correction.get("home_score")
    away_score = correction.get("away_score")
    home = float(home_score) if home_score is not None else None
    away = float(away_score) if away_score is not None else None
    return home, away
