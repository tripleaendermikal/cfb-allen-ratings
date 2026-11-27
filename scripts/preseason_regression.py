#!/usr/bin/env python3
"""Reproduce preseason lag-rating regressions (see preseason_regression.md)."""

from __future__ import annotations

import json
import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import lsq_linear, nnls

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_YEARS = ROOT / "data" / "previous_years.json"
RANKINGS_JSON = ROOT / "data" / "rankings.json"
PREDICTED_2027_CSV = ROOT / "data" / "preseason_2027_predicted_rankings.csv"

# Model B coefficients (fixed after fit on 2025 holdout; see preseason_regression.md)
MODEL_B_BETA_BY_SLOT = (0.027752, 0.132481, 0.038620, 0.443463)  # oldest..newest lag
MODEL_B_ALPHAS = (2.6515, 2.1851, -3.2675, -8.3003)

GROUP_NAMES = [
    "SEC / Notre Dame / Big Ten",
    "ACC / Big 12",
    "Pac-12 / MWC / American / Sun Belt",
    "Rest",
]


def group_for_team(team_id: str, conference: str) -> int:
    conf = (conference or "").strip()
    if str(team_id) == "87" or conf in ("SEC", "Big Ten"):
        return 0
    if conf in ("ACC", "Big 12"):
        return 1
    if conf in ("Pac-12", "Mountain West", "American", "Sun Belt"):
        return 2
    return 3


def final_season_table(season: int) -> tuple[dict[str, float], dict[str, tuple[str, str]]]:
    payload = json.loads(PREVIOUS_YEARS.read_text())
    season_row = payload["seasons"][str(season)]
    final_week = season_row["final_week"]
    rows = season_row["by_week"].get(str(final_week)) or season_row["by_week"][final_week]
    margins: dict[str, float] = {}
    meta: dict[str, tuple[str, str]] = {}
    for row in rows:
        team_id = row["team_id"]
        margins[team_id] = float(row["overall_margin"])
        meta[team_id] = (row["team_name"], row.get("conference", "") or "")
    return margins, meta


def in_season_margins(season_year: int) -> tuple[dict[str, float], dict[str, tuple[str, str]], int]:
    """Overall margin from live rankings export (current week, not final)."""
    payload = json.loads(RANKINGS_JSON.read_text())
    if payload.get("current_week") is None:
        raise SystemExit("rankings.json missing current_week")
    week = int(payload["current_week"])
    rows = payload["by_week"].get(str(week)) or payload["by_week"][week]
    margins: dict[str, float] = {}
    meta: dict[str, tuple[str, str]] = {}
    for row in rows:
        overall = row.get("overall_margin")
        if overall is None:
            continue
        team_id = row["team_id"]
        margins[team_id] = float(overall)
        meta[team_id] = (row["team_name"], row.get("conference", "") or "")
    return margins, meta, week


def predict_2027_rankings(write_csv: Path | None = PREDICTED_2027_CSV) -> list[dict]:
    """Model B projection for 2027 using final-week margins 2023–2025 and in-season 2026."""
    lag_years = (2023, 2024, 2025, 2026)
    archived_years = (2023, 2024, 2025)
    data: dict[int, dict[str, float]] = {}
    meta: dict[int, dict[str, tuple[str, str]]] = {}
    week_2026: int | None = None
    for year in archived_years:
        data[year], meta[year] = final_season_table(year)
    data[2026], meta[2026], week_2026 = in_season_margins(2026)

    # Full current FBS pool (week snapshot), not only teams with four archive seasons.
    team_ids = sorted(
        meta[2026].keys(),
        key=lambda tid: meta[2026].get(tid, ("", ""))[0],
    )
    rows_out: list[dict] = []
    def predicted_margin(tid: str) -> float:
        conf = meta[2026].get(tid, meta[2025].get(tid, ("", "")))[1]
        linear = 0.0
        for i, year in enumerate(lag_years):
            if tid in data[year]:
                linear += MODEL_B_BETA_BY_SLOT[i] * data[year][tid]
        return linear + MODEL_B_ALPHAS[group_for_team(tid, conf)]

    def lag_value(tid: str, year: int) -> str:
        if tid not in data[year]:
            return ""
        return f"{data[year][tid]:.4f}"

    for rank, team_id in enumerate(
        sorted(team_ids, key=lambda tid: -predicted_margin(tid)),
        start=1,
    ):
        conf = meta[2026].get(team_id, meta[2025].get(team_id, ("", "")))[1]
        g = group_for_team(team_id, conf)
        predicted = predicted_margin(team_id)
        name = meta[2026].get(team_id, meta[2025].get(team_id, ("", "")))[0]
        rows_out.append(
            {
                "rank": rank,
                "team_id": team_id,
                "team_name": name,
                "conference": conf,
                "group": g + 1,
                "predicted_overall_margin_2027": round(predicted, 4),
                "r_2023": lag_value(team_id, 2023),
                "r_2024": lag_value(team_id, 2024),
                "r_2025": lag_value(team_id, 2025),
                "r_2026": lag_value(team_id, 2026),
            }
        )

    if write_csv:
        write_csv.parent.mkdir(parents=True, exist_ok=True)
        with write_csv.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
            writer.writeheader()
            writer.writerows(rows_out)
        print(
            f"Wrote {len(rows_out)} projected 2027 rows to {write_csv} "
            f"(2026 inputs: week {week_2026} in-season overall_margin)"
        )
    return rows_out


def main() -> None:
    years = [2021, 2022, 2023, 2024, 2025]
    data: dict[int, dict[str, float]] = {}
    meta: dict[int, dict[str, tuple[str, str]]] = {}
    for year in years:
        data[year], meta[year] = final_season_table(year)

    team_ids = sorted(set.intersection(*[set(data[y]) for y in years]))
    n = len(team_ids)
    x_rating = np.column_stack([[data[y][tid] for tid in team_ids] for y in years[:-1]])
    y = np.array([data[2025][tid] for tid in team_ids])

    groups = [
        group_for_team(tid, meta[2025][tid][1] or meta[2024][tid][1]) for tid in team_ids
    ]

    betas_a, _ = nnls(x_rating, y)
    y_a = x_rating @ betas_a
    ss_tot = np.sum((y - np.mean(y)) ** 2)

    dummies = np.zeros((n, 4))
    for i, g in enumerate(groups):
        dummies[i, g] = 1.0
    x_full = np.hstack([x_rating, dummies])
    lower = [0.0, 0.0, 0.0, 0.0, -np.inf, -np.inf, -np.inf, -np.inf]
    result = lsq_linear(x_full, y, bounds=(lower, np.inf), method="trf")
    betas_b = result.x[:4]
    alphas = result.x[4:]
    y_b = x_full @ result.x

    def metrics(y_hat: np.ndarray) -> tuple[float, float, float]:
        ss_res = np.sum((y - y_hat) ** 2)
        return (
            float(np.sqrt(ss_res / n)),
            float(np.mean(np.abs(y - y_hat))),
            float(1 - ss_res / ss_tot),
        )

    print(f"Teams in all seasons: {n}\n")

    print("Model A (intercept = 0, betas >= 0)")
    for year, beta in zip(years[:-1], betas_a):
        print(f"  {year}: {beta:.6f}")
    print(f"  beta sum: {betas_a.sum():.6f}")
    rmse, mae, r2 = metrics(y_a)
    print(f"  RMSE={rmse:.4f} MAE={mae:.4f} R2={r2:.4f}\n")

    print("Model B (group intercepts, betas >= 0)")
    for year, beta in zip(years[:-1], betas_b):
        print(f"  {year}: {beta:.6f}")
    print(f"  beta sum: {betas_b.sum():.6f}")
    for idx, (name, alpha) in enumerate(zip(GROUP_NAMES, alphas)):
        print(f"  alpha group {idx + 1} ({name}): {alpha:.4f}")
    rmse, mae, r2 = metrics(y_b)
    print(f"  RMSE={rmse:.4f} MAE={mae:.4f} R2={r2:.4f}\n")

    by_group: dict[int, Counter[str]] = defaultdict(Counter)
    for tid, g in zip(team_ids, groups):
        conf = meta[2025][tid][1] or meta[2024][tid][1] or "?"
        by_group[g][conf] += 1
    for g in range(4):
        print(f"Group {g + 1} conferences: {dict(by_group[g])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predict-2027",
        action="store_true",
        help="Write Model B 2027 rankings to data/preseason_2027_predicted_rankings.csv",
    )
    parser.add_argument(
        "--predict-2027-only",
        action="store_true",
        help="Only run 2027 projection (skip refitting 2025 holdout models)",
    )
    args = parser.parse_args()
    if args.predict_2027_only:
        rows = predict_2027_rankings()
        for row in rows[:25]:
            print(
                f"{row['rank']:3d}  {row['predicted_overall_margin_2027']:7.2f}  "
                f"{row['team_name']} ({row['conference']})"
            )
    else:
        main()
        if args.predict_2027:
            predict_2027_rankings()