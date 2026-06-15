"""Load season game data for the team rating algorithm."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

from cfb_rating.rating_algorithm import GameRecord


def _data_root() -> Path:
    env = os.environ.get("CFB_DATA_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent


DEFAULT_YARDS_PER_POINT = 15.5
DEFAULT_ESPN_GAMES_CSV = _data_root() / "cfb_2025_espn_games.csv"
DEFAULT_ESPN_TEAMS_CSV = _data_root() / "espn_cfb_teams_conferences.csv"

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


def _classification(value: str) -> str:
    return (value or "").strip().lower()


def is_fcs_team(classification: str) -> bool:
    return _classification(classification) == "fcs"


def is_fbs_team(classification: str) -> bool:
    return _classification(classification) == "fbs"


def _parse_bool(value: str) -> bool:
    return (value or "").strip().upper() == "TRUE"


def _parse_points(value: str) -> float:
    if value is None or value == "":
        raise ValueError("missing points")
    return float(value)


def _estimate_yards(points: float, yards_per_point: float) -> float:
    return max(points, 0.0) * yards_per_point


def load_season_games(
    path: Union[str, Path],
    *,
    drop_fcs: bool = True,
    fbs_only: bool = True,
    completed_only: bool = True,
    estimate_yards: bool = True,
    yards_per_point: float = DEFAULT_YARDS_PER_POINT,
) -> List[GameRecord]:
    """Load games from a season CSV into ``GameRecord`` rows.

    By default, drops any game with an FCS team, keeps completed FBS vs FBS
  games, and estimates yards from points when the file has no yardage columns.
    """
    games: List[GameRecord] = []
    path = Path(path)

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            home_class = row.get("HomeClassification", "")
            away_class = row.get("AwayClassification", "")

            if drop_fcs and (is_fcs_team(home_class) or is_fcs_team(away_class)):
                continue
            if fbs_only and (not is_fbs_team(home_class) or not is_fbs_team(away_class)):
                continue
            if completed_only and not _parse_bool(row.get("Completed", "")):
                continue

            home_points = _parse_points(row.get("HomePoints", ""))
            away_points = _parse_points(row.get("AwayPoints", ""))

            if estimate_yards:
                home_yards = _estimate_yards(home_points, yards_per_point)
                away_yards = _estimate_yards(away_points, yards_per_point)
            else:
                home_yards = _parse_points(row.get("HomeYards", ""))
                away_yards = _parse_points(row.get("AwayYards", ""))

            season = row.get("Season", "")
            week = row.get("Week", "")
            home_team = row.get("HomeTeam", "").strip()
            away_team = row.get("AwayTeam", "").strip()
            game_id = f"{season}-{week}-{home_team}-{away_team}"

            games.append(
                GameRecord(
                    home_team_id=home_team,
                    away_team_id=away_team,
                    home_score=home_points,
                    away_score=away_points,
                    home_yards=home_yards,
                    away_yards=away_yards,
                    game_id=game_id,
                )
            )

    return games


def load_fbs_team_ids(
    teams_path: Union[str, Path] = DEFAULT_ESPN_TEAMS_CSV,
) -> Dict[str, dict]:
    """Return FBS teams keyed by ESPN team_id."""
    teams_path = Path(teams_path)
    teams: Dict[str, dict] = {}
    with teams_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("conference") not in FBS_CONFERENCES:
                continue
            team_id = row["team_id"].strip()
            teams[team_id] = {
                "team_id": team_id,
                "team_name": row.get("team_name", "").strip(),
                "conference": row.get("conference", "").strip(),
            }
    return teams


def load_espn_games(
    path: Union[str, Path] = DEFAULT_ESPN_GAMES_CSV,
    *,
    fbs_only: bool = True,
    teams_path: Union[str, Path] = DEFAULT_ESPN_TEAMS_CSV,
) -> List[GameRecord]:
    """Load completed games from the ESPN games export."""
    path = Path(path)
    fbs_teams = load_fbs_team_ids(teams_path) if fbs_only else None
    games: List[GameRecord] = []

    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            home_team_id = row["home_team_id"].strip()
            away_team_id = row["away_team_id"].strip()

            if fbs_teams is not None:
                if home_team_id not in fbs_teams or away_team_id not in fbs_teams:
                    continue

            home_yards = float(row["home_total_yards"])
            away_yards = float(row["away_total_yards"])
            if home_yards <= 0 or away_yards <= 0:
                continue

            week_raw = (row.get("week") or "").strip()
            season_raw = (row.get("season") or "").strip()
            games.append(
                GameRecord(
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    home_score=float(row["home_points"]),
                    away_score=float(row["away_points"]),
                    home_yards=home_yards,
                    away_yards=away_yards,
                    game_id=row.get("game_id") or None,
                    week=int(week_raw) if week_raw else None,
                    season=int(season_raw) if season_raw else None,
                )
            )

    return games


def load_fbs_schedule_games(
    path: Union[str, Path],
    *,
    fbs_only: bool = True,
    completed_only: bool = True,
    teams_path: Union[str, Path] = DEFAULT_ESPN_TEAMS_CSV,
    yards_per_point: float = DEFAULT_YARDS_PER_POINT,
) -> List[GameRecord]:
    """Load completed games from the duplicated team-perspective FBS schedule CSV."""
    path = Path(path)
    fbs_teams = load_fbs_team_ids(teams_path) if fbs_only else None
    games: List[GameRecord] = []
    seen: set[str] = set()

    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("home_away") != "home":
                continue
            game_id = (row.get("game_id") or "").strip()
            if not game_id or game_id in seen:
                continue

            home_team_id = (row.get("team_id") or "").strip()
            away_team_id = (row.get("opponent_id") or "").strip()
            if not home_team_id or not away_team_id:
                continue

            if fbs_teams is not None:
                if home_team_id not in fbs_teams or away_team_id not in fbs_teams:
                    continue

            completed = (row.get("game_completed") or "").strip().lower() in {
                "true",
                "1",
                "yes",
            }
            if completed_only and not completed:
                continue

            try:
                home_score = _parse_points(row.get("team_score", ""))
                away_score = _parse_points(row.get("opponent_score", ""))
            except ValueError:
                if completed_only:
                    continue
                home_score = 0.0
                away_score = 0.0

            week_raw = (row.get("week") or "").strip()
            season_raw = (row.get("season_year") or row.get("season") or "").strip()
            home_yards = _estimate_yards(home_score, yards_per_point)
            away_yards = _estimate_yards(away_score, yards_per_point)

            games.append(
                GameRecord(
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    home_score=home_score,
                    away_score=away_score,
                    home_yards=home_yards,
                    away_yards=away_yards,
                    game_id=game_id,
                    week=int(week_raw) if week_raw else None,
                    season=int(season_raw) if season_raw else None,
                )
            )
            seen.add(game_id)

    return games


def load_games_for_in_season_rankings(
    path: Union[str, Path] = DEFAULT_ESPN_GAMES_CSV,
    *,
    fbs_only: bool = True,
    teams_path: Union[str, Path] = DEFAULT_ESPN_TEAMS_CSV,
) -> List[GameRecord]:
    """Load games for in-season rankings from ESPN or team-perspective schedule CSV."""
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        fields = csv.DictReader(handle).fieldnames or []
    if "home_team_id" in fields:
        return load_espn_games(path, fbs_only=fbs_only, teams_path=teams_path)
    if "team_id" in fields and "home_away" in fields:
        return load_fbs_schedule_games(
            path, fbs_only=fbs_only, teams_path=teams_path
        )
    raise ValueError(f"Unrecognized games CSV format: {path}")


def load_2025_season_games(
    path: Optional[Union[str, Path]] = None,
    **kwargs,
) -> List[GameRecord]:
    """Load 2025 season games from the ESPN export (FBS vs FBS by default)."""
    if path is None:
        return load_espn_games(**kwargs)
    path = Path(path)
    if "espn" in path.name.lower():
        return load_espn_games(path, **kwargs)
    return load_season_games(path, **kwargs)


def write_team_ratings_csv(
    ratings: dict[str, float],
    path: Union[str, Path],
    *,
    team_info: Optional[Dict[str, dict]] = None,
    sort_descending: bool = True,
) -> None:
    path = Path(path)
    ordered: Iterable[tuple[str, float]]
    if sort_descending:
        ordered = sorted(ratings.items(), key=lambda item: (-item[1], item[0]))
    else:
        ordered = sorted(ratings.items())

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        if team_info:
            writer = csv.DictWriter(
                handle,
                fieldnames=["team_id", "team_name", "conference", "rating"],
            )
            writer.writeheader()
            for team_id, rating in ordered:
                info = team_info.get(team_id, {})
                writer.writerow(
                    {
                        "team_id": team_id,
                        "team_name": info.get("team_name", ""),
                        "conference": info.get("conference", ""),
                        "rating": f"{rating:.10f}",
                    }
                )
        else:
            writer = csv.writer(handle)
            writer.writerow(["team_id", "rating"])
            for team_id, rating in ordered:
                writer.writerow([team_id, f"{rating:.10f}"])
