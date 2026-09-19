"""Conference championship results from per-simulation game outcomes."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

SIM_RE = re.compile(r"^sim_(\d+)$")
P4 = {"SEC", "Big Ten", "ACC", "Big 12"}


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _sim_columns(fieldnames: list[str]) -> list[str]:
    return sorted(
        [name for name in fieldnames if SIM_RE.match(name or "")],
        key=lambda name: int(SIM_RE.match(name).group(1)),
    )


def _load_conferences(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["team_id"]: row.get("conference", "") for row in csv.DictReader(handle)}


def compute_conf_results_by_sim(
    games_sim_path: Path,
    games_fpi_path: Path,
    conferences_path: Path,
) -> dict:
    _, sim_rows = _load_rows(games_sim_path)
    sim_cols = _sim_columns([key for row in sim_rows for key in row])
    conf_by_id = _load_conferences(conferences_path)

    conf_wins: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    conf_losses: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )

    for row in sim_rows:
        tid = row["team_id"]
        oid = row["opponent_id"]
        team_conf = conf_by_id.get(tid, "")
        opp_conf = conf_by_id.get(oid, "")
        if not team_conf or team_conf != opp_conf:
            continue
        for col in sim_cols:
            if row.get(col) == "1":
                conf_wins[col][team_conf][tid] += 1
                conf_losses[col][team_conf][oid] += 1
            elif row.get(col) == "0":
                conf_losses[col][team_conf][tid] += 1
                conf_wins[col][team_conf][oid] += 1

    champions: dict[str, dict[str, str]] = {}
    finalists: dict[str, dict[str, list[str]]] = {}
    appearances: dict[str, int] = defaultdict(int)
    champ_wins: dict[str, int] = defaultdict(int)

    for col in sim_cols:
        champions[col] = {}
        finalists[col] = {}
        for conf, standings in conf_wins[col].items():
            ranked = sorted(
                standings.keys(),
                key=lambda team_id: (
                    -standings[team_id],
                    conf_losses[col][conf].get(team_id, 0),
                    team_id,
                ),
            )
            if not ranked:
                continue
            top = ranked[:2]
            finalists[col][conf] = top
            for team_id in top:
                appearances[team_id] += 1
            champion = top[0]
            if len(top) == 2 and standings[top[0]] == standings[top[1]]:
                champion = top[0]
            champions[col][conf] = champion
            champ_wins[champion] += 1

    return {
        "champions": champions,
        "finalists": finalists,
        "appearances": dict(appearances),
        "champ_wins": dict(champ_wins),
    }
