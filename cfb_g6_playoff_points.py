#!/usr/bin/env python3
"""Compute Group of 6 playoff points per simulation for autobid selection."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from cfb_playoff_elig import GROUP_CONFERENCES, sim_columns

SIM_COL_PATTERN = re.compile(r"^sim_\d+$")
UCONN_TEAM_ID = "41"
CONFERENCE_BONUS = {"American", "Pac-12"}


def load_conf_by_team_id(path: Path) -> dict[str, str]:
    by_id: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8-sig") as infile:
        for row in csv.DictReader(infile):
            tid = (row.get("team_id") or "").strip()
            conf = (row.get("conference") or "").strip()
            if tid:
                by_id[tid] = conf
    return by_id


def is_non_g6_opponent(opponent_id: str, conf_by_team_id: dict[str, str]) -> bool:
    opp_conf = conf_by_team_id.get(opponent_id, "")
    return opp_conf not in GROUP_CONFERENCES


def points_for_team_sim(
    team_id: str,
    conference: str,
    games: list[dict[str, str]],
    col: str,
    conf_by_team_id: dict[str, str],
    conf_champions_by_sim: dict[str, dict[str, str]],
) -> int:
    points = 0
    for game in games:
        result = (game.get(col) or "").strip()
        opp_id = (game.get("opponent_id") or "").strip()
        if result == "1":
            points += 1
            if is_non_g6_opponent(opp_id, conf_by_team_id) and opp_id != UCONN_TEAM_ID:
                points += 1

    if conf_champions_by_sim.get(col, {}).get(conference) == team_id:
        points += 1
    if conference in CONFERENCE_BONUS:
        points += 1
    return points


def compute_g6_playoff_points(
    games_sim_path: Path,
    conf_path: Path,
    conf_champions_by_sim: dict[str, dict[str, str]],
) -> tuple[list[str], list[dict[str, str]]]:
    conf_by_team_id = load_conf_by_team_id(conf_path)
    games_by_team: dict[str, list[dict[str, str]]] = {}
    team_meta: dict[str, dict[str, str]] = {}

    with games_sim_path.open(newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        sim_cols = sim_columns(reader.fieldnames or [])
        for row in reader:
            tid = (row.get("team_id") or "").strip()
            conf = conf_by_team_id.get(tid, "")
            if not tid or conf not in GROUP_CONFERENCES:
                continue
            if tid not in team_meta:
                team_meta[tid] = {
                    "team_id": tid,
                    "team_name": row.get("team_name", ""),
                    "conference": conf,
                }
            game_row = dict(row)
            games_by_team.setdefault(tid, []).append(game_row)

    fieldnames = ["team_id", "team_name", "conference", *sim_cols]
    rows: list[dict[str, str]] = []
    for tid in sorted(team_meta, key=lambda t: (team_meta[t]["conference"], team_meta[t]["team_name"])):
        meta = team_meta[tid]
        out = dict(meta)
        games = games_by_team.get(tid, [])
        for col in sim_cols:
            pts = points_for_team_sim(
                tid,
                meta["conference"],
                games,
                col,
                conf_by_team_id,
                conf_champions_by_sim,
            )
            out[col] = str(pts)
        rows.append(out)

    return fieldnames, rows


def g6_points_by_team_id_from_rows(
    rows: list[dict[str, str]], fieldnames: list[str]
) -> dict[str, dict[str, int]]:
    sim_cols = [c for c in fieldnames if SIM_COL_PATTERN.match(c or "")]
    out: dict[str, dict[str, int]] = {}
    for row in rows:
        tid = row["team_id"]
        out[tid] = {col: int(row[col]) for col in sim_cols}
    return out


def load_g6_points_by_team_id(path: Path) -> dict[str, dict[str, int]]:
    with path.open(newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return g6_points_by_team_id_from_rows(rows, fieldnames)


def write_g6_playoff_points(
    output_path: Path,
    games_sim_path: Path,
    conf_path: Path,
    conf_champions_by_sim: dict[str, dict[str, str]],
) -> tuple[dict[str, dict[str, int]], int]:
    fieldnames, rows = compute_g6_playoff_points(
        games_sim_path, conf_path, conf_champions_by_sim
    )
    output_path = Path(output_path)
    with output_path.open("w", newline="", encoding="utf-8-sig") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    points_by_team = g6_points_by_team_id_from_rows(rows, fieldnames)
    return points_by_team, len(rows)
