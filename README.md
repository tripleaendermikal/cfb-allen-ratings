# CFB Allen Ratings

In-season college football power rankings and Monte Carlo projections.

- **Live site:** [cfballenratings.onrender.com](https://cfballenratings.onrender.com)
- **Preseason viewer (separate repo):** [cfb-viewer.onrender.com](https://cfb-viewer.onrender.com)

This repo contains the Flask app, **full in-season pipeline**, export scripts, and committed `data/*.json` for Render.

**Pipeline guide:** [docs/IN_SEASON_RANKINGS.md](docs/IN_SEASON_RANKINGS.md)

## Repo layout

```
app.py, wsgi.py                Flask app
templates/, static/            UI
data/                          Exported JSON (committed; served on Render)
cfb_rating/                    Rankings algorithm package
update_in_season_weekly.py     End-to-end weekly orchestrator
run_in_season_sim_pipeline.py  Monte Carlo sim stack
refresh_2026_schedule_scores.py
compute_in_season_rankings.py
export_in_season_data.py       CSV → JSON export
cfb_playoff_*.py, cfb_conf_*.py  Playoff / conference helpers
cfb_paths.py                   CFB_DATA_ROOT path helper
```

## Local CSV inputs (`CFB_DATA_ROOT`)

Simulation CSVs, preseason FPI, and ESPN team metadata live **outside** this repo by default (parent directory of the clone).

```powershell
$env:CFB_DATA_ROOT = "C:\Users\ender"   # optional override
cd C:\Users\ender\cfb-allen-ratings
python update_in_season_weekly.py
```

Required inputs (under `CFB_DATA_ROOT`):

- `cfb_2026_fbs_games_with_fpi.csv` — schedule + scores
- `cfb_2026_in_season_*` — sim outputs (written by pipeline)
- `cfb_2026_in_season_weekly_rankings.csv` — rankings output
- `Preseason_2026_blended.csv` (or `Preseason_2026.csv`)
- `espn_cfb_teams_conferences.csv`

## Weekly refresh

```powershell
cd C:\Users\ender\cfb-allen-ratings
python update_in_season_weekly.py

# Push to GitHub (Render auto-redeploys)
git add data/*.json data/sim/
git commit -m "Update in-season data for week N"
git push
```

Exports write at most **1000** sim JSON files (`0001.json`–`1000.json`).

## Local dev

```powershell
python app.py
# http://127.0.0.1:5000
```

## Deploy (Render)

- **Repo:** `tripleaendermikal/cfb-allen-ratings`
- **Build:** `pip install -r requirements.txt`
- **Start:** `gunicorn wsgi:app --bind 0.0.0.0:$PORT`

Render serves committed `data/` JSON only — no CSV processing at runtime.
