"""Strength of schedule from game lists (preseason / FPI opponent margins)."""

from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence

from cfb_playoff_elig import home_field_adjustment
from cfb_rating.rating_algorithm import GameRecord

DEFAULT_OPPONENT_MARGIN = -32.0


def compute_team_sos_from_games(
    games: Sequence[GameRecord],
    opponent_margins: Mapping[str, float],
    *,
    default_margin: float = DEFAULT_OPPONENT_MARGIN,
) -> dict[str, float]:
    """Mean opponent rating with home-field adjustment (+3 home, −3 away).

    Matches ``build_team_sos`` / ``load_sos_by_team_id`` in the export pipeline.
    """
    by_team: dict[str, list[float]] = defaultdict(list)
    for game in games:
        home_id = game.home_team_id
        away_id = game.away_team_id
        home_m = float(opponent_margins.get(home_id, default_margin))
        away_m = float(opponent_margins.get(away_id, default_margin))
        if game.neutral_site:
            by_team[home_id].append(away_m)
            by_team[away_id].append(home_m)
            continue
        # Home team perspective: opponent away → subtract 3.
        by_team[home_id].append(
            away_m - home_field_adjustment(False, "home")
        )
        by_team[away_id].append(
            home_m - home_field_adjustment(False, "away")
        )
    return {
        tid: round(sum(vals) / len(vals), 2)
        for tid, vals in by_team.items()
        if vals
    }