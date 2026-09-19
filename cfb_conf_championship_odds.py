#!/usr/bin/env python3
"""
Compute conference championship odds from simulated in-conference results.

For each simulation and conference:
  1. Rank teams by conference win percentage (conf wins / conf games)
  2. Select top 2 with H2H-then-FPI tiebreakers
  3. Neutral-site title game via per-sim FPI logistic model

Examples:
  python cfb_conf_championship_odds.py --from-data
"""

from __future__ import annotations

from cfb_paths import data_root

import argparse
from collections import defaultdict
from pathlib import Path

from cfb_conf_championship import write_conf_championship_odds

DEFAULT_GAMES_SIM_PATH = Path(__file__).with_name(
    "cfb_2026_fbs_games_with_fpi_simulated.csv"
)
DEFAULT_GAMES_FPI_PATH = data_root() / "cfb_2026_fbs_games_with_fpi.csv"
DEFAULT_CONF_PATH = data_root() / "espn_cfb_teams_conferences.csv"
DEFAULT_OUTPUT_PATH = data_root() / "cfb_2026_FBS_conf_champ_odds.csv"


def print_conference_favorites(output_path: Path) -> None:
    import csv

    by_conf: dict[str, list[dict]] = defaultdict(list)
    with output_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            conf = row.get("conference", "")
            if not conf or conf == "FBS Indep.":
                continue
            by_conf[conf].append(row)

    print("\nConference favorites:")
    for conf in sorted(by_conf.keys()):
        teams = sorted(
            by_conf[conf],
            key=lambda r: (-float(r["conf_champ_odds_pct"]), r["team_name"]),
        )
        fav = teams[0]
        print(
            f"  {conf}: {fav['team_name']} "
            f"({float(fav['conf_champ_odds_pct']):.1f}%)"
        )


def run_from_data(
    games_sim_path: Path,
    games_fpi_path: Path,
    conf_path: Path,
    output_path: Path,
) -> int:
    count, n_sims = write_conf_championship_odds(
        games_sim_path, games_fpi_path, conf_path, output_path
    )
    print(f"Processed {n_sims} simulations")
    print(f"Wrote {count} teams to {output_path}")
    print_conference_favorites(output_path)
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CFB conference championship odds calculator"
    )
    parser.add_argument(
        "--from-data",
        action="store_true",
        help="Compute odds from simulated games + per-sim FPI",
    )
    parser.add_argument("--games-sim", type=Path, default=DEFAULT_GAMES_SIM_PATH)
    parser.add_argument("--games-fpi", type=Path, default=DEFAULT_GAMES_FPI_PATH)
    parser.add_argument("--conferences", type=Path, default=DEFAULT_CONF_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.from_data:
        run_from_data(
            args.games_sim, args.games_fpi, args.conferences, args.output
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
