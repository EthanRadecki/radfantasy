"""
validate_flock_adp.py

Validates data/adp/adp_flock.json:
  1. Structural checks: required fields, allowed positions only, no leftover
     duplicate-partial-record bug rows, plausible rank/ADP values, exactly
     one row per (player_name, scoring_format, snapshot_date).
  2. Ground-truth spot check against an independently verifiable fact:
     as of the 2026-08-04 snapshot, Jahmyr Gibbs is the consensus #1 overall
     player across PPR/half-PPR/standard formats (matches well-documented
     preseason 2026 fantasy consensus, not just this file's internal logic).
"""

import json
import sys
from collections import Counter
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "adp" / "adp_flock.json"
ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}


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

    required_fields = {"player_name", "team", "position", "position_rank",
                        "rank", "adp", "scoring_format", "window", "snapshot_date"}

    key_counter = Counter()
    for r in records:
        missing = required_fields - r.keys()
        if missing:
            ok = fail(f"record missing fields {missing}: {r}") and ok

        if r["position"] not in ALLOWED_POSITIONS:
            ok = fail(f"disallowed position leaked through: {r}") and ok

        if r["adp"] is None or r["adp"] <= 0:
            ok = fail(f"non-positive ADP: {r}") and ok

        if r["rank"] is None or r["rank"] <= 0:
            ok = fail(f"non-positive rank: {r}") and ok

        key_counter[(r["player_name"], r["scoring_format"], r["snapshot_date"])] += 1

    dupes = {k: c for k, c in key_counter.items() if c > 1}
    if dupes:
        ok = fail(f"{len(dupes)} (player, format, date) keys still duplicated "
                  f"-- dedup bug fix may be incomplete: {list(dupes)[:5]}") and ok
    else:
        print("OK: exactly one row per (player_name, scoring_format, snapshot_date)")

    by_format = {}
    for r in records:
        by_format.setdefault(r["scoring_format"], []).append(r)

    for fmt, recs in by_format.items():
        top = min(recs, key=lambda r: r["rank"])
        if top["rank"] != 1:
            ok = fail(f"{fmt}: no rank-1 row found (min rank is {top['rank']})") and ok
        elif top["player_name"] != "Jahmyr Gibbs":
            ok = fail(
                f"spot check: expected Jahmyr Gibbs at overall #1 in {fmt}, "
                f"got {top['player_name']}"
            ) and ok
        else:
            print(f"OK: {fmt} spot check -- Jahmyr Gibbs is overall #1 as expected")

    print()
    print("ALL CHECKS PASSED" if ok else "VALIDATION FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
