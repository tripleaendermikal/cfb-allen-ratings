"""Shared paths for in-season pipeline scripts."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("CFB_DATA_ROOT", str(REPO_ROOT.parent)))
DATA_DIR = REPO_ROOT / "data"

IN_SEASON_PREFIX = "cfb_2026_in_season"
SIM_COUNT = 1000
FPI_SIGMA = 7.3

GAMES_BASE = DATA_ROOT / "cfb_2026_fbs_games_with_fpi.csv"
GAMES_FPI = DATA_ROOT / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi.csv"
GAMES_MARGIN = DATA_ROOT / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi_margin.csv"
GAMES_SIM = DATA_ROOT / f"{IN_SEASON_PREFIX}_fbs_games_with_fpi_simulated.csv"
TEAM_RECORDS = DATA_ROOT / f"{IN_SEASON_PREFIX}_fbs_team_sim_records_v2.csv"
CONF_ODDS = DATA_ROOT / f"{IN_SEASON_PREFIX}_FBS_conf_champ_odds.csv"
PLAYOFF_ELIG = DATA_ROOT / f"{IN_SEASON_PREFIX}_FBS_playoff_elig_v2.csv"
PLAYOFF_ELIG_PCT = DATA_ROOT / f"{IN_SEASON_PREFIX}_FBS_playoff_elig_pct.csv"
TITLE_ODDS = DATA_ROOT / f"{IN_SEASON_PREFIX}_FBS_playoff_champ_odds_fpi_seed.csv"
RANKINGS_CSV = DATA_ROOT / f"{IN_SEASON_PREFIX}_weekly_rankings.csv"
CONF_CSV = DATA_ROOT / "espn_cfb_teams_conferences.csv"
PRESEASON_CSV = DATA_ROOT / "Preseason_2026_blended.csv"
