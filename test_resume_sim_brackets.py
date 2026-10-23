#!/usr/bin/env python3
"""Resume playoff sims (1001+) must ship per-sim JSON for bracket lookup."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from app import APP_DIR, create_app

DATA_DIR = APP_DIR / "data"


class ResumeSimBracketFilesTests(unittest.TestCase):
    def test_resume_sim_json_tracked_for_deploy(self) -> None:
        meta = json.loads((DATA_DIR / "meta.json").read_text(encoding="utf-8"))
        resume_count = int(meta.get("resume_playoff_sim_count") or 0)
        if resume_count <= 0:
            self.skipTest("no resume playoff sims in export")
        trad = int(meta.get("traditional_sim_count") or 1000)
        first_resume = trad + 1
        path = DATA_DIR / "sim" / f"{first_resume:04d}.json"
        self.assertTrue(
            path.is_file(),
            f"missing {path.name}; resume brackets need per-sim files in git",
        )

    def test_bracket_page_loads_resume_sim(self) -> None:
        meta = json.loads((DATA_DIR / "meta.json").read_text(encoding="utf-8"))
        if not meta.get("resume_playoff_sim_count"):
            self.skipTest("no resume playoff sims")
        trad = int(meta.get("traditional_sim_count") or 1000)
        sim = trad + 1
        client = create_app().test_client()
        response = client.get(f"/bracket?sim={sim}")
        self.assertEqual(response.status_code, 200)
        body = response.data.decode()
        self.assertIn("bracket-layout", body)
        self.assertNotIn("Bracket data not available", body)


if __name__ == "__main__":
    unittest.main()
