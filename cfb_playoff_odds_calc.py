#!/usr/bin/env python3
"""
Compute CFB 12-team playoff championship odds.

Bracket rules:
  - Seeds 1-4 receive byes
  - First round: 5v12, 6v11, 7v10, 8v9 (highest vs lowest)
  - Quarterfinals: 1 vs 8/9 winner, 2 vs 7/10, 3 vs 6/11, 4 vs 5/12
  - Neutral-site games; win probability from per-sim FPI margin via logistic model
  - Seeding and matchup strength use per-simulation team FPI draws (sim_XXXX columns),
    not the static Overall point estimate in team_fpi

Examples:
  python cfb_playoff_odds_calc.py --demo
  python cfb_playoff_odds_calc.py --from-data
  python cfb_playoff_odds_calc.py --teams "Ohio State,Georgia,Texas,..." --ratings "28,26,24,..."
"""

from __future__ import annotations

from cfb_paths import data_root

import argparse
import csv
import re
from pathlib import Path

from cfb_playoff_odds import format_bracket, odds_table

DEFAULT_ELIG_PATH = data_root() / "cfb_2026_FBS_playoff_elig_v2.csv"
DEFAULT_GAMES_FPI_PATH = data_root() / "cfb_2026_fbs_games_with_fpi.csv"
DEFAULT_OUTPUT_PATH = Path(__file__).with_name(
    "cfb_2026_FBS_playoff_champ_odds_fpi_seed.csv"
)

SIM_COL_PATTERN = re.compile(r"^sim_\d+$")


def parse_csv_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_float_list(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def load_sim_fpi_by_team(path: Path) -> dict[str, dict[str, float]]:
    """
    Per-simulation team FPI from games file sim columns.

    Each sim_XXXX column holds that team's simulated FPI for that season draw.
    """
    sim_fpi: dict[str, dict[str, float]] = {}

    with path.open(encoding="utf-8-sig", newline="") as infile:
        reader = csv.DictReader(infile)
        sim_cols = sim_columns(reader.fieldnames or [])
        for col in sim_cols:
            sim_fpi[col] = {}

        for row in reader:
            name = row.get("team_name", "").strip()
            if not name or name == "TBD":
                continue
            for col in sim_cols:
                if name in sim_fpi[col]:
                    continue
                raw = (row.get(col) or "").strip()
                if not raw:
                    continue
                try:
                    sim_fpi[col][name] = float(raw)
                except ValueError:
                    pass

    return sim_fpi


def sim_columns(fieldnames: list[str]) -> list[str]:
    return [col for col in fieldnames if SIM_COL_PATTERN.match(col)]


def seed_playoff_field(
    elig_rows: list[dict[str, str]],
    sim_col: str,
    sim_fpi_for_col: dict[str, float],
) -> list[tuple[str, str, float]]:
    """Return seeded playoff teams: (team_name, conference, sim_fpi)."""
    playoff = [
        row
        for row in elig_rows
        if int(row[sim_col]) == 1 and row["team_name"] in sim_fpi_for_col
    ]
    if len(playoff) != 12:
        return []

    seeded = []
    for row in playoff:
        name = row["team_name"]
        fpi = sim_fpi_for_col[name]
        seeded.append((name, row["conference"], fpi))

    seeded.sort(key=lambda item: (-item[2], item[0]))
    return seeded


def bracket_title_odds(
    seeded: list[tuple[str, str, float]],
) -> dict[str, float]:
    from cfb_playoff_odds import championship_odds_exact

    names = [item[0] for item in seeded]
    ratings = [item[2] for item in seeded]
    probs = championship_odds_exact(ratings)
    return dict(zip(names, probs))


def run_from_data(
    elig_path: Path,
    games_fpi_path: Path,
    output_path: Path,
) -> int:
    sim_fpi_by_col = load_sim_fpi_by_team(games_fpi_path)

    with elig_path.open(encoding="utf-8-sig", newline="") as infile:
        elig_reader = csv.DictReader(infile)
        elig_rows = list(elig_reader)
        elig_sim_cols = sim_columns(elig_reader.fieldnames or [])

    sim_cols = [col for col in elig_sim_cols if col in sim_fpi_by_col]
    if not sim_cols:
        raise RuntimeError("No overlapping sim columns between eligibility and games FPI files")

    totals: dict[str, float] = {}
    appearances: dict[str, int] = {}
    seed_totals: dict[str, float] = {}
    conferences: dict[str, str] = {}
    used_sims = 0

    for sim_col in sim_cols:
        seeded = seed_playoff_field(elig_rows, sim_col, sim_fpi_by_col[sim_col])
        if not seeded:
            continue

        used_sims += 1
        result = bracket_title_odds(seeded)
        for seed_idx, (name, conf, _) in enumerate(seeded, start=1):
            conferences[name] = conf
            appearances[name] = appearances.get(name, 0) + 1
            seed_totals[name] = seed_totals.get(name, 0.0) + seed_idx
            totals[name] = totals.get(name, 0.0) + result[name]

    if used_sims == 0:
        raise RuntimeError("No simulation columns produced a 12-team playoff field")

    summary = []
    for name, total_prob in totals.items():
        apps = appearances[name]
        summary.append(
            {
                "team_name": name,
                "conference": conferences[name],
                "title_odds_pct": round(total_prob / used_sims * 100, 2),
                "playoff_appearances": apps,
                "avg_seed_when_in": round(seed_totals[name] / apps, 2),
            }
        )

    summary.sort(key=lambda row: (-float(row["title_odds_pct"]), row["team_name"]))

    fieldnames = [
        "team_name",
        "conference",
        "title_odds_pct",
        "playoff_appearances",
        "avg_seed_when_in",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)

    print(f"Processed {used_sims} playoff fields from {len(sim_cols)} sim columns")
    print(f"Wrote {len(summary)} teams to {output_path}")
    return len(summary)


def run_demo() -> None:
    teams = [
        "Ohio State Buckeyes",
        "Georgia Bulldogs",
        "Texas Longhorns",
        "Penn State Nittany Lions",
        "Oregon Ducks",
        "Notre Dame Fighting Irish",
        "Miami Hurricanes",
        "Texas Tech Red Raiders",
        "Indiana Hoosiers",
        "LSU Tigers",
        "Alabama Crimson Tide",
        "Michigan Wolverines",
    ]
    conferences = [
        "Big Ten",
        "SEC",
        "SEC",
        "Big Ten",
        "Big Ten",
        "FBS Indep.",
        "ACC",
        "Big 12",
        "Big Ten",
        "SEC",
        "SEC",
        "Big Ten",
    ]
    ratings = [28.0, 27.0, 24.0, 23.0, 22.0, 21.0, 20.0, 19.0, 18.0, 17.0, 16.0, 15.0]

    print(format_bracket(teams))
    print()
    for row in odds_table(teams, ratings, conferences):
        print(
            f"#{row['seed']:>2}  {row['team_name']:<30}  "
            f"{row['title_odds_pct']:>5.2f}%"
        )


def run_manual(teams: list[str], ratings: list[float], conferences: list[str] | None):
    if len(teams) != 12 or len(ratings) != 12:
        raise SystemExit("Manual mode requires exactly 12 teams and 12 ratings")

    print(format_bracket(teams))
    print()
    for row in odds_table(teams, ratings, conferences):
        print(
            f"#{row['seed']:>2}  {row['team_name']:<30}  "
            f"{row['title_odds_pct']:>5.2f}%"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CFB 12-team playoff odds calculator")
    parser.add_argument("--demo", action="store_true", help="Run a sample 12-team bracket")
    parser.add_argument(
        "--from-data",
        action="store_true",
        help="Aggregate odds from eligibility + per-sim FPI in games file",
    )
    parser.add_argument("--teams", help="Comma-separated list of 12 teams, seed order 1-12")
    parser.add_argument(
        "--ratings",
        help="Comma-separated list of 12 strength ratings (e.g. FPI), seed order 1-12",
    )
    parser.add_argument("--conferences", help="Optional comma-separated conferences")
    parser.add_argument("--elig", type=Path, default=DEFAULT_ELIG_PATH)
    parser.add_argument("--games-fpi", type=Path, default=DEFAULT_GAMES_FPI_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.demo:
        run_demo()
        return

    if args.from_data:
        run_from_data(args.elig, args.games_fpi, args.output)
        return

    if args.teams and args.ratings:
        teams = parse_csv_list(args.teams)
        ratings = parse_float_list(args.ratings)
        conferences = parse_csv_list(args.conferences) if args.conferences else None
        run_manual(teams, ratings, conferences)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
