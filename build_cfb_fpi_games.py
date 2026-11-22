#!/usr/bin/env python3
"""Rebuild cfb_2026_fbs_games_with_fpi.csv from ESPN scoreboards (FBS group 80)."""

from __future__ import annotations

import csv
import time
from datetime import date, timedelta
from pathlib import Path

from cfb_conference_corrections import patch_schedule_row_conferences
from cfb_espn_summary import fetch_json
from cfb_paths import data_root

SEASON_YEAR = 2026
SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
)
FPI_URL = (
    "https://site.web.api.espn.com/apis/fitt/v3/sports/football/college-football/"
    "powerindex?region=us&lang=en&season={year}&sort=fpi.fpi%3Adesc&limit=1000"
)
DEFAULT_OUT = data_root() / "cfb_2026_fbs_games_with_fpi.csv"
FIELDNAMES = [
    "game_id",
    "season_year",
    "game_date",
    "week",
    "season_type",
    "team_id",
    "team_name",
    "conference",
    "opponent_id",
    "opponent_name",
    "home_away",
    "neutral_site",
    "team_fpi",
    "opponent_fpi",
    "team_score",
    "opponent_score",
    "game_completed",
    "team_yards",
    "opponent_yards",
]


def resolve_fpi(display_name: str, raw: float | None) -> float:
    name = display_name or ""
    if "North Dakota State" in name:
        return 1.0
    if "Sacramento State" in name:
        return -20.0
    if raw is None:
        return -36.0
    return float(raw)


def load_espn_fpi(season_year: int) -> dict[str, float]:
    payload = fetch_json(FPI_URL.format(year=season_year), user_agent=True)
    out: dict[str, float] = {}
    for entry in payload.get("teams") or []:
        tid = str((entry.get("team") or {}).get("id") or "").strip()
        if not tid:
            continue
        for cat in entry.get("categories") or []:
            if cat.get("name") == "fpi" and cat.get("values"):
                try:
                    out[tid] = float(cat["values"][0])
                except (TypeError, ValueError):
                    pass
                break
    return out


def collect_events(
    start: date,
    end: date,
    *,
    season_year: int = SEASON_YEAR,
    sleep_seconds: float = 0.08,
) -> dict[str, dict]:
    games: dict[str, dict] = {}
    day = start
    while day <= end:
        ds = day.strftime("%Y%m%d")
        url = f"{SCOREBOARD_URL}?dates={ds}&groups=80&limit=400"
        try:
            payload = fetch_json(url, user_agent=True)
        except Exception as exc:
            print(f"Warning: scoreboard failed for {ds}: {exc}")
            day += timedelta(days=1)
            time.sleep(sleep_seconds)
            continue
        for ev in payload.get("events") or []:
            season = ev.get("season") or {}
            if season.get("year") not in (season_year, str(season_year)):
                continue
            gid = str(ev.get("id") or "").strip()
            if gid:
                games.setdefault(gid, ev)
        day += timedelta(days=1)
        time.sleep(sleep_seconds)
    return games


def rows_from_events(
    games: dict[str, dict],
    fpi_by_team: dict[str, float],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for gid, ev in games.items():
        competitions = ev.get("competitions") or []
        if not competitions:
            continue
        comp = competitions[0]
        neutral = bool(comp.get("neutralSite"))
        week = (ev.get("week") or {}).get("number", "")
        season_slug = (ev.get("season") or {}).get("slug") or "regular-season"
        season_year = (ev.get("season") or {}).get("year") or SEASON_YEAR
        completed = bool(((comp.get("status") or {}).get("type") or {}).get("completed"))
        game_date = (ev.get("date") or "").strip()
        if "T" in game_date:
            game_date = game_date.split("T", 1)[0]

        for side in comp.get("competitors") or []:
            tid = str((side.get("team") or {}).get("id") or "").strip()
            tname = (side.get("team") or {}).get("displayName") or ""
            oid = ""
            oname = ""
            oscore = ""
            for other in comp.get("competitors") or []:
                if str((other.get("team") or {}).get("id") or "").strip() != tid:
                    oid = str((other.get("team") or {}).get("id") or "").strip()
                    oname = (other.get("team") or {}).get("displayName") or ""
                    oscore = other.get("score")
                    if oscore is None:
                        oscore = ""
                    break
            tfpi = resolve_fpi(tname, fpi_by_team.get(tid))
            ofpi = resolve_fpi(oname, fpi_by_team.get(oid)) if oid else -36.0
            tscore = side.get("score")
            if tscore is None:
                tscore = ""
            rows.append(
                {
                    "game_id": gid,
                    "season_year": str(season_year),
                    "game_date": game_date,
                    "week": str(week),
                    "season_type": season_slug,
                    "team_id": tid,
                    "team_name": tname,
                    "conference": "",
                    "opponent_id": oid,
                    "opponent_name": oname,
                    "home_away": side.get("homeAway") or "",
                    "neutral_site": "True" if neutral else "False",
                    "team_fpi": fpi_to_csv(tfpi),
                    "opponent_fpi": fpi_to_csv(ofpi),
                    "team_score": str(tscore) if tscore != "" else "",
                    "opponent_score": str(oscore) if oscore != "" else "",
                    "game_completed": "True" if completed and tscore != "" else "False",
                    "team_yards": "",
                    "opponent_yards": "",
                }
            )
    rows.sort(key=lambda r: (r.get("game_date", ""), r.get("game_id", ""), r.get("team_id", "")))
    return rows


def fpi_to_csv(val: float) -> str:
    return f"{val:.3f}".rstrip("0").rstrip(".") if val == int(val) else f"{val:.3f}"


def main() -> int:
    fpi_by_team = load_espn_fpi(SEASON_YEAR)
    print(f"FPI teams loaded: {len(fpi_by_team)}")
    games = collect_events(date(2026, 8, 20), date(2027, 1, 26))
    if not games:
        raise SystemExit("No games collected from ESPN; refusing to overwrite schedule CSV.")
    rows = rows_from_events(games, fpi_by_team)
    conf_csv = data_root() / "espn_cfb_teams_conferences.csv"
    patched = patch_schedule_row_conferences(rows, conf_csv)
    if patched:
        print(f"Patched conference on {patched} schedule row(s)")
    out = DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    unique = len(games)
    print(f"Wrote {len(rows)} rows ({unique} unique games) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())