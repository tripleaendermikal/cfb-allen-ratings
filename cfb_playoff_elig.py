#!/usr/bin/env python3
"""Compute FBS playoff eligibility flags from team simulation win totals."""

import csv
import random
import re
from pathlib import Path

SEC_BIG_TEN = {"SEC", "Big Ten"}
ACC_BIG_12 = {"ACC", "Big 12"}
POWER_FOUR = SEC_BIG_TEN | ACC_BIG_12
POWER_FOUR_CONFERENCES = ("SEC", "Big Ten", "ACC", "Big 12")
NOTRE_DAME_NAME = "Notre Dame Fighting Irish"
GROUP_CONFERENCES = {
    "American",
    "Pac-12",
    "Sun Belt",
    "CUSA",
    "Mountain West",
    "MAC",
}

FILL_TIERS = [
    ("SEC", 10),
    ("Big Ten", 10),
    (ACC_BIG_12, 10),
    ("SEC", 9),
    ("Big Ten", 9),
    (None, 12),
]

MIN_SEC_BIG_TEN_IN_FIELD = 2

SIM_COL_PATTERN = re.compile(r"^sim_\d+$")


def sim_columns(fieldnames):
    return [col for col in fieldnames if SIM_COL_PATTERN.match(col)]


def sim_col_seed(col):
    match = re.search(r"(\d+)$", col)
    return int(match.group(1)) if match else 0


def home_field_adjustment(neutral_site, home_away):
    n = str(neutral_site or "").strip().lower()
    if n in ("true", "1", "yes"):
        return 0.0
    if home_away == "home":
        return 3.0
    if home_away == "away":
        return -3.0
    return 0.0


def load_sos_by_team_id(path):
    """team_id -> static SOS from schedule (opponent FPI adjusted for site)."""
    from pac12_week13 import FLEX_FLAG_COL, FLEX_FLAG_VALUE, PAC12_FLEX_OPPONENT_ID

    by_team: dict[str, list[float]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            tid = (row.get("team_id") or "").strip()
            oid = (row.get("opponent_id") or "").strip()
            opp_raw = (row.get("opponent_fpi") or "").strip()
            if not tid or not opp_raw:
                continue
            if oid == PAC12_FLEX_OPPONENT_ID or (
                row.get(FLEX_FLAG_COL) or ""
            ).strip() == FLEX_FLAG_VALUE:
                continue
            try:
                opp_fpi = float(opp_raw)
            except ValueError:
                continue
            hfa = home_field_adjustment(
                row.get("neutral_site", ""), row.get("home_away", "")
            )
            by_team.setdefault(tid, []).append(opp_fpi - hfa)
    return {
        tid: round(sum(vals) / len(vals), 2) for tid, vals in by_team.items() if vals
    }


def team_sos(sos_by_team_id, team_id):
    return float(sos_by_team_id.get(team_id, float("-inf")))


def winningest_in_conference(source_rows, col, conference):
    candidates = [
        i for i, src in enumerate(source_rows) if src["conference"] == conference
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda i: (int(source_rows[i][col]), -int(source_rows[i]["team_id"])),
    )


def power_four_conf_champion_indices(source_rows, col, conf_champions_by_sim):
    """Row indices for Power Four conference champions in this sim column."""
    team_id_to_index = {
        src["team_id"]: i for i, src in enumerate(source_rows) if src.get("team_id")
    }
    col_champs = conf_champions_by_sim.get(col, {})
    winners = set()
    for conf in POWER_FOUR_CONFERENCES:
        tid = col_champs.get(conf)
        if tid and tid in team_id_to_index:
            winners.add(team_id_to_index[tid])
        else:
            i = winningest_in_conference(source_rows, col, conf)
            if i is not None:
                winners.add(i)
    return winners


def apply_power_four_conf_champions_col(
    output_rows, source_rows, col, conf_champions_by_sim
):
    for i in power_four_conf_champion_indices(
        source_rows, col, conf_champions_by_sim
    ):
        output_rows[i][col] = 1


def group_row_indices(source_rows):
    return [
        i for i, row in enumerate(source_rows) if row["conference"] in GROUP_CONFERENCES
    ]


def g6_points_for_team(g6_points_by_team_id, team_id, col):
    return int((g6_points_by_team_id.get(team_id) or {}).get(col, 0))


def apply_g6_autobid_col(
    output_rows, source_rows, col, g6_points_by_team_id, sos_by_team_id
):
    """Rule 3: G6 autobid to highest playoff-points team (SOS tiebreak)."""
    group_indices = group_row_indices(source_rows)
    for i in group_indices:
        output_rows[i][col] = 0
    if not group_indices:
        return
    pick = max(
        group_indices,
        key=lambda i: (
            g6_points_for_team(
                g6_points_by_team_id, source_rows[i]["team_id"], col
            ),
            team_sos(sos_by_team_id, source_rows[i]["team_id"]),
            -int(source_rows[i]["team_id"]),
        ),
    )
    output_rows[pick][col] = 1


def g6_autobid_index(output_rows, source_rows, col):
    eligible = [
        i
        for i in group_row_indices(source_rows)
        if int(output_rows[i][col]) == 1
    ]
    return eligible[0] if len(eligible) == 1 else None


def notre_dame_index(source_rows):
    for i, src in enumerate(source_rows):
        if src["team_name"] == NOTRE_DAME_NAME:
            return i
    return None


def apply_notre_dame_rule_col(output_rows, source_rows, col):
    """Rule 2: Notre Dame with >= 10 wins."""
    for i, src in enumerate(source_rows):
        if src["team_name"] == NOTRE_DAME_NAME and int(src[col]) >= 10:
            output_rows[i][col] = 1


def eligibility_count(output_rows, col):
    return sum(int(row[col]) == 1 for row in output_rows)


def conference_eligible_count(output_rows, source_rows, col, conference):
    return sum(
        1
        for i, src in enumerate(source_rows)
        if src["conference"] == conference and int(output_rows[i][col]) == 1
    )


def conference_team_count(source_rows, conference):
    return sum(1 for src in source_rows if src["conference"] == conference)


def removable_for_trim(output_rows, source_rows, col, candidates):
    """Drop removals that would leave SEC or Big Ten with fewer than 2 teams."""
    safe = []
    for i in candidates:
        conf = source_rows[i]["conference"]
        if conf in SEC_BIG_TEN:
            league_size = conference_team_count(source_rows, conf)
            in_field = conference_eligible_count(output_rows, source_rows, col, conf)
            if (
                league_size >= MIN_SEC_BIG_TEN_IN_FIELD
                and in_field - 1 < MIN_SEC_BIG_TEN_IN_FIELD
            ):
                continue
        safe.append(i)
    return safe


def enforce_sec_big_ten_floor(output_rows, source_rows, col, sos_by_team_id):
    """Ensure at least MIN_SEC_BIG_TEN_IN_FIELD teams per SEC / Big Ten when possible."""
    for conference in ("SEC", "Big Ten"):
        if conference_team_count(source_rows, conference) < MIN_SEC_BIG_TEN_IN_FIELD:
            continue
        while (
            conference_eligible_count(output_rows, source_rows, col, conference)
            < MIN_SEC_BIG_TEN_IN_FIELD
        ):
            candidates = [
                i
                for i, src in enumerate(source_rows)
                if src["conference"] == conference and int(output_rows[i][col]) != 1
            ]
            if not candidates:
                break
            candidates.sort(
                key=lambda i: wins_rank_key(source_rows, col, sos_by_team_id, i),
                reverse=True,
            )
            output_rows[candidates[0]][col] = 1


def wins_rank_key(source_rows, col, sos_by_team_id, index):
    return (
        int(source_rows[index][col]),
        team_sos(sos_by_team_id, source_rows[index]["team_id"]),
        int(source_rows[index]["team_id"]),
    )


def add_top_n_by_conference(
    output_rows, source_rows, col, conference, n, sos_by_team_id
):
    """Rules 4-5: top N by wins among teams not already in the field."""
    candidates = [
        i
        for i, src in enumerate(source_rows)
        if src["conference"] == conference and int(output_rows[i][col]) != 1
    ]
    candidates.sort(
        key=lambda i: wins_rank_key(source_rows, col, sos_by_team_id, i),
        reverse=True,
    )
    for i in candidates[:n]:
        output_rows[i][col] = 1


def add_all_p4_twelve_win(output_rows, source_rows, col):
    """Rule 6: all Power Four teams with >= 12 wins."""
    for i, src in enumerate(source_rows):
        if (
            src["conference"] in POWER_FOUR
            and int(src[col]) >= 12
            and int(output_rows[i][col]) != 1
        ):
            output_rows[i][col] = 1


def tier_matches(src, col, tier_conf, min_wins):
    wins = int(src[col])
    if wins < min_wins:
        return False
    if tier_conf is None:
        return True
    if isinstance(tier_conf, set):
        return src["conference"] in tier_conf
    return src["conference"] == tier_conf


def fill_win_tiers_col(output_rows, source_rows, col, sos_by_team_id):
    """Fill tiers in order; stop at 12 before advancing to the next tier."""
    for tier_conf, min_wins in FILL_TIERS:
        if eligibility_count(output_rows, col) >= 12:
            break
        while eligibility_count(output_rows, col) < 12:
            candidates = [
                i
                for i, src in enumerate(source_rows)
                if tier_matches(src, col, tier_conf, min_wins)
                and int(output_rows[i][col]) != 1
            ]
            if not candidates:
                break
            pick = max(
                candidates,
                key=lambda i: wins_rank_key(source_rows, col, sos_by_team_id, i),
            )
            output_rows[pick][col] = 1


def team_sim_fpi_for_rank(sim_fpi_by_team_id, team_id, col):
    raw = (sim_fpi_by_team_id.get(team_id) or {}).get(col)
    if raw is None:
        return float("-inf")
    return float(raw)


def fill_by_fpi_col(output_rows, source_rows, col, sim_fpi_by_team_id):
    """FPI backfill: any team, highest per-sim FPI."""
    while eligibility_count(output_rows, col) < 12:
        candidates = [
            i for i in range(len(source_rows)) if int(output_rows[i][col]) != 1
        ]
        if not candidates:
            break
        pick = max(
            candidates,
            key=lambda i: (
                team_sim_fpi_for_rank(
                    sim_fpi_by_team_id, source_rows[i]["team_id"], col
                ),
                int(source_rows[i][col]),
                int(source_rows[i]["team_id"]),
            ),
        )
        output_rows[pick][col] = 1


def trim_overflow_col(
    output_rows,
    source_rows,
    col,
    sos_by_team_id,
    conf_champion_indices,
    protected_rule_123,
):
    """Trim to 12 using SOS-priority categories, then random for unprotected teams."""

    def is_p4_champion(i):
        return i in conf_champion_indices

    def trim_pick(candidates):
        return min(
            candidates,
            key=lambda i: (
                team_sos(sos_by_team_id, source_rows[i]["team_id"]),
                int(source_rows[i]["team_id"]),
            ),
        )

    while eligibility_count(output_rows, col) > 12:
        removed = False
        wins = lambda i: int(source_rows[i][col])
        conf = lambda i: source_rows[i]["conference"]
        eligible = [
            i for i in range(len(source_rows)) if int(output_rows[i][col]) == 1
        ]

        # 1. Big Ten non-champion with exactly 9 wins
        pool = removable_for_trim(
            output_rows,
            source_rows,
            col,
            [
                i
                for i in eligible
                if conf(i) == "Big Ten"
                and not is_p4_champion(i)
                and wins(i) == 9
            ],
        )
        if pool:
            output_rows[trim_pick(pool)][col] = 0
            removed = True
        if removed:
            continue

        # 2. SEC non-champion with exactly 9 wins
        pool = removable_for_trim(
            output_rows,
            source_rows,
            col,
            [
                i
                for i in eligible
                if conf(i) == "SEC" and not is_p4_champion(i) and wins(i) == 9
            ],
        )
        if pool:
            output_rows[trim_pick(pool)][col] = 0
            removed = True
        if removed:
            continue

        # 3. ACC or Big 12 non-champion with exactly 10 wins
        pool = removable_for_trim(
            output_rows,
            source_rows,
            col,
            [
                i
                for i in eligible
                if conf(i) in ACC_BIG_12
                and not is_p4_champion(i)
                and wins(i) == 10
            ],
        )
        if pool:
            output_rows[trim_pick(pool)][col] = 0
            removed = True
        if removed:
            continue

        # 4. SEC or Big Ten non-champion with exactly 10 wins
        pool = removable_for_trim(
            output_rows,
            source_rows,
            col,
            [
                i
                for i in eligible
                if conf(i) in SEC_BIG_TEN
                and not is_p4_champion(i)
                and wins(i) == 10
            ],
        )
        if pool:
            output_rows[trim_pick(pool)][col] = 0
            removed = True
        if removed:
            continue

        # 5. Random among teams not protected by rules 1-3
        pool = removable_for_trim(
            output_rows,
            source_rows,
            col,
            [i for i in eligible if i not in protected_rule_123],
        )
        if pool:
            rng = random.Random(sim_col_seed(col))
            pick = rng.choice(pool)
            output_rows[pick][col] = 0
            removed = True
        if removed:
            continue

        count = eligibility_count(output_rows, col)
        raise RuntimeError(
            f"Cannot trim {col} to 12: {count} teams eligible but no removable "
            "candidate matches overflow trim categories"
        )


def rule_123_protected_indices(
    output_rows, source_rows, col, conf_champions_by_sim, sim_fpi_by_team_id
):
    """Indices locked by rules 1-3 (P4 champs, ND >=10, G6 autobid)."""
    protected = set(
        power_four_conf_champion_indices(source_rows, col, conf_champions_by_sim)
    )
    nd_i = notre_dame_index(source_rows)
    if nd_i is not None and int(source_rows[nd_i][col]) >= 10:
        protected.add(nd_i)
    g6_i = g6_autobid_index(output_rows, source_rows, col)
    if g6_i is not None:
        protected.add(g6_i)
    return protected


def compute_column_eligibility(
    output_rows,
    source_rows,
    col,
    sim_fpi_by_team_id,
    sos_by_team_id,
    conf_champions_by_sim,
    g6_points_by_team_id,
):
    fpi = sim_fpi_by_team_id or {}
    g6_pts = g6_points_by_team_id or {}

    # Rule 1: Power Four conference champions
    apply_power_four_conf_champions_col(
        output_rows, source_rows, col, conf_champions_by_sim
    )

    # Rule 2: Notre Dame >= 10 wins
    apply_notre_dame_rule_col(output_rows, source_rows, col)

    # Rule 3: Group of 6 autobid (playoff points)
    apply_g6_autobid_col(
        output_rows, source_rows, col, g6_pts, sos_by_team_id
    )

    # Rules 4-5: top 2 SEC / Big Ten not already in field
    add_top_n_by_conference(output_rows, source_rows, col, "SEC", 2, sos_by_team_id)
    add_top_n_by_conference(
        output_rows, source_rows, col, "Big Ten", 2, sos_by_team_id
    )

    # Rule 6: Power Four teams with >= 12 wins
    add_all_p4_twelve_win(output_rows, source_rows, col)

    # Win-tier fill (stop at 12 between tiers)
    if eligibility_count(output_rows, col) < 12:
        fill_win_tiers_col(output_rows, source_rows, col, sos_by_team_id)

    # FPI backfill
    if eligibility_count(output_rows, col) < 12:
        fill_by_fpi_col(output_rows, source_rows, col, fpi)

    # Overflow trim
    if eligibility_count(output_rows, col) > 12:
        champs = power_four_conf_champion_indices(
            source_rows, col, conf_champions_by_sim
        )
        protected = rule_123_protected_indices(
            output_rows, source_rows, col, conf_champions_by_sim, fpi
        )
        trim_overflow_col(
            output_rows,
            source_rows,
            col,
            sos_by_team_id,
            champs,
            protected,
        )

    # Re-lock rules 1-3 (clear G6 flags before re-selecting autobid)
    apply_power_four_conf_champions_col(
        output_rows, source_rows, col, conf_champions_by_sim
    )
    apply_notre_dame_rule_col(output_rows, source_rows, col)
    apply_g6_autobid_col(
        output_rows, source_rows, col, g6_pts, sos_by_team_id
    )

    # Re-apply rules 4-5 after trim/re-lock so SEC/Big Ten slots are restored.
    add_top_n_by_conference(output_rows, source_rows, col, "SEC", 2, sos_by_team_id)
    add_top_n_by_conference(
        output_rows, source_rows, col, "Big Ten", 2, sos_by_team_id
    )

    if eligibility_count(output_rows, col) < 12:
        fill_win_tiers_col(output_rows, source_rows, col, sos_by_team_id)
    if eligibility_count(output_rows, col) < 12:
        fill_by_fpi_col(output_rows, source_rows, col, fpi)

    enforce_sec_big_ten_floor(output_rows, source_rows, col, sos_by_team_id)

    if eligibility_count(output_rows, col) > 12:
        champs = power_four_conf_champion_indices(
            source_rows, col, conf_champions_by_sim
        )
        protected = rule_123_protected_indices(
            output_rows, source_rows, col, conf_champions_by_sim, fpi
        )
        trim_overflow_col(
            output_rows,
            source_rows,
            col,
            sos_by_team_id,
            champs,
            protected,
        )


def load_sim_fpi_by_team_id(path):
    """team_id -> sim_col -> FPI from games file."""
    sim_fpi = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        cols = sim_columns(reader.fieldnames or [])
        for row in reader:
            team_id = row.get("team_id", "").strip()
            if not team_id or team_id in sim_fpi:
                continue
            sim_fpi[team_id] = {}
            for c in cols:
                raw = (row.get(c) or "").strip()
                if raw:
                    try:
                        sim_fpi[team_id][c] = float(raw)
                    except ValueError:
                        pass
    return sim_fpi


def compute_playoff_eligibility(
    rows,
    fieldnames,
    sim_fpi_by_team_id=None,
    conf_champions_by_sim=None,
    sos_by_team_id=None,
    g6_points_by_team_id=None,
):
    sim_cols = sim_columns(fieldnames)
    if conf_champions_by_sim is None:
        conf_champions_by_sim = {col: {} for col in sim_cols}
    if sos_by_team_id is None:
        sos_by_team_id = {}
    if g6_points_by_team_id is None:
        g6_points_by_team_id = {}

    output_rows = []
    for row in rows:
        out = {key: row[key] for key in fieldnames if key not in sim_cols}
        for col in sim_cols:
            out[col] = 0
        output_rows.append(out)

    for col in sim_cols:
        compute_column_eligibility(
            output_rows,
            rows,
            col,
            sim_fpi_by_team_id or {},
            sos_by_team_id,
            conf_champions_by_sim,
            g6_points_by_team_id,
        )

    return output_rows


def write_playoff_eligibility(
    input_path,
    output_path,
    games_fpi_path=None,
    conf_champions_by_sim=None,
    games_sim_path=None,
    conf_path=None,
    g6_points_by_team_id=None,
    g6_points_path=None,
):
    input_path = Path(input_path)
    output_path = Path(output_path)

    with input_path.open(newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        rows = list(reader)

    sim_fpi_by_team_id = {}
    sos_by_team_id = {}
    if games_fpi_path:
        games_fpi_path = Path(games_fpi_path)
        sim_fpi_by_team_id = load_sim_fpi_by_team_id(games_fpi_path)
        sos_by_team_id = load_sos_by_team_id(games_fpi_path)

    if conf_champions_by_sim is None and games_sim_path and games_fpi_path and conf_path:
        from cfb_conf_championship import compute_conf_results_by_sim

        results = compute_conf_results_by_sim(
            Path(games_sim_path), Path(games_fpi_path), Path(conf_path)
        )
        conf_champions_by_sim = results["champions"]

    if g6_points_by_team_id is None:
        if g6_points_path and Path(g6_points_path).is_file():
            from cfb_g6_playoff_points import load_g6_points_by_team_id

            g6_points_by_team_id = load_g6_points_by_team_id(Path(g6_points_path))
        elif games_sim_path and conf_path and conf_champions_by_sim is not None:
            from cfb_g6_playoff_points import compute_g6_playoff_points, g6_points_by_team_id_from_rows

            g6_fieldnames, g6_rows = compute_g6_playoff_points(
                Path(games_sim_path),
                Path(conf_path),
                conf_champions_by_sim,
            )
            g6_points_by_team_id = g6_points_by_team_id_from_rows(
                g6_rows, g6_fieldnames
            )
        else:
            g6_points_by_team_id = {}

    output_rows = compute_playoff_eligibility(
        rows,
        fieldnames,
        sim_fpi_by_team_id,
        conf_champions_by_sim,
        sos_by_team_id,
        g6_points_by_team_id,
    )

    with output_path.open("w", newline="", encoding="utf-8-sig") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    return len(output_rows)
