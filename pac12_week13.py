#!/usr/bin/env python3
"""Pac-12 Week 13 flex games: fixed home/away sets and per-sim bipartite pairings."""

from __future__ import annotations

import random
import re
from typing import Sequence

# Former TBD hosts (always home in flex game).
PAC12_HOME_IDS: tuple[str, ...] = ("36", "278", "328", "265")

# Teams without a Week 13 opponent on ESPN schedule (always away in flex game).
PAC12_AWAY_IDS: tuple[str, ...] = ("68", "204", "21", "326")

PAC12_TEAM_IDS: frozenset[str] = frozenset(PAC12_HOME_IDS + PAC12_AWAY_IDS)

PAC12_FLEX_OPPONENT_ID = "-3"
PAC12_FLEX_OPPONENT_NAME = "Pac-12 (TBD)"

FLEX_FLAG_COL = "pac12_flex_week13"
FLEX_FLAG_VALUE = "1"

LEGACY_TBD_PATCH_GAME_IDS = frozenset({"401870001", "401870002"})
FLEX_GAME_ID_START = 401879001

MARGIN_RE = re.compile(r"^margin_(\d+)$")
WIN_RE = re.compile(r"^win_(\d+)$")
SIM_RE = re.compile(r"^sim_(\d+)$")

PAC12_TEAM_NAMES: dict[str, str] = {
    "36": "Colorado State Rams",
    "278": "Fresno State Bulldogs",
    "328": "Utah State Aggies",
    "265": "Washington State Cougars",
    "68": "Boise State Broncos",
    "204": "Oregon State Beavers",
    "21": "San Diego State Aztecs",
    "326": "Texas State Bobcats",
}


def is_pac12_team(team_id: str) -> bool:
    return (team_id or "").strip() in PAC12_TEAM_IDS


def is_flex_row(row: dict[str, str]) -> bool:
    return (row.get(FLEX_FLAG_COL) or "").strip() == FLEX_FLAG_VALUE


def pair_home_away(rng: random.Random) -> list[tuple[str, str]]:
    """Shuffle away teams and assign one to each home team (bipartite matching)."""
    away = list(PAC12_AWAY_IDS)
    rng.shuffle(away)
    return [(home, away[i]) for i, home in enumerate(PAC12_HOME_IDS)]


def pairing_rng(main_seed: int | None, sim_index: int) -> random.Random:
    return random.Random((main_seed or 0) * 100_000 + sim_index)


def col_sim_index(col: str) -> int:
    if m := WIN_RE.match(col or ""):
        return int(m.group(1))
    if m := MARGIN_RE.match(col or ""):
        return int(m.group(1))
    if m := SIM_RE.match(col or ""):
        return int(m.group(1))
    raise ValueError(f"Not a sim/margin/win column: {col}")


def margin_col_index(margin_col: str) -> int:
    return col_sim_index(margin_col)


def apply_flex_conf_stats_for_cols(
    sim_cols: Sequence[str],
    flex_rows_by_team: dict[str, dict],
    conf_games: dict[str, dict[str, int]],
    conf_wins: dict[str, dict[str, int]],
    h2h_wins: dict[str, dict[tuple[str, str], int]],
    h2h_games: dict[str, dict[frozenset[str], int]],
    main_seed: int | None = None,
) -> None:
    """Add Pac-12 flex Week 13 conf games and h2h from win columns on flex rows."""
    if not flex_rows_by_team:
        return

    for col in sim_cols:
        sim_index = col_sim_index(col)
        pairs = pair_home_away(pairing_rng(main_seed, sim_index))
        for home_id, away_id in pairs:
            home_row = flex_rows_by_team.get(home_id)
            away_row = flex_rows_by_team.get(away_id)
            if home_row is None or away_row is None:
                continue

            home_win = (home_row.get(col) or "").strip() == "1"
            conf_games[col][home_id] += 1
            conf_games[col][away_id] += 1
            pair = frozenset((home_id, away_id))
            h2h_games[col][pair] += 1
            if home_win:
                conf_wins[col][home_id] += 1
                h2h_wins[col][(home_id, away_id)] += 1
            else:
                conf_wins[col][away_id] += 1
                h2h_wins[col][(away_id, home_id)] += 1
