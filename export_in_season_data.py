#!/usr/bin/env python3
"""Export in-season CFB data to JSON for the CFB Allen Ratings viewer."""

from __future__ import annotations

import csv
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CFB_DATA_ROOT", str(APP_DIR.parent)))
DATA_DIR = APP_DIR / "data"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import export_sim_data as esd  # noqa: E402
from cfb_in_season_sim import is_completed, parse_score  # noqa: E402

IN_SEASON_PREFIX = "cfb_2026_in_season"

SOURCES = {
    "champ_odds": ROOT / f"{IN_SEASON_PREFIX}_FBS_playoff_champ_odds_fpi_seed.csv",
    "conf_champ_odds": ROOT / f"{IN_SEASON_PREFIX}_FBS_conf_champ_odds.csv",
    "elig": ROOT / f"{IN_SEASON_PREFIX}_FBS_playoff_elig_v2.csv",
    "records": ROOT / f"{IN_SEASON_PREFIX}_fbs_team_sim_records_v2.csv",
    "games_sim": ROOT / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi_simulated.csv",
    "games_fpi": ROOT / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi.csv",
    "games_base": ROOT / "cfb_2026_fbs_games_with_fpi.csv",
    "rankings": ROOT / f"{IN_SEASON_PREFIX}_weekly_rankings.csv",
    "conferences": ROOT / "espn_cfb_teams_conferences.csv",
}


def compute_elig_pct_rows(
    elig_rows: list[dict[str, str]], sim_cols: list[str]
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    n = len(sim_cols)
    for row in elig_rows:
        if n == 0:
            pct = 0.0
        else:
            pct = sum(1 for col in sim_cols if (row.get(col) or "").strip() == "1")
            pct = round(pct / n * 100, 1)
        out.append(
            {
                "team_name": row.get("team_name", ""),
                "conference": row.get("conference", ""),
                "eligibility_pct": str(pct),
            }
        )
    return out


def build_team_records(game_rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    """Overall W-L from completed games on the base schedule (all opponents)."""
    from cfb_in_season_sim import actual_team_win

    records: dict[str, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0})
    for row in game_rows:
        if not is_completed(row):
            continue
        team_id = (row.get("team_id") or "").strip()
        if not team_id:
            continue
        win = actual_team_win(row)
        if win is None:
            continue
        if win == "1":
            records[team_id]["wins"] += 1
        else:
            records[team_id]["losses"] += 1
    return dict(records)


def load_weekly_rankings(path: Path) -> dict:
    if not path.is_file():
        return {"current_week": 0, "weeks": [], "by_week": {}}

    by_week: dict[int, list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            week = int(row["week"])
            by_week[week].append(
                {
                    "team_id": row["team_id"],
                    "team_name": row.get("team_name", ""),
                    "conference": row.get("conference", ""),
                    "rank": int(row["rank"]),
                    "blended_margin": float(row["blended_margin"]),
                    "algorithm_margin": float(row["algorithm_margin"]),
                    "preseason_margin": float(row["preseason_margin"])
                    if (row.get("preseason_margin") or "").strip()
                    else None,
                    "preseason_weight": float(row.get("preseason_weight") or 0),
                    "fbs_games_played": int(row.get("fbs_games_played") or 0),
                    "algorithm_rating": float(row.get("algorithm_rating") or 0),
                }
            )

    weeks = sorted(by_week.keys())
    current_week = max(weeks) if weeks else 0

    # rank movement: prior_week_rank - current_rank (positive = moved up)
    rank_history: dict[str, dict[int, int]] = defaultdict(dict)
    for week in weeks:
        for entry in by_week[week]:
            rank_history[entry["team_id"]][week] = entry["rank"]

    for week in weeks:
        prior_week = week - 1
        for entry in by_week[week]:
            prior_rank = rank_history[entry["team_id"]].get(prior_week)
            if prior_rank is not None:
                entry["rank_delta"] = prior_rank - entry["rank"]
            else:
                entry["rank_delta"] = 0

    return {
        "current_week": current_week,
        "weeks": weeks,
        "by_week": {str(w): by_week[w] for w in weeks},
    }


def merge_rankings_and_records(
    leaderboard: list[dict],
    rankings: dict,
    records: dict[str, dict[str, int]],
    week: int,
) -> None:
    week_key = str(week)
    ranking_rows = {r["team_id"]: r for r in rankings.get("by_week", {}).get(week_key, [])}
    for row in leaderboard:
        tid = row.get("team_id")
        if not tid:
            continue
        rank_row = ranking_rows.get(tid, {})
        row["rank"] = rank_row.get("rank")
        row["blended_margin"] = rank_row.get("blended_margin")
        row["algorithm_margin"] = rank_row.get("algorithm_margin")
        row["rank_delta"] = rank_row.get("rank_delta", 0)
        row["fbs_games_played"] = rank_row.get("fbs_games_played", 0)
        rec = records.get(tid, {"wins": 0, "losses": 0})
        row["wins"] = rec["wins"]
        row["losses"] = rec["losses"]
        row["record"] = f"{rec['wins']}-{rec['losses']}"
        if row.get("avg_wins") is not None:
            row["forecasted_wins"] = round(float(row["avg_wins"]), 2)


def enrich_schedule_scores(
    schedule: list[dict], game_rows: list[dict[str, str]]
) -> None:
    scores_by_game: dict[str, dict] = {}
    for row in game_rows:
        if not is_completed(row):
            continue
        gid = (row.get("game_id") or "").strip()
        if not gid:
            continue
        team_score = parse_score(row.get("team_score"))
        opp_score = parse_score(row.get("opponent_score"))
        if team_score is None or opp_score is None:
            continue
        if row.get("home_away") == "home":
            scores_by_game[gid] = {
                "home_score": int(team_score),
                "away_score": int(opp_score),
                "completed": True,
            }
        elif row.get("home_away") == "away" and gid not in scores_by_game:
            scores_by_game[gid] = {
                "home_score": int(opp_score),
                "away_score": int(team_score),
                "completed": True,
            }

    for row in schedule:
        gid = row.get("game_id", "")
        info = scores_by_game.get(gid)
        if info:
            row["completed"] = True
            row["home_score"] = info["home_score"]
            row["away_score"] = info["away_score"]
            if row.get("home_away") == "home":
                row["team_score"] = info["home_score"]
                row["opponent_score"] = info["away_score"]
            else:
                row["team_score"] = info["away_score"]
                row["opponent_score"] = info["home_score"]
        else:
            row["completed"] = False


def enrich_games_scores(games: dict[str, dict], schedule: list[dict]) -> None:
    score_lookup = {
        g["game_id"]: g
        for g in schedule
        if g.get("completed")
    }
    for gid, game in games.items():
        src = score_lookup.get(gid)
        if not src:
            continue
        game["completed"] = True
        game["home_score"] = src.get("home_score")
        game["away_score"] = src.get("away_score")


def main() -> int:
    esd.SOURCES = SOURCES  # type: ignore[misc]

    for key, path in SOURCES.items():
        if key in ("games_base", "rankings"):
            continue
        if not path.is_file():
            print(f"Missing source file ({key}): {path}", file=sys.stderr)
            return 1

    _, records_rows = esd.read_csv(SOURCES["records"])
    sim_cols = esd.sim_columns(list(records_rows[0].keys()) if records_rows else [])
    n_sims = len(sim_cols)

    teams = esd.build_teams(records_rows, sim_cols)
    try:
        branding = esd.fetch_espn_team_branding()
        esd.enrich_teams_branding(teams, branding)
        print(f"Merged ESPN branding for {len(branding)} teams")
    except Exception as exc:
        print(f"Warning: could not fetch ESPN team branding: {exc}", file=sys.stderr)
        esd.enrich_teams_branding(teams, {})

    name_to_id = {t["team_name"]: t["team_id"] for t in teams}
    id_to_name = {t["team_id"]: t["team_name"] for t in teams}

    _, champ_rows = esd.read_csv(SOURCES["champ_odds"])
    _, elig_rows = esd.read_csv(SOURCES["elig"])
    elig_pct_rows = compute_elig_pct_rows(elig_rows, sim_cols)
    _, conf_champ_rows = esd.read_csv(SOURCES["conf_champ_odds"])

    leaderboard = esd.build_leaderboard(champ_rows, elig_pct_rows)
    esd.merge_team_ids(leaderboard, teams)
    esd.merge_conf_champ_odds(leaderboard, conf_champ_rows)
    conf_by_id = {t["team_id"]: t["conference"] for t in teams}

    _, games_fpi_rows = esd.read_csv(SOURCES["games_fpi"])
    baseline_by_id = esd.build_baseline_fpi(games_fpi_rows)
    esd.enrich_leaderboard_fpi(leaderboard, baseline_by_id, conf_by_id)

    rankings = load_weekly_rankings(SOURCES["rankings"])
    records: dict[str, dict[str, int]] = {}
    if SOURCES["games_base"].is_file():
        _, base_game_rows = esd.read_csv(SOURCES["games_base"])
        records = build_team_records(base_game_rows)

    current_week = rankings.get("current_week") or 0
    if current_week:
        merge_rankings_and_records(leaderboard, rankings, records, current_week)

    leaderboard = [r for r in leaderboard if esd.is_fbs_conference(r.get("conference", ""))]
    leaderboard.sort(
        key=lambda r: (
            r.get("rank") is None,
            r.get("rank") if r.get("rank") is not None else 9999,
        )
    )

    eligibility = esd.build_eligibility(elig_rows, sim_cols, name_to_id)
    field_analysis = esd.build_field_analysis(
        eligibility["fields"], id_to_name, n_sims, conf_by_id
    )

    _, game_rows = esd.read_csv(SOURCES["games_sim"])
    margin_lists = esd.load_margin_lists(SOURCES["games_fpi"], sim_cols)
    margin_map = esd.load_avg_margins(margin_lists)
    full_schedule, schedule = esd.build_schedule(game_rows, sim_cols, margin_map, conf_by_id)
    if SOURCES["games_base"].is_file():
        _, base_rows = esd.read_csv(SOURCES["games_base"])
        enrich_schedule_scores(schedule, base_rows)

    esd.merge_team_sos(teams, leaderboard, esd.build_team_sos(full_schedule))
    conferences = esd.build_conferences(teams, leaderboard, eligibility["fields"], n_sims)
    games = esd.build_games(schedule, conf_by_id, margin_lists)
    enrich_games_scores(games, schedule)
    game_slugs = esd.build_game_slugs(games)
    conf_championship = esd.build_conf_championship(sim_cols, id_to_name)
    brackets = esd.build_brackets(eligibility, sim_cols, name_to_id, id_to_name, leaderboard)
    conference_deep = esd.build_conference_deep(
        conferences,
        conf_championship["champions_by_sim"],
        conf_championship["finalists_by_sim"],
        eligibility["fields"],
        id_to_name,
        n_sims,
    )

    season_year = 2026
    if game_rows and game_rows[0].get("season_year"):
        try:
            season_year = int(game_rows[0]["season_year"])
        except ValueError:
            pass

    team_summaries = esd.build_team_summaries(
        teams, leaderboard, conferences, games, n_sims, season_year
    )
    conference_summaries = esd.build_conference_summaries(
        conferences, conference_deep, n_sims, season_year
    )

    brackets_summary = {
        "sim_count": n_sims,
        "r1_pairings": brackets["r1_pairings"],
        "team_summary": brackets["team_summary"],
    }
    conf_championship_summary = {
        "sim_count": conf_championship["sim_count"],
        "conferences": conf_championship["conferences"],
        "team_summary": conf_championship["team_summary"],
    }
    eligibility_slim = {"sim_count": n_sims}

    meta = {
        "season_year": season_year,
        "mode": "in_season",
        "current_week": current_week,
        "sim_count": n_sims,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "sources": {k: str(v) for k, v in SOURCES.items()},
        "team_count": len(teams),
        "game_count": len(schedule),
        "fpi_sigma": esd.DEFAULT_SIGMA,
        "fpi_ci_method": "analytical_90",
        "app_title": "CFB Allen Ratings",
    }

    sizes = {}
    payloads = [
        ("meta.json", meta),
        ("leaderboard.json", leaderboard),
        ("rankings.json", rankings),
        ("records.json", records),
        ("teams.json", teams),
        ("eligibility.json", eligibility_slim),
        ("field_analysis.json", field_analysis),
        ("schedule.json", schedule),
        ("conferences.json", conferences),
        ("conference_deep.json", conference_deep),
        ("games.json", games),
        ("game_slugs.json", game_slugs),
        ("brackets_summary.json", brackets_summary),
        ("conf_championship_summary.json", conf_championship_summary),
        ("team_summaries.json", team_summaries),
        ("conference_summaries.json", conference_summaries),
    ]
    for name, payload in payloads:
        sizes[name] = esd.write_json(DATA_DIR / name, payload)

    sim_bytes = esd.write_sim_files(
        DATA_DIR,
        n_sims,
        eligibility["fields"],
        brackets["by_sim"],
        conf_championship["champions_by_sim"],
        conf_championship["finalists_by_sim"],
    )
    sizes["sim/*.json"] = sim_bytes

    print(f"Exported to {DATA_DIR}")
    print(f"  Teams: {len(teams)}, Sims: {n_sims}, Games: {len(schedule)}")
    print(f"  Rankings week: {current_week}")
    print(f"  Unique playoff fields: {field_analysis['unique_field_count']}")
    for name, nbytes in sizes.items():
        print(f"  {name}: {nbytes / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
