#!/usr/bin/env python3
"""Field analysis export uses full sim count."""

import unittest

from export_sim_data import build_field_analysis


class TestFieldAnalysisExport(unittest.TestCase):
    def test_build_field_analysis_includes_sim_count(self):
        fields = [["1", "2"], ["1", "3"], ["2", "3"]]
        id_to_name = {"1": "A", "2": "B", "3": "C"}
        conf = {"1": "SEC", "2": "SEC", "3": "MAC"}
        out = build_field_analysis(fields, id_to_name, 3, conf)
        self.assertEqual(out["sim_count"], 3)
        self.assertEqual(out["top_teams"][0]["count"], 2)
        self.assertEqual(out["top_teams"][0]["pct"], round(2 / 3 * 100, 2))


if __name__ == "__main__":
    unittest.main()
