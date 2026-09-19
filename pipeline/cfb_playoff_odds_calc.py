"""Playoff FPI loading and national title odds aggregation."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from pipeline.cfb_playoff_elig import select_playoff_field
from pipeline.cfb_playoff_odds import championship_odds_exact

SIM_RE = re.compile(r"^sim_(\d+)$")


def load_sim_fpi_by_team(path: Path) -> dict[str, dict[str, float]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    sim_cols = sorted(
        [name for name in fieldnames if SIM_RE.match(name or "")],
        key=lambda name: int(SIM_RE.match(name).group(1)),
    )
    by_col: dict[str, dict[str, float]] = {col: {} for col in sim_cols}
    for row in rows:
        name = row.get("team_name", "")
        if not name:
            continue
        for col in sim_cols:
            raw = (row.get(col) or "").strip()
            if raw:
                by_col[col][name] = float(raw)
    return by_col


def build_title_odds_csv(
    games_fpi_path: Path,
    elig_path: Path,
    conferences_path: Path,
    conf_results: dict,
    output_path: Path,
    id_to_name: dict[str, str],
    name_to_id: dict[str, str],
) -> None:
    with elig_path.open(encoding="utf-8-sig", newline="") as handle:
        elig_rows = list(csv.DictReader(handle))
    sim_cols = sorted(
        [name for name in elig_rows[0].keys() if SIM_RE.match(name or "")],
        key=lambda name: int(SIM_RE.match(name).group(1)),
    )
    fpi_by_col = load_sim_fpi_by_team(games_fpi_path)

    title_counts: Counter[str] = Counter()
    playoff_counts: Counter[str] = Counter()
    seed_sums: dict[str, float] = defaultdict(float)
    seed_counts: dict[str, int] = defaultdict(int)

    for col in sim_cols:
        field_ids = [
            name_to_id[row["team_name"]]
            for row in elig_rows
            if row.get(col) == "1" and row["team_name"] in name_to_id
        ]
        if len(field_ids) < 12:
            continue
        fpi_map = fpi_by_col.get(col, {})
        rated = sorted(
            [(tid, fpi_map.get(id_to_name[tid], 0.0)) for tid in field_ids],
            key=lambda item: (-item[1], item[0]),
        )[:12]
        ratings = [0.0] * 12
        for index, (tid, fpi) in enumerate(rated):
            ratings[index] = fpi
            playoff_counts[tid] += 1
            seed_sums[tid] += index + 1
            seed_counts[tid] += 1
        odds = championship_odds_exact(ratings)
        for index, (tid, _) in enumerate(rated):
            title_counts[tid] += odds[index]

    n_sims = len(sim_cols)
    out_rows = []
    conf_by_name = {}
    with conferences_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            conf_by_name[row["team_id"]] = row.get("conference", "")

    for tid, name in id_to_name.items():
        appearances = playoff_counts.get(tid, 0)
        out_rows.append(
            {
                "team_id": tid,
                "team_name": name,
                "conference": conf_by_name.get(tid, ""),
                "title_odds_pct": round(title_counts.get(tid, 0) / n_sims * 100, 2),
                "playoff_appearances": appearances,
                "avg_seed_when_in": round(seed_sums[tid] / seed_counts[tid], 2)
                if seed_counts.get(tid)
                else 0.0,
            }
        )

    out_rows.sort(key=lambda row: (-float(row["title_odds_pct"]), row["team_name"]))
    fieldnames = [
        "team_id",
        "team_name",
        "conference",
        "title_odds_pct",
        "playoff_appearances",
        "avg_seed_when_in",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)
