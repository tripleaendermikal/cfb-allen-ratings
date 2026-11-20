"""Per-season conference membership for Previous Years and prior-season bootstrap."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from cfb_conference_corrections import apply_team_conference_override
from cfb_paths import REPO_ROOT

HISTORICAL_JSON = REPO_ROOT / "data" / "historical_team_conferences.json"


@lru_cache(maxsize=1)
def _load_historical() -> dict[str, dict[str, str]]:
    if not HISTORICAL_JSON.is_file():
        return {}
    raw = json.loads(HISTORICAL_JSON.read_text(encoding="utf-8"))
    seasons = raw.get("seasons") if isinstance(raw, dict) else None
    if not isinstance(seasons, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for year, mapping in seasons.items():
        if isinstance(mapping, dict):
            out[str(year)] = {str(k): str(v) for k, v in mapping.items()}
    return out


def conference_for_season(
    team_id: str,
    default: str,
    season_year: int | None,
) -> str:
    """Return historical conference for ``season_year``, else ``default`` (then global overrides)."""
    tid = (team_id or "").strip()
    conf = (default or "").strip()
    if season_year is not None:
        hist = _load_historical().get(str(season_year), {})
        conf = hist.get(tid, conf)
        return conf
    return apply_team_conference_override(tid, conf)


def apply_season_conferences_to_team_info(
    team_info: Mapping[str, dict],
    season_year: int,
) -> dict[str, dict]:
    """Return a copy of team_info with conferences set for that season."""
    updated: dict[str, dict] = {}
    for tid, meta in team_info.items():
        row = dict(meta)
        row["conference"] = conference_for_season(
            tid,
            row.get("conference", ""),
            season_year,
        )
        updated[tid] = row
    return updated