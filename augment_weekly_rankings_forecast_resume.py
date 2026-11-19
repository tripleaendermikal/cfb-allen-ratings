#!/usr/bin/env python3
"""Add forecast_resume_margin to weekly rankings using sim projected wins."""

from __future__ import annotations

import argparse
from pathlib import Path

from cfb_paths import data_root
from cfb_rating.forecast_resume_enrich import augment_weekly_rankings_csv_forecast_resume

import export_sim_data as esd

IN_SEASON_PREFIX = "cfb_2026_in_season"
DEFAULT_GAMES = data_root() / "cfb_2026_fbs_games_with_fpi.csv"
DEFAULT_RANKINGS = data_root() / f"{IN_SEASON_PREFIX}_weekly_rankings.csv"
DEFAULT_RECORDS = data_root() / f"{IN_SEASON_PREFIX}_fbs_team_sim_records_v2.csv"
DEFAULT_GAMES_SIM = data_root() / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi_simulated.csv"
DEFAULT_GAMES_FPI = data_root() / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi.csv"
DEFAULT_CONFERENCES = data_root() / "espn_cfb_teams_conferences.csv"


def resolve_forecast_week(
    explicit: int | None,
    *,
    games_fpi_rows: list[dict[str, str]] | None,
) -> int | None:
    """Week to compute mean sim forecast resume (not copy resume_margin).

    Uses completed games in the in-season FPI export. ``data/meta.json`` is
    intentionally not used: export updates meta after this step in the weekly
    pipeline, so meta.current_week lags the rankings row we need."""
    if explicit is not None:
        return explicit
    if not games_fpi_rows:
        return None
    from export_in_season_data import infer_current_week_from_games

    inferred = infer_current_week_from_games(games_fpi_rows)
    return inferred if inferred > 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecast-week", type=int, default=None)
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
    _, games_fpi_rows = (
        esd.read_csv(args.games_fpi) if args.games_fpi.is_file() else ([], [])
    )

    count = augment_weekly_rankings_csv_forecast_resume(
        args.rankings,
        game_rows,
        sim_cols,
        forecast_week=resolve_forecast_week(
            args.forecast_week,
            games_fpi_rows=games_fpi_rows or None,
        ),
    )
    print(f"Updated forecast_resume_margin on {count} rows in {args.rankings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
