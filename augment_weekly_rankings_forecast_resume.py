#!/usr/bin/env python3
"""Add forecast_resume_margin to weekly rankings using sim projected wins."""

from __future__ import annotations

import argparse
from pathlib import Path

import export_sim_data as esd
from cfb_paths import data_root
from cfb_rating.forecast_resume_enrich import (
    augment_weekly_rankings_csv_forecast_resume,
    projected_wins_from_sim_records,
)

DEFAULT_GAMES = data_root() / "cfb_2026_fbs_games_with_fpi.csv"
DEFAULT_RANKINGS = data_root() / "cfb_2026_in_season_weekly_rankings.csv"
DEFAULT_RECORDS = data_root() / "cfb_2026_in_season_fbs_team_sim_records_v2.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=Path, default=DEFAULT_GAMES)
    parser.add_argument("--rankings", type=Path, default=DEFAULT_RANKINGS)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    args = parser.parse_args()

    if not args.rankings.is_file():
        print(f"Missing rankings: {args.rankings}")
        return 1
    if not args.records.is_file():
        print(f"Missing sim records: {args.records}")
        return 1

    _, records_rows = esd.read_csv(args.records)
    sim_cols = esd.sim_columns(list(records_rows[0].keys()) if records_rows else [])
    projected = projected_wins_from_sim_records(records_rows, sim_cols)

    count = augment_weekly_rankings_csv_forecast_resume(
        args.rankings,
        args.games,
        projected,
    )
    print(f"Updated forecast_resume_margin on {count} rows in {args.rankings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
