#!/usr/bin/env python3
"""Run the 2026 in-season Monte Carlo simulation pipeline."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

from cfb_in_season_sim import IN_SEASON_PREFIX, count_completed_fbs_game_pairs
from cfb_paths import REPO_ROOT, data_root

PYTHON = sys.executable
DATA = data_root()

BASE_GAMES = DATA / "cfb_2026_fbs_games_with_fpi.csv"
IN_SEASON_FPI = DATA / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi.csv"
IN_SEASON_MARGIN = DATA / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi_margin.csv"
IN_SEASON_SIMULATED = DATA / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi_simulated.csv"
IN_SEASON_RECORDS = DATA / f"{IN_SEASON_PREFIX}_fbs_team_sim_records_v2.csv"
IN_SEASON_CONF_ODDS = DATA / f"{IN_SEASON_PREFIX}_FBS_conf_champ_odds.csv"
IN_SEASON_ELIG = DATA / f"{IN_SEASON_PREFIX}_FBS_playoff_elig_v2.csv"
IN_SEASON_TITLE_ODDS = DATA / f"{IN_SEASON_PREFIX}_FBS_playoff_champ_odds_fpi_seed.csv"
CONF_CSV = DATA / "espn_cfb_teams_conferences.csv"
BUILD_PS1 = REPO_ROOT / "build_cfb_fpi_games.ps1"


def run_step(label: str, cmd: list[str]) -> None:
    print(f"\n==> {label}")
    print("    " + " ".join(str(part) for part in cmd))
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def print_title_odds_preview(path: Path, limit: int = 10) -> None:
    if not path.is_file():
        print(f"No title odds file at {path}")
        return
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    rows.sort(
        key=lambda row: (
            -float(row.get("title_odds_pct") or row.get("championship_odds_pct") or 0),
            row.get("team_name", ""),
        )
    )
    print(f"\nTop {limit} title odds:")
    for row in rows[:limit]:
        odds = row.get("title_odds_pct") or row.get("championship_odds_pct") or ""
        print(f"  {row.get('team_name', ''):<35} {float(odds):.2f}%")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Skip build_cfb_fpi_games.ps1 and apply_preseason_fpi.py",
    )
    parser.add_argument(
        "--simulations",
        type=int,
        default=1000,
        help="Number of Monte Carlo seasons (default: 1000)",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--sigma",
        type=float,
        default=7.3,
        help="Base FPI draw std dev before in-season shrinkage (default: 7.3)",
    )
    parser.add_argument(
        "--rankings",
        type=Path,
        default=None,
        help="Weekly rankings CSV; Overall margins seed in-season sim FPI draws",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.skip_refresh:
        run_step(
            "Refresh schedule and scores",
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(BUILD_PS1),
            ],
        )
        run_step(
            "Apply preseason combined_FPI",
            [PYTHON, str(REPO_ROOT / "apply_preseason_fpi.py")],
        )

    if not BASE_GAMES.is_file():
        print(f"Base games file not found: {BASE_GAMES}", file=sys.stderr)
        return 1

    with BASE_GAMES.open(encoding="utf-8-sig", newline="") as handle:
        base_rows = list(csv.DictReader(handle))
    completed_games = count_completed_fbs_game_pairs(base_rows)
    print(f"\nCompleted FBS-vs-FBS games in base file: {completed_games}")

    fpi_cmd = [
        PYTHON,
        str(REPO_ROOT / "add_fpi_sim_columns.py"),
        str(BASE_GAMES),
        "--in-season",
        "-o",
        str(IN_SEASON_FPI),
        "-n",
        str(args.simulations),
        "--sigma",
        str(args.sigma),
    ]
    if args.seed is not None:
        fpi_cmd.extend(["--seed", str(args.seed)])
    if args.rankings is not None:
        fpi_cmd.extend(["--overall-rankings", str(args.rankings)])
    run_step("Draw per-season FPI with in-season sigma", fpi_cmd)

    run_step(
        "Patch Pac-12 Week 13 flex games",
        [PYTHON, str(REPO_ROOT / "patch_pac12_week13_flex.py"), str(IN_SEASON_FPI)],
    )

    run_step(
        "Add expected margins (preseason model: FPI diff + home_flag)",
        [
            PYTHON,
            str(REPO_ROOT / "add_sim_margins_preseason_simulation.py"),
            str(IN_SEASON_FPI),
            "-o",
            str(IN_SEASON_MARGIN),
        ],
    )

    # Same win formula as preseason viewer; --pin-completed locks actual W/L for played games.
    sim_cmd = [
        PYTHON,
        str(REPO_ROOT / "simulate_cfb_games_preseason_simulation.py"),
        str(IN_SEASON_MARGIN),
        "--pin-completed",
        "-o",
        str(IN_SEASON_SIMULATED),
    ]
    if args.seed is not None:
        sim_cmd.extend(["--seed", str(args.seed)])
    run_step("Simulate games (preseason win formula, pin completed)", sim_cmd)

    run_step(
        "Aggregate team win records",
        [
            PYTHON,
            str(REPO_ROOT / "team_simulation_records.py"),
            str(IN_SEASON_SIMULATED),
            "-o",
            str(IN_SEASON_RECORDS),
            "--conferences",
            str(CONF_CSV),
        ],
    )

    run_step(
        "Conference championship odds",
        [
            PYTHON,
            str(REPO_ROOT / "cfb_conf_championship_odds.py"),
            "--from-data",
            "--games-sim",
            str(IN_SEASON_SIMULATED),
            "--games-fpi",
            str(IN_SEASON_FPI),
            "--conferences",
            str(CONF_CSV),
            "--output",
            str(IN_SEASON_CONF_ODDS),
        ],
    )

    run_step(
        "Playoff eligibility",
        [
            PYTHON,
            str(REPO_ROOT / "cfb_2026_FBS_playoff_elig_v2.py"),
            "--in-season",
        ],
    )

    run_step(
        "National title odds",
        [
            PYTHON,
            str(REPO_ROOT / "cfb_playoff_odds_calc.py"),
            "--from-data",
            "--elig",
            str(IN_SEASON_ELIG),
            "--games-fpi",
            str(IN_SEASON_FPI),
            "--output",
            str(IN_SEASON_TITLE_ODDS),
        ],
    )

    print("\nIn-season pipeline complete.")
    print(f"  Games (FPI):     {IN_SEASON_FPI}")
    print(f"  Simulated games: {IN_SEASON_SIMULATED}")
    print(f"  Team records:    {IN_SEASON_RECORDS}")
    print(f"  Title odds:      {IN_SEASON_TITLE_ODDS}")
    print_title_odds_preview(IN_SEASON_TITLE_ODDS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
