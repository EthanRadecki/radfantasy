"""
validate_player_weekly_stats.py

Validates data/stats/player_weekly_stats.json:
  1. Structural: allowed positions only, one row per (player_id, season, week),
     fantasy-point math internally consistent across all rows.
  2. Kicker-bug-fix check: at least one K row with populated kicking stats.
  3. Ground-truth spot check: Saquon Barkley's 2024 Week 17 game vs. Dallas
     is independently documented as 167 rushing yards on 31 carries (the
     game in which he passed 2,000 rushing yards for the season).

Exits non-zero if any check fails.
"""

import json
import sys
from collections import Counter
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "stats" / "player_weekly_stats.json"
ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def main():
    ok = True

    if not DATA_PATH.exists():
        print(f"FAIL: {DATA_PATH} does not exist -- run generate_player_weekly_stats.py first")
        sys.exit(1)

    records = json.loads(DATA_PATH.read_text())
    print(f"Loaded {len(records)} records from {DATA_PATH}")
    if not records:
        print("FAIL: zero records")
        sys.exit(1)

    bad_pos = [r for r in records if r["position"] not in ALLOWED_POSITIONS]
    if bad_pos:
        ok = fail(f"{len(bad_pos)} rows outside {ALLOWED_POSITIONS}") and ok
    else:
        print(f"OK: all rows within {ALLOWED_POSITIONS}")

    key_counts = Counter((r["player_id"], r["season"], r["week"]) for r in records)
    dupes = {k: c for k, c in key_counts.items() if c > 1}
    if dupes:
        ok = fail(f"{len(dupes)} duplicate (player_id, season, week) keys") and ok
    else:
        print("OK: exactly one row per (player_id, season, week)")

    math_errors = 0
    for r in records:
        rec = r["raw_stats"].get("receptions", 0)
        fp = r["fantasy_points"]
        if abs((fp["ppr"] - fp["half_ppr"]) - 0.5 * rec) > 0.02:
            math_errors += 1
        if abs((fp["ppr"] - fp["standard"]) - 1.0 * rec) > 0.02:
            math_errors += 1
    if math_errors:
        ok = fail(f"{math_errors} rows have inconsistent PPR/half-PPR/standard math") and ok
    else:
        print("OK: fantasy-point math is internally consistent across all rows")

    kickers = [r for r in records if r["position"] == "K"]
    kickers_with_kicking = [r for r in kickers if "kicking" in r["raw_stats"]]
    if not kickers:
        ok = fail("zero K rows present at all -- kicker bug not fixed") and ok
    elif not kickers_with_kicking:
        ok = fail(f"{len(kickers)} K rows present but none carry kicking stats") and ok
    else:
        print(f"OK: {len(kickers_with_kicking)}/{len(kickers)} K rows have kicking stats")

    # --- ground-truth spot check ---
    candidates = [r for r in records if r["season"] == 2024 and r["week"] == 17
                  and "Barkley" in r["player_name"]]
    if not candidates:
        ok = fail("spot check: Barkley Week 17 2024 row not found") and ok
    else:
        r = candidates[0]
        rush_yds = r["raw_stats"]["rushing_yards"]
        if abs(rush_yds - 167) > 1:
            ok = fail(f"spot check: Barkley Week 17 2024 expected ~167 rushing yards, "
                      f"got {rush_yds}") and ok
        else:
            print(f"OK: spot check -- Barkley Week 17 2024 rushing yards = {rush_yds} "
                  f"(expected ~167)")

    print()
    print("ALL CHECKS PASSED" if ok else "VALIDATION FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
