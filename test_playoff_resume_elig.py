#!/usr/bin/env python3
"""Tests for resume-based playoff selection."""

import unittest

from cfb_playoff_elig import NOTRE_DAME_NAME
from cfb_playoff_resume_elig import (
    compute_column_eligibility_resume,
    paired_game_sim_col,
    paired_resume_elig_col,
    resume_bid_blocked_four_loss_non_champ,
    seed_playoff_indices_resume_col,
)


def _rows(teams: list[dict], wins: dict[str, int], cols: list[str]) -> list[dict]:
    out = []
    for t in teams:
        row = {
            "team_id": t["team_id"],
            "team_name": t["team_name"],
            "conference": t["conference"],
        }
        for c in cols:
            row[c] = str(wins.get(t["team_id"], 0))
        out.append(row)
    return out


class TestResumePlayoffElig(unittest.TestCase):
    def test_paired_columns(self):
        self.assertEqual(paired_resume_elig_col("sim_0001"), "sim_1001")
        self.assertEqual(paired_game_sim_col("sim_1001"), "sim_0001")

    def test_twelve_team_field_and_g6_seed_twelve(self):
        teams = []
        tid = 1
        for conf in ("SEC", "Big Ten", "ACC", "Big 12"):
            for _ in range(3):
                teams.append(
                    {
                        "team_id": str(tid),
                        "team_name": f"P4 {tid}",
                        "conference": conf,
                    }
                )
                tid += 1
        teams.append(
            {"team_id": "200", "team_name": "G6 Team", "conference": "MAC"}
        )
        while len(teams) < 20:
            teams.append(
                {
                    "team_id": str(tid),
                    "team_name": f"Other {tid}",
                    "conference": "SEC",
                }
            )
            tid += 1
        cols = ["sim_0001", "sim_1001"]
        wins = {t["team_id"]: 8 for t in teams}
        wins.update({"1": 12, "4": 12, "7": 12, "10": 12, "200": 6})
        source = _rows(teams, wins, ["sim_0001"])
        out = _rows(teams, wins, cols)
        margins = {t["team_id"]: float(i) for i, t in enumerate(teams)}
        margins["200"] = 50.0
        champs = {
            "sim_0001": {
                "SEC": "1",
                "Big Ten": "4",
                "ACC": "7",
                "Big 12": "10",
            }
        }
        compute_column_eligibility_resume(
            out,
            source,
            "sim_1001",
            margins,
            champs,
            {},
            "sim_0001",
        )
        elig_count = sum(int(r["sim_1001"]) for r in out)
        self.assertEqual(elig_count, 12)
        elig_by_team = {
            (r["team_id"]): int(r["sim_1001"]) for r in out if r.get("team_id")
        }
        seeds = seed_playoff_indices_resume_col(source, elig_by_team, margins)
        self.assertIsNotNone(seeds)
        self.assertEqual(len(seeds), 12)
        g6_idx = next(i for i, t in enumerate(teams) if t["team_id"] == "200")
        self.assertEqual(seeds[-1], g6_idx)

    def test_four_loss_at_large_blocked_conf_champ_ok(self):
        teams = [
            {"team_id": "1", "team_name": "SEC Champ", "conference": "SEC"},
            {"team_id": "2", "team_name": "Four Loss", "conference": "SEC"},
            {"team_id": "3", "team_name": "Filler", "conference": "Big Ten"},
        ]
        for n in range(4, 20):
            teams.append(
                {
                    "team_id": str(n),
                    "team_name": f"T{n}",
                    "conference": "Big Ten",
                }
            )
        cols = ["sim_0001", "sim_1001"]
        wins = {t["team_id"]: 8 for t in teams}
        wins["1"] = 8
        wins["2"] = 8
        source = _rows(teams, wins, ["sim_0001"])
        out = _rows(teams, wins, cols)
        margins = {t["team_id"]: float(100 - int(t["team_id"])) for t in teams}
        margins["2"] = 99.0
        champs = {"sim_0001": {"SEC": "1"}}
        losses = {t["team_id"]: 3 for t in teams}
        losses["2"] = 4
        compute_column_eligibility_resume(
            out,
            source,
            "sim_1001",
            margins,
            champs,
            {},
            "sim_0001",
            losses,
        )
        elig = {r["team_id"]: int(r["sim_1001"]) for r in out}
        self.assertEqual(elig["2"], 0)
        self.assertTrue(
            resume_bid_blocked_four_loss_non_champ("2", 4, "sim_0001", champs)
        )
        losses["1"] = 4
        compute_column_eligibility_resume(
            out,
            source,
            "sim_1001",
            margins,
            champs,
            {},
            "sim_0001",
            losses,
        )
        elig = {r["team_id"]: int(r["sim_1001"]) for r in out}
        self.assertEqual(elig["1"], 1)


if __name__ == "__main__":
    unittest.main()
