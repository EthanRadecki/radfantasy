"""
scoring.py

Shared fantasy-point calculator for standard / half-PPR / PPR scoring, used
by both generate_player_weekly_stats.py and generate_player_season_stats.py
so the two pipelines can never drift out of sync on scoring rules.

This is a common industry-default scoring set, NOT necessarily your league's
exact rules -- the constants below are the one place to edit if your league
scores differently (e.g. TE premium, different PPR fractions, 6pt-passing-TD
leagues, different FG distance brackets).
"""

PASSING_YARDS_PER_POINT = 25
PASSING_TD_POINTS = 4
INTERCEPTION_POINTS = -2
TWO_POINT_CONVERSION_POINTS = 2

RUSHING_YARDS_PER_POINT = 10
RUSHING_TD_POINTS = 6
FUMBLE_LOST_POINTS = -2

RECEIVING_YARDS_PER_POINT = 10
RECEIVING_TD_POINTS = 6
RECEPTION_POINTS = {"standard": 0.0, "half_ppr": 0.5, "ppr": 1.0}

SPECIAL_TEAMS_TD_POINTS = 6

# Kicking (used only for rows that carry kicking_stats -- see kicking.py)
FG_POINTS_BY_DISTANCE = [
    (39, 3),   # 0-39 yards
    (49, 4),   # 40-49 yards
    (59, 5),   # 50-59 yards
    (999, 6),  # 60+ yards
]
FG_MISSED_POINTS = -1
PAT_MADE_POINTS = 1


def _fg_points(makes_by_distance: dict) -> float:
    """makes_by_distance: {"0-39": n, "40-49": n, "50-59": n, "60+": n}"""
    return (
        makes_by_distance.get("0-39", 0) * 3
        + makes_by_distance.get("40-49", 0) * 4
        + makes_by_distance.get("50-59", 0) * 5
        + makes_by_distance.get("60+", 0) * 6
    )


def calculate_fantasy_points(raw_stats: dict, kicking_stats: dict | None = None) -> dict:
    """
    raw_stats: dict with the standard offensive counting-stat keys (passing_yards,
    passing_tds, interceptions, passing_2pt_conversions, rushing_yards, rushing_tds,
    rushing_2pt_conversions, rushing_fumbles_lost, receiving_yards, receiving_tds,
    receiving_2pt_conversions, receiving_fumbles_lost, receptions, special_teams_tds).

    kicking_stats: optional dict with fg_makes_by_distance (see _fg_points) and
    pat_made -- only populated for position == "K" rows once kicking.py has
    merged in play-by-play-derived kicking stats.

    Returns {"standard": x, "half_ppr": x, "ppr": x}.
    """
    base = (
        raw_stats.get("passing_yards", 0) / PASSING_YARDS_PER_POINT
        + raw_stats.get("passing_tds", 0) * PASSING_TD_POINTS
        + raw_stats.get("interceptions", 0) * INTERCEPTION_POINTS
        + raw_stats.get("passing_2pt_conversions", 0) * TWO_POINT_CONVERSION_POINTS
        + raw_stats.get("rushing_yards", 0) / RUSHING_YARDS_PER_POINT
        + raw_stats.get("rushing_tds", 0) * RUSHING_TD_POINTS
        + raw_stats.get("rushing_2pt_conversions", 0) * TWO_POINT_CONVERSION_POINTS
        + raw_stats.get("rushing_fumbles_lost", 0) * FUMBLE_LOST_POINTS
        + raw_stats.get("receiving_yards", 0) / RECEIVING_YARDS_PER_POINT
        + raw_stats.get("receiving_tds", 0) * RECEIVING_TD_POINTS
        + raw_stats.get("receiving_2pt_conversions", 0) * TWO_POINT_CONVERSION_POINTS
        + raw_stats.get("receiving_fumbles_lost", 0) * FUMBLE_LOST_POINTS
        + raw_stats.get("special_teams_tds", 0) * SPECIAL_TEAMS_TD_POINTS
    )

    kicking_points = 0.0
    if kicking_stats:
        fg_attempts = kicking_stats.get("fg_attempts", 0)
        fg_made = kicking_stats.get("fg_made", sum(kicking_stats.get("fg_makes_by_distance", {}).values()))
        fg_missed = fg_attempts - fg_made
        kicking_points = (
            _fg_points(kicking_stats.get("fg_makes_by_distance", {}))
            + fg_missed * FG_MISSED_POINTS
            + kicking_stats.get("pat_made", 0) * PAT_MADE_POINTS
        )

    receptions = raw_stats.get("receptions", 0)
    return {
        fmt: round(base + kicking_points + receptions * mult, 2)
        for fmt, mult in RECEPTION_POINTS.items()
    }
