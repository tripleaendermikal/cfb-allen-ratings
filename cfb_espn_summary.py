"""ESPN college football game summary helpers (yards, box score)."""

from __future__ import annotations

import json
import subprocess
import time
from typing import Dict, Iterable, Optional

SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary"
)


def fetch_json(url: str, *, user_agent: bool = False) -> dict:
    import urllib.request

    headers = {"User-Agent": "Mozilla/5.0"} if user_agent else {}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        cmd = ["curl", "-sS"]
        if user_agent:
            cmd.extend(["--compressed", "-H", "User-Agent: Mozilla/5.0"])
        cmd.append(url)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(stderr or f"curl failed: {proc.returncode}")
        return json.loads(proc.stdout.decode("utf-8"))


def stat_display_value(statistics: Iterable[dict], stat_name: str) -> Optional[str]:
    for stat in statistics:
        if stat.get("name") == stat_name:
            value = stat.get("displayValue")
            if value in (None, "", "-"):
                return None
            return str(value)
    return None


def parse_total_yards(statistics: Iterable[dict]) -> Optional[int]:
    raw = stat_display_value(statistics, "totalYards")
    if raw is None:
        return None
    return int(raw.replace(",", ""))


def parse_game_yards_from_summary(summary: dict) -> Dict[str, int]:
    """Return team_id -> total yards from an ESPN summary payload."""
    yards_by_team: Dict[str, int] = {}
    for team_block in summary.get("boxscore", {}).get("teams", []):
        team_id = str((team_block.get("team") or {}).get("id") or "").strip()
        if not team_id:
            continue
        total_yards = parse_total_yards(team_block.get("statistics", []))
        if total_yards is not None and total_yards > 0:
            yards_by_team[team_id] = total_yards
    return yards_by_team


def fetch_game_yards(
    game_id: str,
    *,
    sleep_seconds: float = 0.0,
) -> Dict[str, int]:
    """Fetch total yards per team_id for a completed game from ESPN summary."""
    summary = fetch_json(f"{SUMMARY_URL}?event={game_id}")
    if sleep_seconds:
        time.sleep(sleep_seconds)
    return parse_game_yards_from_summary(summary)
