"""Head-to-head matchup projection helpers (scheduled games + rating-based)."""

from __future__ import annotations

from export_sim_data import home_field_adjustment
from simulate_cfb_games_preseason_simulation import win_probability


def find_scheduled_games(
    games: dict,
    team_a: str,
    team_b: str,
) -> list[dict]:
    """Return all games in ``games`` where the two team ids meet (either side)."""
    a, b = str(team_a), str(team_b)
    if a == b:
        return []
    out: list[dict] = []
    for g in games.values():
        home = str(g.get("home_team_id", ""))
        away = str(g.get("away_team_id", ""))
        if {home, away} == {a, b}:
            out.append(g)
    return out


def _scheduled_neutral(game: dict) -> bool:
    return bool(game.get("neutral_site"))


def game_matches_requested_site(
    game: dict,
    home_id: str,
    neutral: bool,
) -> bool:
    """True when the scheduled game's site matches the user's home/neutral choice."""
    if neutral:
        return _scheduled_neutral(game)
    return not _scheduled_neutral(game) and str(game.get("home_team_id", "")) == str(
        home_id
    )


def pick_game_for_site(
    candidates: list[dict],
    home_id: str,
    neutral: bool,
) -> dict | None:
    """Pick a scheduled game matching the requested site, or a single unambiguous game."""
    if not candidates:
        return None
    home_id = str(home_id)

    def site_match(g: dict) -> bool:
        if neutral:
            return _scheduled_neutral(g)
        return not _scheduled_neutral(g) and str(g.get("home_team_id", "")) == home_id

    matches = [g for g in candidates if site_match(g)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        incomplete = [g for g in matches if not g.get("completed")]
        if len(incomplete) == 1:
            return incomplete[0]
        return matches[0]

    incomplete = [g for g in candidates if not g.get("completed")]
    if len(candidates) == 1:
        return candidates[0]
    if len(incomplete) == 1:
        return incomplete[0]
    return None


def project_from_ratings(
    home_overall: float,
    away_overall: float,
    *,
    neutral: bool,
) -> dict:
    """Project margin and win % from Overall ratings (hypothetical matchup)."""
    internal_margin = float(home_overall) - float(away_overall)
    home_flag = 0.0 if neutral else 1.0
    p_home = win_probability(internal_margin, home_flag)
    if neutral:
        hfa = 0.0
    else:
        hfa = home_field_adjustment("", "home")
    avg_margin = round(internal_margin + hfa, 3)
    return {
        "home_win_pct": round(p_home * 100, 2),
        "away_win_pct": round((1.0 - p_home) * 100, 2),
        "avg_margin": avg_margin,
        "home_fpi": round(home_overall, 3),
        "away_fpi": round(away_overall, 3),
        "method": "ratings",
    }


def matchup_projection_from_schedule(game: dict) -> dict:
    """Normalized projection fields from a games.json entry."""
    home_wp = game.get("home_win_pct")
    if home_wp is None:
        away_wp = None
    else:
        away_wp = round(100.0 - float(home_wp), 2)
    return {
        "home_win_pct": home_wp,
        "away_win_pct": away_wp,
        "avg_margin": game.get("avg_margin"),
        "home_fpi": game.get("home_fpi"),
        "away_fpi": game.get("away_fpi"),
        "margin_histogram": game.get("margin_histogram"),
        "neutral_site": bool(game.get("neutral_site")),
        "completed": bool(game.get("completed")),
        "game_id": game.get("game_id"),
        "method": "schedule",
    }
