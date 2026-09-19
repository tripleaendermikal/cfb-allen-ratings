#!/usr/bin/env python3
"""Aggregate per-simulation regular-season wins from simulated games."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

from pipeline._paths import CONF_CSV, GAMES_SIM, TEAM_RECORDS

SIM_RE = re.compile(r"^sim_(\d+)$")


def load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def load_conferences(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["team_id"]: row.get("conference", "") for row in csv.DictReader(handle)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("games_sim", nargs="?", type=Path, default=GAMES_SIM)
    parser.add_argument("-o", "--output", type=Path, default=TEAM_RECORDS)
    parser.add_argument("--conferences", type=Path, default=CONF_CSV)
    args = parser.parse_args()

    fieldnames, rows = load_rows(args.games_sim)
    sim_cols = sorted(
        [name for name in fieldnames if SIM_RE.match(name or "")],
        key=lambda name: int(SIM_RE.match(name).group(1)),
    )
    if not sim_cols:
        print("No sim columns found", file=sys.stderr)
        return 1

    conf_by_id = load_conferences(args.conferences)
    wins: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    names: dict[str, str] = {}

    for row in rows:
        tid = row["team_id"]
        names[tid] = row.get("team_name", tid)
        for col in sim_cols:
            if row.get(col) == "1":
                wins[tid][col] += 1

    out_fields = ["team_id", "team_name", "conference"] + sim_cols
    out_rows = []
    for tid in sorted(names):
        out_rows.append(
            {
                "team_id": tid,
                "team_name": names[tid],
                "conference": conf_by_id.get(tid, ""),
                **{col: str(wins[tid].get(col, 0)) for col in sim_cols},
            }
        )

    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote {len(out_rows)} team rows to {args.output}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())
