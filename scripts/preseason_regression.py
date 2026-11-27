#!/usr/bin/env python3
"""Reproduce preseason lag-rating regressions (see preseason_regression.md)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import lsq_linear, nnls

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_YEARS = ROOT / "data" / "previous_years.json"

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
    main()