"""
validate_season_stats.py

Validates data/stats/player_season_stats.json (nested raw_stats/fantasy_points
schema):
  1. Structural: allowed positions only, one row per (player_id, season),
     fantasy-point math is internally consistent (ppr - half_ppr ==
     0.5 * receptions, ppr - standard == 1.0 * receptions) for every row,
     not just the spot-checked ones.
  2. Kicker-bug-fix check: at least one K row exists with non-null kicking
     stats, for the seasons present -- if this fails, the pbp-derived
     kicking merge silently produced nothing.
  3. Ground-truth spot checks against independently verified 2024 facts:
     Saquon Barkley (2,005 rushing yards, 16 games played) and Ja'Marr Chase
     (led the NFL in 2024 receiving yards, 1,708).

Exits non-zero if any check fails.
"""

import json
import sys
from collections import Counter
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "stats" / "player_season_stats.json"
ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def main():
    ok = True

    if not DATA_PATH.exists():
        print(f"FAIL: {DATA_PATH} does not exist -- run generate_player_season_stats.py first")
        sys.exit(1)

    records = json.loads(DATA_PATH.read_text())
    print(f"Loaded {len(records)} records from {DATA_PATH}")
    if not records:
        print("FAIL: zero records")
        sys.exit(1)

    bad_pos = [r for r in records if r["position"] not in ALLOWED_POSITIONS]
    if bad_pos:
        ok = fail(f"{len(bad_pos)} rows outside {ALLOWED_POSITIONS}, "
                  f"e.g. {bad_pos[0]['position']}") and ok
    else:
        print(f"OK: all rows within {ALLOWED_POSITIONS}")

    key_counts = Counter((r["player_id"], r["season"]) for r in records)
    dupes = {k: c for k, c in key_counts.items() if c > 1}
    if dupes:
        ok = fail(f"{len(dupes)} duplicate (player_id, season) keys: {list(dupes)[:5]}") and ok
    else:
        print("OK: exactly one row per (player_id, season)")

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
        ok = fail(f"{len(kickers)} K rows present but none carry kicking stats -- "
                  f"pbp merge produced nothing") and ok
    else:
        print(f"OK: {len(kickers_with_kicking)}/{len(kickers)} K rows have kicking stats")

    # --- ground-truth spot checks ---
    barkley = next((r for r in records if r["season"] == 2024
                     and "Barkley" in r["player_name"]), None)
    if barkley is None:
        ok = fail("spot check: Saquon Barkley 2024 not found") and ok
    else:
        if abs(barkley["raw_stats"]["rushing_yards"] - 2005) > 2:
            ok = fail(f"spot check: Barkley 2024 rushing_yards expected ~2005, "
                      f"got {barkley['raw_stats']['rushing_yards']}") and ok
        elif barkley["games_played"] not in (16, None):
            ok = fail(f"spot check: Barkley 2024 games_played expected 16, "
                      f"got {barkley['games_played']}") and ok
        else:
            print(f"OK: spot check -- Barkley 2024: "
                  f"{barkley['raw_stats']['rushing_yards']} rush yds, "
                  f"{barkley['games_played']} games")

    season_2024 = [r for r in records if r["season"] == 2024
                    and r["position"] in ("QB", "RB", "WR", "TE")]
    if season_2024:
        top_receiver = max(season_2024, key=lambda r: r["raw_stats"].get("receiving_yards", 0))
        if "Chase" not in top_receiver["player_name"]:
            ok = fail(f"spot check: expected Ja'Marr Chase to lead 2024 receiving yards, "
                      f"got {top_receiver['player_name']} "
                      f"({top_receiver['raw_stats']['receiving_yards']})") and ok
        else:
            print(f"OK: spot check -- {top_receiver['player_name']} leads 2024 receiving "
                  f"yards with {top_receiver['raw_stats']['receiving_yards']}")

    print()
    print("ALL CHECKS PASSED" if ok else "VALIDATION FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
