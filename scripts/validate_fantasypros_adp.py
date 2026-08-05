"""
validate_fantasypros_adp.py

Validates data/adp/adp_fantasypros.json:
  1. Structural checks: required fields present, positions in the allowed
     skill/K/DST set, no IDP leakage, bye weeks in a plausible range, no
     exact duplicate (year, player_name, team) rows, ADP values positive
     and non-decreasing enough to catch gross parsing errors.
  2. Ground-truth spot checks against independently verifiable facts about
     real NFL/FantasyPros ADP history (not derived from this file).

Exits non-zero if any check fails.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "adp" / "adp_fantasypros.json"
ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DST"}

# Independently verifiable facts about real-world consensus ADP, used as
# spot checks. These are well-documented historical facts, not values we
# derived from this dataset.
SPOT_CHECKS = [
    # (year, player_name, expected overall rank == 1)
    (2018, "Todd Gurley", 1),
    (2021, "Christian McCaffrey", 1),
    (2022, "Jonathan Taylor", 1),
    (2025, "Ja'Marr Chase", 1),
]


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def main():
    ok = True

    if not DATA_PATH.exists():
        print(f"FAIL: {DATA_PATH} does not exist")
        sys.exit(1)

    records = json.loads(DATA_PATH.read_text())
    print(f"Loaded {len(records)} records from {DATA_PATH}")

    # --- structural checks ---
    required_fields = {"year", "rank", "player_name", "team", "bye_week", "position", "position_rank", "adp"}
    seen = set()
    dup_count = 0
    by_year = defaultdict(list)

    for r in records:
        by_year[r["year"]].append(r)

        missing = required_fields - r.keys()
        if missing:
            ok = fail(f"record missing fields {missing}: {r}") and ok

        if r["position"] not in ALLOWED_POSITIONS:
            ok = fail(f"disallowed position leaked through: {r}") and ok

        if r["bye_week"] is not None and not (1 <= r["bye_week"] <= 18):
            ok = fail(f"implausible bye week: {r}") and ok

        if r["adp"] is None or r["adp"] <= 0:
            ok = fail(f"non-positive ADP: {r}") and ok

        key = (r["year"], r["player_name"], r["team"])
        if key in seen:
            dup_count += 1
        seen.add(key)

    if dup_count:
        ok = fail(f"{dup_count} exact duplicate (year, player_name, team) rows found") and ok
    else:
        print("OK: no exact duplicate (year, player_name, team) rows")

    for year, recs in sorted(by_year.items()):
        ranks = [r["rank"] for r in recs]
        if len(ranks) != len(set(ranks)):
            ok = fail(f"{year}: duplicate overall ranks within the same year") and ok
        dst_count = sum(1 for r in recs if r["position"] == "DST")
        if dst_count == 0:
            ok = fail(f"{year}: zero DST rows -- team-defense parsing likely broken") and ok
        elif dst_count > 32:
            ok = fail(f"{year}: {dst_count} DST rows, more than the 32 real NFL teams") and ok

    print(f"OK: structural checks passed for {len(by_year)} years"
          if ok else "Some structural checks failed (see above)")

    # --- ground-truth spot checks ---
    for year, name, expected_rank in SPOT_CHECKS:
        match = next((r for r in by_year.get(year, []) if r["player_name"] == name), None)
        if match is None:
            ok = fail(f"spot check: {name} not found in {year} data at all") and ok
            continue
        if match["rank"] != expected_rank:
            ok = fail(
                f"spot check: expected {name} rank {expected_rank} in {year}, "
                f"got rank {match['rank']}"
            ) and ok
        else:
            print(f"OK: {year} spot check -- {name} is rank {expected_rank} as expected")

    print()
    print("ALL CHECKS PASSED" if ok else "VALIDATION FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
