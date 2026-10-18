#!/usr/bin/env python3
"""Unit tests for playoff eligibility selection."""

import csv
import tempfile
import unittest
from pathlib import Path

from cfb_g6_playoff_points import (
    compute_g6_playoff_points,
    points_for_team_sim,
)
from cfb_playoff_elig import (
    AT_LARGE_BIDS,
    GROUP_CONFERENCES,
    NOTRE_DAME_NAME,
    apply_g6_autobid_col,
    build_season_h2h_by_sim,
    compute_playoff_eligibility,
    eligibility_count,
    rank_at_large_candidates,
)


def make_rows(teams, wins_by_id, fieldnames=None):
    cols = fieldnames or ["team_id", "team_name", "conference", "sim_0001"]
    rows = []
    for t in teams:
        row = {k: "" for k in cols}
        row.update(t)
        row["sim_0001"] = str(wins_by_id.get(t["team_id"], 0))
        rows.append(row)
    return rows


def make_g6_points(teams, sim_col, points_by_id):
    out = {}
    for t in teams:
        if t["conference"] in GROUP_CONFERENCES:
            out[t["team_id"]] = {sim_col: points_by_id.get(t["team_id"], 0)}
    return out


def make_h2h(game_specs, sim_col="sim_0001"):
    """game_specs: list of (winner_id, loser_id) for one meeting each."""
    rows = []
    for w, loser in game_specs:
        rows.append(
            {
                "team_id": w,
                "opponent_id": loser,
                sim_col: "1",
            }
        )
        rows.append(
            {
                "team_id": loser,
                "opponent_id": w,
                sim_col: "0",
            }
        )
    h2h_w, h2h_g = build_season_h2h_by_sim(rows, [sim_col])
    return h2h_w, h2h_g


class TestPlayoffEligibility(unittest.TestCase):
    def test_field_size_always_twelve_minimal(self):
        teams = []
        tid = 1
        for conf in ("SEC", "Big Ten", "ACC", "Big 12"):
            for _ in range(6):
                teams.append(
                    {
                        "team_id": str(tid),
                        "team_name": f"Team {tid}",
                        "conference": conf,
                    }
                )
                tid += 1
        teams.append(
            {"team_id": "200", "team_name": "G6", "conference": "MAC"}
        )
        fieldnames = ["team_id", "team_name", "conference", "sim_0001"]
        wins = {t["team_id"]: 6 for t in teams}
        wins.update(
            {
                "1": 12,
                "7": 12,
                "13": 12,
                "19": 12,
                "2": 11,
                "3": 11,
                "4": 11,
                "5": 11,
                "6": 11,
                "8": 11,
                "9": 11,
                "10": 11,
                "200": 8,
            }
        )
        rows = make_rows(teams, wins, fieldnames)
        conf_champs = {
            "sim_0001": {
                "SEC": "1",
                "Big Ten": "7",
                "ACC": "13",
                "Big 12": "19",
            }
        }
        sos = {t["team_id"]: float(tid) for t in teams}
        fpi = {t["team_id"]: {"sim_0001": 0.0} for t in teams}
        g6_pts = make_g6_points(teams, "sim_0001", {"200": 50})

        out = compute_playoff_eligibility(
            rows, fieldnames, fpi, conf_champs, sos, g6_pts
        )
        self.assertEqual(eligibility_count(out, "sim_0001"), 12)

    def test_p4_and_g6_autobids_plus_seven(self):
        teams = [
            {"team_id": "1", "team_name": "SEC", "conference": "SEC"},
            {"team_id": "2", "team_name": "BT", "conference": "Big Ten"},
            {"team_id": "3", "team_name": "ACC", "conference": "ACC"},
            {"team_id": "4", "team_name": "B12", "conference": "Big 12"},
            {"team_id": "5", "team_name": "G6", "conference": "MAC"},
        ]
        for i in range(6, 20):
            teams.append(
                {
                    "team_id": str(i),
                    "team_name": f"T{i}",
                    "conference": "SEC",
                }
            )
        fieldnames = ["team_id", "team_name", "conference", "sim_0001"]
        wins = {t["team_id"]: 10 for t in teams}
        wins.update({"1": 9, "2": 9, "3": 9, "4": 9, "5": 7, "6": 12, "7": 11})
        rows = make_rows(teams, wins, fieldnames)
        champs = {
            "sim_0001": {
                "SEC": "1",
                "Big Ten": "2",
                "ACC": "3",
                "Big 12": "4",
            }
        }
        sos = {t["team_id"]: float(i) for i, t in enumerate(teams)}
        g6_pts = make_g6_points(teams, "sim_0001", {"5": 20})
        out = compute_playoff_eligibility(
            rows, fieldnames, {}, champs, sos, g6_pts
        )
        self.assertEqual(int(out[0]["sim_0001"]), 1)
        self.assertEqual(int(out[4]["sim_0001"]), 1)
        self.assertEqual(eligibility_count(out, "sim_0001"), 12)

    def test_at_large_order_wins_then_sos(self):
        source = [
            {"team_id": "1", "team_name": "A", "conference": "SEC", "sim_0001": "11"},
            {"team_id": "2", "team_name": "B", "conference": "SEC", "sim_0001": "10"},
            {"team_id": "3", "team_name": "C", "conference": "SEC", "sim_0001": "10"},
        ]
        sos = {"1": 1.0, "2": 5.0, "3": 2.0}
        ranked = rank_at_large_candidates(source, "sim_0001", sos, {"sim_0001": {}})
        self.assertEqual(ranked[0], 0)
        self.assertEqual(ranked[1], 1)
        self.assertEqual(ranked[2], 2)

    def test_h2h_sweep_moves_team_up(self):
        source = [
            {"team_id": "1", "team_name": "A", "conference": "SEC", "sim_0001": "10"},
            {"team_id": "2", "team_name": "B", "conference": "SEC", "sim_0001": "10"},
        ]
        sos = {"1": 1.0, "2": 5.0}
        h2h_w, h2h_g = make_h2h([("2", "1")])
        ranked = rank_at_large_candidates(
            source, "sim_0001", sos, {"sim_0001": {}}, h2h_w, h2h_g
        )
        self.assertEqual(ranked[0], 1)

    def test_h2h_three_cycle_uses_sos_only(self):
        source = [
            {"team_id": "1", "team_name": "A", "conference": "SEC", "sim_0001": "10"},
            {"team_id": "2", "team_name": "B", "conference": "SEC", "sim_0001": "10"},
            {"team_id": "3", "team_name": "C", "conference": "SEC", "sim_0001": "10"},
        ]
        sos = {"1": 1.0, "2": 2.0, "3": 3.0}
        h2h_w, h2h_g = make_h2h([("1", "2"), ("2", "3"), ("3", "1")])
        ranked = rank_at_large_candidates(
            source, "sim_0001", sos, {"sim_0001": {}}, h2h_w, h2h_g
        )
        self.assertEqual(ranked, [2, 1, 0])

    def test_conf_champ_same_wins_same_league(self):
        source = [
            {"team_id": "1", "team_name": "Champ", "conference": "SEC", "sim_0001": "10"},
            {"team_id": "2", "team_name": "Other", "conference": "SEC", "sim_0001": "10"},
        ]
        sos = {"1": 1.0, "2": 5.0}
        champs = {"sim_0001": {"SEC": "1"}}
        ranked = rank_at_large_candidates(source, "sim_0001", sos, champs)
        self.assertEqual(ranked[0], 0)

    def test_notre_dame_no_auto_bid(self):
        teams = []
        for i in range(1, 25):
            conf = ["SEC", "Big Ten", "ACC", "Big 12"][i % 4]
            teams.append(
                {"team_id": str(i), "team_name": f"T{i}", "conference": conf}
            )
        teams.append(
            {
                "team_id": "87",
                "team_name": NOTRE_DAME_NAME,
                "conference": "FBS Indep.",
            }
        )
        teams.append({"team_id": "200", "team_name": "G6", "conference": "MAC"})
        fieldnames = ["team_id", "team_name", "conference", "sim_0001"]
        wins = {t["team_id"]: 8 for t in teams}
        wins.update(
            {
                "1": 12,
                "2": 12,
                "3": 12,
                "4": 12,
                "87": 11,
                "5": 12,
                "6": 12,
                "7": 12,
                "8": 12,
                "9": 12,
                "10": 12,
                "11": 12,
                "200": 6,
            }
        )
        rows = make_rows(teams, wins, fieldnames)
        champs = {
            "sim_0001": {
                "SEC": "1",
                "Big Ten": "2",
                "ACC": "3",
                "Big 12": "4",
            }
        }
        sos = {t["team_id"]: float(i) for i, t in enumerate(teams)}
        g6_pts = make_g6_points(teams, "sim_0001", {"200": 99})
        out = compute_playoff_eligibility(
            rows, fieldnames, {}, champs, sos, g6_pts
        )
        nd_row = next(r for r in out if r["team_id"] == "87")
        self.assertEqual(int(nd_row["sim_0001"]), 0)


class TestG6PlayoffPoints(unittest.TestCase):
    def test_scoring_components(self):
        conf_by_team = {
            "100": "American",
            "200": "SEC",
            "41": "FBS Indep.",
        }
        games = [
            {"opponent_id": "200", "sim_0001": "1"},
            {"opponent_id": "41", "sim_0001": "1"},
        ]
        champs = {"sim_0001": {"American": "100"}}
        pts = points_for_team_sim(
            "100", "American", games, "sim_0001", conf_by_team, champs
        )
        self.assertEqual(pts, 4)

    def test_uconn_win_no_extra_bonus(self):
        conf_by_team = {"100": "MAC", "41": "FBS Indep."}
        games = [{"opponent_id": "41", "sim_0001": "1"}]
        pts = points_for_team_sim(
            "100", "MAC", games, "sim_0001", conf_by_team, {"sim_0001": {}}
        )
        self.assertEqual(pts, 1)

    def test_g6_autobid_picks_highest_points(self):
        source = [
            {"team_id": "10", "team_name": "A", "conference": "MAC"},
            {"team_id": "11", "team_name": "B", "conference": "American"},
        ]
        output = [
            {"team_id": "10", "conference": "MAC", "sim_0001": 0},
            {"team_id": "11", "conference": "American", "sim_0001": 0},
        ]
        g6_pts = {"10": {"sim_0001": 5}, "11": {"sim_0001": 12}}
        sos = {"10": 0.0, "11": 0.0}
        apply_g6_autobid_col(output, source, "sim_0001", g6_pts, sos)
        self.assertEqual(int(output[0]["sim_0001"]), 0)
        self.assertEqual(int(output[1]["sim_0001"]), 1)

    def test_g6_autobid_sos_tiebreak(self):
        source = [
            {"team_id": "10", "team_name": "A", "conference": "MAC"},
            {"team_id": "11", "team_name": "B", "conference": "Sun Belt"},
        ]
        output = [
            {"team_id": "10", "conference": "MAC", "sim_0001": 0},
            {"team_id": "11", "conference": "Sun Belt", "sim_0001": 0},
        ]
        g6_pts = {"10": {"sim_0001": 8}, "11": {"sim_0001": 8}}
        sos = {"10": 1.0, "11": 5.0}
        apply_g6_autobid_col(output, source, "sim_0001", g6_pts, sos)
        self.assertEqual(int(output[1]["sim_0001"]), 1)

    def test_compute_from_games_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf_path = Path(tmp) / "conf.csv"
            games_path = Path(tmp) / "games.csv"
            with conf_path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["team_id", "team_name", "conference"])
                writer.writerow(["100", "G6 Team", "American"])
                writer.writerow(["200", "P4 Team", "SEC"])
            with games_path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "team_id",
                        "team_name",
                        "opponent_id",
                        "sim_0001",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "team_id": "100",
                        "team_name": "G6 Team",
                        "opponent_id": "200",
                        "sim_0001": "1",
                    }
                )
            champs = {"sim_0001": {"American": "100"}}
            _, rows = compute_g6_playoff_points(games_path, conf_path, champs)
            row = next(r for r in rows if r["team_id"] == "100")
            self.assertEqual(int(row["sim_0001"]), 3)


if __name__ == "__main__":
    unittest.main()
