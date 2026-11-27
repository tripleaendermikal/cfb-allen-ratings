"""Per-simulation standings context for conference championship tiebreakers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from cfb_paths import data_root
from cfb_rating.sim_resume import compute_sim_resume_margins, overall_margins_for_sim_col
from pac12_week13 import is_flex_row

import csv

from cfb_conference_corrections import apply_conference_lookup_overrides

FBS_INDEP = "FBS Indep."

SEC_MARGIN_CAP = 28.0
WIN_MARGIN_PROXY = 21.0
LOSS_MARGIN_PROXY = -21.0

SUN_BELT = "Sun Belt"
PAC_12 = "Pac-12"


def load_sun_belt_divisions(
    path: Path | None = None,
    season_year: int = 2026,
) -> dict[str, str]:
    """team_id -> East|West for Sun Belt."""
    path = path or data_root() / "sun_belt_divisions.json"
    if not path.is_file():
        repo_path = Path(__file__).resolve().parent / "cfb_data" / "sun_belt_divisions.json"
        if repo_path.is_file():
            path = repo_path
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    by_season = data.get("by_season") or {}
    year_key = str(season_year)
    if year_key not in by_season:
        year_key = str(data.get("default_season_year", season_year))
    divisions = by_season.get(year_key) or {}
    out: dict[str, str] = {}
    for div_name, team_ids in divisions.items():
        for tid in team_ids:
            out[str(tid)] = div_name
    return out


def infer_season_year(game_rows: Sequence[Mapping[str, str]]) -> int:
    for row in game_rows:
        raw = (row.get("season_year") or "").strip()
        if raw.isdigit():
            return int(raw)
    return 2026


@dataclass
class ConferenceStandings:
    """One conference within one simulation column."""

    conference: str
    conf_wins: dict[str, int] = field(default_factory=dict)
    conf_games: dict[str, int] = field(default_factory=dict)
    h2h_wins: dict[tuple[str, str], int] = field(default_factory=dict)
    h2h_games: dict[frozenset[str], int] = field(default_factory=dict)
    overall_wins: dict[str, int] = field(default_factory=dict)
    overall_games: dict[str, int] = field(default_factory=dict)
    div_wins: dict[str, int] = field(default_factory=dict)
    div_games: dict[str, int] = field(default_factory=dict)
    capped_margin: dict[str, float] = field(default_factory=dict)
    conf_opponents: dict[str, set[str]] = field(default_factory=dict)
    week14_conf_win: dict[str, bool] = field(default_factory=dict)
    resume_margin: dict[str, float] = field(default_factory=dict)
    overall_margin: dict[str, float] = field(default_factory=dict)


@dataclass
class SimColStandings:
    sim_col: str
    by_conference: dict[str, ConferenceStandings]


def is_tbd_team_id(team_id: str, team_name: str = "") -> bool:
    if (team_id or "").strip() in {"-1", "-2"}:
        return True
    return (team_name or "").strip().upper() == "TBD"


def load_fbs_team_ids(conf_path: Path) -> frozenset[str]:
    by_id: dict[str, str] = {}
    with conf_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            tid = (row.get("team_id") or "").strip()
            if tid:
                by_id[tid] = (row.get("conference") or "").strip()
    apply_conference_lookup_overrides(by_id)
    return frozenset(by_id.keys())


def build_sim_col_standings(
    col: str,
    game_rows: Sequence[Mapping[str, str]],
    conf_by_id: dict[str, str],
    conf_teams: dict[str, list[str]],
    conf_games: dict[str, int],
    conf_wins: dict[str, int],
    h2h_wins: dict[tuple[str, str], int],
    h2h_games: dict[frozenset[str], int],
    *,
    partial_ccg_game_ids: frozenset[str] = frozenset(),
    sim_fpi_by_team_id: dict[str, dict[str, float]],
    fbs_team_ids: frozenset[str],
    sun_belt_div: dict[str, str],
) -> SimColStandings:
    conferences = {
        conf: ConferenceStandings(conference=conf) for conf in conf_teams
    }
    global_overall_wins: dict[str, int] = {}
    global_overall_games: dict[str, int] = {}

    for conf, members in conf_teams.items():
        cs = conferences[conf]
        for tid in members:
            cs.conf_games[tid] = conf_games.get(tid, 0)
            cs.conf_wins[tid] = conf_wins.get(tid, 0)
            cs.conf_opponents[tid] = set()
        cs.h2h_wins = dict(h2h_wins)
        cs.h2h_games = dict(h2h_games)
        for pair in h2h_games:
            ids = list(pair)
            if len(ids) != 2:
                continue
            tid, oid = ids[0], ids[1]
            if tid in members and oid in members:
                cs.conf_opponents.setdefault(tid, set()).add(oid)
                cs.conf_opponents.setdefault(oid, set()).add(tid)

    def _conf_name(tid: str, oid: str) -> str | None:
        tconf = conf_by_id.get(tid, "")
        oconf = conf_by_id.get(oid, "")
        if not tconf or tconf != oconf or tconf == FBS_INDEP:
            return None
        return tconf

    for row in game_rows:
        if is_flex_row(row):
            continue
        gid = (row.get("game_id") or "").strip()
        if gid and gid in partial_ccg_game_ids:
            continue
        if (row.get("home_away") or "").strip() != "home":
            continue
        home_id = (row.get("team_id") or "").strip()
        away_id = (row.get("opponent_id") or "").strip()
        if not home_id or not away_id:
            continue
        if is_tbd_team_id(home_id) or is_tbd_team_id(away_id):
            continue
        if home_id not in fbs_team_ids or away_id not in fbs_team_ids:
            continue
        result = (row.get(col) or "").strip()
        if result not in ("0", "1"):
            continue
        home_win = result == "1"
        week = (row.get("week") or "").strip()

        for tid, oid, won in (
            (home_id, away_id, home_win),
            (away_id, home_id, not home_win),
        ):
            conf = _conf_name(tid, oid)
            if conf and conf in conferences:
                cs = conferences[conf]
                margin = WIN_MARGIN_PROXY if won else LOSS_MARGIN_PROXY
                margin = max(-SEC_MARGIN_CAP, min(SEC_MARGIN_CAP, margin))
                cs.capped_margin[tid] = cs.capped_margin.get(tid, 0.0) + margin
                if week == "14":
                    cs.week14_conf_win[tid] = won

            global_overall_games[tid] = global_overall_games.get(tid, 0) + 1
            if won:
                global_overall_wins[tid] = global_overall_wins.get(tid, 0) + 1

            if conf == SUN_BELT and conf in conferences:
                cs = conferences[SUN_BELT]
                if sun_belt_div.get(tid) == sun_belt_div.get(oid):
                    cs.div_games[tid] = cs.div_games.get(tid, 0) + 1
                    if won:
                        cs.div_wins[tid] = cs.div_wins.get(tid, 0) + 1

    for conf, members in conf_teams.items():
        cs = conferences[conf]
        for tid in members:
            cs.overall_wins[tid] = global_overall_wins.get(tid, 0)
            cs.overall_games[tid] = global_overall_games.get(tid, 0)

    all_fbs = sorted(fbs_team_ids, key=lambda t: int(t) if t.isdigit() else t)
    overall = overall_margins_for_sim_col(sim_fpi_by_team_id, col, all_fbs)
    resume = compute_sim_resume_margins(
        game_rows,
        col,
        all_fbs,
        overall,
        fbs_team_ids=fbs_team_ids,
    )

    for conf, cs in conferences.items():
        for tid in conf_teams.get(conf, []):
            if tid in resume:
                cs.resume_margin[tid] = resume[tid]
            if tid in overall:
                cs.overall_margin[tid] = overall[tid]

    return SimColStandings(sim_col=col, by_conference=conferences)