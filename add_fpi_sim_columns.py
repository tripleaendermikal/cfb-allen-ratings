#!/usr/bin/env python3
"""
Add sim_0001..sim_N columns to cfb_2026_fbs_games_with_fpi.csv.

Each column is one synthetic season. Per team_id, draw one adjustment ~ N(0, sigma)
used for every game that team plays in that column. Cell value is
clamp(team_fpi + adjustment, fpi_min, fpi_max).

Group-of-6 conferences (Pac-12, American, Mountain West, Sun Belt, CUSA, MAC)
use a lower ceiling of 27 instead of 40.
"""

from __future__ import annotations

from cfb_paths import data_root

import argparse
import csv
import random
import sys
from pathlib import Path

from cfb_in_season_sim import (
    IN_SEASON_PREFIX,
    count_completed_fbs_games,
    is_completed,
    is_fbs_vs_fbs_row,
    load_fbs_ids,
    per_team_sigma,
)
from cfb_rating.in_season import (
    compute_overall_margins_snapshot,
    load_preseason_margins,
)
from cfb_rating.season_data import load_fbs_team_ids, load_games_for_in_season_rankings

DEFAULT_NUM_SIMS = 1000
DEFAULT_SIGMA = 7.3
FPI_MIN = -40.0
FPI_MAX = 40.0
FPI_MAX_GROUP_OF_6 = 27.0
GROUP_CONFERENCES = {
    "American",
    "Pac-12",
    "Sun Belt",
    "CUSA",
    "Mountain West",
    "MAC",
}


def clamp(x: float, fpi_max: float) -> float:
    return max(FPI_MIN, min(fpi_max, x))


def load_conference_lookup(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    by_id: dict[str, str] = {}
    by_name: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tid = (row.get("team_id") or "").strip()
            name = (row.get("team_name") or "").strip()
            conf = (row.get("conference") or "").strip()
            if tid:
                by_id[tid] = conf
            if name:
                by_name[name] = conf
    return by_id, by_name


def resolve_conference(
    team_id: str,
    team_name: str,
    by_id: dict[str, str],
    by_name: dict[str, str],
) -> str:
    return by_id.get(team_id) or by_name.get(team_name) or ""


def fpi_max_for_team(conference: str) -> float:
    if conference in GROUP_CONFERENCES:
        return FPI_MAX_GROUP_OF_6
    return FPI_MAX


def sim_column_names(n: int) -> list[str]:
    w = max(4, len(str(n)))
    return [f"sim_{i:0{w}d}" for i in range(1, n + 1)]


def build_base_fpi(rows: list[dict[str, str]]) -> dict[str, float]:
    base: dict[str, float] = {}
    names: dict[str, str] = {}
    for row in rows:
        tid = (row.get("team_id") or "").strip()
        if not tid:
            continue
        if tid not in names and row.get("team_name"):
            names[tid] = row["team_name"]
        if tid in base:
            continue
        raw = (row.get("team_fpi") or "").strip()
        try:
            base[tid] = float(raw) if raw else 0.0
        except ValueError:
            base[tid] = 0.0
    return base, names


def infer_through_week(rows: list[dict[str, str]], fbs_ids: set[str]) -> int:
    """Latest week with a completed FBS-vs-FBS game (0 if none)."""
    weeks: list[int] = []
    for row in rows:
        if not is_completed(row) or not is_fbs_vs_fbs_row(row, fbs_ids):
            continue
        try:
            week = int((row.get("week") or "").strip() or "0")
        except ValueError:
            continue
        if week > 0:
            weeks.append(week)
    return max(weeks) if weeks else 0


def load_overall_from_rankings_csv(
    rankings_csv: Path,
    week: int | None = None,
) -> dict[str, float]:
    """Overall margins from weekly rankings export (same values shown on site)."""
    with rankings_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {}
    if week is None:
        week = max(int(row["week"]) for row in rows if (row.get("week") or "").isdigit())
    overall: dict[str, float] = {}
    for row in rows:
        if int(row["week"]) != week:
            continue
        tid = (row.get("team_id") or "").strip()
        raw = (row.get("overall_margin") or "").strip()
        if tid and raw:
            overall[tid] = float(raw)
    return overall


def load_overall_base_fpi(
    input_csv: Path,
    rows: list[dict[str, str]],
) -> dict[str, float]:
    """Overall margins at the current completed-game week."""
    fbs_ids = load_fbs_ids()
    through_week = infer_through_week(rows, fbs_ids)
    games = load_games_for_in_season_rankings(input_csv, fbs_only=True)
    team_info = load_fbs_team_ids()
    team_ids = sorted(team_info.keys())
    preseason_margins = load_preseason_margins()
    return compute_overall_margins_snapshot(
        games,
        through_week,
        team_ids,
        preseason_margins,
        team_info=team_info,
    )


def apply_overall_to_rows(
    rows: list[dict[str, str]],
    overall_fpi: dict[str, float],
) -> int:
    """Patch team_fpi/opponent_fpi to Overall margins. Returns teams changed vs preseason."""
    preseason_fpi, _ = build_base_fpi(rows)
    changed_teams: set[str] = set()
    for row in rows:
        tid = (row.get("team_id") or "").strip()
        oid = (row.get("opponent_id") or "").strip()
        if tid and tid in overall_fpi:
            row["team_fpi"] = str(round(overall_fpi[tid], 3))
            pre = preseason_fpi.get(tid)
            if pre is not None and abs(overall_fpi[tid] - pre) > 0.01:
                changed_teams.add(tid)
        if oid and oid in overall_fpi:
            row["opponent_fpi"] = str(round(overall_fpi[oid], 3))
    return len(changed_teams)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_csv",
        nargs="?",
        type=Path,
        default=data_root() / "cfb_2026_fbs_games_with_fpi.csv",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: overwrite input)",
    )
    parser.add_argument(
        "-n",
        "--simulations",
        type=int,
        default=DEFAULT_NUM_SIMS,
        metavar="N",
    )
    parser.add_argument(
        "--sigma",
        type=float,
        default=DEFAULT_SIGMA,
        help="Std dev of per-team adjustment (default: 7.3)",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--conferences",
        type=Path,
        default=None,
        help="Team conference CSV (default: espn_cfb_teams_conferences.csv)",
    )
    parser.add_argument(
        "--in-season",
        action="store_true",
        help="Shrink per-team sigma by completed FBS-vs-FBS games played",
    )
    parser.add_argument(
        "--overall-rankings",
        type=Path,
        default=None,
        help="Weekly rankings CSV; use overall_margin as sim FPI mu (in-season)",
    )
    parser.add_argument(
        "--overall-week",
        type=int,
        default=None,
        help="Rankings week for --overall-rankings (default: latest in file)",
    )
    args = parser.parse_args()

    if args.simulations < 1:
        print("--simulations must be >= 1", file=sys.stderr)
        return 1
    if args.sigma <= 0:
        print("--sigma must be positive", file=sys.stderr)
        return 1

    inp = args.input_csv
    if not inp.is_file():
        print(f"Input not found: {inp}", file=sys.stderr)
        return 1

    out_path = args.output
    if out_path is None:
        if args.in_season:
            out_path = inp.parent / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi.csv"
        else:
            out_path = inp
    rng = random.Random(args.seed)
    n_sims = args.simulations
    sim_cols = sim_column_names(n_sims)

    with inp.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        base_fields = [
            c
            for c in (reader.fieldnames or [])
            if not c.startswith("sim_") and not c.startswith("margin_")
        ]
        rows = list(reader)

    base_fpi, team_names = build_base_fpi(rows)
    team_ids = sorted(base_fpi.keys(), key=lambda x: int(x) if x.lstrip("-").isdigit() else x)

    conf_path = args.conferences or Path(__file__).resolve().parent / "espn_cfb_teams_conferences.csv"
    by_id: dict[str, str] = {}
    by_name: dict[str, str] = {}
    if conf_path.is_file():
        by_id, by_name = load_conference_lookup(conf_path)
    else:
        print(f"Warning: conference file not found: {conf_path}", file=sys.stderr)

    team_fpi_max = {
        tid: fpi_max_for_team(resolve_conference(tid, team_names.get(tid, ""), by_id, by_name))
        for tid in team_ids
    }
    group_count = sum(1 for tid in team_ids if team_fpi_max[tid] == FPI_MAX_GROUP_OF_6)

    games_played: dict[str, int] = {}
    overall_fpi: dict[str, float] = {}
    if args.in_season:
        games_played = count_completed_fbs_games(rows)
        if args.overall_rankings:
            if not args.overall_rankings.is_file():
                print(f"Rankings file not found: {args.overall_rankings}", file=sys.stderr)
                return 1
            overall_week = args.overall_week
            if overall_week is None:
                fbs_ids = load_fbs_ids()
                overall_week = infer_through_week(rows, fbs_ids) or 1
            overall_fpi = load_overall_from_rankings_csv(
                args.overall_rankings, overall_week
            )
            print(
                f"Using Overall margins from {args.overall_rankings.name} "
                f"(week {overall_week}, {len(overall_fpi)} teams)"
            )
        else:
            overall_fpi = load_overall_base_fpi(inp, rows)
        for tid in team_ids:
            if tid in overall_fpi:
                base_fpi[tid] = overall_fpi[tid]

    # team_id -> list of n_sims adjusted FPI values
    adjusted: dict[str, list[float]] = {}
    sigma_by_team: dict[str, float] = {}
    for tid in team_ids:
        mu = base_fpi[tid]
        cap = team_fpi_max[tid]
        sigma_t = (
            per_team_sigma(args.sigma, games_played.get(tid, 0))
            if args.in_season
            else args.sigma
        )
        sigma_by_team[tid] = sigma_t
        adjusted[tid] = [
            round(clamp(mu + rng.gauss(0.0, sigma_t), cap), 3) for _ in range(n_sims)
        ]

    out_fields = base_fields + sim_cols
    if args.in_season and overall_fpi:
        overall_changed = apply_overall_to_rows(rows, overall_fpi)
    else:
        overall_changed = 0

    out_rows: list[dict[str, str]] = []
    for row in rows:
        r = {k: row[k] for k in base_fields if k in row}
        tid = (row.get("team_id") or "").strip()
        series = adjusted.get(tid)
        if series is not None:
            for name, val in zip(sim_cols, series):
                r[name] = val
        else:
            for name in sim_cols:
                r[name] = ""
        out_rows.append(r)

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(out_rows)

    print(
        f"Wrote {len(out_rows)} rows, {len(team_ids)} teams, "
        f"{n_sims} sim columns to {out_path}"
    )
    print(
        f"Adjustment: N(0, {args.sigma}^2); clamp [{FPI_MIN}, {FPI_MAX}] "
        f"or [{FPI_MIN}, {FPI_MAX_GROUP_OF_6}] for Group-of-6 ({group_count} teams)"
    )
    if args.in_season:
        at_zero = sum(1 for tid in team_ids if games_played.get(tid, 0) == 0)
        at_one = sum(1 for tid in team_ids if games_played.get(tid, 0) == 1)
        at_two_plus = len(team_ids) - at_zero - at_one
        sigmas = list(sigma_by_team.values())
        print(
            f"In-season sigma: teams at 0 games={at_zero}, 1 game={at_one}, "
            f"2+ games={at_two_plus}; "
            f"sigma_eff min={min(sigmas):.3f} max={max(sigmas):.3f}"
        )
        through_week = infer_through_week(rows, load_fbs_ids())
        print(f"In-season FPI base: Overall margin at week {through_week}")
        print(
            f"In-season static FPI: patched team_fpi/opponent_fpi; "
            f"{overall_changed} teams differ from preseason by >0.01"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
