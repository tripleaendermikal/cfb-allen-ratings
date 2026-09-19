#!/usr/bin/env python3
"""Bootstrap CFB_DATA_ROOT CSVs from committed viewer JSON for cloud pipeline runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
DATA_DIR = REPO / "cfb_data"
DATA_DIR.mkdir(exist_ok=True)

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
    return json.loads((REPO / "data" / name).read_text(encoding="utf-8"))


def write_teams_csv() -> None:
    teams = load_json("teams.json")
    path = DATA_DIR / "espn_cfb_teams_conferences.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["team_id", "team_name", "conference"],
        )
        writer.writeheader()
        for team in teams:
            conf = (team.get("conference") or "").strip()
            if conf not in FBS_CONFERENCES:
                continue
            writer.writerow(
                {
                    "team_id": team["team_id"],
                    "team_name": team["team_name"],
                    "conference": conf,
                }
            )
    print(f"Wrote {path}")


def write_preseason_csv() -> None:
    rankings = load_json("rankings.json")
    week1 = rankings["by_week"].get("1") or rankings["by_week"].get(1) or []
    by_team = {row["team_id"]: row for row in week1}
    teams = load_json("teams.json")
    path = DATA_DIR / "Preseason_2026_blended.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Team Proper Name", "Team", "combined_FPI"],
        )
        writer.writeheader()
        for team in teams:
            conf = (team.get("conference") or "").strip()
            if conf not in FBS_CONFERENCES:
                continue
            rank_row = by_team.get(team["team_id"], {})
            preseason = rank_row.get("preseason_margin")
            if preseason is None:
                continue
            short = team["team_name"].replace(" State", " St.").split()[-2:]
            writer.writerow(
                {
                    "Team Proper Name": team["team_name"],
                    "Team": " ".join(short) if short else team["team_name"],
                    "combined_FPI": f"{float(preseason):.3f}",
                }
            )
    print(f"Wrote {path}")


def schedule_row_to_csv(game: dict) -> dict:
    completed = bool(game.get("completed"))
    return {
        "game_id": game["game_id"],
        "season_year": "2026",
        "game_date": game.get("game_date", ""),
        "week": str(game.get("week", "")),
        "season_type": game.get("season_type", "regular-season"),
        "team_id": game["team_id"],
        "team_name": game.get("team_name", ""),
        "conference": game.get("conference", ""),
        "opponent_id": game["opponent_id"],
        "opponent_name": game.get("opponent_name", ""),
        "home_away": game.get("home_away", "home"),
        "neutral_site": str(game.get("neutral_site", "False")),
        "team_fpi": str(game.get("team_fpi", "")),
        "opponent_fpi": str(game.get("opponent_fpi", "")),
        "team_score": str(game.get("team_score", "")) if completed else "",
        "opponent_score": str(game.get("opponent_score", "")) if completed else "",
        "game_completed": "True" if completed else "False",
        "team_yards": "",
        "opponent_yards": "",
    }


def flip_perspective(row: dict) -> dict:
    flipped = dict(row)
    flipped["team_id"] = row["opponent_id"]
    flipped["team_name"] = row["opponent_name"]
    flipped["conference"] = ""
    flipped["opponent_id"] = row["team_id"]
    flipped["opponent_name"] = row["team_name"]
    flipped["team_fpi"] = row["opponent_fpi"]
    flipped["opponent_fpi"] = row["team_fpi"]
    flipped["home_away"] = "away" if row.get("home_away") == "home" else "home"
    flipped["team_score"] = row["opponent_score"]
    flipped["opponent_score"] = row["team_score"]
    flipped["team_yards"] = row["opponent_yards"]
    flipped["opponent_yards"] = row["team_yards"]
    return flipped


def write_games_csv() -> None:
    schedule = load_json("schedule.json")
    rows: list[dict] = []
    for game in schedule:
        home_row = schedule_row_to_csv(game)
        rows.append(home_row)
        rows.append(flip_perspective(home_row))

    fieldnames = list(rows[0].keys()) if rows else []
    path = DATA_DIR / "cfb_2026_fbs_games_with_fpi.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {path} ({len(rows)} rows)")


def main() -> None:
    write_teams_csv()
    write_preseason_csv()
    write_games_csv()
    print(f"Bootstrap complete: {DATA_DIR}")


if __name__ == "__main__":
    main()
