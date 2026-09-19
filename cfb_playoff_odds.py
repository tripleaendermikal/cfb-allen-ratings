#!/usr/bin/env python3
"""12-team CFB playoff championship odds calculator."""

from __future__ import annotations

import math
from itertools import product
from typing import Iterable, Sequence

# 0-based seed indices: 5v12, 6v11, 7v10, 8v9
FIRST_ROUND_PAIRINGS = ((4, 11), (5, 10), (6, 9), (7, 8))


def win_probability(margin: float) -> float:
    """P(favorite wins) from expected margin on a neutral field."""
    return 1.0 / (1.0 + math.exp(-0.1 * margin))


def matchup_win_prob(rating_a: float, rating_b: float) -> float:
    """Probability team A beats team B at a neutral playoff site."""
    return win_probability(rating_a - rating_b)


def _matchup_outcomes(
    idx_a: int, idx_b: int, ratings: Sequence[float]
) -> tuple[tuple[int, float], tuple[int, float]]:
    prob_a = matchup_win_prob(ratings[idx_a], ratings[idx_b])
    return (idx_a, prob_a), (idx_b, 1.0 - prob_a)


def championship_odds_exact(ratings: Sequence[float]) -> list[float]:
    """
    Exact title odds for a 12-team bracket.

    ratings[i] is the strength rating for seed i+1 (length must be 12).
    Seeds 1-4 receive byes. First round: 5v12, 6v11, 7v10, 8v9.
    Quarterfinals: 1 vs 8/9 winner, 2 vs 7/10, 3 vs 6/11, 4 vs 5/12.
    """
    if len(ratings) != 12:
        raise ValueError("ratings must contain exactly 12 values (seeds 1-12)")

    champ = [0.0] * 12
    r1_options = [
        _matchup_outcomes(a, b, ratings) for a, b in FIRST_ROUND_PAIRINGS
    ]

    for r1 in product(*r1_options):
        w_5_12, w_6_11, w_7_10, w_8_9 = (outcome[0] for outcome in r1)
        p_r1 = 1.0
        for outcome in r1:
            p_r1 *= outcome[1]

        qf_pairings = ((0, w_8_9), (1, w_7_10), (2, w_6_11), (3, w_5_12))
        qf_options = [
            _matchup_outcomes(a, b, ratings) for a, b in qf_pairings
        ]

        for qf in product(*qf_options):
            w_1, w_2, w_3, w_4 = (outcome[0] for outcome in qf)
            p_qf = 1.0
            for outcome in qf:
                p_qf *= outcome[1]

            sf_pairings = ((w_1, w_2), (w_3, w_4))
            sf_options = [
                _matchup_outcomes(a, b, ratings) for a, b in sf_pairings
            ]

            for sf in product(*sf_options):
                w_a, w_b = (outcome[0] for outcome in sf)
                p_sf = 1.0
                for outcome in sf:
                    p_sf *= outcome[1]

                for winner, p_fin in _matchup_outcomes(w_a, w_b, ratings):
                    champ[winner] += p_r1 * p_qf * p_sf * p_fin

    total = sum(champ)
    if not math.isclose(total, 1.0, rel_tol=1e-9, abs_tol=1e-9):
        raise RuntimeError(f"championship probabilities sum to {total}, not 1.0")

    return champ


def format_bracket(team_names: Sequence[str]) -> str:
    """Pretty-print the 12-team CFB bracket."""
    if len(team_names) != 12:
        raise ValueError("team_names must contain exactly 12 entries")

    lines = [
        "CFB 12-Team Playoff Bracket",
        f"  #1  {team_names[0]}  (bye)",
        f"  #2  {team_names[1]}  (bye)",
        f"  #3  {team_names[2]}  (bye)",
        f"  #4  {team_names[3]}  (bye)",
        f"  #5  {team_names[4]}  vs  #12 {team_names[11]}",
        f"  #6  {team_names[5]}  vs  #11 {team_names[10]}",
        f"  #7  {team_names[6]}  vs  #10 {team_names[9]}",
        f"  #8  {team_names[7]}  vs  #9  {team_names[8]}",
        "Quarterfinals:",
        f"  #1 vs winner(#8/#9)",
        f"  #2 vs winner(#7/#10)",
        f"  #3 vs winner(#6/#11)",
        f"  #4 vs winner(#5/#12)",
    ]
    return "\n".join(lines)


def odds_table(
    team_names: Sequence[str],
    ratings: Sequence[float],
    conferences: Sequence[str] | None = None,
) -> list[dict[str, object]]:
    """Return sorted rows with seed, team, conference, rating, title_odds."""
    if len(team_names) != 12 or len(ratings) != 12:
        raise ValueError("team_names and ratings must each have 12 entries")

    title_probs = championship_odds_exact(ratings)
    rows = []
    for seed, (name, rating, prob) in enumerate(
        zip(team_names, ratings, title_probs), start=1
    ):
        conf = conferences[seed - 1] if conferences is not None else ""
        rows.append(
            {
                "seed": seed,
                "team_name": name,
                "conference": conf,
                "rating": round(float(rating), 3),
                "title_odds_pct": round(prob * 100, 2),
            }
        )

    rows.sort(key=lambda row: (-float(row["title_odds_pct"]), int(row["seed"])))
    return rows


def average_title_odds(
    bracket_results: Iterable[dict[str, float]],
) -> dict[str, float]:
    """
    Average title odds across many bracket scenarios.

    Each item maps team_name -> title probability for one bracket.
    Teams omitted from a bracket are treated as 0 for that scenario.
    """
    totals: dict[str, float] = {}
    count = 0
    for result in bracket_results:
        count += 1
        for team, prob in result.items():
            totals[team] = totals.get(team, 0.0) + prob

    if count == 0:
        return {}

    all_teams = set(totals)
    return {team: totals.get(team, 0.0) / count for team in all_teams}
