#!/usr/bin/env python3
"""
Compute CFB 12-team playoff championship odds.

Bracket rules:
  - Seeds 1-4 receive byes
  - First round: 5v12, 6v11, 7v10, 8v9 (highest vs lowest)
  - Quarterfinals: 1 vs 8/9 winner, 2 vs 7/10, 3 vs 6/11, 4 vs 5/12
  - Neutral-site games; win probability from per-sim FPI margin via logistic model
  - Seeding: at-large ranking rules (wins, SOS, H2H, conf-champ boost); G6 is seed 12
  - Matchup strength uses per-simulation team FPI draws (sim_XXXX columns)

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
from cfb_playoff_elig import (
    build_season_h2h_by_sim,
    elig_by_team_id_for_col,
    load_game_rows_for_h2h,
    load_sim_fpi_by_team_id,
    load_sos_by_team_id,
    seed_playoff_field_col,
)
from cfb_playoff_resume_elig import (
    is_resume_eligibility_col,
    paired_game_sim_col,
    seed_playoff_field_resume_col,
)
from cfb_rating.season_data import load_fbs_team_ids
from cfb_rating.sim_resume import compute_sim_resume_margins, overall_margins_for_sim_col

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


def infer_records_path(elig_path: Path) -> Path:
    return Path(str(elig_path).replace("FBS_playoff_elig_v2", "fbs_team_sim_records_v2"))


def infer_games_sim_path(games_fpi_path: Path) -> Path:
    base = str(games_fpi_path)
    if base.endswith("_fbs_games_with_fpi.csv"):
        return Path(base.replace("_fbs_games_with_fpi.csv", "_fbs_games_with_fpi_simulated.csv"))
    return Path(base.replace("games_with_fpi.csv", "games_with_fpi_simulated.csv"))


def bracket_title_odds(
    seeded: list[tuple[str, str, float]],
) -> dict[str, float]:
    from cfb_playoff_odds import championship_odds_exact

    names = [item[0] for item in seeded]
    ratings = [item[2] for item in seeded]
    probs = championship_odds_exact(ratings)
    return dict(zip(names, probs))


def _aggregate_title_odds(
    sim_cols: list[str],
    elig_rows: list[dict],
    records_rows: list[dict],
    sim_fpi_by_col: dict[str, dict[str, float]],
    sos_by_team_id: dict,
    conf_champions_by_sim: dict,
    h2h_wins_by_col,
    h2h_games_by_col,
    game_rows: list[dict] | None,
    sim_fpi_by_team_id: dict,
    team_ids: list[str],
    fbs_ids: frozenset[str],
) -> tuple[dict[str, dict], int]:
    totals: dict[str, float] = {}
    appearances: dict[str, int] = {}
    seed_totals: dict[str, float] = {}
    conferences: dict[str, str] = {}
    used_sims = 0

    for sim_col in sim_cols:
        elig_by_team = elig_by_team_id_for_col(elig_rows, sim_col)
        if is_resume_eligibility_col(sim_col):
            if not game_rows:
                continue
            game_col = paired_game_sim_col(sim_col)
            fpi_map = sim_fpi_by_col.get(game_col)
            if not fpi_map:
                continue
            overall = overall_margins_for_sim_col(
                sim_fpi_by_team_id, game_col, team_ids
            )
            margins = compute_sim_resume_margins(
                game_rows,
                game_col,
                team_ids,
                overall,
                fbs_team_ids=fbs_ids,
            )
            seeded = seed_playoff_field_resume_col(
                records_rows,
                elig_by_team,
                fpi_map,
                margins,
            )
        else:
            fpi_map = sim_fpi_by_col.get(sim_col)
            if not fpi_map:
                continue
            seeded = seed_playoff_field_col(
                records_rows,
                sim_col,
                elig_by_team,
                fpi_map,
                sos_by_team_id,
                conf_champions_by_sim,
                h2h_wins_by_col,
                h2h_games_by_col,
            )
        if not seeded:
            continue

        used_sims += 1
        result = bracket_title_odds(seeded)
        for seed_idx, (name, conf, _) in enumerate(seeded, start=1):
            conferences[name] = conf
            appearances[name] = appearances.get(name, 0) + 1
            seed_totals[name] = seed_totals.get(name, 0.0) + seed_idx
            totals[name] = totals.get(name, 0.0) + result[name]

    by_name: dict[str, dict] = {}
    for name, total_prob in totals.items():
        apps = appearances[name]
        by_name[name] = {
            "team_name": name,
            "conference": conferences[name],
            "title_odds_pct": round(total_prob / used_sims * 100, 2) if used_sims else 0.0,
            "playoff_appearances": apps,
            "avg_seed_when_in": round(seed_totals[name] / apps, 2) if apps else 0.0,
        }
    return by_name, used_sims


def run_from_data(
    elig_path: Path,
    games_fpi_path: Path,
    output_path: Path,
    *,
    records_path: Path | None = None,
    games_sim_path: Path | None = None,
    conf_path: Path | None = None,
) -> int:
    sim_fpi_by_col = load_sim_fpi_by_team(games_fpi_path)
    sim_fpi_by_team_id = load_sim_fpi_by_team_id(games_fpi_path)
    sos_by_team_id = load_sos_by_team_id(games_fpi_path)

    records_path = records_path or infer_records_path(elig_path)
    games_sim_path = games_sim_path or infer_games_sim_path(games_fpi_path)
    conf_path = conf_path or games_fpi_path.parent / "espn_cfb_teams_conferences.csv"

    with records_path.open(encoding="utf-8-sig", newline="") as infile:
        records_rows = list(csv.DictReader(infile))

    team_ids = sorted(
        (row.get("team_id") or "").strip()
        for row in records_rows
        if (row.get("team_id") or "").strip()
    )
    fbs_ids = frozenset(load_fbs_team_ids().keys())

    game_rows: list[dict] | None = None
    h2h_wins_by_col = None
    h2h_games_by_col = None
    conf_champions_by_sim = {col: {} for col in sim_columns(records_rows[0].keys()) if records_rows}
    if games_sim_path.is_file() and conf_path.is_file():
        from cfb_conf_championship import compute_conf_results_by_sim

        conf_champions_by_sim = compute_conf_results_by_sim(
            games_sim_path, games_fpi_path, conf_path
        )["champions"]
        game_rows, sim_cols_h2h = load_game_rows_for_h2h(games_sim_path)
        if sim_cols_h2h:
            h2h_wins_by_col, h2h_games_by_col = build_season_h2h_by_sim(
                game_rows, sim_cols_h2h
            )

    with elig_path.open(encoding="utf-8-sig", newline="") as infile:
        elig_reader = csv.DictReader(infile)
        elig_rows = list(elig_reader)
        elig_sim_cols = sim_columns(elig_reader.fieldnames or [])

    trad_cols = [c for c in elig_sim_cols if not is_resume_eligibility_col(c)]
    resume_cols = [c for c in elig_sim_cols if is_resume_eligibility_col(c)]
    if not trad_cols:
        raise RuntimeError("No traditional eligibility sim columns found")

    trad_stats, used_trad = _aggregate_title_odds(
        trad_cols,
        elig_rows,
        records_rows,
        sim_fpi_by_col,
        sos_by_team_id,
        conf_champions_by_sim,
        h2h_wins_by_col,
        h2h_games_by_col,
        game_rows,
        sim_fpi_by_team_id,
        team_ids,
        fbs_ids,
    )
    resume_stats, used_resume = _aggregate_title_odds(
        resume_cols,
        elig_rows,
        records_rows,
        sim_fpi_by_col,
        sos_by_team_id,
        conf_champions_by_sim,
        h2h_wins_by_col,
        h2h_games_by_col,
        game_rows,
        sim_fpi_by_team_id,
        team_ids,
        fbs_ids,
    )

    if used_trad == 0:
        raise RuntimeError("No simulation columns produced a 12-team playoff field")

    all_names = set(trad_stats) | set(resume_stats)
    summary = []
    for name in sorted(all_names, key=lambda n: (-trad_stats.get(n, {}).get("title_odds_pct", 0), n)):
        trad = trad_stats.get(name, {})
        resume = resume_stats.get(name, {})
        summary.append(
            {
                "team_name": name,
                "conference": trad.get("conference") or resume.get("conference", ""),
                "title_odds_pct": trad.get("title_odds_pct", 0.0),
                "playoff_appearances": trad.get("playoff_appearances", 0),
                "avg_seed_when_in": trad.get("avg_seed_when_in", 0.0),
                "resume_title_odds_pct": resume.get("title_odds_pct", 0.0),
                "resume_playoff_appearances": resume.get("playoff_appearances", 0),
                "resume_avg_seed_when_in": resume.get("avg_seed_when_in", 0.0),
            }
        )

    fieldnames = [
        "team_name",
        "conference",
        "title_odds_pct",
        "playoff_appearances",
        "avg_seed_when_in",
        "resume_title_odds_pct",
        "resume_playoff_appearances",
        "resume_avg_seed_when_in",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)

    print(
        f"Processed {used_trad} traditional and {used_resume} resume playoff fields "
        f"from {len(elig_sim_cols)} eligibility columns"
    )
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
