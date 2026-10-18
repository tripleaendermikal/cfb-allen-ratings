#!/usr/bin/env python3
"""Tests for conference championship game record adjustments."""

import unittest

from cfb_conf_championship import apply_ccg_win_deltas_to_wins, ccg_participants_by_col
from export_sim_data import build_sim_records_by_team_col


class TestCcgRecords(unittest.TestCase):
    def test_ccg_participants(self):
        finalists = {
            "sim_0001": {"SEC": ["1", "2"], "ACC": ["3", "4"]},
        }
        parts = ccg_participants_by_col(finalists, ["sim_0001"])
        self.assertEqual(parts["sim_0001"], {"1", "2", "3", "4"})

    def test_apply_ccg_win_delta(self):
        wins = {"10": {"sim_0001": 11}}
        apply_ccg_win_deltas_to_wins(
            wins,
            {"sim_0001": {"SEC": "10"}},
            {"sim_0001": {"SEC": ["10", "20"]}},
            ["sim_0001"],
        )
        self.assertEqual(wins["10"]["sim_0001"], 12)
        self.assertEqual(wins.get("20", {}).get("sim_0001", 11), 11)

    def test_build_sim_records_includes_ccg_loss(self):
        records_rows = [
            {"team_id": "1", "sim_0001": "13"},
            {"team_id": "2", "sim_0001": "12"},
        ]
        game_rows = [{"team_id": "1", "sim_0001": "1"} for _ in range(12)]
        game_rows += [{"team_id": "2", "sim_0001": "1"} for _ in range(12)]
        finalists = {"sim_0001": {"SEC": ["1", "2"]}}
        champions = {"sim_0001": {"SEC": "1"}}
        by_team = build_sim_records_by_team_col(
            records_rows,
            ["sim_0001"],
            game_rows,
            champions,
            finalists,
        )
        self.assertEqual(by_team["1"]["sim_0001"], (13, 0))
        self.assertEqual(by_team["2"]["sim_0001"], (12, 1))


if __name__ == "__main__":
    unittest.main()
