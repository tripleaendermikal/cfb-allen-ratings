#!/usr/bin/env python3
"""
Add Week 13 Pac-12 flex games for all 8 Pac-12 teams.

Replaces TBD Week 13 placeholders with one flex row per team (opponent varies per sim).
Idempotent: skips teams that already have pac12_flex_week13=1.
Run after FPI sim columns exist and before add_sim_margins.
"""

from __future__ import annotations

from cfb_paths import data_root

import argparse
import csv
import sys
from pathlib import Path

from pac12_week13 import (
    FLEX_FLAG_COL,
    FLEX_FLAG_VALUE,
    FLEX_GAME_ID_START,
    LEGACY_TBD_PATCH_GAME_IDS,
    PAC12_AWAY_IDS,
    PAC12_FLEX_OPPONENT_ID,
    PAC12_FLEX_OPPONENT_NAME,
    PAC12_HOME_IDS,
    PAC12_TEAM_IDS,
    PAC12_TEAM_NAMES,
    is_flex_row,
    is_pac12_team,
)

DEFAULT_GAMES = data_root() / "cfb_2026_fbs_games_with_fpi.csv"
GAME_DATE = "2026-11-28T05:00Z"
WEEK = "13"
TBD_ID = "-2"


def sim_columns(fieldnames: list[str]) -> list[str]:
    return [c for c in fieldnames if c.startswith("sim_")]


def find_team_row(rows: list[dict[str, str]], team_id: str) -> dict[str, str] | None:
    for row in rows:
        if (row.get("team_id") or "").strip() == team_id:
            return row
    return None


def has_flex_row(rows: list[dict[str, str]], team_id: str) -> bool:
    for row in rows:
        if (row.get("team_id") or "").strip() != team_id:
            continue
        if is_flex_row(row):
            return True
    return False


def should_remove_row(row: dict[str, str]) -> bool:
    gid = (row.get("game_id") or "").strip()
    if gid in LEGACY_TBD_PATCH_GAME_IDS:
        return True
    week = (row.get("week") or "").strip()
    tid = (row.get("team_id") or "").strip()
    oid = (row.get("opponent_id") or "").strip()
    if week == WEEK and is_pac12_team(tid) and oid == TBD_ID:
        return True
    if week == WEEK and tid == TBD_ID and is_pac12_team(oid):
        return True
    return False


def build_flex_row(
    team_id: str,
    game_id: str,
    team_row: dict[str, str],
    sim_cols: list[str],
) -> dict[str, str]:
    home_away = "home" if team_id in PAC12_HOME_IDS else "away"
    team_name = PAC12_TEAM_NAMES.get(team_id, team_row.get("team_name", ""))
    team_fpi = (team_row.get("team_fpi") or "").strip()

    row = {k: "" for k in team_row}
    row.update(
        {
            "game_id": game_id,
            "game_date_utc": GAME_DATE,
            "season_year": "2026",
            "week": WEEK,
            "season_type": "regular-season",
            "neutral_site": "False",
            "team_id": team_id,
            "team_name": team_name,
            "home_away": home_away,
            "opponent_id": PAC12_FLEX_OPPONENT_ID,
            "opponent_name": PAC12_FLEX_OPPONENT_NAME,
            "team_fpi": team_fpi,
            "opponent_fpi": "",
            "expected_margin_of_victory": "",
            "team_score": "0",
            "opponent_score": "0",
            "game_completed": "False",
            FLEX_FLAG_COL: FLEX_FLAG_VALUE,
        }
    )
    for col in sim_cols:
        row[col] = team_row.get(col, "")
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("games_csv", nargs="?", type=Path, default=DEFAULT_GAMES)
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()

    inp = args.games_csv
    if not inp.is_file():
        print(f"Input not found: {inp}", file=sys.stderr)
        return 1

    out_path = args.output or inp

    with inp.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if FLEX_FLAG_COL not in fieldnames:
        fieldnames.append(FLEX_FLAG_COL)

    sim_cols = sim_columns(fieldnames)
    removed = sum(1 for row in rows if should_remove_row(row))
    rows = [row for row in rows if not should_remove_row(row)]

    added = 0
    game_id_num = FLEX_GAME_ID_START
    for team_id in list(PAC12_HOME_IDS) + list(PAC12_AWAY_IDS):
        if has_flex_row(rows, team_id):
            print(f"Skip team_id {team_id}: flex Week {WEEK} row already present")
            continue

        team_row = find_team_row(rows, team_id)
        if team_row is None:
            print(f"Team row not found for team_id {team_id}", file=sys.stderr)
            return 1

        game_id = str(game_id_num)
        game_id_num += 1
        rows.append(build_flex_row(team_id, game_id, team_row, sim_cols))
        added += 1
        print(f"Added flex game {game_id}: {PAC12_TEAM_NAMES.get(team_id, team_id)} (Week {WEEK})")

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(
        f"Wrote {len(rows)} rows ({removed} removed, {added} flex added) -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
