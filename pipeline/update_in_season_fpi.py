#!/usr/bin/env python3
"""Write in-season per-simulation FPI draws centered on Overall margins."""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

from cfb_in_season_sim import count_completed_fbs_games, load_fbs_ids, per_team_sigma

from pipeline._paths import FPI_SIGMA, GAMES_BASE, GAMES_FPI, RANKINGS_CSV, SIM_COUNT


def load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_overall_margins(path: Path, week: int) -> dict[str, float]:
    margins: dict[str, float] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if int(row["week"]) != week:
                continue
            margins[row["team_id"]] = float(row["overall_margin"])
    return margins


def sim_columns(count: int) -> list[str]:
    width = max(4, len(str(count)))
    return [f"sim_{index:0{width}d}" for index in range(1, count + 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=Path, default=GAMES_BASE)
    parser.add_argument("--rankings", type=Path, default=RANKINGS_CSV)
    parser.add_argument("--output", type=Path, default=GAMES_FPI)
    parser.add_argument("--week", type=int, default=None)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--simulations", type=int, default=SIM_COUNT)
    args = parser.parse_args()

    if not args.games.is_file():
        print(f"Missing games file: {args.games}", file=sys.stderr)
        return 1
    if not args.rankings.is_file():
        print(f"Missing rankings file: {args.rankings}", file=sys.stderr)
        return 1

    fieldnames, rows = load_rows(args.games)
    week = args.week
    if week is None:
        completed_weeks = [
            int(row["week"])
            for row in rows
            if row.get("game_completed", "").lower() in {"true", "1", "yes"} and row.get("week", "").isdigit()
        ]
        week = max(completed_weeks) if completed_weeks else 1

    overall = load_overall_margins(args.rankings, week)
    fbs_ids = load_fbs_ids()
    games_played = count_completed_fbs_games(rows, fbs_ids)
    sim_cols = sim_columns(args.simulations)
    rng = random.Random(args.seed)

    base_fields = [field for field in fieldnames if not field.startswith("sim_")]
    out_fields = base_fields + sim_cols
    out_rows: list[dict[str, str]] = []
    draws_by_team: dict[str, list[str]] = {}

    for team_id in sorted(overall):
        sigma = per_team_sigma(FPI_SIGMA, games_played.get(team_id, 0))
        draws_by_team[team_id] = [
            f"{overall[team_id] + rng.gauss(0.0, sigma):.3f}" for _ in sim_cols
        ]

    for row in rows:
        out = dict(row)
        tid = row["team_id"]
        oid = row["opponent_id"]
        for col in sim_cols:
            idx = sim_cols.index(col)
            if tid in draws_by_team:
                out[col] = draws_by_team[tid][idx]
            elif oid in draws_by_team:
                out[col] = draws_by_team[oid][idx]
            else:
                out[col] = row.get("team_fpi", "0")
        out_rows.append(out)

    write_rows(args.output, out_fields, out_rows)
    print(f"Wrote in-season FPI draws for week {week} to {args.output}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
