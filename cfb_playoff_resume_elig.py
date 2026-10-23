"""Playoff selection and seeding using end-of-season resume margins."""

from __future__ import annotations

import re
from typing import Mapping

from cfb_playoff_elig import (
    GROUP_CONFERENCES,
    NOTRE_DAME_NAME,
    PLAYOFF_FIELD_SIZE,
    group_row_indices,
    is_placeholder_team,
    power_four_conf_champion_indices,
    team_sos,
)
from cfb_rating.sim_resume import rank_team_ids_by_resume

RESUME_PLAYOFF_SIM_OFFSET = 1000
_SIM_COL = re.compile(r"^sim_(\d+)$")


def is_resume_eligibility_col(col: str) -> bool:
    match = _SIM_COL.match(col or "")
    return bool(match and int(match.group(1)) > RESUME_PLAYOFF_SIM_OFFSET)


def paired_game_sim_col(resume_elig_col: str) -> str:
    match = _SIM_COL.match(resume_elig_col)
    if not match:
        raise ValueError(f"Not a sim column: {resume_elig_col}")
    n = int(match.group(1)) - RESUME_PLAYOFF_SIM_OFFSET
    if n < 1:
        raise ValueError(f"Not a resume eligibility column: {resume_elig_col}")
    return f"sim_{n:04d}"


def paired_resume_elig_col(game_sim_col: str) -> str:
    match = _SIM_COL.match(game_sim_col)
    if not match:
        raise ValueError(f"Not a sim column: {game_sim_col}")
    n = int(match.group(1)) + RESUME_PLAYOFF_SIM_OFFSET
    return f"sim_{n:04d}"


def _team_id_to_index(source_rows: list[dict]) -> dict[str, int]:
    return {
        (row.get("team_id") or "").strip(): i
        for i, row in enumerate(source_rows)
        if (row.get("team_id") or "").strip()
    }


def resume_rank_indices(
    source_rows: list[dict],
    resume_margins: Mapping[str, float],
) -> list[int]:
    indices = [
        i
        for i, row in enumerate(source_rows)
        if not is_placeholder_team(row)
    ]
    return sorted(
        indices,
        key=lambda i: (
            -float(resume_margins.get(source_rows[i]["team_id"], -999.0)),
            int(source_rows[i]["team_id"])
            if (source_rows[i]["team_id"] or "").isdigit()
            else 0,
            source_rows[i]["team_id"],
        ),
    )


def compute_column_eligibility_resume(
    output_rows: list[dict],
    source_rows: list[dict],
    col: str,
    resume_margins: Mapping[str, float],
    conf_champions_by_sim: dict,
    sos_by_team_id: dict,
    game_sim_col: str,
) -> None:
    for i in range(len(output_rows)):
        output_rows[i][col] = 0

    eligible: set[int] = set()
    for i in power_four_conf_champion_indices(
        source_rows, game_sim_col, conf_champions_by_sim
    ):
        eligible.add(i)
        output_rows[i][col] = 1

    group_indices = group_row_indices(source_rows)
    if group_indices:
        g6_pick = max(
            group_indices,
            key=lambda i: (
                float(resume_margins.get(source_rows[i]["team_id"], -999.0)),
                team_sos(sos_by_team_id, source_rows[i]["team_id"]),
                -int(source_rows[i]["team_id"])
                if (source_rows[i]["team_id"] or "").isdigit()
                else 0,
            ),
        )
        eligible.add(g6_pick)
        output_rows[g6_pick][col] = 1

    ranked = resume_rank_indices(source_rows, resume_margins)
    nd_index = next(
        (
            i
            for i, row in enumerate(source_rows)
            if (row.get("team_name") or "").strip() == NOTRE_DAME_NAME
        ),
        None,
    )
    if nd_index is not None and nd_index in ranked:
        nd_rank = ranked.index(nd_index)
        if nd_rank < 12 and nd_index not in eligible:
            eligible.add(nd_index)
            output_rows[nd_index][col] = 1

    for i in ranked:
        if len(eligible) >= PLAYOFF_FIELD_SIZE:
            break
        if source_rows[i]["conference"] in GROUP_CONFERENCES:
            continue
        if i in eligible:
            continue
        eligible.add(i)
        output_rows[i][col] = 1


def seed_playoff_indices_resume_col(
    source_rows: list[dict],
    elig_by_team_id: dict[str, int],
    resume_margins: Mapping[str, float],
) -> list[int] | None:
    eligible = [
        i
        for i, src in enumerate(source_rows)
        if elig_by_team_id.get(src["team_id"], 0) == 1
        and not is_placeholder_team(src)
    ]
    if len(eligible) != PLAYOFF_FIELD_SIZE:
        return None

    g6_indices = [
        i for i in eligible if source_rows[i]["conference"] in GROUP_CONFERENCES
    ]
    if len(g6_indices) != 1:
        return None
    g6_i = g6_indices[0]
    eligible_non_g6 = [i for i in eligible if i != g6_i]

    ranked = resume_rank_indices(source_rows, resume_margins)
    seed_indices: list[int] = []
    for i in ranked:
        if i in eligible_non_g6:
            seed_indices.append(i)
    for i in eligible:
        if i != g6_i and i not in seed_indices:
            seed_indices.append(i)
    if len(seed_indices) != PLAYOFF_FIELD_SIZE - 1:
        return None
    seed_indices.append(g6_i)
    return seed_indices


def seed_playoff_field_resume_col(
    source_rows: list[dict],
    elig_by_team_id: dict[str, int],
    sim_fpi_for_col: dict[str, float],
    resume_margins: Mapping[str, float],
) -> list[tuple[str, str, float]] | None:
    indices = seed_playoff_indices_resume_col(
        source_rows, elig_by_team_id, resume_margins
    )
    if not indices:
        return None
    seeded: list[tuple[str, str, float]] = []
    for i in indices:
        src = source_rows[i]
        name = (src.get("team_name") or "").strip()
        if not name or name == "TBD" or name not in sim_fpi_for_col:
            return None
        seeded.append((name, src.get("conference", ""), sim_fpi_for_col[name]))
    return seeded
