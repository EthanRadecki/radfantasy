"""
validate_team_defense_stats.py

Validates BOTH data/stats/team_defense_stats.json (weekly) and
data/stats/team_defense_season_stats.json (season), if present.

Checks:
  1. Structural: no negative raw stat values, fantasy_points recomputes
     correctly from raw_stats via dst_scoring (weekly file only -- season
     file is a sum of already-correct weekly points, not re-tiered, see
     generate_team_defense_season_stats.py's docstring for why),
     one row per (team, season, week) / (team, season).
  2. Ground-truth spot check: the 2025 Denver Broncos led the NFL with 68
     sacks (independently documented -- StatMuse, FanDuel Research,
     Sportskeeda, and others all agree on this figure).

Exits non-zero on any structural failure. Prints a warning (does not fail)
if the season file is missing, since it's optional.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dst_scoring import calculate_dst_fantasy_points

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "stats"
WEEKLY_PATH = DATA_DIR / "team_defense_stats.json"
SEASON_PATH = DATA_DIR / "team_defense_season_stats.json"

NON_NEGATIVE_FIELDS = ["sacks", "interceptions", "fumbles_recovered", "safeties",
                       "blocked_kicks", "def_tds", "two_point_returns",
                       "points_allowed", "yards_allowed"]


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def validate_weekly():
    ok = True
    if not WEEKLY_PATH.exists():
        print(f"FAIL: {WEEKLY_PATH} does not exist -- run generate_team_defense_stats.py first")
        return False

    records = json.loads(WEEKLY_PATH.read_text())
    print(f"Loaded {len(records)} weekly records from {WEEKLY_PATH}")
    if not records:
        print("FAIL: zero records")
        return False

    key_counts = Counter((r["team"], r["season"], r["week"]) for r in records)
    dupes = {k: c for k, c in key_counts.items() if c > 1}
    if dupes:
        ok = fail(f"{len(dupes)} duplicate (team, season, week) keys") and ok
    else:
        print("OK: exactly one row per (team, season, week)")

    negative_count = 0
    for r in records:
        for f in NON_NEGATIVE_FIELDS:
            if r["raw_stats"][f] < 0:
                negative_count += 1
    if negative_count:
        ok = fail(f"{negative_count} negative raw-stat values found") and ok
    else:
        print("OK: no negative raw-stat values")

    math_errors = 0
    for r in records:
        recomputed = calculate_dst_fantasy_points(r["raw_stats"])
        if abs(recomputed - r["fantasy_points"]) > 0.01:
            math_errors += 1
    if math_errors:
        ok = fail(f"{math_errors} rows where stored fantasy_points doesn't match "
                  f"recomputing from raw_stats") and ok
    else:
        print("OK: fantasy_points recomputes correctly from raw_stats for every row")

    return ok


def validate_season():
    if not SEASON_PATH.exists():
        print(f"NOTE: {SEASON_PATH} not found -- skipping season-level checks "
              f"(run generate_team_defense_season_stats.py if you want it)")
        return True

    ok = True
    records = json.loads(SEASON_PATH.read_text())
    print(f"Loaded {len(records)} season records from {SEASON_PATH}")

    key_counts = Counter((r["team"], r["season"]) for r in records)
    dupes = {k: c for k, c in key_counts.items() if c > 1}
    if dupes:
        ok = fail(f"{len(dupes)} duplicate (team, season) keys") and ok
    else:
        print("OK: exactly one row per (team, season)")

    den_2025 = next((r for r in records if r["team"] == "DEN" and r["season"] == 2025), None)
    if den_2025 is None:
        ok = fail("spot check: 2025 Denver Broncos row not found") and ok
    elif den_2025["raw_stats"]["sacks"] != 68:
        ok = fail(f"spot check: 2025 Denver sacks expected 68, "
                  f"got {den_2025['raw_stats']['sacks']}") and ok
    else:
        print("OK: spot check -- 2025 Denver Broncos recorded 68 sacks as expected")

    return ok


def main():
    weekly_ok = validate_weekly()
    print()
    season_ok = validate_season()

    print()
    print("ALL CHECKS PASSED" if (weekly_ok and season_ok) else "VALIDATION FAILED")
    sys.exit(0 if (weekly_ok and season_ok) else 1)


if __name__ == "__main__":
    main()
