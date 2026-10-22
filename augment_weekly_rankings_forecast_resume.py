#!/usr/bin/env python3
"""Add forecast_resume_margin to weekly rankings using sim projected wins."""

from __future__ import annotations

import argparse
from pathlib import Path

from cfb_conf_championship import compute_conf_results_by_sim

import export_sim_data as esd
from cfb_paths import data_root
from cfb_rating.forecast_resume_enrich import (
    augment_weekly_rankings_csv_forecast_resume,
    projected_season_stats_from_sims,
)

IN_SEASON_PREFIX = "cfb_2026_in_season"
DEFAULT_GAMES = data_root() / "cfb_2026_fbs_games_with_fpi.csv"
DEFAULT_RANKINGS = data_root() / f"{IN_SEASON_PREFIX}_weekly_rankings.csv"
DEFAULT_RECORDS = data_root() / f"{IN_SEASON_PREFIX}_fbs_team_sim_records_v2.csv"
DEFAULT_GAMES_SIM = data_root() / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi_simulated.csv"
DEFAULT_GAMES_FPI = data_root() / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi.csv"
DEFAULT_CONFERENCES = data_root() / "espn_cfb_teams_conferences.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=Path, default=DEFAULT_GAMES)
    parser.add_argument("--rankings", type=Path, default=DEFAULT_RANKINGS)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--games-sim", type=Path, default=DEFAULT_GAMES_SIM)
    parser.add_argument("--games-fpi", type=Path, default=DEFAULT_GAMES_FPI)
    parser.add_argument("--conferences", type=Path, default=DEFAULT_CONFERENCES)
    args = parser.parse_args()

    if not args.rankings.is_file():
        print(f"Missing rankings: {args.rankings}")
        return 1
    if not args.records.is_file():
        print(f"Missing sim records: {args.records}")
        return 1
    if not args.games_sim.is_file():
        print(f"Missing simulated games: {args.games_sim}")
        return 1

    _, records_rows = esd.read_csv(args.records)
    _, game_rows = esd.read_csv(args.games_sim)
    sim_cols = esd.sim_columns(list(records_rows[0].keys()) if records_rows else [])
    conf_finalists = None
    if args.games_fpi.is_file() and args.conferences.is_file():
        conf_finalists = compute_conf_results_by_sim(
            args.games_sim, args.games_fpi, args.conferences
        )["finalists"]
    projected_wins, projected_games = projected_season_stats_from_sims(
        records_rows,
        sim_cols,
        game_rows,
        conf_finalists_by_sim=conf_finalists,
    )

    count = augment_weekly_rankings_csv_forecast_resume(
        args.rankings,
        args.games,
        projected_wins,
        projected_games,
    )
    print(f"Updated forecast_resume_margin on {count} rows in {args.rankings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
