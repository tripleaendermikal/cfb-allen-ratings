#!/usr/bin/env python3
"""Replace team_fpi / opponent_fpi with combined_FPI from Preseason 2026.csv."""

from __future__ import annotations

from cfb_paths import data_root

import csv
from pathlib import Path

PRESEASON = data_root() / "Preseason_2026.csv"
BLENDED = data_root() / "Preseason_2026_blended.csv"


def preseason_csv() -> Path:
    if BLENDED.is_file():
        with BLENDED.open(newline="", encoding="utf-8-sig") as f:
            fields = csv.DictReader(f).fieldnames or []
        if "combined_FPI" in fields:
            return BLENDED
    return PRESEASON
FILES = [
    data_root() / "cfb_2026_fbs_games_with_fpi.csv",
    data_root() / "cfb_2026_fbs_games_with_fpi_margin.csv",
]


def norm(s: str) -> str:
    return (s or "").strip().casefold().replace("\u2019", "'").replace("\u00e9", "e")


def rating_from_row(row: dict[str, str]) -> float | None:
    combined = (row.get("combined_FPI") or "").strip()
    if combined:
        return round(float(combined), 3)
    forecast = (row.get("Forecast") or "").strip()
    if forecast:
        return round(float(forecast), 3)
    return None


def load_forecasts() -> tuple[dict[str, float], dict[str, float]]:
    by_proper: dict[str, float] = {}
    by_short: dict[str, float] = {}
    with preseason_csv().open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            proper = (row.get("Team Proper Name") or "").strip()
            short = (row.get("Team") or "").strip()
            val = rating_from_row(row)
            if val is None:
                continue
            if proper:
                by_proper[norm(proper)] = val
            if short:
                by_short[norm(short)] = val
    return by_proper, by_short


def lookup_fpi(
    display_name: str,
    by_proper: dict[str, float],
    by_short: dict[str, float],
    old_val: str | None,
) -> float:
    n = norm(display_name)
    if n in by_proper:
        return by_proper[n]
    if "north dakota state" in n:
        return by_proper.get(norm("North Dakota State Bison"), by_short.get(norm("North Dakota State"), 1.0))
    if "sacramento state" in n:
        return by_proper.get(norm("Sacramento State Hornets"), by_short.get(norm("Sac State"), -20.0))
    if old_val is not None and str(old_val).strip() != "":
        try:
            return round(float(old_val), 3)
        except ValueError:
            pass
    return -36.0


def home_field(neutral: str, home_away: str) -> float:
    if str(neutral).strip().lower() in ("true", "1", "yes"):
        return 0.0
    if home_away == "home":
        return 3.0
    if home_away == "away":
        return -3.0
    return 0.0


def main() -> None:
    by_proper, by_short = load_forecasts()
    for path in FILES:
        if not path.is_file():
            print(f"skip missing {path}")
            continue
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames or [])
            rows = list(reader)

        has_margin = "expected_margin_of_victory" in fields
        matched = 0
        for row in rows:
            tname = row.get("team_name", "")
            oname = row.get("opponent_name", "")
            if norm(tname) in by_proper:
                matched += 1
            tf = lookup_fpi(tname, by_proper, by_short, row.get("team_fpi"))
            of = lookup_fpi(oname, by_proper, by_short, row.get("opponent_fpi"))
            row["team_fpi"] = tf
            row["opponent_fpi"] = of
            if has_margin:
                m = home_field(row.get("neutral_site", ""), row.get("home_away", ""))
                row["expected_margin_of_victory"] = round(tf - of + m, 3)

        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(
            f"Updated {path.name}: {len(rows)} rows, "
            f"{matched} team-side rows matched preseason by name"
        )


if __name__ == "__main__":
    main()
