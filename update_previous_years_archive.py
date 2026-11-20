#!/usr/bin/env python3
"""Bootstrap (if needed) and export prior seasons into data/previous_years.json."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from cfb_paths import REPO_ROOT

PYTHON = sys.executable
DEFAULT_SEASONS = [
    2011,
    2012,
    2013,
    2014,
    2015,
    2016,
    2017,
    2018,
    2019,
    2021,
    2022,
    2023,
    2024,
    2025,
]


def season_inputs_ready(season: int, data_root: Path) -> bool:
    games = data_root / f"cfb_{season}_espn_games.csv"
    pre = data_root / f"Preseason_{season}_blended.csv"
    return games.is_file() and pre.is_file()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=DEFAULT_SEASONS,
        help="Years to export (default: 2011-2019, 2021-2025)",
    )
    parser.add_argument("--skip-bootstrap", action="store_true")
    parser.add_argument(
        "--skip-yards",
        action="store_true",
        help="Passed to bootstrap (faster but weaker algorithm inputs)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="CFB_DATA_ROOT override",
    )
    args = parser.parse_args()

    import os

    from cfb_paths import data_root

    root = args.data_root or data_root()
    run_env = {**os.environ, "CFB_DATA_ROOT": str(root)}

    for season in args.seasons:
        if not args.skip_bootstrap and not season_inputs_ready(season, root):
            cmd = [PYTHON, str(REPO_ROOT / "bootstrap_prior_season_data.py"), "--season", str(season)]
            if args.skip_yards:
                cmd.append("--skip-yards")
            print(f"\n=== Bootstrap {season} ===")
            rc = subprocess.call(cmd, env=run_env)
            if rc != 0:
                print(f"Bootstrap failed for {season}")
                return rc

        if not season_inputs_ready(season, root):
            print(f"Missing inputs for {season} after bootstrap")
            return 1

        print(f"\n=== Export {season} ===")
        rc = subprocess.call(
            [
                PYTHON,
                str(REPO_ROOT / "export_previous_years.py"),
                "--season",
                str(season),
            ],
            env=run_env,
        )
        if rc != 0:
            print(f"Export failed for {season}")
            return rc

    print(f"\nUpdated {REPO_ROOT / 'data' / 'previous_years.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())