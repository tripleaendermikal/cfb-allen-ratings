"""Margin rating: expected point margin vs a median (0.5) team."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Union

MEDIAN_RATING = 0.5
R_SCALE = 0.5
MARGIN_MULTIPLIER = 14.0


@dataclass(frozen=True)
class MarginRatingResult:
    team_id: str
    rating: float
    r: float
    rs: float
    margin_rating: float


def compute_r(rating: float, median: float = MEDIAN_RATING, scale: float = R_SCALE) -> float:
    """R = (rating - median) / scale."""
    return (rating - median) / scale


def _standard_deviation(values: Iterable[float]) -> float:
    vals = list(values)
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    variance = sum((value - mean) ** 2 for value in vals) / len(vals)
    return math.sqrt(variance)


def compute_margin_ratings(
    ratings: Mapping[str, float],
    *,
    median: float = MEDIAN_RATING,
    scale: float = R_SCALE,
    margin_multiplier: float = MARGIN_MULTIPLIER,
) -> Dict[str, MarginRatingResult]:
    """Convert team ratings to expected margin vs a median team.

    1. R = (rating - 0.5) / 0.5
    2. RS = R / std_dev(R) across all teams
    3. margin_rating = RS * 14
    """
    r_values = {team_id: compute_r(rating, median, scale) for team_id, rating in ratings.items()}
    r_std = _standard_deviation(r_values.values())

    results: Dict[str, MarginRatingResult] = {}
    for team_id, rating in ratings.items():
        r = r_values[team_id]
        rs = r / r_std if r_std else 0.0
        results[team_id] = MarginRatingResult(
            team_id=team_id,
            rating=rating,
            r=r,
            rs=rs,
            margin_rating=rs * margin_multiplier,
        )
    return results


def write_margin_ratings_csv(
    margin_ratings: Mapping[str, MarginRatingResult],
    path: Union[str, Path],
    *,
    team_info: Optional[Dict[str, dict]] = None,
    sort_descending: bool = True,
) -> None:
    path = Path(path)
    ordered = margin_ratings.values()
    if sort_descending:
        ordered = sorted(ordered, key=lambda row: (-row.margin_rating, row.team_id))
    else:
        ordered = sorted(ordered, key=lambda row: (row.margin_rating, row.team_id))

    fieldnames = ["team_id", "team_name", "conference", "rating", "r", "rs", "margin_rating"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in ordered:
            info = (team_info or {}).get(row.team_id, {})
            writer.writerow(
                {
                    "team_id": row.team_id,
                    "team_name": info.get("team_name", ""),
                    "conference": info.get("conference", ""),
                    "rating": f"{row.rating:.10f}",
                    "r": f"{row.r:.10f}",
                    "rs": f"{row.rs:.10f}",
                    "margin_rating": f"{row.margin_rating:.10f}",
                }
            )
