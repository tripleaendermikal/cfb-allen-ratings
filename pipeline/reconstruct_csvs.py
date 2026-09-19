#!/usr/bin/env python3
"""Rebuild pipeline CSV inputs from committed viewer JSON."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from pipeline._paths import (
    CONF_CSV,
    DATA_DIR,
    DATA_ROOT,
    GAMES_BASE,
    PRESEASON_CSV,
)

FBS_CONFERENCES = {
    "ACC",
    "American",
    "Big 12",
    "Big Ten",
    "CUSA",
    "FBS Indep.",
    "MAC",
    "Mountain West",
    "Pac-12",
    "SEC",
    "Sun Belt",
}


def load_json(name: str):
    with (DATA_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_bootstrap_leaderboard() -> list[dict]:
    """Prefer the last committed leaderboard for full FBS conference metadata."""
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(DATA_DIR.parent), "show", "HEAD:data/leaderboard.json"],
            text=True,
        )
        return json.loads(raw)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return load_json("leaderboard.json")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _entry_to_row(entry: dict, *, team_id: str, team_name: str, conference: str,
                  home_away: str, opponent_id: str, opponent_name: str,
                  team_fpi, opponent_fpi, team_score, opponent_score, completed: bool) -> dict[str, str]:
    return {
        "game_id": entry["game_id"],
        "game_date": entry.get("game_date", ""),
        "game_date_utc": entry.get("game_date", ""),
        "week": str(entry.get("week", "")),
        "season_type": entry.get("season_type", "regular-season"),
        "season_year": "2026",
        "team_id": team_id,
        "team_name": team_name,
        "conference": conference,
        "home_away": home_away,
        "neutral_site": "True" if entry.get("neutral_site") else "False",
        "opponent_id": opponent_id,
        "opponent_name": opponent_name,
        "team_fpi": "" if team_fpi is None else str(team_fpi),
        "opponent_fpi": "" if opponent_fpi is None else str(opponent_fpi),
        "game_completed": "true" if completed else "false",
        "team_score": "" if team_score is None else str(team_score),
        "opponent_score": "" if opponent_score is None else str(opponent_score),
    }


def schedule_to_game_rows(schedule: list[dict]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_games: set[str] = set()
    conf_by_team: dict[str, str] = {}
    for entry in schedule:
        conf_by_team[entry["team_id"]] = entry.get("conference", "")

    for entry in schedule:
        gid = entry["game_id"]
        if gid in seen_games:
            continue
        seen_games.add(gid)
        completed = bool(entry.get("completed"))
        home_away = entry.get("home_away", "")
        if home_away == "home":
            home_row = _entry_to_row(
                entry,
                team_id=entry["team_id"],
                team_name=entry.get("team_name", ""),
                conference=entry.get("conference", ""),
                home_away="home",
                opponent_id=entry.get("opponent_id", ""),
                opponent_name=entry.get("opponent_name", ""),
                team_fpi=entry.get("team_fpi"),
                opponent_fpi=entry.get("opponent_fpi"),
                team_score=entry.get("team_score"),
                opponent_score=entry.get("opponent_score"),
                completed=completed,
            )
            away_row = _entry_to_row(
                entry,
                team_id=entry.get("opponent_id", ""),
                team_name=entry.get("opponent_name", ""),
                conference=conf_by_team.get(entry.get("opponent_id", ""), ""),
                home_away="away",
                opponent_id=entry["team_id"],
                opponent_name=entry.get("team_name", ""),
                team_fpi=entry.get("opponent_fpi"),
                opponent_fpi=entry.get("team_fpi"),
                team_score=entry.get("opponent_score"),
                opponent_score=entry.get("team_score"),
                completed=completed,
            )
            rows.extend([home_row, away_row])
        else:
            rows.append(
                _entry_to_row(
                    entry,
                    team_id=entry["team_id"],
                    team_name=entry.get("team_name", ""),
                    conference=entry.get("conference", ""),
                    home_away=home_away,
                    opponent_id=entry.get("opponent_id", ""),
                    opponent_name=entry.get("opponent_name", ""),
                    team_fpi=entry.get("team_fpi"),
                    opponent_fpi=entry.get("opponent_fpi"),
                    team_score=entry.get("team_score"),
                    opponent_score=entry.get("opponent_score"),
                    completed=completed,
                )
            )
    return rows


def build_conferences_csv(
    schedule: list[dict],
    leaderboard: list[dict],
    games: dict[str, dict],
) -> list[dict[str, str]]:
    teams: dict[str, dict[str, str]] = {}
    conf_by_id = {row["team_id"]: row.get("conference", "") for row in leaderboard}
    for game in games.values():
        conf_by_id[game.get("home_team_id", "")] = game.get("home_conference", "")
        conf_by_id[game.get("away_team_id", "")] = game.get("away_conference", "")

    def add_team(team_id: str, team_name: str, conference: str) -> None:
        if not team_id:
            return
        resolved_conf = conf_by_id.get(team_id) or conference
        existing = teams.get(team_id)
        if existing:
            if resolved_conf in FBS_CONFERENCES and existing["conference"] not in FBS_CONFERENCES:
                existing["conference"] = resolved_conf
                existing["classification"] = "fbs"
            return
        teams[team_id] = {
            "team_id": team_id,
            "team_name": team_name,
            "conference": resolved_conf,
            "classification": "fbs" if resolved_conf in FBS_CONFERENCES else "fcs",
        }

    for row in leaderboard:
        add_team(row["team_id"], row.get("team_name", ""), row.get("conference", ""))
    for entry in schedule:
        add_team(entry["team_id"], entry.get("team_name", ""), entry.get("conference", ""))
        add_team(
            entry.get("opponent_id", ""),
            entry.get("opponent_name", ""),
            conf_by_id.get(entry.get("opponent_id", ""), ""),
        )
    return sorted(teams.values(), key=lambda row: (row["conference"], row["team_name"]))


def build_preseason_csv(rankings: dict, leaderboard: list[dict]) -> list[dict[str, str]]:
    by_id = {row["team_id"]: row for row in leaderboard}
    week1 = {row["team_id"]: row for row in rankings.get("by_week", {}).get("1", [])}
    rows: list[dict[str, str]] = []
    for team_id, lb in by_id.items():
        week_row = week1.get(team_id, {})
        preseason = week_row.get("preseason_margin", lb.get("some_preseason_margin"))
        if preseason is None:
            continue
        rows.append(
            {
                "Team": lb["team_name"],
                "Team Proper Name": lb["team_name"],
                "combined_FPI": str(preseason),
                "Forecast": str(preseason),
            }
        )
    return rows


def main() -> int:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    schedule = load_json("schedule.json")
    rankings = load_json("rankings.json")
    bootstrap_leaderboard = load_bootstrap_leaderboard()
    games = load_json("games.json")

    game_rows = schedule_to_game_rows(schedule)
    base_fields = list(game_rows[0].keys()) if game_rows else []
    write_csv(GAMES_BASE, base_fields, game_rows)
    print(f"Wrote {len(game_rows)} rows to {GAMES_BASE}")

    conf_rows = build_conferences_csv(schedule, bootstrap_leaderboard, games)
    write_csv(CONF_CSV, ["team_id", "team_name", "conference", "classification"], conf_rows)
    print(f"Wrote {len(conf_rows)} teams to {CONF_CSV}")

    preseason_rows = build_preseason_csv(rankings, bootstrap_leaderboard)
    if preseason_rows:
        write_csv(
            PRESEASON_CSV,
            ["Team", "Team Proper Name", "combined_FPI", "Forecast"],
            preseason_rows,
        )
        print(f"Wrote {len(preseason_rows)} rows to {PRESEASON_CSV}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
