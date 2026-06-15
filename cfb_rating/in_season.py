"""In-season team rankings: algorithm margins blended with preseason combined_FPI."""

from __future__ import annotations

import csv
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Union

from cfb_rating.margin_rating import compute_margin_ratings
from cfb_rating.rating_algorithm import GameRecord, compute_team_ratings
from cfb_rating.season_data import DEFAULT_ESPN_TEAMS_CSV, load_fbs_team_ids


def _data_root() -> Path:
    env = os.environ.get("CFB_DATA_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent


DEFAULT_PRESEASON_CSV = _data_root() / "Preseason_2026.csv"
DEFAULT_PRESEASON_BLENDED_CSV = _data_root() / "Preseason_2026_blended.csv"
DEFAULT_FADE_GAMES = 10
DEFAULT_MAX_WEEK = 14


def norm_name(value: str) -> str:
    text = (value or "").strip()
    text = (
        text.replace("\u2019", "'")
        .replace("\u00e9", "e")
        .replace("Ã©", "e")
        .replace("ã©", "e")
    )
    return text.casefold()


def resolve_preseason_csv(path: Optional[Union[str, Path]] = None) -> Path:
    """Pick preseason CSV, preferring blended file when it has combined_FPI."""
    if path is not None:
        return Path(path)
    if DEFAULT_PRESEASON_BLENDED_CSV.is_file():
        with DEFAULT_PRESEASON_BLENDED_CSV.open(encoding="utf-8-sig", newline="") as handle:
            fields = csv.DictReader(handle).fieldnames or []
        if "combined_FPI" in fields:
            return DEFAULT_PRESEASON_BLENDED_CSV
    return DEFAULT_PRESEASON_CSV


def _preseason_margin_from_row(row: Mapping[str, str]) -> Optional[float]:
    combined = (row.get("combined_FPI") or "").strip()
    if combined:
        return float(combined)
    forecast = (row.get("Forecast") or "").strip()
    if forecast:
        return float(forecast)
    return None


def load_preseason_margins(
    path: Optional[Union[str, Path]] = None,
    *,
    teams_path: Union[str, Path] = DEFAULT_ESPN_TEAMS_CSV,
) -> Dict[str, float]:
    """Load combined_FPI keyed by ESPN team_id."""
    preseason_path = resolve_preseason_csv(path)
    by_proper: Dict[str, float] = {}
    by_short: Dict[str, float] = {}

    with preseason_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            proper = (row.get("Team Proper Name") or "").strip()
            short = (row.get("Team") or "").strip()
            margin = _preseason_margin_from_row(row)
            if margin is None:
                continue
            if proper:
                by_proper[norm_name(proper)] = margin
            if short:
                by_short[norm_name(short)] = margin

    team_info = load_fbs_team_ids(teams_path)
    preseason_by_team_id: Dict[str, float] = {}
    unmatched: list[str] = []

    for team_id, info in team_info.items():
        team_name = info.get("team_name", "")
        key = norm_name(team_name)
        margin = by_proper.get(key)
        if margin is None:
            margin = by_short.get(key)
        if margin is None and "north dakota state" in key:
            margin = by_proper.get(norm_name("North Dakota State Bison"))
        if margin is None and "sacramento state" in key:
            margin = by_proper.get(norm_name("Sacramento State Hornets"))
        if margin is None and "san jose state" in key:
            margin = by_proper.get(norm_name("San José State Spartans"))
        if margin is None:
            unmatched.append(team_name or team_id)
            continue
        preseason_by_team_id[team_id] = margin

    if unmatched:
        warnings.warn(
            f"{len(unmatched)} FBS teams missing preseason margin in {preseason_path.name}",
            stacklevel=2,
        )

    return preseason_by_team_id


def filter_games_through_week(
    games: Sequence[GameRecord],
    through_week: int,
    *,
    max_week: int = DEFAULT_MAX_WEEK,
) -> list[GameRecord]:
    """Keep regular-season games with week <= through_week."""
    filtered: list[GameRecord] = []
    for game in games:
        if game.week is None:
            continue
        if game.week > through_week or game.week > max_week:
            continue
        filtered.append(game)
    return filtered


def count_fbs_games(
    games: Sequence[GameRecord],
    team_ids: Sequence[str],
) -> Dict[str, int]:
    """Count FBS-vs-FBS games per team in the provided game set."""
    counts = {team_id: 0 for team_id in team_ids}
    for game in games:
        if game.home_team_id in counts:
            counts[game.home_team_id] += 1
        if game.away_team_id in counts:
            counts[game.away_team_id] += 1
    return counts


def preseason_fade_weight(
    games_played: int,
    *,
    fade_games: int = DEFAULT_FADE_GAMES,
) -> float:
    """Return preseason weight after ``games_played`` FBS games."""
    if fade_games <= 0:
        return 0.0
    capped = min(max(games_played, 0), fade_games)
    return (fade_games - capped) / fade_games


def blend_in_season_margins(
    preseason_margins: Mapping[str, float],
    algorithm_margins: Mapping[str, float],
    games_played: Mapping[str, int],
    *,
    fade_games: int = DEFAULT_FADE_GAMES,
) -> Dict[str, float]:
    """Blend preseason and algorithm margins using the linear fade rule."""
    blended: Dict[str, float] = {}
    for team_id, algorithm_margin in algorithm_margins.items():
        games = games_played.get(team_id, 0)
        preseason_weight = preseason_fade_weight(games, fade_games=fade_games)
        preseason_margin = preseason_margins.get(team_id)
        if preseason_margin is None or preseason_weight == 0.0:
            blended[team_id] = algorithm_margin
            continue
        if preseason_weight == 1.0:
            blended[team_id] = preseason_margin
            continue
        algorithm_weight = 1.0 - preseason_weight
        blended[team_id] = (
            preseason_weight * preseason_margin + algorithm_weight * algorithm_margin
        )
    return blended


@dataclass(frozen=True)
class InSeasonRankingRow:
    week: int
    rank: int
    team_id: str
    team_name: str
    conference: str
    fbs_games_played: int
    preseason_margin: Optional[float]
    algorithm_margin: float
    blended_margin: float
    algorithm_rating: float
    preseason_weight: float


def compute_in_season_rankings_for_week(
    games: Sequence[GameRecord],
    through_week: int,
    team_ids: Sequence[str],
    preseason_margins: Mapping[str, float],
    *,
    team_info: Optional[Mapping[str, dict]] = None,
    iterations: int = 1000,
    max_week: int = DEFAULT_MAX_WEEK,
    fade_games: int = DEFAULT_FADE_GAMES,
) -> list[InSeasonRankingRow]:
    """Compute blended in-season rankings as of ``through_week``."""
    week_games = filter_games_through_week(games, through_week, max_week=max_week)
    games_played = count_fbs_games(week_games, team_ids)

    ratings = compute_team_ratings(
        week_games,
        team_ids=team_ids,
        iterations=iterations,
    )
    margin_results = compute_margin_ratings(ratings)
    algorithm_margins = {
        team_id: result.margin_rating for team_id, result in margin_results.items()
    }
    blended_margins = blend_in_season_margins(
        preseason_margins,
        algorithm_margins,
        games_played,
        fade_games=fade_games,
    )

    info = team_info or {}
    ordered = sorted(
        team_ids,
        key=lambda team_id: (
            -blended_margins[team_id],
            info.get(team_id, {}).get("team_name", team_id),
        ),
    )

    rows: list[InSeasonRankingRow] = []
    for rank, team_id in enumerate(ordered, start=1):
        meta = info.get(team_id, {})
        preseason_weight = preseason_fade_weight(
            games_played.get(team_id, 0),
            fade_games=fade_games,
        )
        rows.append(
            InSeasonRankingRow(
                week=through_week,
                rank=rank,
                team_id=team_id,
                team_name=meta.get("team_name", ""),
                conference=meta.get("conference", ""),
                fbs_games_played=games_played.get(team_id, 0),
                preseason_margin=preseason_margins.get(team_id),
                algorithm_margin=algorithm_margins[team_id],
                blended_margin=blended_margins[team_id],
                algorithm_rating=ratings[team_id],
                preseason_weight=preseason_weight,
            )
        )
    return rows


def compute_weekly_in_season_rankings(
    games: Sequence[GameRecord],
    preseason_margins: Mapping[str, float],
    team_ids: Sequence[str],
    *,
    team_info: Optional[Mapping[str, dict]] = None,
    max_week: int = DEFAULT_MAX_WEEK,
    iterations: int = 1000,
    fade_games: int = DEFAULT_FADE_GAMES,
) -> list[InSeasonRankingRow]:
    """Compute stacked weekly rankings for weeks 1 through ``max_week``."""
    all_rows: list[InSeasonRankingRow] = []
    for week in range(1, max_week + 1):
        all_rows.extend(
            compute_in_season_rankings_for_week(
                games,
                week,
                team_ids,
                preseason_margins,
                team_info=team_info,
                iterations=iterations,
                max_week=max_week,
                fade_games=fade_games,
            )
        )
    return all_rows


def write_in_season_rankings_csv(
    rows: Sequence[InSeasonRankingRow],
    path: Union[str, Path],
) -> None:
    path = Path(path)
    fieldnames = [
        "week",
        "rank",
        "team_id",
        "team_name",
        "conference",
        "fbs_games_played",
        "preseason_margin",
        "algorithm_margin",
        "blended_margin",
        "algorithm_rating",
        "preseason_weight",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "week": row.week,
                    "rank": row.rank,
                    "team_id": row.team_id,
                    "team_name": row.team_name,
                    "conference": row.conference,
                    "fbs_games_played": row.fbs_games_played,
                    "preseason_margin": (
                        f"{row.preseason_margin:.10f}"
                        if row.preseason_margin is not None
                        else ""
                    ),
                    "algorithm_margin": f"{row.algorithm_margin:.10f}",
                    "blended_margin": f"{row.blended_margin:.10f}",
                    "algorithm_rating": f"{row.algorithm_rating:.10f}",
                    "preseason_weight": f"{row.preseason_weight:.10f}",
                }
            )
