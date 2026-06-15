#!/usr/bin/env python3
"""Compute weekly in-season FBS rankings with preseason margin fade."""

import argparse
import os
from pathlib import Path

from cfb_rating.in_season import (
    DEFAULT_MAX_WEEK,
    compute_weekly_in_season_rankings,
    load_preseason_margins,
    resolve_preseason_csv,
    write_in_season_rankings_csv,
)
from cfb_rating.season_data import load_fbs_team_ids, load_games_for_in_season_rankings

APP_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("CFB_DATA_ROOT", str(APP_DIR.parent)))

DEFAULT_GAMES = DATA_ROOT / "cfb_2026_fbs_games_with_fpi.csv"
DEFAULT_OUTPUT = DATA_ROOT / "cfb_2026_in_season_weekly_rankings.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=Path, default=DEFAULT_GAMES)
    parser.add_argument("--preseason", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-week", type=int, default=DEFAULT_MAX_WEEK)
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()

    games = load_games_for_in_season_rankings(args.games, fbs_only=True)

    team_info = load_fbs_team_ids()
    team_ids = sorted(team_info.keys())
    preseason_path = resolve_preseason_csv(args.preseason)
    preseason_margins = load_preseason_margins(preseason_path)

    rows = compute_weekly_in_season_rankings(
        games,
        preseason_margins,
        team_ids,
        team_info=team_info,
        max_week=args.max_week,
        iterations=args.iterations,
    )
    write_in_season_rankings_csv(rows, args.output)

    week_rows = [row for row in rows if row.week == 1]
    late_rows = [row for row in rows if row.week == args.max_week]
    print(f"Games used: {len(games)}")
    print(f"Teams ranked: {len(team_ids)}")
    print(f"Preseason source: {preseason_path}")
    print(f"Wrote {len(rows)} rows to {args.output}")
    print("Week 1 top 10 (blended margin):")
    for row in week_rows[:10]:
        print(
            f"  #{row.rank:<3} {row.team_name:<35} "
            f"blend={row.blended_margin:+.2f}  "
            f"pre_wt={row.preseason_weight:.1f}  games={row.fbs_games_played}"
        )
    print(f"Week {args.max_week} top 10 (blended margin):")
    for row in late_rows[:10]:
        print(
            f"  #{row.rank:<3} {row.team_name:<35} "
            f"blend={row.blended_margin:+.2f}  "
            f"pre_wt={row.preseason_weight:.1f}  games={row.fbs_games_played}"
        )


if __name__ == "__main__":
    main()
