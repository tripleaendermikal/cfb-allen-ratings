#!/usr/bin/env python3
"""Compute playoff eligibility flags from team simulation records."""

from __future__ import annotations

from cfb_paths import data_root

import argparse
from pathlib import Path

from cfb_conf_championship import compute_conf_results_by_sim
from cfb_g6_playoff_points import write_g6_playoff_points
from cfb_in_season_sim import IN_SEASON_PREFIX
from cfb_playoff_elig import write_playoff_eligibility

DEFAULT_RECORDS = data_root() / "cfb_2026_fbs_team_sim_records_v2.csv"
DEFAULT_GAMES_SIM = data_root() / "cfb_2026_fbs_games_with_fpi_simulated.csv"
DEFAULT_GAMES_FPI = data_root() / "cfb_2026_fbs_games_with_fpi.csv"
DEFAULT_CONF = data_root() / "espn_cfb_teams_conferences.csv"
DEFAULT_G6_POINTS = data_root() / "cfb_2026_FBS_g6_playoff_points.csv"
DEFAULT_OUTPUT = data_root() / "cfb_2026_FBS_playoff_elig_v2.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--games-sim", type=Path, default=DEFAULT_GAMES_SIM)
    parser.add_argument("--games-fpi", type=Path, default=DEFAULT_GAMES_FPI)
    parser.add_argument("--conferences", type=Path, default=DEFAULT_CONF)
    parser.add_argument("--g6-points", type=Path, default=DEFAULT_G6_POINTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--in-season",
        action="store_true",
        help=f"Use default {IN_SEASON_PREFIX}_* input/output paths",
    )
    return parser


def resolve_paths(
    args: argparse.Namespace,
) -> tuple[Path, Path, Path, Path, Path, Path]:
    if not args.in_season:
        return (
            args.records,
            args.games_sim,
            args.games_fpi,
            args.conferences,
            args.g6_points,
            args.output,
        )
    return (
        data_root() / f"{IN_SEASON_PREFIX}_fbs_team_sim_records_v2.csv",
        data_root() / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi_simulated.csv",
        data_root() / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi.csv",
        args.conferences,
        data_root() / f"{IN_SEASON_PREFIX}_FBS_g6_playoff_points.csv",
        data_root() / f"{IN_SEASON_PREFIX}_FBS_playoff_elig_v2.csv",
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    (
        records_path,
        games_sim_path,
        games_fpi_path,
        conf_path,
        g6_points_path,
        output_path,
    ) = resolve_paths(args)

    results = compute_conf_results_by_sim(games_sim_path, games_fpi_path, conf_path)
    g6_points_by_team_id, g6_count = write_g6_playoff_points(
        g6_points_path,
        games_sim_path,
        conf_path,
        results["champions"],
    )
    print(f"Wrote {g6_count} rows to {g6_points_path}")

    count = write_playoff_eligibility(
        records_path,
        output_path,
        games_fpi_path=games_fpi_path,
        games_sim_path=games_sim_path,
        conf_path=conf_path,
        conf_champions_by_sim=results["champions"],
        g6_points_by_team_id=g6_points_by_team_id,
        g6_points_path=g6_points_path,
    )
    print(f"Wrote {count} rows to {output_path}")
    print()
    print("NEXT (required): refresh national title odds from the new eligibility field:")
    if args.in_season:
        print(
            "  python cfb_playoff_odds_calc.py --from-data "
            f"--elig {output_path} "
            f"--games-fpi {games_fpi_path} "
            "--output cfb_2026_in_season_FBS_playoff_champ_odds_fpi_seed.csv"
        )
    else:
        print("  python cfb_playoff_odds_calc.py --from-data")
    print("  python cfb-viewer/export_sim_data.py")


if __name__ == "__main__":
    main()
