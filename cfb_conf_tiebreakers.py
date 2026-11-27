"""Conference-specific CCG participant selection via official-style tiebreakers."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from cfb_conf_standings import (
    PAC_12,
    SUN_BELT,
    ConferenceStandings,
    SimColStandings,
)

StepFn = Callable[
    [list[str], ConferenceStandings, random.Random],
    tuple[list[str], list[str]],
]


class Step(Enum):
    HEAD_TO_HEAD = auto()
    COMMON_OPP_PCT = auto()
    NEXT_COMMON_CHAIN = auto()
    COMBINED_OPP_PCT = auto()
    CAPPED_MARGIN = auto()
    TOTAL_WINS = auto()
    RESUME_RANK = auto()
    OVERALL_RANK = auto()
    MINI_ROUND_ROBIN = auto()
    SWEEP_ELIMINATE = auto()
    DIVISION_PCT = auto()
    WEEK14_RESUME = auto()
    COIN_FLIP = auto()


TWO_TEAM_P4 = [
    Step.HEAD_TO_HEAD,
    Step.COMMON_OPP_PCT,
    Step.NEXT_COMMON_CHAIN,
    Step.COMBINED_OPP_PCT,
    Step.OVERALL_RANK,
    Step.COIN_FLIP,
]

TWO_TEAM_SEC = [
    Step.HEAD_TO_HEAD,
    Step.COMMON_OPP_PCT,
    Step.NEXT_COMMON_CHAIN,
    Step.COMBINED_OPP_PCT,
    Step.CAPPED_MARGIN,
    Step.OVERALL_RANK,
    Step.COIN_FLIP,
]

MULTI_TEAM_P4 = [
    Step.MINI_ROUND_ROBIN,
    Step.SWEEP_ELIMINATE,
    Step.COMMON_OPP_PCT,
    Step.NEXT_COMMON_CHAIN,
    Step.COMBINED_OPP_PCT,
    Step.OVERALL_RANK,
    Step.COIN_FLIP,
]

MULTI_TEAM_SEC = [
    Step.MINI_ROUND_ROBIN,
    Step.SWEEP_ELIMINATE,
    Step.COMMON_OPP_PCT,
    Step.NEXT_COMMON_CHAIN,
    Step.COMBINED_OPP_PCT,
    Step.CAPPED_MARGIN,
    Step.OVERALL_RANK,
    Step.COIN_FLIP,
]

MULTI_TEAM_BIG12 = [
    Step.MINI_ROUND_ROBIN,
    Step.SWEEP_ELIMINATE,
    Step.COMMON_OPP_PCT,
    Step.NEXT_COMMON_CHAIN,
    Step.COMBINED_OPP_PCT,
    Step.TOTAL_WINS,
    Step.OVERALL_RANK,
    Step.COIN_FLIP,
]

TWO_TEAM_BIG12 = [
    Step.HEAD_TO_HEAD,
    Step.COMMON_OPP_PCT,
    Step.NEXT_COMMON_CHAIN,
    Step.COMBINED_OPP_PCT,
    Step.TOTAL_WINS,
    Step.OVERALL_RANK,
    Step.COIN_FLIP,
]

TWO_TEAM_G6 = [
    Step.HEAD_TO_HEAD,
    Step.WEEK14_RESUME,
    Step.RESUME_RANK,
    Step.OVERALL_RANK,
    Step.TOTAL_WINS,
    Step.COIN_FLIP,
]

MULTI_TEAM_G6 = [
    Step.MINI_ROUND_ROBIN,
    Step.SWEEP_ELIMINATE,
    Step.WEEK14_RESUME,
    Step.RESUME_RANK,
    Step.OVERALL_RANK,
    Step.TOTAL_WINS,
    Step.COIN_FLIP,
]

SUN_BELT_DIV_STEPS = [
    Step.HEAD_TO_HEAD,
    Step.DIVISION_PCT,
    Step.WEEK14_RESUME,
    Step.RESUME_RANK,
    Step.OVERALL_RANK,
    Step.TOTAL_WINS,
    Step.COIN_FLIP,
]

CONF_TWO_STEPS: dict[str, list[Step]] = {
    "SEC": TWO_TEAM_SEC,
    "Big Ten": TWO_TEAM_P4,
    "ACC": TWO_TEAM_P4,
    "Big 12": TWO_TEAM_BIG12,
    "MAC": TWO_TEAM_P4,
    "American": TWO_TEAM_G6,
    "Mountain West": TWO_TEAM_G6,
    "CUSA": TWO_TEAM_G6,
    SUN_BELT: SUN_BELT_DIV_STEPS,
}

CONF_MULTI_STEPS: dict[str, list[Step]] = {
    "SEC": MULTI_TEAM_SEC,
    "Big Ten": MULTI_TEAM_P4,
    "ACC": MULTI_TEAM_P4,
    "Big 12": MULTI_TEAM_BIG12,
    "MAC": MULTI_TEAM_P4,
    "American": MULTI_TEAM_G6,
    "Mountain West": MULTI_TEAM_G6,
    "CUSA": MULTI_TEAM_G6,
    SUN_BELT: SUN_BELT_DIV_STEPS,
}


def _conf_win_pct(cs: ConferenceStandings, tid: str) -> float:
    games = cs.conf_games.get(tid, 0)
    if games <= 0:
        return 0.0
    return cs.conf_wins.get(tid, 0) / games


def _h2h_record(
    a: str,
    b: str,
    cs: ConferenceStandings,
) -> tuple[int, int]:
    wins = cs.h2h_wins.get((a, b), 0)
    losses = cs.h2h_wins.get((b, a), 0)
    return wins, losses


def _common_opponents(teams: list[str], cs: ConferenceStandings) -> set[str]:
    if not teams:
        return set()
    commons = set(cs.conf_opponents.get(teams[0], set()))
    for tid in teams[1:]:
        commons &= cs.conf_opponents.get(tid, set())
    return {o for o in commons if o not in teams}


def _record_vs_opponents(
    tid: str,
    opps: set[str],
    cs: ConferenceStandings,
) -> tuple[int, int]:
    wins = 0
    games = 0
    for opp in opps:
        pair = frozenset((tid, opp))
        g = cs.h2h_games.get(pair, 0)
        if g == 0:
            continue
        games += g
        wins += cs.h2h_wins.get((tid, opp), 0)
    return wins, games


def _combined_opp_conf_pct(tid: str, cs: ConferenceStandings) -> float:
    opps = cs.conf_opponents.get(tid, set())
    if not opps:
        return 0.0
    total = 0.0
    for opp in opps:
        total += _conf_win_pct(cs, opp)
    return total / len(opps)


def _stable_draw(teams: list[str], cs: ConferenceStandings, rng: random.Random) -> str:
    ordered = sorted(teams, key=lambda t: int(t) if t.isdigit() else t)
    idx = rng.randint(0, len(ordered) - 1)
    return ordered[idx]


def _apply_step(
    step: Step,
    teams: list[str],
    cs: ConferenceStandings,
    rng: random.Random,
) -> tuple[list[str], list[str]]:
    """Return (advancing, eliminated). Empty advancing = no split yet."""
    if len(teams) <= 1:
        return teams, []

    if step == Step.HEAD_TO_HEAD and len(teams) == 2:
        a, b = teams
        aw, al = _h2h_record(a, b, cs)
        bw, bl = _h2h_record(b, a, cs)
        if aw + bw > 0:
            if aw > bw:
                return [a], [b]
            if bw > aw:
                return [b], [a]
        return [], []

    if step == Step.COMMON_OPP_PCT:
        opps = _common_opponents(teams, cs)
        if not opps:
            return [], []
        scores: dict[str, float] = {}
        for tid in teams:
            w, g = _record_vs_opponents(tid, opps, cs)
            scores[tid] = w / g if g else 0.0
        best = max(scores.values())
        advancing = [t for t in teams if scores[t] == best]
        eliminated = [t for t in teams if t not in advancing]
        if len(advancing) < len(teams):
            return advancing, eliminated
        return [], []

    if step == Step.NEXT_COMMON_CHAIN:
        opps = _common_opponents(teams, cs)
        if not opps:
            return [], []
        opp_order = sorted(
            opps,
            key=lambda o: (_conf_win_pct(cs, o), cs.overall_margin.get(o, -999)),
            reverse=True,
        )
        pool = list(teams)
        for opp in opp_order:
            scores = {}
            for tid in pool:
                w, g = _record_vs_opponents(tid, {opp}, cs)
                scores[tid] = w / g if g else 0.0
            best = max(scores.values())
            next_pool = [t for t in pool if scores[t] == best]
            if len(next_pool) < len(pool):
                eliminated = [t for t in pool if t not in next_pool]
                return next_pool, eliminated
            pool = next_pool
        return [], []

    if step == Step.COMBINED_OPP_PCT:
        scores = {tid: _combined_opp_conf_pct(tid, cs) for tid in teams}
        best = max(scores.values())
        advancing = [t for t in teams if scores[t] == best]
        eliminated = [t for t in teams if t not in advancing]
        if len(advancing) < len(teams):
            return advancing, eliminated
        return [], []

    if step == Step.CAPPED_MARGIN:
        scores = {tid: cs.capped_margin.get(tid, 0.0) for tid in teams}
        best = max(scores.values())
        advancing = [t for t in teams if scores[t] == best]
        eliminated = [t for t in teams if t not in advancing]
        if len(advancing) < len(teams):
            return advancing, eliminated
        return [], []

    if step == Step.TOTAL_WINS:
        scores = {
            tid: cs.overall_wins.get(tid, cs.conf_wins.get(tid, 0)) for tid in teams
        }
        best = max(scores.values())
        advancing = [t for t in teams if scores[t] == best]
        eliminated = [t for t in teams if t not in advancing]
        if len(advancing) < len(teams):
            return advancing, eliminated
        return [], []

    if step == Step.RESUME_RANK:
        scores = {tid: cs.resume_margin.get(tid, -999.0) for tid in teams}
        best = max(scores.values())
        advancing = [t for t in teams if scores[t] == best]
        eliminated = [t for t in teams if t not in advancing]
        if len(advancing) < len(teams):
            return advancing, eliminated
        return [], []

    if step == Step.OVERALL_RANK:
        scores = {tid: cs.overall_margin.get(tid, -999.0) for tid in teams}
        best = max(scores.values())
        advancing = [t for t in teams if scores[t] == best]
        eliminated = [t for t in teams if t not in advancing]
        if len(advancing) < len(teams):
            return advancing, eliminated
        return [], []

    if step == Step.DIVISION_PCT:
        scores = {}
        for tid in teams:
            g = cs.div_games.get(tid, 0)
            scores[tid] = cs.div_wins.get(tid, 0) / g if g else _conf_win_pct(cs, tid)
        best = max(scores.values())
        advancing = [t for t in teams if scores[t] == best]
        eliminated = [t for t in teams if t not in advancing]
        if len(advancing) < len(teams):
            return advancing, eliminated
        return [], []

    if step == Step.WEEK14_RESUME:
        ranked = sorted(
            teams,
            key=lambda t: (
                -(cs.resume_margin.get(t, -999.0)),
                cs.overall_margin.get(t, -999.0),
            ),
        )
        for tid in ranked:
            if cs.week14_conf_win.get(tid, True):
                return [tid], [x for x in teams if x != tid]
        return [], []

    if step == Step.MINI_ROUND_ROBIN:
        scores: dict[str, float] = defaultdict(float)
        for i, a in enumerate(teams):
            for b in teams[i + 1 :]:
                aw, bw = _h2h_record(a, b, cs)[0], _h2h_record(b, a, cs)[0]
                if aw + bw == 0:
                    continue
                if aw > bw:
                    scores[a] += 1.0
                elif bw > aw:
                    scores[b] += 1.0
                else:
                    scores[a] += 0.5
                    scores[b] += 0.5
        if not scores:
            return [], []
        best = max(scores.get(t, 0.0) for t in teams)
        advancing = [t for t in teams if scores.get(t, 0.0) == best]
        eliminated = [t for t in teams if t not in advancing]
        if len(advancing) < len(teams):
            return advancing, eliminated
        return [], []

    if step == Step.SWEEP_ELIMINATE:
        eliminated: list[str] = []
        remaining = list(teams)
        for tid in list(remaining):
            beat_all = True
            lost_all = True
            for other in remaining:
                if other == tid:
                    continue
                w, _ = _h2h_record(tid, other, cs)
                lw, _ = _h2h_record(other, tid, cs)
                if w <= lw:
                    beat_all = False
                if lw <= w:
                    lost_all = False
            if beat_all:
                return [tid], [x for x in remaining if x != tid]
            if lost_all:
                eliminated.append(tid)
        if eliminated and len(eliminated) < len(remaining):
            return [t for t in remaining if t not in eliminated], eliminated
        return [], []

    if step == Step.COIN_FLIP:
        winner = _stable_draw(teams, cs, rng)
        return [winner], [t for t in teams if t != winner]

    return [], []


def _resolve_tie(
    conference: str,
    teams: list[str],
    cs: ConferenceStandings,
    rng: random.Random,
    *,
    multi: bool,
) -> list[str]:
    if len(teams) <= 1:
        return teams
    steps = (
        CONF_MULTI_STEPS.get(conference, MULTI_TEAM_P4)
        if multi
        else CONF_TWO_STEPS.get(conference, TWO_TEAM_P4)
    )
    pool = list(teams)
    for step in steps:
        if len(pool) <= 1:
            break
        advancing, eliminated = _apply_step(step, pool, cs, rng)
        if advancing and len(advancing) < len(pool):
            if step == Step.COIN_FLIP and len(advancing) == 1 and multi:
                return advancing
            pool = advancing
            if multi and len(pool) <= 2:
                break
            continue
        if advancing and len(advancing) == len(pool):
            continue
    if len(pool) == 1:
        return pool
    pool.sort(
        key=lambda t: (
            _conf_win_pct(cs, t),
            cs.overall_margin.get(t, -999.0),
        ),
        reverse=True,
    )
    return pool


def _teams_by_conf_pct(eligible: list[str], cs: ConferenceStandings) -> dict[float, list[str]]:
    buckets: dict[float, list[str]] = defaultdict(list)
    for tid in eligible:
        buckets[_conf_win_pct(cs, tid)].append(tid)
    return dict(buckets)


def select_league_ccg_pair(
    conference: str,
    eligible: list[str],
    cs: ConferenceStandings,
    rng: random.Random,
) -> list[str] | None:
    if conference == PAC_12:
        return None
    if len(eligible) < 2:
        return None

    buckets = _teams_by_conf_pct(eligible, cs)
    sorted_pcts = sorted(buckets.keys(), reverse=True)
    top_pct = sorted_pcts[0]
    top_group = buckets[top_pct]

    if len(top_group) == 1:
        first = top_group[0]
        if len(sorted_pcts) < 2:
            return None
        second_pool = buckets[sorted_pcts[1]]
        if len(second_pool) == 1:
            return [first, second_pool[0]]
        second = _resolve_tie(conference, second_pool, cs, rng, multi=len(second_pool) > 2)
        if not second:
            return None
        return [first, second[0]]

    if len(top_group) == 2:
        return top_group

    if len(top_group) > 2:
        resolved = _resolve_tie(conference, top_group, cs, rng, multi=True)
        if len(resolved) >= 2:
            return resolved[:2]
        return None

    return None


def select_sun_belt_ccg_pair(
    eligible: list[str],
    cs: ConferenceStandings,
    sun_belt_div: dict[str, str],
    rng: random.Random,
) -> list[str] | None:
    east = [t for t in eligible if sun_belt_div.get(t) == "East"]
    west = [t for t in eligible if sun_belt_div.get(t) == "West"]
    if len(east) < 1 or len(west) < 1:
        return None

    def division_champ(pool: list[str]) -> str | None:
        buckets = _teams_by_conf_pct(pool, cs)
        best = max(buckets.keys())
        group = buckets[best]
        if len(group) == 1:
            return group[0]
        resolved = _resolve_tie(
            SUN_BELT,
            group,
            cs,
            rng,
            multi=len(group) > 2,
        )
        if not resolved:
            return None
        if len(resolved) > 1:
            resolved = _resolve_tie(SUN_BELT, resolved[:2], cs, rng, multi=False)
        return resolved[0] if resolved else None

    east_champ = division_champ(east)
    west_champ = division_champ(west)
    if not east_champ or not west_champ:
        return None
    return [east_champ, west_champ]


def select_ccg_participants(
    conference: str,
    eligible: list[str],
    sim_standings: SimColStandings,
    sun_belt_div: dict[str, str],
    rng: random.Random,
    *,
    partial_known_team_id: str | None = None,
) -> list[str] | None:
    cs = sim_standings.by_conference.get(conference)
    if cs is None:
        return None

    if partial_known_team_id and partial_known_team_id in eligible:
        pair = select_league_ccg_pair(conference, [t for t in eligible if t != partial_known_team_id], cs, rng)
        if not pair:
            return None
        return [partial_known_team_id, pair[0]]

    if conference == SUN_BELT:
        return select_sun_belt_ccg_pair(eligible, cs, sun_belt_div, rng)

    return select_league_ccg_pair(conference, eligible, cs, rng)