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
    GROUP_CONFERENCES,
    NOTRE_DAME_NAME,
    apply_g6_autobid_col,
    compute_playoff_eligibility,
    eligibility_count,
    enforce_sec_big_ten_floor,
    fill_win_tiers_col,
    removable_for_trim,
    trim_overflow_col,
)


def make_rows(teams, wins_by_id, fieldnames=None):
    """teams: list of dicts with team_id, team_name, conference."""
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


class TestPlayoffEligibility(unittest.TestCase):
    def test_field_size_always_twelve_minimal(self):
        """Synthetic field produces exactly 12 eligible."""
        teams = []
        tid = 1
        for conf in ("SEC", "Big Ten", "ACC", "Big 12"):
            for _ in range(4):
                teams.append(
                    {
                        "team_id": str(tid),
                        "team_name": f"Team {tid}",
                        "conference": conf,
                    }
                )
                tid += 1
        for conf in ("MAC", "American"):
            teams.append(
                {"team_id": str(tid), "team_name": f"Team {tid}", "conference": conf}
            )
            tid += 1
        teams.append(
            {
                "team_id": "87",
                "team_name": NOTRE_DAME_NAME,
                "conference": "FBS Indep.",
            }
        )
        wins = {t["team_id"]: 8 for t in teams}
        wins.update(
            {
                "1": 12,
                "5": 12,
                "9": 12,
                "13": 12,
                "17": 11,
                "18": 10,
                "87": 11,
                "2": 11,
                "3": 10,
                "6": 10,
                "7": 9,
            }
        )

        fieldnames = ["team_id", "team_name", "conference", "sim_0001"]
        rows = make_rows(teams, wins, fieldnames)
        conf_champs = {
            "sim_0001": {
                "SEC": "1",
                "Big Ten": "5",
                "ACC": "9",
                "Big 12": "13",
            }
        }
        sos = {t["team_id"]: float(i) for i, t in enumerate(teams)}
        fpi = {t["team_id"]: {"sim_0001": float(i)} for i, t in enumerate(teams)}
        g6_pts = make_g6_points(teams, "sim_0001", {"17": 50, "18": 40})

        out = compute_playoff_eligibility(
            rows, fieldnames, fpi, conf_champs, sos, g6_pts
        )
        self.assertEqual(eligibility_count(out, "sim_0001"), 12)

    def test_notre_dame_ten_wins_gets_bid(self):
        teams = [
            {"team_id": "1", "team_name": "A", "conference": "SEC"},
            {
                "team_id": "87",
                "team_name": NOTRE_DAME_NAME,
                "conference": "FBS Indep.",
            },
        ]
        for extra_id in range(2, 20):
            conf = ["SEC", "Big Ten", "ACC", "Big 12"][extra_id % 4]
            teams.append(
                {
                    "team_id": str(extra_id),
                    "team_name": f"T{extra_id}",
                    "conference": conf,
                }
            )
        teams.append(
            {"team_id": "200", "team_name": "Boise", "conference": "Pac-12"}
        )
        fieldnames = ["team_id", "team_name", "conference", "sim_0001"]
        wins = {t["team_id"]: 7 + (int(t["team_id"]) % 5) for t in teams}
        wins["1"] = 12
        wins["87"] = 10
        rows = make_rows(teams, wins, fieldnames)
        champs = {
            "sim_0001": {
                "SEC": "1",
                "Big Ten": "2",
                "ACC": "3",
                "Big 12": "4",
            }
        }
        sos = {t["team_id"]: 0.0 for t in teams}
        fpi = {t["team_id"]: {"sim_0001": 0.0} for t in teams}
        g6_pts = make_g6_points(teams, "sim_0001", {"200": 30})
        out = compute_playoff_eligibility(rows, fieldnames, fpi, champs, sos, g6_pts)
        nd_row = next(r for r in out if r["team_name"] == NOTRE_DAME_NAME)
        self.assertEqual(int(nd_row["sim_0001"]), 1)

    def test_sos_tiebreak_sec_rule4(self):
        """Higher SOS wins when SEC wins are tied for rule 4 pool."""
        source = [
            {"team_id": "10", "team_name": "Low SOS", "conference": "SEC"},
            {"team_id": "11", "team_name": "High SOS", "conference": "SEC"},
        ]
        output = [
            {"team_id": "10", "team_name": "Low SOS", "conference": "SEC", "sim_0001": 0},
            {"team_id": "11", "team_name": "High SOS", "conference": "SEC", "sim_0001": 0},
        ]
        for row in source:
            row["sim_0001"] = "10"
        from cfb_playoff_elig import add_top_n_by_conference

        sos = {"10": 1.0, "11": 5.0}
        add_top_n_by_conference(output, source, "sim_0001", "SEC", 1, sos)
        self.assertEqual(int(output[1]["sim_0001"]), 1)
        self.assertEqual(int(output[0]["sim_0001"]), 0)

    def test_fill_tiers_stop_at_twelve(self):
        """Tier fill stops at 12 before advancing to the next tier."""
        source = []
        output = []
        for i in range(15):
            source.append(
                {
                    "team_id": str(i),
                    "team_name": f"T{i}",
                    "conference": "SEC",
                    "sim_0001": "10",
                }
            )
            output.append({"team_id": str(i), "sim_0001": 0})
        sos = {str(i): float(i) for i in range(15)}
        fill_win_tiers_col(output, source, "sim_0001", sos)
        self.assertEqual(eligibility_count(output, "sim_0001"), 12)

    def test_trim_sec_ten_win_non_champion(self):
        """Category 4 removes lowest-SOS SEC non-champion with exactly 10 wins."""
        source = [
            {"team_id": "1", "team_name": "Champ", "conference": "SEC"},
            {"team_id": "2", "team_name": "Low SOS", "conference": "SEC"},
            {"team_id": "3", "team_name": "Third SEC", "conference": "SEC"},
        ]
        for row in source:
            row["sim_0001"] = "10"
        output = [
            {
                "team_id": row["team_id"],
                "team_name": row["team_name"],
                "conference": row["conference"],
                "sim_0001": 1,
            }
            for row in source
        ]
        for i in range(4, 17):
            source.append(
                {
                    "team_id": str(i),
                    "team_name": f"F{i}",
                    "conference": "ACC",
                    "sim_0001": "11",
                }
            )
            output.append({"team_id": str(i), "sim_0001": 1})
        protected = {0}
        champs = {0}
        sos = {"1": 0.0, "2": 1.0, "3": 2.0}
        sos.update({str(i): 0.0 for i in range(4, 17)})
        trim_overflow_col(output, source, "sim_0001", sos, champs, protected)
        self.assertEqual(eligibility_count(output, "sim_0001"), 12)
        self.assertEqual(int(output[0]["sim_0001"]), 1)
        self.assertEqual(int(output[1]["sim_0001"]), 0)
        self.assertEqual(int(output[2]["sim_0001"]), 1)

    def test_trim_protects_rule_123_from_random(self):
        """Random trim category never removes rule 1-3 protected teams."""
        source = []
        output = []
        for i in range(13):
            source.append(
                {
                    "team_id": str(i),
                    "team_name": f"T{i}",
                    "conference": "ACC",
                    "sim_0001": "11",
                }
            )
            output.append({"team_id": str(i), "sim_0001": 1})
        protected = {0, 1, 2}
        champs = set()
        sos = {str(i): float(i) for i in range(13)}
        trim_overflow_col(output, source, "sim_0001", sos, champs, protected)
        self.assertEqual(eligibility_count(output, "sim_0001"), 12)
        for idx in protected:
            self.assertEqual(int(output[idx]["sim_0001"]), 1)


class TestG6PlayoffPoints(unittest.TestCase):
    def test_scoring_components(self):
        conf_by_team = {
            "100": "American",
            "200": "SEC",
            "41": "FBS Indep.",
        }
        games = [
            {
                "opponent_id": "200",
                "sim_0001": "1",
            },
            {
                "opponent_id": "41",
                "sim_0001": "1",
            },
        ]
        champs = {"sim_0001": {"American": "100"}}
        pts = points_for_team_sim(
            "100", "American", games, "sim_0001", conf_by_team, champs
        )
        # 2 wins + 1 non-G6 win (not UConn) + conf champ + American bonus
        self.assertEqual(pts, 5)

    def test_uconn_win_no_extra_bonus(self):
        conf_by_team = {"100": "MAC", "41": "FBS Indep."}
        games = [{"opponent_id": "41", "sim_0001": "1"}]
        pts = points_for_team_sim(
            "100", "MAC", games, "sim_0001", conf_by_team, {"sim_0001": {}}
        )
        # 1 win only (no non-G6 win bonus vs UConn)
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

    def test_removable_for_trim_allows_drop_to_two_sec(self):
        """Trim may remove a third SEC team when two would remain."""
        source = [
            {"team_id": "1", "team_name": "SEC A", "conference": "SEC"},
            {"team_id": "2", "team_name": "SEC B", "conference": "SEC"},
            {"team_id": "3", "team_name": "SEC C", "conference": "SEC"},
        ]
        for row in source:
            row["sim_0001"] = "10"
        output = [
            {"team_id": row["team_id"], "sim_0001": 1} for row in source
        ]
        sos = {"1": 3.0, "2": 2.0, "3": 1.0}
        safe = removable_for_trim(output, source, "sim_0001", [0, 1, 2])
        self.assertEqual(safe, [0, 1, 2])
        output_two = [
            {"team_id": "1", "sim_0001": 1},
            {"team_id": "2", "sim_0001": 1},
        ]
        source_two = source[:2]
        self.assertEqual(
            removable_for_trim(output_two, source_two, "sim_0001", [0, 1]), []
        )

    def test_enforce_sec_big_ten_floor_stops_at_two(self):
        """Floor backfills only until two SEC teams are in the field."""
        source = [
            {"team_id": "1", "team_name": "SEC A", "conference": "SEC"},
            {"team_id": "2", "team_name": "SEC B", "conference": "SEC"},
            {"team_id": "3", "team_name": "SEC C", "conference": "SEC"},
        ]
        for row in source:
            row["sim_0001"] = "10"
        output = [
            {"team_id": "1", "sim_0001": 1},
            {"team_id": "2", "sim_0001": 0},
            {"team_id": "3", "sim_0001": 0},
        ]
        sos = {"1": 3.0, "2": 2.0, "3": 1.0}
        enforce_sec_big_ten_floor(output, source, "sim_0001", sos)
        self.assertEqual(int(output[0]["sim_0001"]), 1)
        self.assertEqual(int(output[1]["sim_0001"]), 1)
        self.assertEqual(int(output[2]["sim_0001"]), 0)

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
            # 1 win + 1 non-G6 win + conf champ + American bonus
            self.assertEqual(int(row["sim_0001"]), 4)


if __name__ == "__main__":
    unittest.main()
