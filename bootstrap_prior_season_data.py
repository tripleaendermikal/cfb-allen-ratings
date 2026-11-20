#!/usr/bin/env python3
"""Bootstrap gitignored prior-season inputs (ESPN games + preseason FPI) for export."""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from cfb_paths import data_root

SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
)
POWER_INDEX_URL = (
    "https://site.web.api.espn.com/apis/fitt/v3/sports/football/college-football/"
    "powerindex?region=us&lang=en&season={year}&sort=fpi.fpi%3Adesc&limit=500"
)
TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams"
    "?groups=80&limit=200"
)

FBS_CONFERENCES = {
    "ACC",
    "American",
    "Big 12",
    "Big Ten",
    "CUSA",
    "FBS Independents",
    "FBS Indep.",
    "Independents",
    "MAC",
    "Mountain West",
    "Pac-12",
    "Pac-10",
    "SEC",
    "Sun Belt",
}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "cfb-allen-ratings-bootstrap/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_fpi_map(season_year: int) -> dict[str, tuple[str, float]]:
    data = fetch_json(POWER_INDEX_URL.format(year=season_year))
    out: dict[str, tuple[str, float]] = {}
    for entry in data.get("teams") or []:
        tid = str(entry.get("team", {}).get("id", "")).strip()
        name = (entry.get("team", {}).get("displayName") or "").strip()
        fpi = None
        for cat in entry.get("categories") or []:
            if cat.get("name") == "fpi" and cat.get("values"):
                try:
                    fpi = float(cat["values"][0])
                except (TypeError, ValueError):
                    pass
                break
        if tid and fpi is not None:
            out[tid] = (name, fpi)
    return out


def fetch_team_conferences() -> dict[str, tuple[str, str]]:
    data = fetch_json(TEAMS_URL)
    out: dict[str, tuple[str, str]] = {}
    for sport in data.get("sports") or []:
        for league in sport.get("leagues") or []:
            for team in league.get("teams") or []:
                t = team.get("team") or {}
                tid = str(t.get("id", "")).strip()
                name = (t.get("displayName") or "").strip()
                conf = (
                    (team.get("groups") or {}).get("conference")
                    or (t.get("groups") or {}).get("conference")
                    or ""
                )
                if isinstance(conf, dict):
                    conf = conf.get("name") or ""
                conf = str(conf).strip()
                if tid:
                    out[tid] = (name, conf)
    return out


def iter_season_dates(season_year: int):
    start = date(season_year, 8, 20)
    end = date(season_year + 1, 1, 25)
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def collect_games(season_year: int, sleep_s: float = 0.08) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for day in iter_season_dates(season_year):
        ds = day.strftime("%Y%m%d")
        url = f"{SCOREBOARD_URL}?dates={ds}&groups=80&limit=400"
        try:
            sb = fetch_json(url)
        except Exception as exc:
            print(f"warn: scoreboard {ds}: {exc}")
            time.sleep(sleep_s)
            continue
        for ev in sb.get("events") or []:
            season = ev.get("season") or {}
            if int(season.get("year") or 0) != season_year:
                continue
            gid = str(ev.get("id", "")).strip()
            if not gid or gid in by_id:
                continue
            comp = (ev.get("competitions") or [{}])[0]
            competitors = comp.get("competitors") or []
            if len(competitors) != 2:
                continue
            home = away = None
            for side in competitors:
                item = {
                    "id": str(side.get("team", {}).get("id", "")),
                    "name": side.get("team", {}).get("displayName", ""),
                    "score": side.get("score", ""),
                    "homeAway": side.get("homeAway", ""),
                }
                if item["homeAway"] == "home":
                    home = item
                else:
                    away = item
            if not home or not away:
                continue
            if home.get("score") in ("", None) or away.get("score") in ("", None):
                continue
            status = (comp.get("status") or {}).get("type") or {}
            if not status.get("completed"):
                continue
            week_obj = ev.get("week") or {}
            by_id[gid] = {
                "game_id": gid,
                "season": season_year,
                "week": int(week_obj.get("number") or 0),
                "game_date_utc": (ev.get("date") or "")[:10],
                "neutral_site": comp.get("neutralSite", False),
                "home_team_id": home["id"],
                "home_team": home["name"],
                "home_points": int(home["score"]),
                "away_team_id": away["id"],
                "away_team": away["name"],
                "away_points": int(away["score"]),
            }
        time.sleep(sleep_s)
    return by_id


def attach_yards(games: dict[str, dict], sleep_s: float = 0.05) -> None:
    from cfb_espn_summary import fetch_game_yards

    for gid, row in games.items():
        yards = fetch_game_yards(gid)
        if yards:
            row["home_total_yards"] = yards.get(row["home_team_id"], 0)
            row["away_total_yards"] = yards.get(row["away_team_id"], 0)
        else:
            row["home_total_yards"] = 0
            row["away_total_yards"] = 0
        time.sleep(sleep_s)


def write_espn_games(path: Path, games: dict[str, dict]) -> int:
    fieldnames = [
        "game_id",
        "season",
        "week",
        "game_date_utc",
        "neutral_site",
        "home_team_id",
        "home_team",
        "home_points",
        "home_total_yards",
        "away_team_id",
        "away_team",
        "away_points",
        "away_total_yards",
    ]
    rows = sorted(
        games.values(),
        key=lambda r: (r.get("game_date_utc", ""), r.get("week", 0), r["game_id"]),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "neutral_site": "true" if row.get("neutral_site") else "false",
                }
            )
    return len(rows)


def write_preseason_blended(path: Path, fpi_map: dict[str, tuple[str, float]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["Team Proper Name", "Team", "combined_FPI"]
        )
        writer.writeheader()
        for tid in sorted(fpi_map.keys(), key=lambda t: -fpi_map[t][1]):
            name, fpi = fpi_map[tid]
            writer.writerow(
                {
                    "Team Proper Name": name,
                    "Team": name,
                    "combined_FPI": f"{fpi:.10f}",
                }
            )
    return len(fpi_map)


def write_margin_ratings(
    path: Path,
    fpi_map: dict[str, tuple[str, float]],
    conf_by_id: dict[str, tuple[str, str]],
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "team_id",
        "team_name",
        "conference",
        "rating",
        "r",
        "rs",
        "margin_rating",
    ]
    rows: list[dict[str, str]] = []
    from cfb_rating.season_data import load_fbs_team_ids

    teams_csv = root / "espn_cfb_teams_conferences.csv"
    espn_conf = {
        tid: meta.get("conference", "")
        for tid, meta in load_fbs_team_ids(teams_csv).items()
    }
    for tid, (name, fpi) in fpi_map.items():
        tname, conf = conf_by_id.get(tid, (name, ""))
        if not conf:
            conf = espn_conf.get(tid, "")
        conf_norm = conf
        if conf in ("FBS Independents", "Independents"):
            conf_norm = "FBS Indep."
        if conf_norm not in FBS_CONFERENCES and conf_norm != "FBS Indep.":
            continue
        margin = fpi * 14.0 / 30.0 if fpi else 0.0
        rows.append(
            {
                "team_id": tid,
                "team_name": tname or name,
                "conference": conf_norm or conf,
                "rating": f"{fpi:.10f}",
                "r": "0",
                "rs": "0",
                "margin_rating": f"{margin:.10f}",
            }
        )
    rows.sort(key=lambda r: float(r["rating"]), reverse=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--skip-yards", action="store_true", help="Skip per-game yard fetches")
    parser.add_argument("--data-root", type=Path, default=None)
    args = parser.parse_args()

    root = args.data_root or data_root()
    root.mkdir(parents=True, exist_ok=True)

    print(f"Fetching FPI preseason map for {args.season}…")
    fpi_map = fetch_fpi_map(args.season)
    conf_by_id = fetch_team_conferences()

    pre_path = root / f"Preseason_{args.season}_blended.csv"
    margin_path = root / f"cfb_{args.season}_fbs_margin_ratings.csv"
    games_path = root / f"cfb_{args.season}_espn_games.csv"

    n_pre = write_preseason_blended(pre_path, fpi_map)
    n_margin = write_margin_ratings(margin_path, fpi_map, conf_by_id)
    print(f"Wrote {n_pre} teams to {pre_path}")
    print(f"Wrote {n_margin} FBS rows to {margin_path}")

    print(f"Collecting scoreboard for {args.season} season…")
    games = collect_games(args.season)
    print(f"  {len(games)} completed games")
    if not args.skip_yards:
        print("Fetching yards (slow)…")
        attach_yards(games)
    else:
        for row in games.values():
            row.setdefault("home_total_yards", 350)
            row.setdefault("away_total_yards", 350)

    kept = {
        gid: row
        for gid, row in games.items()
        if int(row.get("home_total_yards") or 0) > 0
        and int(row.get("away_total_yards") or 0) > 0
    }
    n_games = write_espn_games(games_path, kept)
    print(f"Wrote {n_games} games with yards to {games_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())