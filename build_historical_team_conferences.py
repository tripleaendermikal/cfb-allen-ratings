#!/usr/bin/env python3
"""Fetch per-season FBS conference membership from ESPN standings."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from cfb_paths import REPO_ROOT

STANDINGS_URL = (
    "https://site.web.api.espn.com/apis/v2/sports/football/college-football/"
    "standings?season={year}&group={group_id}&type=0"
)

DEFAULT_OUTPUT = REPO_ROOT / "data" / "historical_team_conferences.json"
FBS_GROUP_ID = "80"
FPI_URL = (
    "https://site.web.api.espn.com/apis/fitt/v3/sports/football/college-football/"
    "powerindex?region=us&lang=en&season={year}&sort=fpi.fpi%3Adesc&limit=500"
)
TEAM_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/"
    "teams/{tid}?season={year}"
)

# ESPN drops some defunct conferences from the FBS standings tree; fetch by group id.
SUPPLEMENTAL_GROUPS: list[tuple[str, int, int]] = [
    ("16", 2007, 2012),  # Western Athletic Conference
    ("10", 2007, 2013),  # Big East (pre-realignment football)
]

_STANDING_CONF_RE = re.compile(r"\bin\s+(.+?)(?:\s+-\s+|$)", re.IGNORECASE)

_NAME_TO_CANONICAL = {
    "American Conference": "American",
    "Atlantic Coast Conference": "ACC",
    "Big 12 Conference": "Big 12",
    "Big Ten Conference": "Big Ten",
    "Conference USA": "CUSA",
    "FBS Independents": "FBS Indep.",
    "Independents": "FBS Indep.",
    "Mid-American Conference": "MAC",
    "Mid-American": "MAC",
    "Mountain West Conference": "Mountain West",
    "Pac-12 Conference": "Pac-12",
    "Southeastern Conference": "SEC",
    "Sun Belt Conference": "Sun Belt",
    "Western Athletic Conference": "WAC",
    "WAC": "WAC",
    "Big East Conference": "Big East",
    "Big East": "Big East",
}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "cfb-allen-ratings-historical-conf/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def canonical_conference(name: str) -> str:
    raw = (name or "").strip()
    if " - " in raw:
        raw = raw.split(" - ", 1)[0].strip()
    if raw in _NAME_TO_CANONICAL:
        return _NAME_TO_CANONICAL[raw]
    if raw.replace(" ", "") in ("Pac12", "Pac-12"):
        return "Pac-12"
    if raw.startswith("Pac-12") or raw.startswith("Pac 12"):
        return "Pac-12"
    if raw.startswith("SEC"):
        return "SEC"
    if raw.startswith("Big Ten"):
        return "Big Ten"
    if raw.startswith("Big 12"):
        return "Big 12"
    return raw


def conference_from_standing(summary: str) -> str | None:
    match = _STANDING_CONF_RE.search(summary or "")
    if not match:
        return None
    raw = match.group(1).strip()
    if raw.upper() == "FBS":
        return None
    return canonical_conference(raw)


def fpi_team_ids(season_year: int) -> list[str]:
    data = fetch_json(FPI_URL.format(year=season_year))
    ids: list[str] = []
    for entry in data.get("teams") or []:
        tid = str((entry.get("team") or {}).get("id") or "").strip()
        if tid:
            ids.append(tid)
    return ids


def standings_entries(data: dict) -> list[dict]:
    standings = data.get("standings")
    if isinstance(standings, dict):
        entries = standings.get("entries")
        if isinstance(entries, list):
            return entries
    if isinstance(standings, list):
        return standings
    return []


def merge_standings_group(
    season_year: int,
    group_id: str,
    out: dict[str, str],
    *,
    sleep_s: float,
) -> None:
    time.sleep(sleep_s)
    try:
        conf_data = fetch_json(
            STANDINGS_URL.format(year=season_year, group_id=group_id)
        )
    except Exception:
        return
    label = canonical_conference(
        (conf_data.get("name") or conf_data.get("shortName") or "").strip()
    )
    for entry in standings_entries(conf_data):
        team = entry.get("team") or {}
        tid = str(team.get("id") or "").strip()
        if tid and label:
            out.setdefault(tid, label)
    for child in conf_data.get("children") or []:
        child_id = str(child.get("id") or "").strip()
        if not child_id:
            continue
        time.sleep(sleep_s)
        try:
            child_data = fetch_json(
                STANDINGS_URL.format(year=season_year, group_id=child_id)
            )
        except Exception:
            continue
        child_label = canonical_conference(
            (child_data.get("name") or child.get("name") or label).strip()
        )
        for entry in standings_entries(child_data):
            team = entry.get("team") or {}
            tid = str(team.get("id") or "").strip()
            if tid and child_label:
                out.setdefault(tid, child_label)


def fill_missing_from_team_pages(
    season_year: int,
    out: dict[str, str],
    *,
    sleep_s: float,
) -> None:
    for tid in fpi_team_ids(season_year):
        if tid in out:
            continue
        time.sleep(sleep_s)
        try:
            data = fetch_json(TEAM_URL.format(tid=tid, year=season_year))
        except Exception:
            continue
        team = data.get("team") or {}
        conf = conference_from_standing(team.get("standingSummary") or "")
        if conf:
            out[tid] = conf


def fetch_season_conferences(
    season_year: int,
    *,
    sleep_s: float = 0.08,
) -> dict[str, str]:
    root_url = STANDINGS_URL.format(year=season_year, group_id=FBS_GROUP_ID)
    root = fetch_json(root_url)
    out: dict[str, str] = {}
    for conf_node in root.get("children") or []:
        conf_id = str(conf_node.get("id") or "").strip()
        if not conf_id:
            continue
        merge_standings_group(season_year, conf_id, out, sleep_s=sleep_s)
    for group_id, start, end in SUPPLEMENTAL_GROUPS:
        if start <= season_year <= end:
            merge_standings_group(season_year, group_id, out, sleep_s=sleep_s)
    fill_missing_from_team_pages(season_year, out, sleep_s=sleep_s)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=list(range(2007, 2020))
        + [2021, 2022, 2023, 2024, 2025],
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    seasons: dict[str, dict[str, str]] = {}
    if args.output.is_file():
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        prior = existing.get("seasons")
        if isinstance(prior, dict):
            seasons = {
                str(k): {str(tid): str(c) for tid, c in v.items()}
                for k, v in prior.items()
                if isinstance(v, dict)
            }
    for year in args.seasons:
        print(f"Fetching {year}…", flush=True)
        seasons[str(year)] = fetch_season_conferences(year)
        print(f"  {len(seasons[str(year)])} teams", flush=True)

    payload = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "seasons": seasons,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())