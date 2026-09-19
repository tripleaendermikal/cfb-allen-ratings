"""Playoff field selection and eligibility CSV generation."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from pipeline.cfb_conf_championship import P4

SIM_RE = re.compile(r"^sim_(\d+)$")
GROUP_OF_6 = {"American", "Pac-12", "Sun Belt", "CUSA", "Mountain West", "MAC"}


def select_playoff_field(
    champions: dict[str, str],
    fpi_by_name: dict[str, float],
    conf_by_id: dict[str, str],
    id_to_name: dict[str, str],
    all_team_ids: list[str],
) -> list[str]:
    selected: list[str] = []
    selected_set: set[str] = set()

    for conf in sorted(P4):
        champ = champions.get(conf)
        if champ and champ not in selected_set:
            selected.append(champ)
            selected_set.add(champ)

    g6_candidates = []
    for conf, champ in champions.items():
        if conf in GROUP_OF_6:
            g6_candidates.append((fpi_by_name.get(id_to_name.get(champ, ""), -999.0), champ))
    if g6_candidates:
        g6_candidates.sort(reverse=True)
        champ = g6_candidates[0][1]
        if champ not in selected_set:
            selected.append(champ)
            selected_set.add(champ)

    remaining = [
        (fpi_by_name.get(id_to_name[team_id], -999.0), team_id)
        for team_id in all_team_ids
        if team_id not in selected_set
    ]
    remaining.sort(key=lambda item: (-item[0], item[1]))
    for _, team_id in remaining:
        if len(selected) >= 12:
            break
        selected.append(team_id)
        selected_set.add(team_id)
    return selected[:12]


def build_playoff_eligibility_csv(
    games_fpi_path: Path,
    conferences_path: Path,
    conf_results: dict,
    output_path: Path,
    pct_output_path: Path,
    id_to_name: dict[str, str],
) -> None:
    from pipeline.cfb_playoff_odds_calc import load_sim_fpi_by_team

    with conferences_path.open(encoding="utf-8-sig", newline="") as handle:
        conf_by_id = {row["team_id"]: row.get("conference", "") for row in csv.DictReader(handle)}
    name_to_conf = {id_to_name[tid]: conf for tid, conf in conf_by_id.items() if tid in id_to_name}
    all_team_ids = sorted(id_to_name.keys())
    fpi_by_col = load_sim_fpi_by_team(games_fpi_path)
    sim_cols = sorted(fpi_by_col.keys(), key=lambda name: int(SIM_RE.match(name).group(1)))

    elig_counts: dict[str, int] = {name: 0 for name in name_to_conf}
    out_rows = []

    for name, conference in sorted(name_to_conf.items()):
        out_rows.append({"team_name": name, "conference": conference})

    for col in sim_cols:
        champions = conf_results["champions"].get(col, {})
        fpi_map = fpi_by_col[col]
        field = select_playoff_field(
            champions,
            fpi_map,
            conf_by_id,
            id_to_name,
            all_team_ids,
        )
        field_names = {id_to_name[tid] for tid in field}
        for row in out_rows:
            row[col] = "1" if row["team_name"] in field_names else "0"
            if row[col] == "1":
                elig_counts[row["team_name"]] += 1

    fieldnames = ["team_name", "conference"] + sim_cols
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    pct_rows = [
        {
            "team_name": name,
            "conference": name_to_conf[name],
            "eligibility_pct": round(elig_counts[name] / len(sim_cols) * 100, 1),
        }
        for name in sorted(name_to_conf)
    ]
    with pct_output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["team_name", "conference", "eligibility_pct"])
        writer.writeheader()
        writer.writerows(pct_rows)


def build_conf_champ_odds_csv(
    conf_results: dict,
    conferences_path: Path,
    output_path: Path,
    id_to_name: dict[str, str],
) -> None:
    sim_cols = sorted(
        conf_results["champions"].keys(),
        key=lambda name: int(SIM_RE.match(name).group(1)),
    )
    n_sims = len(sim_cols)
    with conferences_path.open(encoding="utf-8-sig", newline="") as handle:
        conf_by_id = {row["team_id"]: row.get("conference", "") for row in csv.DictReader(handle)}

    summary: dict[str, dict[str, float | int | str]] = {}
    for tid, name in id_to_name.items():
        summary[tid] = {
            "team_id": tid,
            "team_name": name,
            "conference": conf_by_id.get(tid, ""),
            "conf_champ_appearances": 0,
            "conf_champ_wins": 0,
        }

    for col in sim_cols:
        for conf, champ in conf_results["champions"].get(col, {}).items():
            if champ in summary:
                summary[champ]["conf_champ_wins"] = int(summary[champ]["conf_champ_wins"]) + 1
        for conf, finalists in conf_results["finalists"].get(col, {}).items():
            for tid in finalists:
                if tid in summary:
                    summary[tid]["conf_champ_appearances"] = (
                        int(summary[tid]["conf_champ_appearances"]) + 1
                    )

    out_rows = []
    for tid, row in summary.items():
        apps = int(row["conf_champ_appearances"])
        wins = int(row["conf_champ_wins"])
        out_rows.append(
            {
                "team_id": tid,
                "team_name": row["team_name"],
                "conference": row["conference"],
                "conf_champ_odds_pct": round(wins / n_sims * 100, 1) if n_sims else 0.0,
                "conf_champ_appearances": apps,
                "conf_champ_game_win_pct": round(wins / apps * 100, 2) if apps else 0.0,
            }
        )

    out_rows.sort(key=lambda row: (-float(row["conf_champ_odds_pct"]), row["team_name"]))
    fieldnames = [
        "team_id",
        "team_name",
        "conference",
        "conf_champ_odds_pct",
        "conf_champ_appearances",
        "conf_champ_game_win_pct",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)
