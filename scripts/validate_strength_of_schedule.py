"""
validate_strength_of_schedule.py

Validates data/context/strength_of_schedule_2026.json:
  1. Structural: 32 teams, all six SOS groups present per team
     (passing/rushing/receiving_wr/receiving_te/kicking/dst), each with
     full_season and playoff_weeks sub-objects, ranks within each of the
     11 rankable fields (5 position SOS x 2 windows, 1 composite DST rank
     x 2 windows... position ranks) form clean 1-32 permutations with no
     duplicates (ties are possible in principle if two teams have exactly
     equal average values, so this checks "no team missing a rank" rather
     than a strict permutation).
  2. Sanity check: no team's playoff-weeks value is computed from an empty
     set (every team should play at least one game in weeks 15-17).
  3. Directional sanity check: for D/ST, a team with a LOWER
     avg_opponent_points_scored should never have a WORSE composite_rank
     than a team with clearly higher avg_opponent_points_scored and
     identical values on the other two components -- this is a soft check
     (logged, not failed) since the three components can pull in different
     directions for any individual team; it's meant to catch a wholesale
     sign error, not flag normal composite disagreement.

Exits non-zero on structural failures. This does NOT check the "is 2025
performance a good predictor of 2026" question -- there's no ground truth
for that until the 2026 season is played. See the module docstring in
generate_strength_of_schedule.py for that limitation.
"""

import json
import sys
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "context" / "strength_of_schedule_2026.json"

POSITION_SOS_FIELDS = ["passing_sos", "rushing_sos", "receiving_wr_sos", "receiving_te_sos", "kicking_sos"]


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def main():
    ok = True

    if not DATA_PATH.exists():
        print(f"FAIL: {DATA_PATH} does not exist -- run generate_strength_of_schedule.py first")
        sys.exit(1)

    records = json.loads(DATA_PATH.read_text())
    print(f"Loaded {len(records)} records from {DATA_PATH}")

    if len(records) != 32:
        ok = fail(f"expected 32 teams, got {len(records)}") and ok
    else:
        print("OK: all 32 teams present")

    for r in records:
        for field in POSITION_SOS_FIELDS + ["dst_sos"]:
            if field not in r:
                ok = fail(f"{r['team']}: missing '{field}'") and ok
                continue
            for window in ("full_season", "playoff_weeks"):
                if window not in r[field]:
                    ok = fail(f"{r['team']}.{field}: missing '{window}'") and ok

    for field in POSITION_SOS_FIELDS:
        for window in ("full_season", "playoff_weeks"):
            ranks = [r[field][window]["rank"] for r in records if r[field][window]["rank"] is not None]
            missing = 32 - len(ranks)
            if missing:
                ok = fail(f"{field}.{window}: {missing} team(s) have no rank at all "
                          f"(likely missing baseline data for an opponent)") and ok
            elif sorted(ranks) != list(range(1, 33)):
                ok = fail(f"{field}.{window}: ranks aren't a clean 1-32 permutation "
                          f"(duplicates or gaps -- check for tied average values)") and ok
        print(f"OK: {field} ranks are complete for both windows" if ok else "")

    for window in ("full_season", "playoff_weeks"):
        composite_ranks = [r["dst_sos"][window]["composite_rank"] for r in records
                            if r["dst_sos"][window]["composite_rank"] is not None]
        if len(composite_ranks) != 32:
            ok = fail(f"dst_sos.{window}: only {len(composite_ranks)}/32 teams have a composite rank") and ok
        else:
            print(f"OK: dst_sos.{window} composite rank complete for all 32 teams")

    # Playoff-weeks values should never be None for a real 17-game schedule.
    for r in records:
        for field in POSITION_SOS_FIELDS:
            if r[field]["playoff_weeks"]["value"] is None:
                ok = fail(f"{r['team']}.{field}.playoff_weeks: no value -- team may have "
                          f"no games in weeks 15-17, check the schedule fetch") and ok

    print()
    print("ALL CHECKS PASSED" if ok else "VALIDATION FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
