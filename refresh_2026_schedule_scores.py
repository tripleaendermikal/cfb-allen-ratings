#!/usr/bin/env python3

"""Update scores and completion flags in the 2026 FBS schedule CSV via ESPN."""



from __future__ import annotations

from cfb_paths import data_root



import argparse

import csv

import json

import subprocess

import time

from datetime import date, datetime, timedelta

from pathlib import Path

from typing import Dict, Iterable, List, Set, Tuple



from cfb_espn_summary import fetch_game_yards, fetch_json

from cfb_game_corrections import (

    apply_score_corrections,

    apply_yard_corrections,

    load_corrections,

)



SCOREBOARD_URL = (

    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"

)

DEFAULT_GAMES = data_root() / "cfb_2026_fbs_games_with_fpi.csv"

SEASON_YEAR = 2026

YARD_COLUMNS = ("team_yards", "opponent_yards")








def iter_dates(start: date, end: date) -> Iterable[date]:

    current = start

    while current <= end:

        yield current

        current += timedelta(days=1)





def collect_scoreboard_results(

    start: date,

    end: date,

    *,

    season_year: int = SEASON_YEAR,

    sleep_seconds: float = 0.08,

) -> Dict[str, Tuple[Dict[str, str], bool]]:

    """Return game_id -> (team_id -> score string, completed bool)."""

    results: Dict[str, Tuple[Dict[str, str], bool]] = {}

    for day in iter_dates(start, end):

        date_str = day.strftime("%Y%m%d")

        url = f"{SCOREBOARD_URL}?dates={date_str}&groups=80&limit=400"

        payload = fetch_json(url)

        events = payload.get("events") or []

        for event in events:

            season = event.get("season") or {}

            if season.get("year") not in (season_year, str(season_year)):

                continue

            game_id = str(event.get("id") or "").strip()

            if not game_id:

                continue

            competition = (event.get("competitions") or [{}])[0]

            completed = bool((competition.get("status") or {}).get("type", {}).get("completed"))

            scores: Dict[str, str] = {}

            for competitor in competition.get("competitors") or []:

                team_id = str((competitor.get("team") or {}).get("id") or "").strip()

                if not team_id:

                    continue

                score = competitor.get("score")

                if score in (None, ""):

                    score = "0"

                scores[team_id] = str(score)

            if scores:

                results[game_id] = (scores, completed)

        if sleep_seconds:

            time.sleep(sleep_seconds)

    return results





def _ensure_yard_columns(fieldnames: List[str]) -> List[str]:

    updated = list(fieldnames)

    for column in YARD_COLUMNS:

        if column not in updated:

            updated.append(column)

    return updated





def _completed_game_ids(rows: List[dict]) -> Set[str]:

    completed: Set[str] = set()

    for row in rows:

        if (row.get("game_completed") or "").strip().lower() not in {"true", "1", "yes"}:

            continue

        game_id = (row.get("game_id") or "").strip()

        if game_id:

            completed.add(game_id)

    return completed





def _apply_yards_to_rows(

    rows: List[dict],

    yards_by_game: Dict[str, Dict[str, int]],

) -> Tuple[int, List[str]]:

    updated_rows = 0

    missing_games: List[str] = []



    for row in rows:

        game_id = (row.get("game_id") or "").strip()

        if game_id not in yards_by_game:

            continue

        team_id = (row.get("team_id") or "").strip()

        opponent_id = (row.get("opponent_id") or "").strip()

        game_yards = yards_by_game[game_id]

        if team_id not in game_yards or opponent_id not in game_yards:

            if game_id not in missing_games:

                missing_games.append(game_id)

            continue

        row["team_yards"] = str(game_yards[team_id])

        row["opponent_yards"] = str(game_yards[opponent_id])

        updated_rows += 1



    return updated_rows, missing_games





def fetch_yards_for_games(

    game_ids: Iterable[str],

    *,

    sleep_seconds: float = 0.05,

) -> Tuple[Dict[str, Dict[str, int]], List[str]]:

    yards_by_game: Dict[str, Dict[str, int]] = {}

    failed: List[str] = []

    for game_id in sorted(game_ids, key=lambda value: int(value)):

        try:

            yards = fetch_game_yards(game_id, sleep_seconds=sleep_seconds)

        except (RuntimeError, json.JSONDecodeError, ValueError):

            failed.append(game_id)

            continue

        if len(yards) < 2:

            failed.append(game_id)

            continue

        yards_by_game[game_id] = yards

    return yards_by_game, failed





def update_schedule_csv(

    path: Path,

    results: Dict[str, Tuple[Dict[str, str], bool]],

    *,

    corrections_path: Path | None = None,

    yard_sleep_seconds: float = 0.05,

) -> Tuple[int, int, List[str], int, List[str], List[str], List[str]]:

    with path.open(encoding="utf-8-sig", newline="") as handle:

        reader = csv.DictReader(handle)

        fieldnames = _ensure_yard_columns(list(reader.fieldnames or []))

        rows = list(reader)



    if not fieldnames:

        raise ValueError(f"No columns found in {path}")



    updated_games = 0

    updated_rows = 0

    for row in rows:

        game_id = (row.get("game_id") or "").strip()

        if game_id not in results:

            continue

        scores, completed = results[game_id]

        team_id = (row.get("team_id") or "").strip()

        opponent_id = (row.get("opponent_id") or "").strip()

        if team_id not in scores or opponent_id not in scores:

            continue

        row["team_score"] = scores[team_id]

        row["opponent_score"] = scores[opponent_id]

        row["game_completed"] = "True" if completed else "False"

        updated_rows += 1

        if row.get("home_away") == "home":

            updated_games += 1



    corrections = load_corrections(corrections_path)

    corrected_score_games = apply_score_corrections(rows, corrections)



    completed_ids = _completed_game_ids(rows)

    yards_by_game, failed_yard_games = fetch_yards_for_games(

        completed_ids,

        sleep_seconds=yard_sleep_seconds,

    )

    yard_rows_updated, partial_yard_games = _apply_yards_to_rows(rows, yards_by_game)

    corrected_yard_games = apply_yard_corrections(rows, corrections)



    with path.open("w", encoding="utf-8-sig", newline="") as handle:

        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")

        writer.writeheader()

        writer.writerows(rows)



    return (

        updated_games,

        updated_rows,

        corrected_score_games,

        yard_rows_updated,

        failed_yard_games,

        corrected_yard_games,

        partial_yard_games,

    )





def main() -> int:

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--games", type=Path, default=DEFAULT_GAMES)

    parser.add_argument("--start", type=str, default="2026-08-20")

    parser.add_argument("--end", type=str, default=date.today().isoformat())

    parser.add_argument("--sleep", type=float, default=0.08)

    parser.add_argument(

        "--yard-sleep",

        type=float,

        default=0.05,

        help="Seconds between ESPN summary requests when fetching yards",

    )

    args = parser.parse_args()



    if not args.games.is_file():

        raise SystemExit(f"Games file not found: {args.games}")



    start = datetime.strptime(args.start, "%Y-%m-%d").date()

    end = datetime.strptime(args.end, "%Y-%m-%d").date()

    print(f"Fetching ESPN scoreboards from {start} through {end}...")

    results = collect_scoreboard_results(start, end, sleep_seconds=args.sleep)

    print(f"Scoreboard games collected: {len(results)}")



    (

        updated_games,

        updated_rows,

        corrected_score_games,

        yard_rows_updated,

        failed_yard_games,

        corrected_yard_games,

        partial_yard_games,

    ) = update_schedule_csv(

        args.games,

        results,

        yard_sleep_seconds=args.yard_sleep,

    )

    completed_home = sum(

        1

        for scores, completed in results.values()

        if completed

    )

    print(f"Updated {updated_rows} rows across {updated_games} home-perspective games")

    if corrected_score_games:

        print(f"Applied score corrections for game(s): {', '.join(corrected_score_games)}")

    print(f"Updated yards on {yard_rows_updated} rows from ESPN summaries")

    if corrected_yard_games:

        print(f"Applied yard corrections for game(s): {', '.join(corrected_yard_games)}")

    if failed_yard_games:

        print(

            f"Warning: could not fetch yards for {len(failed_yard_games)} game(s) "

            f"(first few: {', '.join(failed_yard_games[:5])})"

        )

    if partial_yard_games:

        print(

            f"Warning: incomplete yard mapping for {len(partial_yard_games)} game(s) "

            f"(first few: {', '.join(partial_yard_games[:5])})"

        )

    print(f"Completed games in ESPN feed: {completed_home}")

    print(f"Wrote {args.games}")

    return 0





if __name__ == "__main__":

    raise SystemExit(main())

