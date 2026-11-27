"""Tests for power vs non-power classification by season."""

import unittest

from cfb_power_classification import (
    NOTRE_DAME_TEAM_ID,
    filter_rows_by_power,
    is_power_team,
    parse_power_filter,
)


class PowerClassificationTests(unittest.TestCase):
    def test_notre_dame_always_power(self) -> None:
        self.assertTrue(is_power_team(2026, "FBS Independents", NOTRE_DAME_TEAM_ID))
        self.assertTrue(is_power_team(2007, "FBS Independents", NOTRE_DAME_TEAM_ID))

    def test_2024_plus_power_four_only(self) -> None:
        self.assertTrue(is_power_team(2026, "SEC"))
        self.assertTrue(is_power_team(2024, "Big Ten"))
        self.assertFalse(is_power_team(2026, "Pac-12"))
        self.assertFalse(is_power_team(2026, "American"))
        self.assertFalse(is_power_team(2026, "Sun Belt"))

    def test_2014_through_2023_includes_pac12(self) -> None:
        self.assertTrue(is_power_team(2023, "Pac-12"))
        self.assertTrue(is_power_team(2018, "Pac-10"))
        self.assertFalse(is_power_team(2023, "American"))

    def test_before_2014_includes_aac_and_big_east(self) -> None:
        self.assertTrue(is_power_team(2013, "Pac-12"))
        self.assertTrue(is_power_team(2012, "American"))
        self.assertTrue(is_power_team(2011, "Big East"))
        self.assertFalse(is_power_team(2010, "Sun Belt"))

    def test_parse_power_filter(self) -> None:
        self.assertEqual(parse_power_filter(None), "")
        self.assertEqual(parse_power_filter("power"), "power")
        self.assertEqual(parse_power_filter("non-power"), "non_power")

    def test_filter_rows_renumbers(self) -> None:
        rows = [
            {"team_id": "1", "conference": "SEC", "display_rank": 1},
            {"team_id": "2", "conference": "Sun Belt", "display_rank": 2},
            {"team_id": NOTRE_DAME_TEAM_ID, "conference": "FBS Independents", "display_rank": 3},
        ]
        power_only = filter_rows_by_power(rows, 2026, "power")
        self.assertEqual(len(power_only), 2)
        self.assertEqual(power_only[0]["display_rank"], 1)
        self.assertEqual(power_only[1]["display_rank"], 2)


if __name__ == "__main__":
    unittest.main()