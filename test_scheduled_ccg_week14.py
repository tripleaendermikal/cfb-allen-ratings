#!/usr/bin/env python3
"""Tests for ESPN week-14 scheduled conference championship deduplication."""

import csv
import tempfile
import unittest
from pathlib import Path

from cfb_conf_championship import (
    apply_ccg_win_deltas_to_wins,
    load_conference_lookup,
    load_scheduled_ccg_by_conference,
    compute_conf_results_by_sim,
)
from export_sim_data import build_sim_records_by_team_col


class TestScheduledCcgWeek14(unittest.TestCase):
    def test_load_resolved_week14_ccg(self):
        with tempfile.TemporaryDirectory() as td:
            games = Path(td) / "games.csv"
            conf = Path(td) / "conf.csv"
            conf.write_text(
                "team_id,team_name,conference\n"
                "68,Boise State,Pac-12\n"
                "254,Utah,Pac-12\n",
                encoding="utf-8",
            )
            games.write_text(
                "game_id,week,home_away,team_id,team_name,opponent_id,opponent_name\n"
                "401860999,14,home,68,Boise State,254,Utah\n"
                "401860999,14,away,254,Utah,68,Boise State\n",
                encoding="utf-8",
            )
            conf_by_id, _, _ = load_conference_lookup(conf)
            scheduled = load_scheduled_ccg_by_conference(games, conf_by_id)
            self.assertIn("Pac-12", scheduled)
            self.assertTrue(scheduled["Pac-12"].resolved)

    def test_resolved_ccg_no_synthetic_win_delta(self):
        wins = {"68": {"sim_0001": 11}, "254": {"sim_0001": 10}}
        finalists = {"sim_0001": {"Pac-12": ["68", "254"]}}
        champions = {"sim_0001": {"Pac-12": "68"}}
        apply_ccg_win_deltas_to_wins(
            wins,
            champions,
            finalists,
            ["sim_0001"],
            skip_confs_with_scheduled_ccg=frozenset({"Pac-12"}),
        )
        self.assertEqual(wins["68"]["sim_0001"], 11)

    def test_resolved_ccg_game_count_not_doubled(self):
        records_rows = [
            {"team_id": "68", "sim_0001": "12"},
            {"team_id": "254", "sim_0001": "11"},
        ]
        game_rows = [{"team_id": "68", "game_id": f"g{i}", "sim_0001": "1"} for i in range(11)]
        game_rows += [
            {"team_id": "68", "game_id": "ccg", "sim_0001": "1"},
            {"team_id": "254", "game_id": "ccg", "sim_0001": "0"},
        ]
        game_rows += [{"team_id": "254", "game_id": f"g{i}", "sim_0001": "1"} for i in range(11)]
        finalists = {"sim_0001": {"Pac-12": ["68", "254"]}}
        champions = {"sim_0001": {"Pac-12": "68"}}
        conf_by_id = {"68": "Pac-12", "254": "Pac-12"}
        by_team = build_sim_records_by_team_col(
            records_rows,
            ["sim_0001"],
            game_rows,
            champions,
            finalists,
            conf_by_id=conf_by_id,
            skip_confs_with_scheduled_ccg=frozenset({"Pac-12"}),
        )
        self.assertEqual(by_team["68"]["sim_0001"], (12, 0))

    def test_compute_conf_results_uses_scheduled_ccg_winner(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            conf = td_path / "conf.csv"
            games_fpi = td_path / "games_fpi.csv"
            sim = td_path / "sim.csv"
            conf.write_text(
                "team_id,team_name,conference\n"
                "1,TeamA,TestConf\n"
                "2,TeamB,TestConf\n",
                encoding="utf-8",
            )
            games_fpi.write_text(
                "game_id,week,home_away,team_id,team_name,opponent_id,"
                "opponent_name,sim_0001\n"
                "ccg14,14,home,1,TeamA,2,TeamB,10.0\n"
                "ccg14,14,away,2,TeamB,1,TeamA,5.0\n",
                encoding="utf-8",
            )
            rows = [
                {
                    "game_id": "reg1",
                    "team_id": "1",
                    "opponent_id": "2",
                    "sim_0001": "1",
                    "week": "1",
                },
                {
                    "game_id": "reg1",
                    "team_id": "2",
                    "opponent_id": "1",
                    "sim_0001": "0",
                    "week": "1",
                },
                {
                    "game_id": "ccg14",
                    "team_id": "1",
                    "opponent_id": "2",
                    "sim_0001": "0",
                    "week": "14",
                },
                {
                    "game_id": "ccg14",
                    "team_id": "2",
                    "opponent_id": "1",
                    "sim_0001": "1",
                    "week": "14",
                },
            ]
            with sim.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "game_id",
                        "team_id",
                        "opponent_id",
                        "sim_0001",
                        "week",
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)

            results = compute_conf_results_by_sim(sim, games_fpi, conf)
            self.assertIn("TestConf", results["scheduled_ccg_resolved_confs"])
            self.assertEqual(results["champions"]["sim_0001"]["TestConf"], "2")


if __name__ == "__main__":
    unittest.main()