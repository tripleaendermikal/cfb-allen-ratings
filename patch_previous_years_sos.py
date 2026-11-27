#!/usr/bin/env python3
"""Backfill season SOS into data/previous_years.json without recomputing rankings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cfb_paths import REPO_ROOT, data_root
from cfb_rating.in_season import load_preseason_margins
from cfb_rating.season_data import load_espn_games
from cfb_team_sos import compute_team_sos_from_games
from export_previous_years import default_paths_for_season


def patch_season(
    archive: dict,
    season_year: int,
    *,
    games_path: Path | None = None,
    preseason_path: Path | None = None,
    teams_path: Path | None = None,
) -> bool:
    defaults = default_paths_for_season(season_year)
    games_path = games_path or defaults["games"]
    preseason_path = preseason_path or defaults["preseason"]
    teams_path = teams_path or defaults["teams"]
    if not games_path.is_file() or not preseason_path.is_file():
        return False

    games = load_espn_games(
        games_path,
        fbs_only=False,
        teams_path=teams_path if teams_path.is_file() else None,
        season_year=season_year,
        single_postseason_week=True,
    )
    preseason = load_preseason_margins(
        preseason_path,
        teams_path=teams_path if teams_path.is_file() else None,
    )
    sos_map = compute_team_sos_from_games(games, preseason)

    season_key = str(season_year)
    seasons = archive.setdefault("seasons", {})
    payload = seasons.get(season_key)
    if not isinstance(payload, dict):
        return False

    payload["sos_by_team"] = sos_map
    by_week = payload.get("by_week") or {}
    for week_rows in by_week.values():
        if not isinstance(week_rows, list):
            continue
        for row in week_rows:
            tid = row.get("team_id")
            if tid and tid in sos_map:
                row["sos"] = sos_map[tid]
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "previous_years.json",
    )
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="*",
        help="Seasons to patch (default: all seasons present in archive)",
    )
    parser.add_argument("--data-root", type=Path, default=None)
    args = parser.parse_args()

    if not args.output.is_file():
        print(f"Missing {args.output}", file=sys.stderr)
        return 1

    archive = json.loads(args.output.read_text(encoding="utf-8"))
    season_list = args.seasons
    if not season_list:
        seasons = archive.get("seasons") or {}
        season_list = sorted(int(s) for s in seasons.keys())

    root = args.data_root or data_root()
    if args.data_root:
        import os

        os.environ["CFB_DATA_ROOT"] = str(args.data_root)

    patched = 0
    for season in season_list:
        if patch_season(archive, season):
            print(f"Patched SOS for {season}")
            patched += 1
        else:
            print(f"Skipped {season} (missing games/preseason or season payload)")

    if patched:
        args.output.write_text(
            json.dumps(archive, separators=(",", ":")),
            encoding="utf-8",
        )
    print(f"Done ({patched} season(s))")
    return 0 if patched else 1


if __name__ == "__main__":
    raise SystemExit(main())