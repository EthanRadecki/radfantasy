"""
validate_offensive_line_rankings_2025.py

Validates data/context/offensive_line_rankings_2025.json:
  1. Structural: exactly 32 teams, ranks form a clean 1-32 permutation
     (no ties, no gaps, no duplicates -- unlike the 2026 4for4 data, PFF's
     list here has no ties).
  2. Spot checks against the source document itself: Broncos are rank 1,
     Raiders are rank 32.

Exits non-zero if any check fails.
"""

import json
import sys
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "context" / "offensive_line_rankings_2025.json"


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def main():
    ok = True

    if not DATA_PATH.exists():
        print(f"FAIL: {DATA_PATH} does not exist -- run ingest_offensive_line_rankings_2025.py first")
        sys.exit(1)

    records = json.loads(DATA_PATH.read_text())
    print(f"Loaded {len(records)} records from {DATA_PATH}")

    if len(records) != 32:
        ok = fail(f"expected 32 teams, got {len(records)}") and ok
    else:
        print("OK: all 32 teams present")

    ranks = sorted(r["ol_rank"] for r in records)
    if ranks != list(range(1, 33)):
        ok = fail(f"ranks aren't a clean 1-32 permutation: {ranks}") and ok
    else:
        print("OK: ranks form a valid 1-32 permutation, no ties or gaps")

    teams = [r["team"] for r in records]
    if len(teams) != len(set(teams)):
        ok = fail("duplicate team codes present") and ok
    else:
        print("OK: no duplicate team codes")

    den = next((r for r in records if r["team"] == "DEN"), None)
    lv = next((r for r in records if r["team"] == "LV"), None)
    if den is None or den["ol_rank"] != 1:
        ok = fail(f"spot check: Broncos expected rank 1, "
                  f"got {den['ol_rank'] if den else 'missing'}") and ok
    else:
        print("OK: spot check -- Broncos are rank 1")
    if lv is None or lv["ol_rank"] != 32:
        ok = fail(f"spot check: Raiders expected rank 32, "
                  f"got {lv['ol_rank'] if lv else 'missing'}") and ok
    else:
        print("OK: spot check -- Raiders are rank 32")

    print()
    print("ALL CHECKS PASSED" if ok else "VALIDATION FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
