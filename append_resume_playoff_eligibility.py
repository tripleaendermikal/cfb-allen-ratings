#!/usr/bin/env python3
"""Append sim_1001..sim_2000 resume-playoff eligibility columns."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from cfb_conf_championship import compute_conf_results_by_sim
from cfb_in_season_sim import IN_SEASON_PREFIX
from cfb_paths import data_root
from cfb_playoff_elig import (
    load_sim_fpi_by_team_id,
    load_sos_by_team_id,
    sim_columns,
)
from cfb_playoff_resume_elig import (
    compute_column_eligibility_resume,
    paired_resume_elig_col,
)
from cfb_rating.season_data import load_fbs_team_ids
from cfb_rating.sim_resume import (
    compute_sim_resume_margins,
    overall_margins_for_sim_col,
)
from export_sim_data import build_sim_records_by_team_col

DEFAULT_RECORDS = data_root() / f"{IN_SEASON_PREFIX}_fbs_team_sim_records_v2.csv"
DEFAULT_GAMES_SIM = data_root() / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi_simulated.csv"
DEFAULT_GAMES_FPI = data_root() / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi.csv"
DEFAULT_ELIG = data_root() / f"{IN_SEASON_PREFIX}_FBS_playoff_elig_v2.csv"
DEFAULT_CONF = data_root() / "espn_cfb_teams_conferences.csv"


def append_resume_columns(
    elig_path: Path,
    records_path: Path,
    games_sim_path: Path,
    games_fpi_path: Path,
    conf_path: Path,
) -> tuple[int, int]:
    with elig_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        elig_rows = list(reader)

    with records_path.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    with games_sim_path.open(encoding="utf-8-sig", newline="") as handle:
        game_rows = list(csv.DictReader(handle))

    game_sim_cols = sim_columns(source_rows[0].keys() if source_rows else [])
    if not game_sim_cols:
        raise RuntimeError("No sim columns on records file")

    sim_fpi_by_team_id = load_sim_fpi_by_team_id(games_fpi_path)
    sos_by_team_id = load_sos_by_team_id(games_fpi_path)
    conf_results = compute_conf_results_by_sim(
        games_sim_path, games_fpi_path, conf_path
    )
    conf_champions = conf_results["champions"]
    conf_finalists = conf_results["finalists"]
    wl_by_team_col = build_sim_records_by_team_col(
        source_rows,
        game_sim_cols,
        game_rows,
        conf_champions,
        conf_finalists,
    )

    fbs_ids = frozenset(load_fbs_team_ids().keys())
    team_ids = sorted(
        (row.get("team_id") or "").strip()
        for row in source_rows
        if (row.get("team_id") or "").strip()
    )

    new_cols: list[str] = []
    for game_col in game_sim_cols:
        resume_col = paired_resume_elig_col(game_col)
        if resume_col not in fieldnames:
            fieldnames.append(resume_col)
            new_cols.append(resume_col)
        for row in elig_rows:
            row.setdefault(resume_col, "0")

    ok = 0
    failed = 0
    for game_col in game_sim_cols:
        resume_col = paired_resume_elig_col(game_col)
        overall = overall_margins_for_sim_col(sim_fpi_by_team_id, game_col, team_ids)
        margins = compute_sim_resume_margins(
            game_rows,
            game_col,
            team_ids,
            overall,
            fbs_team_ids=fbs_ids,
        )
        losses_by_team_id = {
            tid: wl[1]
            for tid, wl in (
                (tid, by_col.get(game_col, (0, 0)))
                for tid, by_col in wl_by_team_col.items()
            )
        }
        compute_column_eligibility_resume(
            elig_rows,
            source_rows,
            resume_col,
            margins,
            conf_champions,
            sos_by_team_id,
            game_col,
            losses_by_team_id,
        )
        count = sum(int(row.get(resume_col) or 0) for row in elig_rows)
        if count == 12:
            ok += 1
        else:
            failed += 1
            print(
                f"Warning: {resume_col} has {count} playoff teams (expected 12)",
                file=sys.stderr,
            )

    with elig_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(elig_rows)

    print(f"Resume playoff columns: {ok} ok, {failed} failed (of {len(game_sim_cols)})")
    return ok, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elig", type=Path, default=DEFAULT_ELIG)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--games-sim", type=Path, default=DEFAULT_GAMES_SIM)
    parser.add_argument("--games-fpi", type=Path, default=DEFAULT_GAMES_FPI)
    parser.add_argument("--conferences", type=Path, default=DEFAULT_CONF)
    args = parser.parse_args()

    for label, path in (
        ("elig", args.elig),
        ("records", args.records),
        ("games-sim", args.games_sim),
        ("games-fpi", args.games_fpi),
    ):
        if not path.is_file():
            print(f"Missing {label}: {path}", file=sys.stderr)
            return 1

    append_resume_columns(
        args.elig,
        args.records,
        args.games_sim,
        args.games_fpi,
        args.conferences,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
