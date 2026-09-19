#!/usr/bin/env python3
"""Refresh completed game scores on the base schedule CSV from ESPN."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import httpx

from pipeline._paths import GAMES_BASE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Referer": "https://www.espn.com/college-football/scoreboard",
}


def load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, list(reader)


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _parse_finals(payload: dict) -> dict[str, dict]:
    finals: dict[str, dict] = {}
    for event in payload.get("events", []):
        if event.get("status", {}).get("type", {}).get("name") != "STATUS_FINAL":
            continue
        gid = str(event["id"])
        competition = event["competitions"][0]
        competitors = competition["competitors"]
        home = next(item for item in competitors if item["homeAway"] == "home")
        away = next(item for item in competitors if item["homeAway"] == "away")
        finals[gid] = {
            "home_score": int(home.get("score") or 0),
            "away_score": int(away.get("score") or 0),
        }
    return finals


def fetch_finals_for_dates(dates: set[str], weeks: set[int]) -> dict[str, dict]:
    finals: dict[str, dict] = {}
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        for date in sorted(dates):
            compact = date.replace("-", "")
            url = (
                "https://site.api.espn.com/apis/site/v2/sports/football/"
                f"college-football/scoreboard?dates={compact}"
            )
            for attempt in range(4):
                response = client.get(url)
                if response.status_code == 200 and response.content:
                    finals.update(_parse_finals(response.json()))
                    break
        for week in sorted(weeks):
            url = (
                "https://site.api.espn.com/apis/site/v2/sports/football/"
                f"college-football/scoreboard?week={week}&seasontype=2&year=2026"
            )
            for attempt in range(4):
                response = client.get(url)
                if response.status_code == 200 and response.content:
                    finals.update(_parse_finals(response.json()))
                    break
    return finals


def apply_scores(rows: list[dict[str, str]], finals: dict[str, dict]) -> int:
    updated = 0
    by_game: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_game[row["game_id"]].append(row)

    for gid, sides in by_game.items():
        result = finals.get(gid)
        if not result:
            continue
        home = next((side for side in sides if side.get("home_away") == "home"), None)
        away = next((side for side in sides if side.get("home_away") == "away"), None)
        if not home or not away:
            continue
        for side, score, opp_score in (
            (home, result["home_score"], result["away_score"]),
            (away, result["away_score"], result["home_score"]),
        ):
            changed = (
                side.get("game_completed", "").lower() != "true"
                or side.get("team_score") != str(score)
                or side.get("opponent_score") != str(opp_score)
            )
            side["game_completed"] = "true"
            side["team_score"] = str(score)
            side["opponent_score"] = str(opp_score)
            if changed:
                updated += 1
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=Path, default=GAMES_BASE)
    args = parser.parse_args()

    if not args.games.is_file():
        print(f"Games file not found: {args.games}", file=sys.stderr)
        return 1

    fieldnames, rows = load_rows(args.games)
    dates = {row.get("game_date", "")[:10] for row in rows if row.get("game_date")}
    dates.discard("")
    weeks = {
        int(row["week"])
        for row in rows
        if (row.get("week") or "").isdigit()
    }
    finals = fetch_finals_for_dates(dates, weeks)
    updated = apply_scores(rows, finals)
    write_rows(args.games, fieldnames, rows)
    print(f"ESPN finals fetched: {len(finals)}")
    print(f"Updated team rows: {updated}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
