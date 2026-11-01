"""Augment weekly rankings with forecast resume from in-season sim outcomes."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

from cfb_conf_championship import ccg_participants_by_col
from cfb_rating.resume import compute_resume_margins
from cfb_rating.season_data import load_fbs_team_ids
from cfb_rating.sim_resume import build_sim_season_games


def projected_wins_from_sim_records(
    records_rows: Sequence[Mapping[str, str]], sim_cols: Sequence[str]
) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in records_rows:
        team_id = (row.get("team_id") or row.get("\ufeffteam_id") or "").strip()
        if not team_id or not sim_cols:
            continue
        wins = [int(row[col]) for col in sim_cols]
        out[team_id] = sum(wins) / len(wins) if wins else 0.0
    return out


def projected_games_from_sim_games(
    game_rows: Sequence[Mapping[str, str]],
    sim_cols: Sequence[str],
    *,
    conf_finalists_by_sim: Mapping[str, Mapping[str, list[str]]] | None = None,
) -> dict[str, float]:
    """Mean games played per sim (schedule results + CCG when applicable)."""
    games_played: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in game_rows:
        team_id = (row.get("team_id") or "").strip()
        if not team_id:
            continue
        for col in sim_cols:
            result = (row.get(col) or "").strip()
            if result in ("0", "1"):
                games_played[team_id][col] += 1

    ccg_played = (
        ccg_participants_by_col(conf_finalists_by_sim, list(sim_cols))
        if conf_finalists_by_sim
        else {}
    )

    team_ids = set(games_played.keys())
    for participants in ccg_played.values():
        team_ids.update(participants)

    out: dict[str, float] = {}
    for team_id in team_ids:
        totals: list[int] = []
        for col in sim_cols:
            gp = games_played[team_id].get(col, 0)
            if team_id in ccg_played.get(col, set()):
                gp += 1
            totals.append(gp)
        out[team_id] = sum(totals) / len(totals) if totals else 0.0
    return out


def projected_season_stats_from_sims(
    records_rows: Sequence[Mapping[str, str]],
    sim_cols: Sequence[str],
    game_rows: Sequence[Mapping[str, str]],
    *,
    conf_finalists_by_sim: Mapping[str, Mapping[str, list[str]]] | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    wins = projected_wins_from_sim_records(records_rows, sim_cols)
    games = projected_games_from_sim_games(
        game_rows, sim_cols, conf_finalists_by_sim=conf_finalists_by_sim
    )
    return wins, games


def mean_sim_forecast_resume_for_overall(
    season_by_col: Mapping[str, Sequence],
    sim_cols: Sequence[str],
    team_ids: Sequence[str],
    overall_by_team: Mapping[str, float],
) -> dict[str, float]:
    """Average end-of-season resume margin over sim columns (opponents at Overall)."""
    if not sim_cols:
        return {}
    totals: dict[str, float] = defaultdict(float)
    n = float(len(sim_cols))
    for col in sim_cols:
        per_sim = compute_resume_margins(
            team_ids, season_by_col[col], overall_by_team
        )
        for tid, margin in per_sim.items():
            totals[tid] += margin
    return {tid: totals[tid] / n for tid in totals}


def augment_weekly_rankings_csv_forecast_resume(
    rankings_csv: Path,
    game_rows: Sequence[Mapping[str, str]],
    sim_cols: Sequence[str],
    *,
    team_ids: Sequence[str] | None = None,
    forecast_week: int | None = None,
) -> int:
    """Write ``forecast_resume_margin`` on the weekly rankings CSV.

    Mean sim end-of-season resume is computed only for ``forecast_week`` (default:
    latest week in the file). Other weeks copy ``resume_margin`` so export stays fast.
    """
    rankings_csv = Path(rankings_csv)
    ids = list(team_ids) if team_ids is not None else sorted(load_fbs_team_ids())
    season_by_col = {
        col: build_sim_season_games(game_rows, col) for col in sim_cols
    }

    with rankings_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "forecast_resume_margin" not in fieldnames:
        fieldnames.append("forecast_resume_margin")

    by_week: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_week[int(row["week"])].append(row)

    target_week = forecast_week if forecast_week is not None else max(by_week.keys())
    margins: dict[str, float] | None = None
    if target_week in by_week and sim_cols:
        week_rows = by_week[target_week]
        overall_by_team = {
            row["team_id"]: float(row["overall_margin"])
            for row in week_rows
            if (row.get("overall_margin") or "").strip()
        }
        week_ids = [tid for tid in ids if tid in overall_by_team]
        margins = mean_sim_forecast_resume_for_overall(
            season_by_col, sim_cols, week_ids, overall_by_team
        )

    for week, week_rows in by_week.items():
        for row in week_rows:
            tid = row["team_id"]
            if week == target_week and margins and tid in margins:
                row["forecast_resume_margin"] = f"{margins[tid]:.10f}"
            elif (row.get("resume_margin") or "").strip():
                row["forecast_resume_margin"] = row["resume_margin"]

    with rankings_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)
