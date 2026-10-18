#!/usr/bin/env python3
"""Compute FBS playoff eligibility flags from team simulation win totals.

Selection (12-team field per simulation):
  1. Power Four conference champions autobid
  2. Group of 6 team with highest playoff points autobid
  3. Rank remaining teams: wins, then SOS within win tier, then H2H sweeps
     (skip H2H if a 3+ team sweep cycle exists in the tier), then conf-champ boost
  4. Top 7 ranked teams not already in the field
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

SEC_BIG_TEN = {"SEC", "Big Ten"}
ACC_BIG_12 = {"ACC", "Big 12"}
POWER_FOUR = SEC_BIG_TEN | ACC_BIG_12
POWER_FOUR_CONFERENCES = ("SEC", "Big Ten", "ACC", "Big 12")
NOTRE_DAME_NAME = "Notre Dame Fighting Irish"
GROUP_CONFERENCES = {
    "American",
    "Pac-12",
    "Sun Belt",
    "CUSA",
    "Mountain West",
    "MAC",
}

AT_LARGE_BIDS = 7
PLAYOFF_FIELD_SIZE = 12

SIM_COL_PATTERN = re.compile(r"^sim_\d+$")
PLACEHOLDER_TEAM_IDS = frozenset({"-1", "-2"})


def is_placeholder_team(row: dict) -> bool:
    tid = (row.get("team_id") or "").strip()
    name = (row.get("team_name") or "").strip().upper()
    if tid in PLACEHOLDER_TEAM_IDS:
        return True
    return name == "TBD"


def sim_columns(fieldnames):
    return [col for col in fieldnames if SIM_COL_PATTERN.match(col)]


def home_field_adjustment(neutral_site, home_away):
    n = str(neutral_site or "").strip().lower()
    if n in ("true", "1", "yes"):
        return 0.0
    if home_away == "home":
        return 3.0
    if home_away == "away":
        return -3.0
    return 0.0


def load_sos_by_team_id(path):
    """team_id -> static SOS from schedule (opponent FPI adjusted for site)."""
    from pac12_week13 import FLEX_FLAG_COL, FLEX_FLAG_VALUE, PAC12_FLEX_OPPONENT_ID

    by_team: dict[str, list[float]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            tid = (row.get("team_id") or "").strip()
            oid = (row.get("opponent_id") or "").strip()
            opp_raw = (row.get("opponent_fpi") or "").strip()
            if not tid or not opp_raw:
                continue
            if oid == PAC12_FLEX_OPPONENT_ID or (
                row.get(FLEX_FLAG_COL) or ""
            ).strip() == FLEX_FLAG_VALUE:
                continue
            try:
                opp_fpi = float(opp_raw)
            except ValueError:
                continue
            hfa = home_field_adjustment(
                row.get("neutral_site", ""), row.get("home_away", "")
            )
            by_team.setdefault(tid, []).append(opp_fpi - hfa)
    return {
        tid: round(sum(vals) / len(vals), 2) for tid, vals in by_team.items() if vals
    }


def team_sos(sos_by_team_id, team_id):
    return float(sos_by_team_id.get(team_id, float("-inf")))


def winningest_in_conference(source_rows, col, conference):
    candidates = [
        i
        for i, src in enumerate(source_rows)
        if src["conference"] == conference and not is_placeholder_team(src)
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda i: (int(source_rows[i][col]), -int(source_rows[i]["team_id"])),
    )


def power_four_conf_champion_indices(source_rows, col, conf_champions_by_sim):
    """Row indices for Power Four conference champions in this sim column."""
    team_id_to_index = {
        src["team_id"]: i for i, src in enumerate(source_rows) if src.get("team_id")
    }
    col_champs = conf_champions_by_sim.get(col, {})
    winners = set()
    for conf in POWER_FOUR_CONFERENCES:
        tid = col_champs.get(conf)
        if tid and tid in team_id_to_index and not is_placeholder_team(
            source_rows[team_id_to_index[tid]]
        ):
            winners.add(team_id_to_index[tid])
        else:
            i = winningest_in_conference(source_rows, col, conf)
            if i is not None:
                winners.add(i)
    return winners


def apply_power_four_conf_champions_col(
    output_rows, source_rows, col, conf_champions_by_sim
):
    for i in power_four_conf_champion_indices(
        source_rows, col, conf_champions_by_sim
    ):
        output_rows[i][col] = 1


def group_row_indices(source_rows):
    return [
        i
        for i, row in enumerate(source_rows)
        if row["conference"] in GROUP_CONFERENCES and not is_placeholder_team(row)
    ]


def g6_points_for_team(g6_points_by_team_id, team_id, col):
    return int((g6_points_by_team_id.get(team_id) or {}).get(col, 0))


def apply_g6_autobid_col(
    output_rows, source_rows, col, g6_points_by_team_id, sos_by_team_id
):
    """G6 autobid to highest playoff-points team (SOS tiebreak)."""
    group_indices = group_row_indices(source_rows)
    for i in group_indices:
        output_rows[i][col] = 0
    if not group_indices:
        return
    pick = max(
        group_indices,
        key=lambda i: (
            g6_points_for_team(
                g6_points_by_team_id, source_rows[i]["team_id"], col
            ),
            team_sos(sos_by_team_id, source_rows[i]["team_id"]),
            -int(source_rows[i]["team_id"]),
        ),
    )
    output_rows[pick][col] = 1


def eligibility_count(output_rows, col):
    return sum(int(row[col]) == 1 for row in output_rows)


def sos_rank_key(source_rows, sos_by_team_id, index):
    tid = source_rows[index]["team_id"]
    return (team_sos(sos_by_team_id, tid), int(tid))


def build_season_h2h_by_sim(
    game_rows: list[dict],
    sim_cols: list[str],
) -> tuple[
    dict[str, dict[frozenset[str], int]],
    dict[str, dict[tuple[str, str], int]],
]:
    """Per sim column: meeting counts per pair and directed win counts."""
    h2h_wins: dict[str, dict[tuple[str, str], int]] = {
        col: defaultdict(int) for col in sim_cols
    }
    h2h_games: dict[str, dict[frozenset[str], int]] = {
        col: defaultdict(int) for col in sim_cols
    }
    for row in game_rows:
        tid = (row.get("team_id") or "").strip()
        oid = (row.get("opponent_id") or "").strip()
        if not tid or not oid:
            continue
        for col in sim_cols:
            result = (row.get(col) or "").strip()
            if result not in ("0", "1"):
                continue
            pair = frozenset((tid, oid))
            h2h_games[col][pair] += 1
            if result == "1":
                h2h_wins[col][(tid, oid)] += 1
    return h2h_wins, h2h_games


def sweep_dominates(
    team_a: str,
    team_b: str,
    col: str,
    h2h_wins: dict[str, dict[tuple[str, str], int]],
    h2h_games: dict[str, dict[frozenset[str], int]],
) -> bool:
    """True if team_a won every meeting vs team_b in this sim."""
    pair = frozenset((team_a, team_b))
    games = h2h_games.get(col, {}).get(pair, 0)
    if games <= 0:
        return False
    w_ab = h2h_wins.get(col, {}).get((team_a, team_b), 0)
    w_ba = h2h_wins.get(col, {}).get((team_b, team_a), 0)
    return w_ab > 0 and w_ba == 0 and w_ab * 2 == games


def _has_directed_cycle_len_at_least_three(
    team_ids: list[str],
    edges: set[tuple[str, str]],
) -> bool:
    if len(team_ids) < 3:
        return False
    adj: dict[str, list[str]] = {tid: [] for tid in team_ids}
    for u, v in edges:
        if u in adj and v in adj:
            adj[u].append(v)

    visited: set[str] = set()

    def dfs(node: str, path: list[str]) -> bool:
        visited.add(node)
        path.append(node)
        for nxt in adj[node]:
            if nxt not in visited:
                if dfs(nxt, path):
                    return True
            elif nxt in path:
                cycle_len = len(path) - path.index(nxt)
                if cycle_len >= 3:
                    return True
        path.pop()
        return False

    for tid in team_ids:
        if tid not in visited and dfs(tid, []):
            return True
    return False


def _topological_order_by_sweep(
    indices: list[int],
    source_rows: list[dict],
    col: str,
    sos_by_team_id: dict,
    h2h_wins: dict[str, dict[tuple[str, str], int]],
    h2h_games: dict[str, dict[frozenset[str], int]],
) -> list[int]:
    sos_order = sorted(indices, key=lambda i: sos_rank_key(source_rows, sos_by_team_id, i), reverse=True)
    position = {idx: pos for pos, idx in enumerate(sos_order)}
    tids = [source_rows[i]["team_id"] for i in indices]
    edges: set[tuple[str, str]] = set()
    for a in tids:
        for b in tids:
            if a != b and sweep_dominates(a, b, col, h2h_wins, h2h_games):
                edges.add((a, b))
    if _has_directed_cycle_len_at_least_three(tids, edges):
        return sos_order

    in_degree = {tid: 0 for tid in tids}
    for u, v in edges:
        in_degree[v] += 1

    tid_to_index = {source_rows[i]["team_id"]: i for i in indices}
    ready = sorted(
        [tid for tid in tids if in_degree[tid] == 0],
        key=lambda tid: position[tid_to_index[tid]],
    )
    ordered_tids: list[str] = []
    while ready:
        tid = ready.pop(0)
        ordered_tids.append(tid)
        for v in adjacency_from_edges(tids, edges).get(tid, []):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                ready.append(v)
                ready.sort(key=lambda t: position[tid_to_index[t]])
    if len(ordered_tids) != len(tids):
        return sos_order
    return [tid_to_index[tid] for tid in ordered_tids]


def adjacency_from_edges(
    team_ids: list[str], edges: set[tuple[str, str]]
) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {tid: [] for tid in team_ids}
    for u, v in edges:
        adj[u].append(v)
    return adj


def apply_conf_champion_boost_within_bucket(
    ordered_indices: list[int],
    source_rows: list[dict],
    col: str,
    conf_champions_by_sim: dict,
) -> list[int]:
    """Rule D: conf champ above same-conference, same-win non-champs in bucket."""
    if not ordered_indices:
        return ordered_indices
    col_champs = conf_champions_by_sim.get(col, {})
    order_pos = {i: pos for pos, i in enumerate(ordered_indices)}
    by_conf: dict[str, list[int]] = defaultdict(list)
    for i in ordered_indices:
        by_conf[source_rows[i]["conference"]].append(i)

    boosted: dict[str, list[int]] = {}
    for conf, members in by_conf.items():
        members_sorted = sorted(members, key=lambda j: order_pos[j])
        if len(members_sorted) < 2:
            boosted[conf] = members_sorted
            continue
        champ_tid = col_champs.get(conf)
        champs = [
            j
            for j in members_sorted
            if champ_tid and source_rows[j]["team_id"] == champ_tid
        ]
        if len(champs) == 1:
            champ_i = champs[0]
            rest = [j for j in members_sorted if j != champ_i]
            boosted[conf] = [champ_i] + rest
        else:
            boosted[conf] = members_sorted

    result: list[int] = []
    placed: set[int] = set()
    for i in ordered_indices:
        conf = source_rows[i]["conference"]
        if i in placed:
            continue
        for j in boosted[conf]:
            if j not in placed:
                result.append(j)
                placed.add(j)
    return result


def rank_at_large_candidates(
    source_rows: list[dict],
    col: str,
    sos_by_team_id: dict,
    conf_champions_by_sim: dict,
    h2h_wins: dict[str, dict[tuple[str, str], int]] | None = None,
    h2h_games: dict[str, dict[frozenset[str], int]] | None = None,
) -> list[int]:
    """Rules 3A-D: row indices best-first for at-large selection."""
    h2h_wins = h2h_wins or {}
    h2h_games = h2h_games or {}
    all_indices = [
        i for i, src in enumerate(source_rows) if not is_placeholder_team(src)
    ]
    by_wins: dict[int, list[int]] = defaultdict(list)
    for i in all_indices:
        by_wins[int(source_rows[i][col])].append(i)

    ranked: list[int] = []
    for wins in sorted(by_wins.keys(), reverse=True):
        bucket = by_wins[wins]
        sos_sorted = sorted(
            bucket, key=lambda i: sos_rank_key(source_rows, sos_by_team_id, i), reverse=True
        )
        if h2h_wins.get(col) and h2h_games.get(col):
            ordered = _topological_order_by_sweep(
                bucket, source_rows, col, sos_by_team_id, h2h_wins, h2h_games
            )
        else:
            ordered = sos_sorted
        ordered = apply_conf_champion_boost_within_bucket(
            ordered, source_rows, col, conf_champions_by_sim
        )
        ranked.extend(ordered)
    return ranked


def apply_at_large_bids_col(
    output_rows,
    source_rows,
    col,
    sos_by_team_id,
    conf_champions_by_sim,
    h2h_wins_by_col,
    h2h_games_by_col,
    n_bids: int = AT_LARGE_BIDS,
):
    ranked = rank_at_large_candidates(
        source_rows,
        col,
        sos_by_team_id,
        conf_champions_by_sim,
        h2h_wins_by_col,
        h2h_games_by_col,
    )
    added = 0
    for i in ranked:
        if added >= n_bids:
            break
        if int(output_rows[i][col]) != 1:
            output_rows[i][col] = 1
            added += 1


def compute_column_eligibility(
    output_rows,
    source_rows,
    col,
    sim_fpi_by_team_id,
    sos_by_team_id,
    conf_champions_by_sim,
    g6_points_by_team_id,
    h2h_wins_by_col=None,
    h2h_games_by_col=None,
):
    _ = sim_fpi_by_team_id  # retained for API compatibility
    g6_pts = g6_points_by_team_id or {}
    h2h_w = h2h_wins_by_col or {}
    h2h_g = h2h_games_by_col or {}

    for i in range(len(output_rows)):
        output_rows[i][col] = 0

    apply_power_four_conf_champions_col(
        output_rows, source_rows, col, conf_champions_by_sim
    )
    apply_g6_autobid_col(
        output_rows, source_rows, col, g6_pts, sos_by_team_id
    )
    apply_at_large_bids_col(
        output_rows,
        source_rows,
        col,
        sos_by_team_id,
        conf_champions_by_sim,
        h2h_w,
        h2h_g,
    )


def load_sim_fpi_by_team_id(path):
    """team_id -> sim_col -> FPI from games file."""
    sim_fpi = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        cols = sim_columns(reader.fieldnames or [])
        for row in reader:
            team_id = row.get("team_id", "").strip()
            if not team_id or team_id in sim_fpi:
                continue
            sim_fpi[team_id] = {}
            for c in cols:
                raw = (row.get(c) or "").strip()
                if raw:
                    try:
                        sim_fpi[team_id][c] = float(raw)
                    except ValueError:
                        pass
    return sim_fpi


def load_game_rows_for_h2h(games_sim_path: Path) -> tuple[list[dict], list[str]]:
    with games_sim_path.open(newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        sim_cols = sim_columns(reader.fieldnames or [])
        return list(reader), sim_cols


def compute_playoff_eligibility(
    rows,
    fieldnames,
    sim_fpi_by_team_id=None,
    conf_champions_by_sim=None,
    sos_by_team_id=None,
    g6_points_by_team_id=None,
    h2h_wins_by_col=None,
    h2h_games_by_col=None,
):
    sim_cols = sim_columns(fieldnames)
    if conf_champions_by_sim is None:
        conf_champions_by_sim = {col: {} for col in sim_cols}
    if sos_by_team_id is None:
        sos_by_team_id = {}
    if g6_points_by_team_id is None:
        g6_points_by_team_id = {}

    output_rows = []
    for row in rows:
        out = {key: row[key] for key in fieldnames if key not in sim_cols}
        for col in sim_cols:
            out[col] = 0
        output_rows.append(out)

    for col in sim_cols:
        compute_column_eligibility(
            output_rows,
            rows,
            col,
            sim_fpi_by_team_id or {},
            sos_by_team_id,
            conf_champions_by_sim,
            g6_points_by_team_id,
            h2h_wins_by_col,
            h2h_games_by_col,
        )

    return output_rows


def write_playoff_eligibility(
    input_path,
    output_path,
    games_fpi_path=None,
    conf_champions_by_sim=None,
    games_sim_path=None,
    conf_path=None,
    g6_points_by_team_id=None,
    g6_points_path=None,
):
    input_path = Path(input_path)
    output_path = Path(output_path)

    with input_path.open(newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        rows = list(reader)

    sim_fpi_by_team_id = {}
    sos_by_team_id = {}
    if games_fpi_path:
        games_fpi_path = Path(games_fpi_path)
        sim_fpi_by_team_id = load_sim_fpi_by_team_id(games_fpi_path)
        sos_by_team_id = load_sos_by_team_id(games_fpi_path)

    h2h_wins_by_col = None
    h2h_games_by_col = None
    if games_sim_path and Path(games_sim_path).is_file():
        game_rows, sim_cols_h2h = load_game_rows_for_h2h(Path(games_sim_path))
        if sim_cols_h2h:
            h2h_wins_by_col, h2h_games_by_col = build_season_h2h_by_sim(
                game_rows, sim_cols_h2h
            )

    if conf_champions_by_sim is None and games_sim_path and games_fpi_path and conf_path:
        from cfb_conf_championship import compute_conf_results_by_sim

        results = compute_conf_results_by_sim(
            Path(games_sim_path), Path(games_fpi_path), Path(conf_path)
        )
        conf_champions_by_sim = results["champions"]

    if g6_points_by_team_id is None:
        if g6_points_path and Path(g6_points_path).is_file():
            from cfb_g6_playoff_points import load_g6_points_by_team_id

            g6_points_by_team_id = load_g6_points_by_team_id(Path(g6_points_path))
        elif games_sim_path and conf_path and conf_champions_by_sim is not None:
            from cfb_g6_playoff_points import compute_g6_playoff_points, g6_points_by_team_id_from_rows

            g6_fieldnames, g6_rows = compute_g6_playoff_points(
                Path(games_sim_path),
                Path(conf_path),
                conf_champions_by_sim,
            )
            g6_points_by_team_id = g6_points_by_team_id_from_rows(
                g6_rows, g6_fieldnames
            )
        else:
            g6_points_by_team_id = {}

    output_rows = compute_playoff_eligibility(
        rows,
        fieldnames,
        sim_fpi_by_team_id,
        conf_champions_by_sim,
        sos_by_team_id,
        g6_points_by_team_id,
        h2h_wins_by_col,
        h2h_games_by_col,
    )

    with output_path.open("w", newline="", encoding="utf-8-sig") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    return len(output_rows)
