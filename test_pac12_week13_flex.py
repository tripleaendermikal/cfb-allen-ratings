#!/usr/bin/env python3
"""Tests for Pac-12 Week 13 flex placeholder cleanup."""

import unittest

from patch_pac12_week13_flex import should_remove_row
from pac12_week13 import FLEX_FLAG_COL, FLEX_FLAG_VALUE, PAC12_FLEX_OPPONENT_ID


class ShouldRemoveRowTests(unittest.TestCase):
    def test_removes_non_flex_placeholder_against_pac12_tbd(self) -> None:
        row = {
            "week": "13",
            "team_id": "68",
            "opponent_id": PAC12_FLEX_OPPONENT_ID,
            FLEX_FLAG_COL: "",
        }
        self.assertTrue(should_remove_row(row))

    def test_keeps_flex_row_against_pac12_tbd(self) -> None:
        row = {
            "week": "13",
            "team_id": "68",
            "opponent_id": PAC12_FLEX_OPPONENT_ID,
            FLEX_FLAG_COL: FLEX_FLAG_VALUE,
        }
        self.assertFalse(should_remove_row(row))


if __name__ == "__main__":
    unittest.main()
