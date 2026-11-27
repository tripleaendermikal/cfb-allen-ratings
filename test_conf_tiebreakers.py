#!/usr/bin/env python3
"""Conference championship tiebreaker selection."""

from __future__ import annotations

import random
import unittest

from cfb_conf_standings import ConferenceStandings, SimColStandings, load_sun_belt_divisions
from cfb_conf_tiebreakers import select_ccg_participants, select_league_ccg_pair


def _cs(**kwargs) -> ConferenceStandings:
    return ConferenceStandings(conference="SEC", **kwargs)


class ConfTiebreakerTests(unittest.TestCase):
    def test_two_team_h2h_picks_winner_for_second_place(self) -> None:
        cs = _cs(
            conf_wins={"1": 2, "2": 2, "3": 4},
            conf_games={"1": 4, "2": 4, "3": 4},
            h2h_wins={("1", "2"): 1, ("2", "1"): 0, ("3", "1"): 2, ("3", "2"): 2},
            h2h_games={frozenset(("1", "2")): 1, frozenset(("3", "1")): 2, frozenset(("3", "2")): 2},
            conf_opponents={"1": {"2", "3"}, "2": {"1", "3"}, "3": {"1", "2"}},
            overall_margin={"1": 1.0, "2": 2.0, "3": 5.0},
        )
        rng = random.Random(42)
        pair = select_league_ccg_pair("SEC", ["1", "2", "3"], cs, rng)
        self.assertEqual(pair, ["3", "1"])

    def test_two_teams_tied_for_first_both_advance(self) -> None:
        cs = _cs(
            conf_wins={"1": 3, "2": 3},
            conf_games={"1": 4, "2": 4},
        )
        rng = random.Random(1)
        pair = select_league_ccg_pair("Big Ten", ["1", "2"], cs, rng)
        self.assertEqual(set(pair), {"1", "2"})

    def test_pac12_has_no_ccg(self) -> None:
        cs = _cs(conf_wins={"1": 2, "2": 1}, conf_games={"1": 4, "2": 4})
        rng = random.Random(1)
        self.assertIsNone(select_league_ccg_pair("Pac-12", ["1", "2"], cs, rng))

    def test_sun_belt_division_champions(self) -> None:
        div = load_sun_belt_divisions(season_year=2026)
        self.assertIn("256", div)
        self.assertEqual(div["256"], "East")

        cs = ConferenceStandings(conference="Sun Belt")
        east = [t for t, d in div.items() if d == "East"][:2]
        west = [t for t, d in div.items() if d == "West"][:2]
        for tid in east + west:
            cs.conf_games[tid] = 8
            cs.conf_wins[tid] = 6 if tid == east[0] or tid == west[0] else 4
            cs.div_games[tid] = 6
            cs.div_wins[tid] = 5 if tid == east[0] or tid == west[0] else 3
            cs.overall_margin[tid] = float(cs.conf_wins[tid])
            cs.resume_margin[tid] = float(cs.conf_wins[tid])
        sim = SimColStandings(sim_col="sim_0001", by_conference={"Sun Belt": cs})
        eligible = east + west
        rng = random.Random(7)
        pair = select_ccg_participants(
            "Sun Belt",
            eligible,
            sim,
            div,
            rng,
        )
        self.assertIsNotNone(pair)
        assert pair is not None
        self.assertEqual(pair[0], east[0])
        self.assertEqual(pair[1], west[0])


if __name__ == "__main__":
    unittest.main()