# In-Season Rankings & Simulation Pipeline

Full guide for weekly CFB Allen Ratings updates. Live site: [cfballenratings.onrender.com](https://cfballenratings.onrender.com).

## Quick command

From the repo root:

```powershell
python update_in_season_weekly.py
```

| Flag | Effect |
|------|--------|
| `--skip-refresh` | Skip ESPN score refresh |
| `--skip-sims` | Skip Monte Carlo sims — Fcst Wins / Playoff % / Title % stay stale |
| `--simulations N` | Monte Carlo count (default **1000**) |

## Pipeline order

`update_in_season_weekly.py` runs:

1. **Refresh scores** — `refresh_2026_schedule_scores.py` (updates `cfb_2026_fbs_games_with_fpi.csv` in place; preserves sim columns; fetches real yards)
2. **Weekly rankings** — `compute_in_season_rankings.py` (Overall margins seed sim FPI draws)
3. **In-season sims** — `run_in_season_sim_pipeline.py --skip-refresh` (1k seasons; pins completed games)
4. **Validate** — `validate_in_season_sim_overall.py` (sim FPI μ matches Overall)
5. **Export** — `export_in_season_data.py` → `data/*.json` for Render

## Data layout

Large CSV inputs/outputs default to the **parent** of this repo. Override with:

```powershell
$env:CFB_DATA_ROOT = "C:\path\to\data"
```

Required under `CFB_DATA_ROOT`:

| File | Role |
|------|------|
| `cfb_2026_fbs_games_with_fpi.csv` | Master schedule + scores |
| `cfb_2026_in_season_weekly_rankings.csv` | Stacked weekly rankings |
| `cfb_2026_in_season_*.csv` | Sim pipeline outputs |
| `Preseason_2026_blended.csv` | Preseason combined_FPI |
| `espn_cfb_teams_conferences.csv` | Team metadata |

`cfb_game_corrections.json` ships in the repo for manual score/yard overrides.

## Overall rating

Primary sort and sim FPI base. Let `n` = FBS games played:

| Games | Overall blend |
|-------|----------------|
| 0 | 100% preseason |
| 1–4 | Preseason + Opp Adj + No Preseason (5% each per game, with early-season Opp Adj boost) |
| 5–9 | Preseason fades; Opp Adj drops out; No Preseason ramps to 100% |
| 10+ | 100% No Preseason (algorithm margin) |

### Opp Adj (middle component)

Stored in CSV/JSON as `some_preseason_margin`. The viewer UI still labels this column **Some Preseason** until a future rename.

Opp Adj is the mean per-game **residual vs expectation**, using stabilized opponent strength (not the noisy in-season algorithm rating):

1. **Pilot overall** (circularity guard): `w_pre * preseason + w_algo * no_preseason` — omits Opp Adj from the blend used to rate opponents.
2. **Stable opponent strength**: `anchor * preseason + (1 - anchor) * pilot_overall`, where `anchor` runs from 100% preseason at 0 FBS games to 40% preseason at 6+ games.
3. **Per-game actual**: `(point_margin + 0.25 * yard_margin / 15.5) / 8`
4. **Per-game expected**: `(team_strength - opp_strength + HFA) / 8` (+3 home / -3 away / 0 neutral)
5. **Residual**: `actual - expected`; team Opp Adj = mean of residuals (no clamp). Teams with 0 FBS games use preseason.

Implementation: [`cfb_rating/opp_adjust.py`](cfb_rating/opp_adjust.py).

## Preseason fade (Blended column)

`preseason_weight = (10 - min(games_played, 10)) / 10`

```
blended_margin = pre_wt * preseason + (1 - pre_wt) * algorithm_margin
```

| FBS games | Preseason wt | Algorithm wt |
|-----------|-------------|--------------|
| 0 | 100% | 0% |
| 5 | 50% | 50% |
| 10+ | 0% | 100% |

## Deploy

```powershell
git add data/*.json data/sim/
git commit -m "Update in-season data for week N"
git push
```

Render auto-redeploys from committed `data/` JSON.

## Pipeline scripts (in this repo)

| Script | Role |
|--------|------|
| `update_in_season_weekly.py` | Orchestrator |
| `refresh_2026_schedule_scores.py` | ESPN scores + yards |
| `compute_in_season_rankings.py` | Weekly rankings |
| `run_in_season_sim_pipeline.py` | Monte Carlo sim stack |
| `add_fpi_sim_columns.py` | Per-season FPI draws |
| `add_sim_margins_preseason_simulation.py` | Expected margins |
| `simulate_cfb_games_preseason_simulation.py` | Game outcomes |
| `team_simulation_records.py` | Win totals |
| `cfb_conf_championship_odds.py` | Conf title odds |
| `cfb_2026_FBS_playoff_elig_v2.py` | Playoff eligibility |
| `cfb_playoff_odds_calc.py` | National title odds |
| `export_in_season_data.py` | Viewer JSON export |

Shared libraries: `cfb_playoff_elig.py`, `cfb_playoff_odds.py`, `cfb_conf_championship.py`, `cfb_g6_playoff_points.py`, `cfb_espn_summary.py`, `cfb_game_corrections.py`, `cfb_rating/`.
