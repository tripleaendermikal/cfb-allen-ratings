#!/usr/bin/env python3
"""Refresh scores, sims, blended rankings, and CFB Allen Ratings export."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from cfb_paths import REPO_ROOT, data_root

PYTHON = sys.executable
DATA = data_root()

GAMES_CSV = DATA / "cfb_2026_fbs_games_with_fpi.csv"
RANKINGS_CSV = DATA / "cfb_2026_in_season_weekly_rankings.csv"
IN_SEASON_FPI = DATA / "cfb_2026_in_season_fbs_games_with_fpi.csv"


def run_step(label: str, cmd: list[str], *, cwd: Path | None = None) -> None:
    print(f"\n==> {label}")
    print("    " + " ".join(str(part) for part in cmd))
    subprocess.run(cmd, cwd=cwd or REPO_ROOT, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "End-to-end in-season weekly update: ESPN scores, Monte Carlo sims, "
            "blended rankings, and viewer JSON (move, fcst wins, playoff%, title%)."
        )
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="Skip ESPN score refresh",
    )
    parser.add_argument(
        "--skip-sims",
        action="store_true",
        help="Skip in-season sim pipeline (only recompute rankings + export)",
    )
    parser.add_argument(
        "--simulations",
        type=int,
        default=1000,
        help="Monte Carlo seasons when sims run (default: 1000)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not args.skip_refresh:
        run_step(
            "Refresh ESPN scores",
            [PYTHON, str(REPO_ROOT / "refresh_2026_schedule_scores.py")],
        )

    run_step(
        "Compute weekly rankings (Overall margins for sim seed)",
        [
            PYTHON,
            str(REPO_ROOT / "compute_in_season_rankings.py"),
            "--games",
            str(GAMES_CSV),
            "--output",
            str(RANKINGS_CSV),
        ],
    )

    if not args.skip_sims:
        sim_cmd = [
            PYTHON,
            str(REPO_ROOT / "run_in_season_sim_pipeline.py"),
            "--skip-refresh",
            "--simulations",
            str(args.simulations),
            "--rankings",
            str(RANKINGS_CSV),
        ]
        run_step("In-season Monte Carlo pipeline", sim_cmd)

    run_step(
        "Validate sim FPI draws match Overall margins",
        [
            PYTHON,
            str(REPO_ROOT / "validate_in_season_sim_overall.py"),
            "--games-fpi",
            str(IN_SEASON_FPI),
            "--rankings",
            str(RANKINGS_CSV),
        ],
    )

    run_step(
        "Export viewer JSON (move, fcst wins, playoff%, title%)",
        [PYTHON, str(REPO_ROOT / "export_in_season_data.py")],
    )

    print("\nWeekly in-season update complete.")
    print(f"  Rankings: {RANKINGS_CSV}")
    print(f"  Viewer:   {REPO_ROOT / 'data'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
