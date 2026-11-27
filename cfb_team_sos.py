"""Strength of schedule via expected win% and equivalent-opponent inversion."""

from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence

from cfb_rating.rating_algorithm import GameRecord
from cfb_rating.win_prob import equivalent_opponent_margin, team_win_probability

DEFAULT_OPPONENT_MARGIN = -32.0


def _parse_neutral(neutral_site) -> bool:
    n = str(neutral_site or "").strip().lower()
    return n in ("true", "1", "yes")


def compute_equivalent_sos_from_game_records(
    games: Sequence[GameRecord],
    ratings: Mapping[str, float],
    *,
    default_margin: float = DEFAULT_OPPONENT_MARGIN,
) -> dict[str, float]:
    """Step 1: mean expected win% on schedule; step 2: equivalent neutral opponent margin."""
    win_probs: dict[str, list[float]] = defaultdict(list)
    for game in games:
        hr = float(ratings.get(game.home_team_id, default_margin))
        ar = float(ratings.get(game.away_team_id, default_margin))
        p_home = team_win_probability(
            game.home_team_id,
            game.home_team_id,
            game.away_team_id,
            hr,
            ar,
            neutral_site=game.neutral_site,
        )
        win_probs[game.home_team_id].append(p_home)
        win_probs[game.away_team_id].append(1.0 - p_home)

    out: dict[str, float] = {}
    for tid, probs in win_probs.items():
        if not probs:
            continue
        team_m = float(ratings.get(tid, default_margin))
        mean_wp = sum(probs) / len(probs)
        out[tid] = round(equivalent_opponent_margin(team_m, mean_wp), 2)
    return out


def compute_equivalent_sos_from_schedule(
    schedule: Sequence[dict],
    ratings: Mapping[str, float],
    *,
    default_margin: float = DEFAULT_OPPONENT_MARGIN,
    skip_row=None,
) -> dict[str, float]:
    """Same SOS definition from team-centric schedule rows (``team_fpi`` / ``opponent_fpi`` fallback)."""
    from pac12_week13 import FLEX_FLAG_COL, FLEX_FLAG_VALUE, PAC12_FLEX_OPPONENT_ID

    win_probs: dict[str, list[float]] = defaultdict(list)
    for row in schedule:
        if skip_row is not None and skip_row(row):
            continue
        tid = (row.get("team_id") or "").strip()
        oid = (row.get("opponent_id") or "").strip()
        if not tid:
            continue
        if oid == PAC12_FLEX_OPPONENT_ID or (
            (row.get(FLEX_FLAG_COL) or "").strip() == FLEX_FLAG_VALUE
        ):
            continue
        team_m = ratings.get(tid)
        if team_m is None:
            raw = row.get("team_fpi")
            team_m = float(raw) if raw is not None else None
        opp_m = ratings.get(oid)
        if opp_m is None:
            raw = row.get("opponent_fpi")
            opp_m = float(raw) if raw is not None else None
        if team_m is None or opp_m is None:
            continue
        team_m = float(team_m)
        opp_m = float(opp_m)
        neutral = _parse_neutral(row.get("neutral_site"))
        ha = (row.get("home_away") or "").strip().lower()
        if ha == "home":
            p = team_win_probability(
                tid, tid, oid, team_m, opp_m, neutral_site=neutral
            )
        elif ha == "away":
            p = team_win_probability(
                tid, oid, tid, opp_m, team_m, neutral_site=neutral
            )
        else:
            continue
        win_probs[tid].append(p)

    out: dict[str, float] = {}
    for tid, probs in win_probs.items():
        if not probs:
            continue
        team_m = float(ratings.get(tid, default_margin))
        mean_wp = sum(probs) / len(probs)
        out[tid] = round(equivalent_opponent_margin(team_m, mean_wp), 2)
    return out


# Backward-compatible alias for prior-season export (replaces mean-opponent-FPI SOS).
def compute_team_sos_from_games(
    games: Sequence[GameRecord],
    opponent_margins: Mapping[str, float],
    *,
    default_margin: float = DEFAULT_OPPONENT_MARGIN,
) -> dict[str, float]:
    return compute_equivalent_sos_from_game_records(
        games, opponent_margins, default_margin=default_margin
    )