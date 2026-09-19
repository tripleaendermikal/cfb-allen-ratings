#!/usr/bin/env python3
"""All-in-one in-season refresh: scores, sims, rankings, JSON export."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("CFB_DATA_ROOT", str(REPO_ROOT.parent)))
PYTHON = sys.executable


def run_step(label: str, cmd: list[str]) -> None:
    print(f"\n==> {label}")
    print("    " + " ".join(str(part) for part in cmd))
    env = os.environ.copy()
    env["CFB_DATA_ROOT"] = str(DATA_ROOT)
    env["PYTHONPATH"] = str(REPO_ROOT) + (f":{env['PYTHONPATH']}" if env.get("PYTHONPATH") else "")
    subprocess.run(cmd, cwd=REPO_ROOT, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-refresh", action="store_true")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    env = os.environ.copy()
    env["CFB_DATA_ROOT"] = str(DATA_ROOT)

    def run(cmd: list[str], label: str) -> None:
        run_step(label, cmd)

    run(
        [PYTHON, str(REPO_ROOT / "pipeline" / "reconstruct_csvs.py")],
        "Reconstruct pipeline CSV inputs from committed JSON",
    )

    if not args.skip_refresh:
        run(
            [PYTHON, str(REPO_ROOT / "pipeline" / "refresh_espn_scores.py")],
            "Refresh ESPN scores",
        )

    run(
        [PYTHON, str(REPO_ROOT / "compute_in_season_rankings.py")],
        "Compute weekly rankings",
    )

    sim_cmd = [
        PYTHON,
        str(REPO_ROOT / "pipeline" / "run_in_season_sim_pipeline.py"),
        "--skip-refresh",
        "--seed",
        str(args.seed),
    ]
    run(sim_cmd, "In-season simulation pipeline")

    run(
        [PYTHON, str(REPO_ROOT / "compute_in_season_rankings.py")],
        "Recompute rankings after simulations",
    )
    run(
        [PYTHON, str(REPO_ROOT / "export_in_season_data.py")],
        "Export viewer JSON",
    )
    print("\nWeekly in-season refresh complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
