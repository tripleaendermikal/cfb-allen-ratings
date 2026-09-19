#!/usr/bin/env python3
"""Run the in-season Monte Carlo simulation pipeline."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

from pipeline._paths import (
    CONF_CSV,
    CONF_ODDS,
    GAMES_FPI,
    GAMES_MARGIN,
    GAMES_SIM,
    PLAYOFF_ELIG,
    PLAYOFF_ELIG_PCT,
    PIPELINE_DIR,
    RANKINGS_CSV,
    REPO_ROOT,
    SIM_COUNT,
    TITLE_ODDS,
)
from pipeline.cfb_conf_championship import compute_conf_results_by_sim
from pipeline.cfb_playoff_elig import build_conf_champ_odds_csv, build_playoff_eligibility_csv
from pipeline.cfb_playoff_odds_calc import build_title_odds_csv

PYTHON = sys.executable


def run_step(label: str, cmd: list[str]) -> None:
    print(f"\n==> {label}")
    print("    " + " ".join(str(part) for part in cmd))
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def load_name_maps() -> tuple[dict[str, str], dict[str, str]]:
    with CONF_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    id_to_name = {row["team_id"]: row["team_name"] for row in rows}
    name_to_id = {row["team_name"]: row["team_id"] for row in rows}
    return id_to_name, name_to_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-refresh", action="store_true")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--simulations", type=int, default=SIM_COUNT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not RANKINGS_CSV.is_file():
        print(f"Rankings file not found: {RANKINGS_CSV}", file=sys.stderr)
        return 1

    if not args.skip_refresh:
        run_step(
            "Refresh ESPN scores",
            [PYTHON, str(PIPELINE_DIR / "refresh_espn_scores.py")],
        )

    run_step(
        "Update in-season per-simulation FPI draws",
        [
            PYTHON,
            str(PIPELINE_DIR / "update_in_season_fpi.py"),
            "--seed",
            str(args.seed),
            "--simulations",
            str(args.simulations),
        ],
    )
    run_step(
        "Add margin columns",
        [PYTHON, str(PIPELINE_DIR / "add_sim_margins.py")],
    )
    run_step(
        "Simulate remaining games (pin completed)",
        [
            PYTHON,
            str(PIPELINE_DIR / "simulate_games.py"),
            str(GAMES_MARGIN),
            "-o",
            str(GAMES_SIM),
            "--pin-completed",
            "--seed",
            str(args.seed),
        ],
    )
    run_step(
        "Aggregate team win records",
        [PYTHON, str(PIPELINE_DIR / "team_simulation_records.py")],
    )

    conf_results = compute_conf_results_by_sim(GAMES_SIM, GAMES_FPI, CONF_CSV)
    id_to_name, name_to_id = load_name_maps()
    build_conf_champ_odds_csv(conf_results, CONF_CSV, CONF_ODDS, id_to_name)
    build_playoff_eligibility_csv(
        GAMES_FPI,
        CONF_CSV,
        conf_results,
        PLAYOFF_ELIG,
        PLAYOFF_ELIG_PCT,
        id_to_name,
    )
    build_title_odds_csv(
        GAMES_FPI,
        PLAYOFF_ELIG,
        CONF_CSV,
        conf_results,
        TITLE_ODDS,
        id_to_name,
        name_to_id,
    )
    from pipeline._paths import TEAM_RECORDS

    print("\nIn-season simulation pipeline complete.")
    print(f"  Simulated games: {GAMES_SIM}")
    print(f"  Team records:    {TEAM_RECORDS}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT))
    raise SystemExit(main())
