#!/usr/bin/env python3
"""
Build a CSV of each team's win total in every simulated season.

Reads the output of simulate_cfb_games.py (rows = team-game, columns sim_001..sim_N).
Output: one row per distinct team_id, one column per simulation, integer wins only.
"""

from __future__ import annotations

from cfb_paths import data_root

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

SIM_COL_PATTERN = re.compile(r"^sim_(\d+)$")
MAX_WINS = 12

# Teams with fewer than 12 scheduled games may get a per-sim win bonus (playoff eligibility).
WIN_BONUS_BY_TEAM_ID: dict[str, int] = {}


def load_conference_lookup(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Return (by_team_id, by_team_name) -> conference label."""
    by_id: dict[str, str] = {}
    by_name: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tid = (row.get("team_id") or "").strip()
            name = (row.get("team_name") or "").strip()
            conf = (row.get("conference") or "").strip()
            if tid:
                by_id[tid] = conf
            if name:
                by_name[name] = conf
    return by_id, by_name


def resolve_conference(
    team_id: str,
    team_name: str,
    by_id: dict[str, str],
    by_name: dict[str, str],
) -> str:
    return by_id.get(team_id) or by_name.get(team_name) or ""


def find_sim_columns(fieldnames: list[str] | None) -> list[str]:
    if not fieldnames:
        return []
    cols = [c for c in fieldnames if SIM_COL_PATTERN.match(c or "")]
    return sorted(cols, key=lambda c: int(SIM_COL_PATTERN.match(c).group(1)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_csv",
        nargs="?",
        type=Path,
        default=None,
        help="Simulated games CSV (default: *_simulated.csv next to this script)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output CSV (default: input stem + _team_records.csv)",
    )
    parser.add_argument(
        "--conferences",
        type=Path,
        default=None,
        help="ESPN teams/conferences CSV to merge (default: espn_cfb_teams_conferences.csv)",
    )
    args = parser.parse_args()

    script_dir = data_root()
    inp = args.input_csv
    if inp is None:
        cand = script_dir / "cfb_2026_fbs_games_with_fpi_simulated.csv"
        inp = cand if cand.is_file() else script_dir / "cfb_2026_fbs_games_with_fpi_margin_simulated.csv"

    if not inp.is_file():
        print(f"Input not found: {inp}", file=sys.stderr)
        return 1

    out_path = args.output
    if out_path is None:
        out_path = inp.with_name(inp.stem + "_team_records" + inp.suffix)

    with inp.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        sim_cols = find_sim_columns(fieldnames)
        if not sim_cols:
            print("No sim_XXX columns found in input CSV", file=sys.stderr)
            return 1

        wins: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        team_name: dict[str, str] = {}

        for row in reader:
            tid = (row.get("team_id") or "").strip()
            if not tid:
                continue
            if tid not in team_name and row.get("team_name"):
                team_name[tid] = row["team_name"]

            for sc in sim_cols:
                v = (row.get(sc) or "").strip()
                if v == "1":
                    wins[tid][sc] += 1

    for tid in list(wins.keys()):
        team_name.setdefault(tid, "")

    def sort_key(tid: object):
        s = str(tid)
        if s.isdigit():
            return (0, int(s))
        return (1, s)

    team_ids = sorted(set(team_name.keys()) | set(wins.keys()), key=sort_key)

    by_id: dict[str, str] = {}
    by_name: dict[str, str] = {}
    conf_path = args.conferences
    if conf_path is None:
        conf_path = script_dir / "espn_cfb_teams_conferences.csv"
    if conf_path.is_file():
        by_id, by_name = load_conference_lookup(conf_path)

    out_fields = ["team_id", "team_name", "conference"] + sim_cols
    out_rows: list[dict[str, str]] = []
    for tid in team_ids:
        name = team_name.get(tid, "")
        r: dict[str, str] = {
            "team_id": tid,
            "team_name": name,
            "conference": resolve_conference(tid, name, by_id, by_name),
        }
        for sc in sim_cols:
            r[sc] = str(wins[tid][sc])
        bonus = WIN_BONUS_BY_TEAM_ID.get(tid, 0)
        if bonus:
            for sc in sim_cols:
                r[sc] = str(min(MAX_WINS, int(r[sc]) + bonus))
        out_rows.append(r)

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(out_rows)

    print(f"Wrote {len(out_rows)} teams and {len(sim_cols)} season columns to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
