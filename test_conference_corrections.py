#!/usr/bin/env python3
"""Tests for manual conference overrides."""

import unittest

from cfb_conference_corrections import (
    apply_team_conference_override,
    patch_schedule_row_conferences,
)


class TestConferenceCorrections(unittest.TestCase):
    def test_louisiana_tech_sun_belt(self):
        self.assertEqual(
            apply_team_conference_override("2348", "CUSA"),
            "Sun Belt",
        )

    def test_patch_schedule_rows(self):
        rows = [
            {"team_id": "2348", "team_name": "Louisiana Tech Bulldogs", "conference": "CUSA"},
            {"team_id": "99", "team_name": "LSU Tigers", "conference": "SEC"},
        ]
        n = patch_schedule_row_conferences(rows, teams_csv=None)
        self.assertEqual(n, 1)
        self.assertEqual(rows[0]["conference"], "Sun Belt")
        self.assertEqual(rows[1]["conference"], "SEC")


if __name__ == "__main__":
    unittest.main()
