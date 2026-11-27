"""Power vs non-power FBS teams by season (UI filter on rankings / previous years)."""

from __future__ import annotations

NOTRE_DAME_TEAM_ID = "87"

# Core Power Four (2024+); Pac-12 added 2014–2023; American & Big East before 2014.
_POWER_FOUR = frozenset({"ACC", "Big 12", "Big Ten", "SEC"})
_PAC_12_ALIASES = frozenset({"Pac-12", "Pac-10", "Pac 12", "PAC-12"})
_G5_LEGACY_POWER = frozenset({"American", "Big East"})

_CONFERENCE_ALIASES = {
    "acc": "ACC",
    "big 12": "Big 12",
    "big twelve": "Big 12",
    "big ten": "Big Ten",
    "sec": "SEC",
    "pac-12": "Pac-12",
    "pac-10": "Pac-12",
    "pac 12": "Pac-12",
    "american": "American",
    "aac": "American",
    "big east": "Big East",
    "fbs independents": "FBS Independents",
    "fbs indep.": "FBS Independents",
    "independents": "FBS Independents",
}


def normalize_conference_name(conference: str | None) -> str:
    raw = (conference or "").strip()
    if not raw:
        return ""
    key = raw.lower()
    if key in _CONFERENCE_ALIASES:
        return _CONFERENCE_ALIASES[key]
    for alias, canonical in _CONFERENCE_ALIASES.items():
        if key == alias:
            return canonical
    if raw in _POWER_FOUR or raw in _G5_LEGACY_POWER:
        return raw
    if raw in _PAC_12_ALIASES:
        return "Pac-12"
    return raw


def is_power_team(
    season_year: int,
    conference: str | None,
    team_id: str | None = None,
) -> bool:
    """Return True if the team counts as power for ``season_year`` (see product rules)."""
    tid = (team_id or "").strip()
    if tid == NOTRE_DAME_TEAM_ID:
        return True

    conf = normalize_conference_name(conference)
    if not conf:
        return False

    year = int(season_year)
    if conf in _POWER_FOUR:
        return True
    if year < 2024 and conf == "Pac-12":
        return True
    if year < 2014 and conf in _G5_LEGACY_POWER:
        return True
    return False


def parse_power_filter(raw: str | None) -> str:
    """Normalize query param: '' (all), 'power', or 'non_power'."""
    value = (raw or "").strip().lower().replace("-", "_")
    if value in ("power", "non_power"):
        return value
    return ""


def filter_rows_by_power(
    rows: list[dict],
    season_year: int,
    power_filter: str,
) -> list[dict]:
    """Filter leaderboard rows and renumber ``display_rank`` when a tier filter is set."""
    if not power_filter:
        return rows
    want_power = power_filter == "power"
    out: list[dict] = []
    for row in rows:
        tid = row.get("team_id")
        conf = row.get("conference")
        powered = is_power_team(season_year, conf, tid)
        if powered == want_power:
            out.append(dict(row))
    for idx, row in enumerate(out, start=1):
        row["display_rank"] = idx
    return out