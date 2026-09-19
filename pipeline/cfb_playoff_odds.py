"""Exact national-title odds from seeded 12-team bracket ratings."""

from __future__ import annotations

import math


def _win_prob(margin: float) -> float:
    x = 0.175 * margin
    return math.exp(x) / (1.0 + math.exp(x))


def _match_prob(rating_a: float, rating_b: float) -> float:
    return _win_prob(rating_a - rating_b)


def championship_odds_exact(ratings: list[float]) -> list[float]:
    """Return title probability for seeds 1..12 on a neutral-site bracket."""
    if len(ratings) != 12:
        raise ValueError("championship_odds_exact expects 12 seeded ratings")

    r1_winners = {
        (5, 12): _match_prob(ratings[4], ratings[11]),
        (6, 11): _match_prob(ratings[5], ratings[10]),
        (7, 10): _match_prob(ratings[6], ratings[9]),
        (8, 9): _match_prob(ratings[7], ratings[8]),
    }

    def qf_prob(seed: int, r1_pair: tuple[int, int]) -> list[tuple[float, int]]:
        p_r1 = r1_winners[r1_pair]
        winner_seed = r1_pair[0] if p_r1 >= 0.5 else r1_pair[1]
        loser_seed = r1_pair[1] if winner_seed == r1_pair[0] else r1_pair[0]
        p_top = _match_prob(ratings[seed - 1], ratings[winner_seed - 1])
        return [(p_top, seed), (1.0 - p_top, winner_seed)]

    qf_brackets = [
        (1, (8, 9)),
        (4, (7, 10)),
        (3, (6, 11)),
        (2, (5, 12)),
    ]

    sf_states: list[tuple[float, int]] = []
    for top_seed, pair in qf_brackets:
        for prob, finalist in qf_prob(top_seed, pair):
            sf_states.append((prob, finalist))

    final_states: list[tuple[float, int]] = []
    for index_a, (prob_a, seed_a) in enumerate(sf_states):
        for prob_b, seed_b in sf_states[index_a + 1 :]:
            if seed_a == seed_b:
                continue
            p_a = _match_prob(ratings[seed_a - 1], ratings[seed_b - 1])
            final_states.append((prob_a * prob_b * p_a, seed_a))
            final_states.append((prob_a * prob_b * (1.0 - p_a), seed_b))

    title_probs = [0.0] * 12
    for prob, seed in final_states:
        title_probs[seed - 1] += prob
    total = sum(title_probs)
    if total <= 0:
        return [1.0 / 12.0] * 12
    return [value / total for value in title_probs]
