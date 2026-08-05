"""
validate_team_stats.py

Validates data/stats/team_season_stats.json:
  1. Structural: wins+losses+ties == games_played, non-negative points,
     one row per (team, season), 32 teams per season for 2002+ (31 for
     1999-2001, before the Houston Texans' 2002 expansion -- real history,
     not a bug), games_played of 16 or 17 for 2021+ seasons (17-game season,
     allowing one fewer for the rare no-contest game).
  2. Ground-truth spot check: the 2024 Detroit Lions went 15-2 with 564
     points for and 342 points against (independently documented).

Exits non-zero if any check fails.
"""

import json
import sys
from collections import Counter
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "stats" / "team_season_stats.json"


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def main():
    ok = True

    if not DATA_PATH.exists():
        print(f"FAIL: {DATA_PATH} does not exist -- run generate_team_season_stats.py first")
        sys.exit(1)

    records = json.loads(DATA_PATH.read_text())
    print(f"Loaded {len(records)} records from {DATA_PATH}")
    if not records:
        print("FAIL: zero records")
        sys.exit(1)

    key_counts = Counter((r["team"], r["season"]) for r in records)
    dupes = {k: c for k, c in key_counts.items() if c > 1}
    if dupes:
        ok = fail(f"{len(dupes)} duplicate (team, season) keys") and ok
    else:
        print("OK: exactly one row per (team, season)")

    for r in records:
        total = r["wins"] + r["losses"] + r["ties"]
        if total != r["games_played"]:
            ok = fail(f"{r['team']} {r['season']}: wins+losses+ties ({total}) "
                      f"!= games_played ({r['games_played']})") and ok
        if r["points_for"] < 0 or r["points_against"] < 0:
            ok = fail(f"{r['team']} {r['season']}: negative points") and ok
        if r["point_differential"] != r["points_for"] - r["points_against"]:
            ok = fail(f"{r['team']} {r['season']}: point_differential doesn't match "
                      f"points_for - points_against") and ok
        if r["season"] >= 2021 and not (16 <= r["games_played"] <= 17):
            ok = fail(f"{r['team']} {r['season']}: games_played={r['games_played']}, "
                      f"expected 16 or 17") and ok

    by_season = Counter(r["season"] for r in records)
    for season, count in sorted(by_season.items()):
        expected = 31 if season <= 2001 else 32
        if count != expected:
            ok = fail(f"{season}: {count} teams present, expected {expected}") and ok
    print(f"OK: team counts per season check passed for {len(by_season)} seasons "
          f"(31 pre-2002, 32 from 2002 on)" if ok else "")

    lions_2024 = next((r for r in records if r["team"] == "DET" and r["season"] == 2024), None)
    if lions_2024 is None:
        ok = fail("spot check: 2024 Detroit Lions row not found") and ok
    else:
        checks = [("wins", 15), ("losses", 2), ("points_for", 564), ("points_against", 342)]
        mismatches = [(f, e, lions_2024.get(f)) for f, e in checks if lions_2024.get(f) != e]
        if mismatches:
            for f, e, got in mismatches:
                ok = fail(f"spot check: 2024 Lions {f} expected {e}, got {got}") and ok
        else:
            print("OK: spot check -- 2024 Lions are 15-2, 564 PF, 342 PA as expected")

    print()
    print("ALL CHECKS PASSED" if ok else "VALIDATION FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
