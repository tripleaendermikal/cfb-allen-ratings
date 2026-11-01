"""Manual conference fixes when ESPN / bootstrap data is stale."""

from __future__ import annotations

import csv
from pathlib import Path

# team_id -> canonical FBS conference label
TEAM_CONFERENCE_OVERRIDES: dict[str, str] = {
    "2348": "Sun Belt",  # Louisiana Tech Bulldogs
}


def apply_team_conference_override(team_id: str, conference: str) -> str:
    tid = (team_id or "").strip()
    if tid in TEAM_CONFERENCE_OVERRIDES:
        return TEAM_CONFERENCE_OVERRIDES[tid]
    return conference


def apply_conference_lookup_overrides(by_id: dict[str, str]) -> None:
    for tid, conf in TEAM_CONFERENCE_OVERRIDES.items():
        if tid in by_id:
            by_id[tid] = conf


def patch_schedule_row_conferences(
    rows: list[dict[str, str]],
    teams_csv: Path | None = None,
) -> int:
    """Set conference on team-perspective schedule rows from overrides (+ optional CSV)."""
    by_id: dict[str, str] = dict(TEAM_CONFERENCE_OVERRIDES)
    if teams_csv and teams_csv.is_file():
        with teams_csv.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                tid = (row.get("team_id") or "").strip()
                conf = (row.get("conference") or "").strip()
                if tid and conf:
                    by_id.setdefault(tid, conf)
        apply_conference_lookup_overrides(by_id)

    changed = 0
    for row in rows:
        tid = (row.get("team_id") or "").strip()
        if not tid:
            continue
        conf = apply_team_conference_override(tid, by_id.get(tid, row.get("conference", "")))
        if conf and row.get("conference") != conf:
            row["conference"] = conf
            changed += 1
    return changed
