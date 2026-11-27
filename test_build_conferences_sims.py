#!/usr/bin/env python3
"""Conference rollup uses full sim pool for field representation."""

from __future__ import annotations

import unittest

from export_sim_data import build_conferences


class BuildConferencesSimsTests(unittest.TestCase):
    def test_avg_teams_in_field_uses_all_columns(self) -> None:
        teams = [
            {"team_id": "1", "team_name": "A", "conference": "SEC", "avg_wins": 10.0},
            {"team_id": "2", "team_name": "B", "conference": "SEC", "avg_wins": 9.0},
        ]
        leaderboard = [
            {
                "team_id": "1",
                "title_odds_pct": 10.0,
                "resume_title_odds_pct": 20.0,
                "playoff_appearances": 100,
                "resume_playoff_appearances": 50,
                "eligibility_pct": 40.0,
                "resume_playoff_eligibility_pct": 60.0,
                "conf_champ_odds_pct": 30.0,
                "conf_champ_appearances": 200,
                "overall_margin": 5.0,
            },
            {
                "team_id": "2",
                "title_odds_pct": 2.0,
                "resume_title_odds_pct": 4.0,
                "playoff_appearances": 0,
                "resume_playoff_appearances": 0,
                "eligibility_pct": 0.0,
                "resume_playoff_eligibility_pct": 0.0,
                "conf_champ_odds_pct": 0.0,
                "conf_champ_appearances": 0,
                "overall_margin": 1.0,
            },
        ]
        # Per sim: 1, 1, 2, 2 conference members -> avg 1.5
        fields = [["1"], ["1"], ["1", "2"], ["1", "2"]]
        confs = build_conferences(teams, leaderboard, fields, n_sims=4)
        sec = next(c for c in confs if c["conference"] == "SEC")
        self.assertEqual(sec["avg_teams_in_field"], 1.5)
        self.assertEqual(sec["total_title_odds_pct"], 18.0)
        self.assertEqual(sec["total_playoff_appearances"], 150)
        self.assertNotIn("sims_with_member", sec)


if __name__ == "__main__":
    unittest.main()