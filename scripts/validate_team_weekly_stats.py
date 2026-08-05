"""
validate_team_weekly_stats.py

Validates data/stats/team_weekly_stats.json:
  1. Structural: every (team, season, week) key appears exactly once, every
     real game produces exactly two rows (one per team) with matching/
     opposite points_for and points_against, result values are consistent
     with the score, non-negative points.
  2. Ground-truth spot check: the 2024 Detroit Lions beat the San Francisco
     49ers 40-34 on the road in Week 17 (Monday Night Football, 12/30/2024
     -- independently documented, e.g. NFL.com's game center, moved Detroit
     to 14-2).

Exits non-zero if any check fails.
"""

import json
import sys
from collections import Counter
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "stats" / "team_weekly_stats.json"


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def main():
    ok = True

    if not DATA_PATH.exists():
        print(f"FAIL: {DATA_PATH} does not exist -- run generate_team_weekly_stats.py first")
        sys.exit(1)

    records = json.loads(DATA_PATH.read_text())
    print(f"Loaded {len(records)} records from {DATA_PATH}")
    if not records:
        print("FAIL: zero records")
        sys.exit(1)

    key_counts = Counter((r["team"], r["season"], r["week"]) for r in records)
    dupes = {k: c for k, c in key_counts.items() if c > 1}
    if dupes:
        ok = fail(f"{len(dupes)} duplicate (team, season, week) keys") and ok
    else:
        print("OK: exactly one row per (team, season, week)")

    for r in records:
        if r["points_for"] < 0 or r["points_against"] < 0:
            ok = fail(f"{r['team']} {r['season']} wk{r['week']}: negative points") and ok
        expected_result = (
            "W" if r["points_for"] > r["points_against"]
            else "L" if r["points_for"] < r["points_against"]
            else "T"
        )
        if r["result"] != expected_result:
            ok = fail(f"{r['team']} {r['season']} wk{r['week']}: result={r['result']} "
                      f"doesn't match score {r['points_for']}-{r['points_against']}") and ok

    # Every game should appear as a matched pair: team A's pf/pa should be
    # team B's pa/pf for the same (season, week, opponent-pair).
    by_game = {}
    for r in records:
        game_key = tuple(sorted([r["team"], r["opponent"]])) + (r["season"], r["week"])
        by_game.setdefault(game_key, []).append(r)

    unpaired = [k for k, v in by_game.items() if len(v) != 2]
    if unpaired:
        ok = fail(f"{len(unpaired)} games without exactly 2 team-rows, e.g. {unpaired[0]}") and ok
    else:
        mismatched_scores = 0
        for pair in by_game.values():
            a, b = pair
            if a["points_for"] != b["points_against"] or b["points_for"] != a["points_against"]:
                mismatched_scores += 1
        if mismatched_scores:
            ok = fail(f"{mismatched_scores} games where the two team-rows disagree on the score") and ok
        else:
            print(f"OK: all {len(by_game)} games have a consistent, matched team-row pair")

    # --- ground-truth spot check ---
    lions_wk17 = next((r for r in records if r["team"] == "DET"
                        and r["season"] == 2024 and r["week"] == 17), None)
    if lions_wk17 is None:
        ok = fail("spot check: 2024 Lions Week 17 row not found") and ok
    else:
        checks = [("opponent", "SF"), ("points_for", 40), ("points_against", 34), ("result", "W")]
        mismatches = [(f, e, lions_wk17.get(f)) for f, e in checks if lions_wk17.get(f) != e]
        if mismatches:
            for f, e, got in mismatches:
                ok = fail(f"spot check: 2024 Lions Wk17 {f} expected {e}, got {got}") and ok
        else:
            print("OK: spot check -- 2024 Lions beat SF 40-34 in Week 17 as expected")

    print()
    print("ALL CHECKS PASSED" if ok else "VALIDATION FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
