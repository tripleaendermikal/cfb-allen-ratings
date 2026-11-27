"""Per-season conference membership for Previous Years and prior-season bootstrap."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from cfb_conference_corrections import apply_team_conference_override
from cfb_paths import REPO_ROOT

HISTORICAL_JSON = REPO_ROOT / "data" / "historical_team_conferences.json"

# Defunct FBS leagues still shown on Previous Years (not in current teams CSV).
HISTORICAL_FBS_EXTRA = frozenset({"WAC", "Big East"})

# ESPN standings / older exports sometimes use non-canonical labels.
_CONFERENCE_ALIASES = {
    "American Athletic": "American",
    "American Athletic Conference": "American",
    "American Conference": "American",
    "FBS Independents": "FBS Indep.",
    "Independents": "FBS Indep.",
    "Mid-American Conference": "MAC",
    "Mid-American": "MAC",
    "Conference USA": "CUSA",
}

FCS_CONFERENCE_LABELS = frozenset(
    {
        "Big Sky",
        "CAA",
        "FCS Indep.",
        "Ivy",
        "MEAC",
        "MVFC",
        "Missouri Valley",
        "NEC",
        "OVC",
        "OVC-Big South",
        "Patriot",
        "Pioneer",
        "Southern",
        "Southland",
        "SWAC",
        "UAC",
    }
)


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
            out[str(year)] = {
                str(k): normalize_conference_label(str(v))
                for k, v in mapping.items()
            }
    return out


def normalize_conference_label(conf: str) -> str:
    label = (conf or "").strip()
    if not label:
        return ""
    return _CONFERENCE_ALIASES.get(label, label)


def is_fbs_conference_label(conf: str) -> bool:
    """True for a conference label that denotes FBS membership that season."""
    label = normalize_conference_label(conf)
    if not label or label == "Unknown":
        return False
    if label in FCS_CONFERENCE_LABELS:
        return False
    from cfb_rating.season_data import FBS_CONFERENCES

    return label in FBS_CONFERENCES or label in HISTORICAL_FBS_EXTRA


def fbs_team_ids_for_season(season_year: int) -> set[str]:
    """ESPN FBS membership for a season (from ``historical_team_conferences.json``)."""
    hist = _load_historical().get(str(season_year), {})
    return {tid for tid, conf in hist.items() if is_fbs_conference_label(conf)}


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
        conf = normalize_conference_label(hist.get(tid, conf))
        return conf
    return apply_team_conference_override(tid, conf)


def apply_season_conferences_to_team_info(
    team_info: Mapping[str, dict],
    season_year: int,
    *,
    team_ids: set[str] | None = None,
) -> dict[str, dict]:
    """Return a copy of team_info with conferences set for that season."""
    allowed = team_ids if team_ids is not None else set(team_info)
    updated: dict[str, dict] = {}
    for tid in allowed:
        meta = team_info.get(tid)
        if not meta:
            continue
        row = dict(meta)
        row["conference"] = conference_for_season(
            tid,
            row.get("conference", ""),
            season_year,
        )
        if is_fbs_conference_label(row["conference"]):
            updated[tid] = row
    return updated