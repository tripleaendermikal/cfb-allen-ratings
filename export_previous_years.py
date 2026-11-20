#!/usr/bin/env python3
"""Export prior-season Overall / Resume rankings for the Previous Years viewer tab."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from cfb_paths import REPO_ROOT, data_root
from cfb_rating.in_season import (
    InSeasonRankingRow,
    compute_weekly_in_season_rankings,
    filter_games_through_week,
    load_preseason_margins,
)
from cfb_rating.rating_algorithm import GameRecord
from cfb_rating.resume import team_record_from_games
from cfb_rating.season_data import load_espn_games

FCS_CONFERENCES = {"Big Sky", "CAA", "Ivy", "MEAC", "Missouri Valley", "NEC", "OVC", "Patriot", "Pioneer", "Southern", "Southland", "SWAC", "UAC"}


def is_fbs_team(meta: dict) -> bool:
    conf = (meta.get("conference") or "").strip()
    return bool(conf) and conf not in FCS_CONFERENCES and conf != "Unknown"

DATA_DIR = REPO_ROOT / "data"
DEFAULT_OUTPUT = DATA_DIR / "previous_years.json"


def default_paths_for_season(season_year: int) -> dict[str, Path]:
    root = data_root()
    return {
        "games": root / f"cfb_{season_year}_espn_games.csv",
        "preseason": root / f"Preseason_{season_year}_blended.csv",
        "margin_ratings": root / f"cfb_{season_year}_fbs_margin_ratings.csv",
        "teams": root / "espn_cfb_teams_conferences.csv",
    }


def load_team_info_from_margin_ratings(path: Path) -> dict[str, dict]:
    """2025-accurate team_id, name, conference from prior margin export."""
    if not path.is_file():
        return {}
    info: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            tid = (row.get("team_id") or "").strip()
            if not tid:
                continue
            info[tid] = {
                "team_id": tid,
                "team_name": (row.get("team_name") or "").strip(),
                "conference": (row.get("conference") or "").strip(),
            }
    return info


def records_for_week(
    games: Sequence[GameRecord],
    team_ids: Sequence[str],
    through_week: int,
    max_week: int,
) -> dict[str, dict[str, int]]:
    week_games = filter_games_through_week(games, through_week, max_week=max_week)
    out: dict[str, dict[str, int]] = {}
    for tid in team_ids:
        wins, gp = team_record_from_games(week_games, tid)
        losses = gp - wins
        out[tid] = {"wins": wins, "losses": losses, "fbs_games_played": gp}
    return out


def infer_max_week(games: Sequence[GameRecord]) -> int:
    weeks = [g.week for g in games if g.week is not None]
    return max(weeks) if weeks else 14


def row_to_json(
    row: InSeasonRankingRow,
    record: Mapping[str, int],
) -> dict:
    wins = record.get("wins", 0)
    losses = record.get("losses", 0)
    return {
        "week": row.week,
        "team_id": row.team_id,
        "team_name": row.team_name,
        "conference": row.conference,
        "overall_margin": float(row.overall_margin),
        "resume_margin": float(row.resume_margin),
        "algorithm_margin": float(row.algorithm_margin),
        "some_preseason_margin": float(row.some_preseason_margin),
        "fbs_games_played": int(record.get("fbs_games_played", row.fbs_games_played)),
        "wins": int(wins),
        "losses": int(losses),
        "record": f"{wins}-{losses}",
    }


def build_season_export(
    season_year: int,
    games: Sequence[GameRecord],
    preseason_margins: Mapping[str, float],
    team_ids: list[str],
    team_info: Mapping[str, dict],
    *,
    max_week: int,
    iterations: int = 1000,
) -> dict:
    rows = compute_weekly_in_season_rankings(
        games,
        preseason_margins,
        team_ids,
        team_info=team_info,
        max_week=max_week,
        iterations=iterations,
    )
    by_week_rows: dict[int, list[InSeasonRankingRow]] = defaultdict(list)
    for row in rows:
        by_week_rows[row.week].append(row)

    by_week_json: dict[str, list[dict]] = {}
    weeks = sorted(by_week_rows.keys())
    for week in weeks:
        recs = records_for_week(games, team_ids, week, max_week)
        entries = [row_to_json(r, recs.get(r.team_id, {})) for r in by_week_rows[week]]
        by_week_json[str(week)] = entries

    final_week = weeks[-1] if weeks else 0
    return {
        "season_year": season_year,
        "final_week": final_week,
        "weeks": weeks,
        "team_count": len(team_ids),
        "max_week": max_week,
        "by_week": by_week_json,
    }


def write_previous_years_json(
    output: Path,
    season_year: int,
    season_payload: dict,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if output.is_file():
        raw = json.loads(output.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            existing = raw
    seasons = existing.get("seasons")
    if not isinstance(seasons, dict):
        seasons = {}
    seasons[str(season_year)] = season_payload
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "seasons": seasons,
    }
    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--games", type=Path, default=None)
    parser.add_argument("--preseason", type=Path, default=None)
    parser.add_argument("--margin-ratings", type=Path, default=None)
    parser.add_argument("--teams", type=Path, default=None)
    parser.add_argument("--max-week", type=int, default=None)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    defaults = default_paths_for_season(args.season)
    games_path = args.games or defaults["games"]
    preseason_path = args.preseason or defaults["preseason"]
    margin_path = args.margin_ratings or defaults["margin_ratings"]
    teams_path = args.teams or defaults["teams"]

    if not games_path.is_file():
        print(
            f"Missing games CSV: {games_path}\n"
            f"Set CFB_DATA_ROOT or pass --games. For 2025, run bootstrap_prior_season_data.py first."
        )
        return 1
    if not preseason_path.is_file():
        print(
            f"Missing preseason CSV: {preseason_path}\n"
            f"Expected Preseason_{args.season}_blended.csv with combined_FPI."
        )
        return 1

    margin_info = load_team_info_from_margin_ratings(margin_path)
    games = load_espn_games(games_path, teams_path=teams_path)

    from cfb_rating.season_data import load_fbs_team_ids

    team_info = load_fbs_team_ids(teams_path)
    for tid, meta in margin_info.items():
        if tid not in team_info:
            continue
        if meta.get("team_name"):
            team_info[tid] = {**team_info[tid], "team_name": meta["team_name"]}
        conf = (meta.get("conference") or "").strip()
        if conf and is_fbs_team({"conference": conf}):
            team_info[tid] = {**team_info[tid], "conference": conf}

    preseason_margins = load_preseason_margins(
        preseason_path,
        teams_path=teams_path,
    )

    participants = {g.home_team_id for g in games} | {g.away_team_id for g in games}
    fbs_ids = {
        tid
        for tid in participants
        if tid in team_info and is_fbs_team(team_info[tid])
    }
    games = [
        g
        for g in games
        if g.home_team_id in fbs_ids and g.away_team_id in fbs_ids
    ]
    team_ids = sorted(fbs_ids)
    preseason_full = dict(preseason_margins)
    for tid in team_ids:
        preseason_full.setdefault(tid, 0.0)

    inferred = infer_max_week(games)
    max_week = args.max_week if args.max_week is not None else inferred
    if games:
        max_week = max(max_week, max((g.week or 0) for g in games))

    season_payload = build_season_export(
        args.season,
        games,
        preseason_full,
        team_ids,
        team_info,
        max_week=max_week,
        iterations=args.iterations,
    )
    season_payload["sources"] = {
        "games": str(games_path),
        "preseason": str(preseason_path),
        "margin_ratings": str(margin_path) if margin_path.is_file() else None,
        "teams": str(teams_path),
    }

    write_previous_years_json(args.output, args.season, season_payload)
    print(
        f"Wrote season {args.season} ({season_payload['team_count']} teams, "
        f"weeks 1–{season_payload['final_week']}) to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())