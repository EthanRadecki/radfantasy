"""
validate_offensive_line_rankings.py

Validates data/context/offensive_line_rankings_2026.json:
  1. Structural: 32 teams present, every team has all 4 sources (no silent
     name-matching failures), each source's rank values form a clean 1-32
     permutation (or the tied-rank case seen in the raw 4for4 data, where
     DET and NYJ share rank 19), consensus_rank falls strictly between the
     min and max of that team's individual source ranks.
  2. Ground-truth spot checks against what's actually in the source
     documents (not external facts, since these are subjective/projection
     rankings with no independently-verifiable "truth"):
       - Denver is ranked #1 by all four sources (consensus_rank == 1.0
         exactly).
       - Cleveland is FTN's #31 and 4for4's #31 overall, and StackedFantasy's
         #32 (bottom of "Bottom Tier").

Exits non-zero if any check fails.
"""

import json
import sys
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "context" / "offensive_line_rankings_2026.json"


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def main():
    ok = True

    if not DATA_PATH.exists():
        print(f"FAIL: {DATA_PATH} does not exist -- run ingest_offensive_line_rankings.py first")
        sys.exit(1)

    records = json.loads(DATA_PATH.read_text())
    print(f"Loaded {len(records)} records from {DATA_PATH}")

    if len(records) != 32:
        ok = fail(f"expected 32 teams, got {len(records)}") and ok
    else:
        print("OK: all 32 teams present")

    missing_sources = [r["team"] for r in records if r["sources_available"] < 4]
    if missing_sources:
        ok = fail(f"teams missing at least one source (likely a name-matching "
                  f"failure): {missing_sources}") and ok
    else:
        print("OK: every team has all 4 sources")

    for r in records:
        source_ranks = [
            r["sources"]["fantasypros"]["rank"],
            r["sources"]["stackedfantasy"]["rank"],
            r["sources"]["pff_4for4"]["overall"]["rank"],
            r["sources"]["ftnfantasy"]["rank"],
        ]
        lo, hi = min(source_ranks), max(source_ranks)
        if not (lo <= r["consensus_rank"] <= hi):
            ok = fail(f"{r['team']}: consensus_rank {r['consensus_rank']} outside "
                      f"the range of its own source ranks {source_ranks}") and ok

    for source_name, getter in [
        ("fantasypros", lambda r: r["sources"]["fantasypros"]["rank"]),
        ("stackedfantasy", lambda r: r["sources"]["stackedfantasy"]["rank"]),
        ("pff_4for4 overall", lambda r: r["sources"]["pff_4for4"]["overall"]["rank"]),
        ("ftnfantasy", lambda r: r["sources"]["ftnfantasy"]["rank"]),
    ]:
        ranks = sorted(getter(r) for r in records)
        expected = list(range(1, 33))
        # 4for4's raw table ties DET/NYJ at 19 with no rank 20 -- allow one
        # such gap-and-tie pair, but nothing looser than that.
        if ranks != expected and not (
            len(ranks) == 32 and len(set(ranks)) == 31 and ranks.count(19) == 2
        ):
            ok = fail(f"{source_name}: ranks aren't a clean 1-32 permutation "
                      f"(or the known DET/NYJ tie at 19)") and ok
        else:
            print(f"OK: {source_name} ranks form a valid ranking")

    # --- spot checks against the source documents themselves ---
    den = next((r for r in records if r["team"] == "DEN"), None)
    if den is None or den["consensus_rank"] != 1.0:
        ok = fail(f"spot check: Denver expected consensus_rank 1.0, "
                  f"got {den['consensus_rank'] if den else 'missing'}") and ok
    else:
        print("OK: spot check -- Denver is unanimous #1 across all 4 sources")

    cle = next((r for r in records if r["team"] == "CLE"), None)
    if cle is None:
        ok = fail("spot check: Cleveland record missing") and ok
    else:
        checks = [
            (cle["sources"]["ftnfantasy"]["rank"], 31, "FTN rank"),
            (cle["sources"]["pff_4for4"]["overall"]["rank"], 31, "4for4 overall rank"),
            (cle["sources"]["stackedfantasy"]["rank"], 32, "StackedFantasy rank"),
        ]
        for got, expected, label in checks:
            if got != expected:
                ok = fail(f"spot check: Cleveland {label} expected {expected}, got {got}") and ok
        if ok:
            print("OK: spot check -- Cleveland matches source documents "
                  "(FTN #31, 4for4 #31, StackedFantasy #32)")

    print()
    print("ALL CHECKS PASSED" if ok else "VALIDATION FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
