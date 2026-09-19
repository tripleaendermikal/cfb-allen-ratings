#!/usr/bin/env python3
"""Conference championship odds from per-simulation in-conference standings."""

from __future__ import annotations

import csv
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from cfb_playoff_odds import matchup_win_prob
from pac12_week13 import apply_flex_conf_stats_for_cols, is_flex_row

SIM_COL_PATTERN = re.compile(r"^sim_\d+$")
FBS_INDEP = "FBS Indep."


def sim_columns(fieldnames: list[str]) -> list[str]:
    cols = [col for col in fieldnames if SIM_COL_PATTERN.match(col or "")]
    return sorted(cols, key=lambda c: int(c.split("_")[1]))


def sim_col_seed(sim_col: str) -> int:
    return int(sim_col.split("_")[1])


def load_conference_lookup(
    path: Path,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Return (team_id -> conference, team_id -> team_name, team_name -> team_id)."""
    by_id: dict[str, str] = {}
    name_by_id: dict[str, str] = {}
    id_by_name: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tid = (row.get("team_id") or "").strip()
            name = (row.get("team_name") or "").strip()
            conf = (row.get("conference") or "").strip()
            if tid:
                by_id[tid] = conf
                if name:
                    name_by_id[tid] = name
                    id_by_name[name] = tid
    return by_id, name_by_id, id_by_name


def load_sim_fpi_by_team_id(path: Path, sim_cols: list[str]) -> dict[str, dict[str, float]]:
    """Per-sim FPI keyed by team_id."""
    sim_fpi: dict[str, dict[str, float]] = {col: {} for col in sim_cols}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = (row.get("team_id") or "").strip()
            if not tid or tid == "TBD":
                continue
            for col in sim_cols:
                if tid in sim_fpi[col]:
                    continue
                raw = (row.get(col) or "").strip()
                if not raw:
                    continue
                try:
                    sim_fpi[col][tid] = float(raw)
                except ValueError:
                    pass
    return sim_fpi


def h2h_pct_among_peers(
    team_id: str,
    peer_ids: list[str],
    h2h_wins: dict[tuple[str, str], int],
    h2h_games: dict[frozenset[str], int],
) -> float:
    """Win rate vs other teams tied on conference win percentage."""
    wins = 0
    games = 0
    for peer in peer_ids:
        if peer == team_id:
            continue
        pair = frozenset((team_id, peer))
        g = h2h_games.get(pair, 0)
        if g == 0:
            continue
        games += g
        wins += h2h_wins.get((team_id, peer), 0)
    return wins / games if games > 0 else 0.0


def rank_conference_teams(
    team_ids: list[str],
    conf_win_pct: dict[str, float],
    h2h_wins: dict[tuple[str, str], int],
    h2h_games: dict[frozenset[str], int],
    fpi: dict[str, float],
) -> list[str]:
    """Sort teams by conf win %, then H2H among tied peers, then FPI."""

    def sort_key(tid: str) -> tuple[float, float, float]:
        pct = conf_win_pct[tid]
        peers = [p for p in team_ids if conf_win_pct[p] == pct]
        h2h = h2h_pct_among_peers(tid, peers, h2h_wins, h2h_games)
        return (pct, h2h, fpi.get(tid, float("-inf")))

    return sorted(team_ids, key=sort_key, reverse=True)


def build_conf_teams_by_conference(conf_by_id: dict[str, str]) -> dict[str, list[str]]:
    by_conf: dict[str, list[str]] = defaultdict(list)
    for tid, conf in conf_by_id.items():
        if conf and conf != FBS_INDEP:
            by_conf[conf].append(tid)
    return dict(by_conf)


def resolve_ccg_champion(
    finalist_a: str,
    finalist_b: str,
    fpi_a: float,
    fpi_b: float,
    rng: random.Random,
) -> str:
    """Bernoulli CCG winner from per-sim FPI on a neutral field."""
    p_a = matchup_win_prob(fpi_a, fpi_b)
    return finalist_a if rng.random() < p_a else finalist_b


def _build_conf_game_stats(
    game_rows: list[dict],
    conf_by_id: dict[str, str],
    sim_cols: list[str],
) -> tuple[
    dict[str, dict[str, int]],
    dict[str, dict[str, int]],
    dict[str, dict[tuple[str, str], int]],
    dict[str, dict[frozenset[str], int]],
]:
    conf_games: dict[str, dict[str, int]] = {col: defaultdict(int) for col in sim_cols}
    conf_wins: dict[str, dict[str, int]] = {col: defaultdict(int) for col in sim_cols}
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
        tconf = conf_by_id.get(tid, "")
        oconf = conf_by_id.get(oid, "")
        if not tconf or tconf != oconf or tconf == FBS_INDEP:
            continue
        for col in sim_cols:
            conf_games[col][tid] += 1
            pair = frozenset((tid, oid))
            h2h_games[col][pair] += 1
            if row.get(col) == "1":
                conf_wins[col][tid] += 1
                h2h_wins[col][(tid, oid)] += 1

    return conf_games, conf_wins, h2h_wins, h2h_games


def compute_conf_results_by_sim(
    games_sim_path: Path,
    games_fpi_path: Path,
    conf_path: Path,
    *,
    main_seed: int | None = None,
) -> dict[str, Any]:
    """
    Per-simulation conference championship results.

    Returns dict with sim_cols, champions, finalists, appearances, champ_wins,
    and game_win_prob_sum (for conf_champ_game_win_pct).
    """
    conf_by_id, _, _ = load_conference_lookup(conf_path)
    conf_teams = build_conf_teams_by_conference(conf_by_id)

    with games_sim_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        sim_cols = sim_columns(reader.fieldnames or [])
        game_rows = list(reader)

    sim_fpi_by_col = load_sim_fpi_by_team_id(games_fpi_path, sim_cols)
    conf_games, conf_wins, h2h_wins, h2h_games = _build_conf_game_stats(
        game_rows, conf_by_id, sim_cols
    )

    flex_rows_by_team = {
        (row.get("team_id") or "").strip(): row
        for row in game_rows
        if is_flex_row(row) and (row.get("team_id") or "").strip()
    }
    apply_flex_conf_stats_for_cols(
        sim_cols,
        flex_rows_by_team,
        conf_games,
        conf_wins,
        h2h_wins,
        h2h_games,
        main_seed=main_seed,
    )

    champions: dict[str, dict[str, str]] = {col: {} for col in sim_cols}
    finalists: dict[str, dict[str, list[str]]] = {col: {} for col in sim_cols}
    appearances: dict[str, int] = defaultdict(int)
    champ_wins: dict[str, int] = defaultdict(int)
    game_win_prob_sum: dict[str, float] = defaultdict(float)

    sorted_confs = sorted(conf_teams.keys())

    for col in sim_cols:
        fpi = sim_fpi_by_col[col]
        rng = random.Random(sim_col_seed(col))
        for conf in sorted_confs:
            members = conf_teams[conf]
            eligible = [tid for tid in members if conf_games[col].get(tid, 0) > 0]
            if len(eligible) < 2:
                continue

            win_pct = {
                tid: conf_wins[col][tid] / conf_games[col][tid] for tid in eligible
            }
            ranked = rank_conference_teams(
                eligible,
                win_pct,
                h2h_wins[col],
                h2h_games[col],
                fpi,
            )
            top_two = ranked[:2]
            if len(top_two) < 2:
                continue

            a, b = top_two[0], top_two[1]
            fpi_a = fpi.get(a)
            fpi_b = fpi.get(b)
            if fpi_a is None or fpi_b is None:
                continue

            p_a = matchup_win_prob(fpi_a, fpi_b)
            champion = resolve_ccg_champion(a, b, fpi_a, fpi_b, rng)

            finalists[col][conf] = [a, b]
            champions[col][conf] = champion
            appearances[a] += 1
            appearances[b] += 1
            champ_wins[champion] += 1
            game_win_prob_sum[a] += p_a
            game_win_prob_sum[b] += 1.0 - p_a

    return {
        "sim_cols": sim_cols,
        "champions": champions,
        "finalists": finalists,
        "appearances": dict(appearances),
        "champ_wins": dict(champ_wins),
        "game_win_prob_sum": dict(game_win_prob_sum),
        "conf_by_id": conf_by_id,
    }


def compute_conf_championship_odds(
    games_sim_path: Path,
    games_fpi_path: Path,
    conf_path: Path,
) -> tuple[list[dict], int]:
    """Compute conference championship odds across all simulations."""
    conf_by_id, name_by_id, _ = load_conference_lookup(conf_path)
    results = compute_conf_results_by_sim(games_sim_path, games_fpi_path, conf_path)
    sim_cols = results["sim_cols"]
    appearances = results["appearances"]
    champ_wins = results["champ_wins"]
    game_win_prob_sum = results["game_win_prob_sum"]
    n_sims = len(sim_cols)

    all_team_ids = sorted(conf_by_id.keys(), key=lambda t: int(t) if t.isdigit() else t)
    summary: list[dict] = []
    for tid in all_team_ids:
        conf = conf_by_id.get(tid, "")
        name = name_by_id.get(tid, tid)
        apps = appearances.get(tid, 0)
        game_win_pct = (
            round(game_win_prob_sum.get(tid, 0.0) / apps * 100, 2) if apps else 0.0
        )
        summary.append(
            {
                "team_id": tid,
                "team_name": name,
                "conference": conf,
                "conf_champ_odds_pct": round(
                    champ_wins.get(tid, 0) / n_sims * 100, 2
                ),
                "conf_champ_appearances": apps,
                "conf_champ_game_win_pct": game_win_pct,
            }
        )

    summary.sort(
        key=lambda r: (-float(r["conf_champ_odds_pct"]), r["team_name"].lower())
    )
    return summary, n_sims


def write_conf_championship_odds(
    games_sim_path: Path,
    games_fpi_path: Path,
    conf_path: Path,
    output_path: Path,
) -> tuple[int, int]:
    summary, n_sims = compute_conf_championship_odds(
        games_sim_path, games_fpi_path, conf_path
    )
    fieldnames = [
        "team_id",
        "team_name",
        "conference",
        "conf_champ_odds_pct",
        "conf_champ_appearances",
        "conf_champ_game_win_pct",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)

    return len(summary), n_sims
