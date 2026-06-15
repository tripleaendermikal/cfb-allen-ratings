# CFB Allen Ratings

In-season college football power rankings and Monte Carlo projections.

- **Live site:** [cfballenratings.onrender.com](https://cfballenratings.onrender.com)
- **Preseason viewer (separate repo):** [cfb-viewer.onrender.com](https://cfb-viewer.onrender.com)

This repo is **separate** from [cfb-viewer](https://github.com/tripleaendermikal/cfb-viewer). It contains the Flask app, weekly rankings pipeline, export scripts, and committed `data/*.json` for Render.

## Repo layout

```
app.py, wsgi.py              Flask app
templates/, static/          UI
data/                        Exported JSON (committed; served on Render)
cfb_rating/                    Rankings algorithm package
compute_in_season_rankings.py  Weekly rankings CLI
export_in_season_data.py       CSV → JSON export for the app
export_sim_data.py             Vendored export builders (from cfb-viewer)
cfb_in_season_sim.py           Shared in-season helpers
```

## Local CSV inputs (`CFB_DATA_ROOT`)

Simulation CSVs, preseason FPI, and ESPN team metadata live **outside** this repo. By default scripts read from the parent directory of this repo (`C:\Users\ender` on this machine).

Set `CFB_DATA_ROOT` to override:

```powershell
$env:CFB_DATA_ROOT = "C:\Users\ender"
```

Required inputs (under `CFB_DATA_ROOT`):

- `cfb_2026_in_season_*` — in-season sim outputs
- `cfb_2026_fbs_games_with_fpi.csv` — schedule + scores
- `cfb_2026_in_season_weekly_rankings.csv` — rankings output (written by compute script)
- `Preseason_2026_blended.csv` (or `Preseason_2026.csv`)
- `espn_cfb_teams_conferences.csv`

The in-season sim pipeline (`run_in_season_sim_pipeline.py`) remains in the parent workspace.

## Weekly refresh

```powershell
# 1. Refresh ESPN scores + in-season sims (parent workspace)
python C:\Users\ender\run_in_season_sim_pipeline.py

# 2. Weekly rankings
python C:\Users\ender\cfb-allen-ratings\compute_in_season_rankings.py

# 3. Export JSON
python C:\Users\ender\cfb-allen-ratings\export_in_season_data.py

# 4. Push to GitHub (Render auto-redeploys)
cd C:\Users\ender\cfb-allen-ratings
git add data/
git commit -m "Update in-season data for week N"
git push
```

## Local dev

```powershell
python C:\Users\ender\cfb-allen-ratings\app.py
# http://127.0.0.1:5000
```

## Deploy (Render)

- **Repo:** `tripleaendermikal/cfb-allen-ratings`
- **Build:** `pip install -r requirements.txt`
- **Start:** `gunicorn wsgi:app --bind 0.0.0.0:$PORT`
- Or use [`render.yaml`](render.yaml) blueprint (service name `CFBAllenRatings`)

Render serves committed `data/` JSON only — no CSV processing at runtime.
