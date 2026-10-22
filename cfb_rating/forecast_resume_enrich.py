"""Augment weekly rankings with forecast resume (post-sim projected wins)."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

from cfb_rating.in_season import DEFAULT_MAX_WEEK, filter_games_through_week
from cfb_rating.rating_algorithm import GameRecord
from cfb_rating.resume import compute_forecast_resume_margins
from cfb_rating.season_data import load_fbs_team_ids, load_games_for_in_season_rankings


def projected_wins_from_sim_records(
    records_rows: Sequence[Mapping[str, str]], sim_cols: Sequence[str]
) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in records_rows:
        team_id = (row.get("team_id") or "").strip()
        if not team_id or not sim_cols:
            continue
        wins = [int(row[col]) for col in sim_cols]
        out[team_id] = sum(wins) / len(wins) if wins else 0.0
    return out


def enrich_rankings_json_forecast_resume(
    rankings: dict,
    games: Sequence[GameRecord],
    projected_wins_by_team: Mapping[str, float],
    *,
    team_ids: Sequence[str] | None = None,
    max_week: int = DEFAULT_MAX_WEEK,
) -> None:
    """Add ``forecast_resume_margin`` to each entry in ``rankings['by_week']``."""
    ids = list(team_ids) if team_ids is not None else sorted(projected_wins_by_team.keys())
    by_week = rankings.get("by_week") or {}
    for week_key, entries in by_week.items():
        week = int(week_key)
        week_games = filter_games_through_week(games, week, max_week=max_week)
        overall_by_team = {
            entry["team_id"]: float(entry["overall_margin"])
            for entry in entries
            if entry.get("overall_margin") is not None
        }
        if not overall_by_team:
            continue
        margins = compute_forecast_resume_margins(
            ids,
            week_games,
            overall_by_team,
            projected_wins_by_team,
        )
        for entry in entries:
            tid = entry["team_id"]
            if tid in margins:
                entry["forecast_resume_margin"] = margins[tid]


def augment_weekly_rankings_csv_forecast_resume(
    rankings_csv: Path,
    games_csv: Path,
    projected_wins_by_team: Mapping[str, float],
    *,
    team_ids: Sequence[str] | None = None,
    max_week: int = DEFAULT_MAX_WEEK,
) -> int:
    """Write ``forecast_resume_margin`` column on the weekly rankings CSV."""
    rankings_csv = Path(rankings_csv)
    games = load_games_for_in_season_rankings(games_csv, fbs_only=True)
    ids = list(team_ids) if team_ids is not None else sorted(load_fbs_team_ids().keys())

    with rankings_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "forecast_resume_margin" not in fieldnames:
        fieldnames.append("forecast_resume_margin")

    by_week: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_week[int(row["week"])].append(row)

    for week, week_rows in by_week.items():
        week_games = filter_games_through_week(games, week, max_week=max_week)
        overall_by_team = {
            row["team_id"]: float(row["overall_margin"])
            for row in week_rows
            if (row.get("overall_margin") or "").strip()
        }
        margins = compute_forecast_resume_margins(
            ids,
            week_games,
            overall_by_team,
            projected_wins_by_team,
        )
        for row in week_rows:
            tid = row["team_id"]
            row["forecast_resume_margin"] = f"{margins.get(tid, overall_by_team.get(tid, 0.0)):.10f}"

    with rankings_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)
