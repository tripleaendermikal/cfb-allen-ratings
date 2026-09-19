#!/usr/bin/env python3
"""Verify in-season sim FPI draws are centered on Overall margins from rankings."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from add_fpi_sim_columns import infer_through_week
from cfb_in_season_sim import IN_SEASON_PREFIX, load_fbs_ids

SIM_RE = re.compile(r"^sim_\d+$")
DEFAULT_TOLERANCE = 1.0


def sim_columns(fieldnames: list[str]) -> list[str]:
    return sorted(
        [c for c in fieldnames if SIM_RE.match(c or "")],
        key=lambda c: int(c.split("_")[1]),
    )


def mean_sim_fpi_by_team(games_fpi_path: Path) -> dict[str, float]:
    with games_fpi_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        sim_cols = sim_columns(list(reader.fieldnames or []))
        if not sim_cols:
            raise ValueError(f"No sim columns in {games_fpi_path}")
        means: dict[str, float] = {}
        for row in reader:
            tid = (row.get("team_id") or "").strip()
            if not tid or tid in means:
                continue
            vals = []
            for col in sim_cols:
                raw = (row.get(col) or "").strip()
                if raw:
                    vals.append(float(raw))
            if vals:
                means[tid] = sum(vals) / len(vals)
    return means


def infer_current_week(games_fpi_path: Path) -> int:
    with games_fpi_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fbs_ids = load_fbs_ids()
    return infer_through_week(rows, fbs_ids) or 1


def overall_by_team(rankings_path: Path, week: int | None) -> dict[str, float]:
    with rankings_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if week is None:
        raise ValueError("week is required")
    out: dict[str, float] = {}
    for row in rows:
        if int(row["week"]) != week:
            continue
        tid = (row.get("team_id") or "").strip()
        raw = (row.get("overall_margin") or "").strip()
        if tid and raw:
            out[tid] = float(raw)
    return out


def validate(
    games_fpi_path: Path,
    rankings_path: Path,
    *,
    week: int | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> list[str]:
    sim_means = mean_sim_fpi_by_team(games_fpi_path)
    overall = overall_by_team(rankings_path, week)
    errors: list[str] = []
    for tid, expected in sorted(overall.items(), key=lambda item: item[0]):
        actual = sim_means.get(tid)
        if actual is None:
            errors.append(f"team_id={tid}: missing sim draws")
            continue
        delta = abs(actual - expected)
        if delta > tolerance:
            errors.append(
                f"team_id={tid}: mean sim FPI {actual:.3f} vs Overall {expected:.3f} "
                f"(delta {delta:.3f} > {tolerance})"
            )
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--games-fpi",
        type=Path,
        default=Path(__file__).resolve().parent
        / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi.csv",
    )
    parser.add_argument(
        "--rankings",
        type=Path,
        default=Path(__file__).resolve().parent
        / f"{IN_SEASON_PREFIX}_weekly_rankings.csv",
    )
    parser.add_argument("--week", type=int, default=None)
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help="Max allowed |mean sim FPI - Overall| per team (default: 0.75)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.games_fpi.is_file():
        print(f"Games FPI file not found: {args.games_fpi}", file=sys.stderr)
        return 1
    if not args.rankings.is_file():
        print(f"Rankings file not found: {args.rankings}", file=sys.stderr)
        return 1

    week = args.week
    if week is None:
        week = infer_current_week(args.games_fpi)

    errors = validate(
        args.games_fpi,
        args.rankings,
        week=week,
        tolerance=args.tolerance,
    )
    if errors:
        print("In-season sim Overall validation failed:", file=sys.stderr)
        for err in errors[:20]:
            print(f"  {err}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more", file=sys.stderr)
        return 1

    week = args.week
    if week is None:
        week = infer_current_week(args.games_fpi)
    print(
        f"OK: sim FPI means match Overall margins for week {week} "
        f"(tolerance {args.tolerance})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
