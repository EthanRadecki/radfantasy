"""
dst_scoring.py

Team Defense/Special Teams fantasy scoring, using the exact custom scoring
rules provided (not a generic default -- these numbers were given directly):

  Each Sack (SK)                          1
  Each Interception (INT)                 2
  Each Fumble Recovered (FR)               2
  Each Safety (SF)                        2
  Blocked Punt, PAT or FG (BLKK)           2
  Any D/ST return TD (KRTD/PRTD/INTTD/     6
    FRTD/BLKKRTD -- all worth the same,
    so tracked as one def_tds count)
  2pt Return (2PTRET)                      2   -- see NOTE below, NOT implemented
  Points allowed: tiered, see POINTS_ALLOWED_TIERS
  Yards allowed: tiered, see YARDS_ALLOWED_TIERS

Unlike offensive scoring, D/ST has no PPR/half-PPR/standard variants --
it's the same point value regardless of scoring format.

NOTE ON 2PT RETURN: this is one of the rarest events in football (a defense
returning an opponent's failed 2-point conversion attempt for 2 points has
happened only a handful of times in NFL history). Reliably detecting it from
play-by-play requires very specific columns whose presence/consistency
wasn't something I could verify without live data access. Rather than ship
a guessed, untested detection rule for an event this rare, raw_stats always
carries "two_point_returns": 0 with a flag noting it's not implemented --
if this exact event happens to occur for a team you're tracking, you'd need
to manually correct that field.
"""

POINTS_ALLOWED_TIERS = [
    (0, 0, 5),      # 0 points allowed
    (1, 6, 4),      # 1-6
    (7, 13, 3),     # 7-13
    (14, 17, 1),    # 14-17
    (18, 27, 0),    # 18-27 (not explicitly listed in the source rules -- treated as the neutral gap between 17 and 28)
    (28, 34, -1),   # 28-34
    (35, 45, -3),   # 35-45
    (46, float("inf"), -5),  # 46+
]

YARDS_ALLOWED_TIERS = [
    (0, 99, 5),       # less than 100
    (100, 199, 3),
    (200, 299, 2),
    (300, 349, 0),    # not explicitly listed in the source rules -- neutral gap between 299 and 350
    (350, 399, -1),
    (400, 449, -3),
    (450, 499, -5),
    (500, 549, -6),
    (550, float("inf"), -7),
]


def _tier_points(value: int, tiers: list) -> int:
    for lo, hi, points in tiers:
        if lo <= value <= hi:
            return points
    raise ValueError(f"value {value} did not match any tier -- tier table is incomplete")


def calculate_dst_fantasy_points(raw_stats: dict) -> float:
    """
    raw_stats keys: sacks, interceptions, fumbles_recovered, safeties,
    blocked_kicks, def_tds, two_point_returns, points_allowed, yards_allowed.
    """
    points = (
        raw_stats.get("sacks", 0) * 1
        + raw_stats.get("interceptions", 0) * 2
        + raw_stats.get("fumbles_recovered", 0) * 2
        + raw_stats.get("safeties", 0) * 2
        + raw_stats.get("blocked_kicks", 0) * 2
        + raw_stats.get("def_tds", 0) * 6
        + raw_stats.get("two_point_returns", 0) * 2
        + _tier_points(raw_stats["points_allowed"], POINTS_ALLOWED_TIERS)
        + _tier_points(raw_stats["yards_allowed"], YARDS_ALLOWED_TIERS)
    )
    return round(points, 2)
