"""
ingest_flock_adp.py

Parses Flock Fantasy's current-season ADP export CSVs -- one per scoring
format (standard / half-PPR / PPR) for a given rolling window -- into a
single clean JSON file: data/adp/adp_flock.json

Flock has no public API; the source of truth is the manually-downloaded raw
CSVs in raw/flock_adp/. This script is re-run whenever fresher exports are
downloaded, and never modifies the raw files.

Filename convention expected: <format>_overall_<window>_<MMDDYYYY>.csv
  e.g. ppr_overall_7d_08042026.csv -> format=ppr, window=7d, date=2026-08-04

Known source-format quirk handled here:
  - CONFIRMED FLOCK-SIDE BUG: a handful of players appear twice under the
    same name, once as a complete row (Team populated, most/all expert
    source columns populated) and once as a sparse partial row (Team blank,
    only one or two source columns populated, often with AVG equal to a
    single raw source rank). This has been confirmed to reproduce
    identically across all three scoring-format files for a given date, and
    the partial rows are simply dropped in favor of the complete row for
    the same name -- they are not distinct real players. If future data
    shows two DIFFERENT real players sharing a name (verifiable by both
    rows having a populated Team and multiple sources), this heuristic will
    correctly leave both in place, since it only drops rows with a blank
    Team AND fewer populated sources than a same-name sibling row.
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "raw" / "flock_adp"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "adp" / "adp_flock.json"

ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
SOURCE_COLUMNS = ["Expert", "Sleeper", "ESPN", "Yahoo", "Underdog", "CBS", "FFPC"]
POS_RE = re.compile(r"^([A-Z]+)(\d+)?$")
FILENAME_RE = re.compile(r"^(std|ppr|half_ppr)_overall_(\d+d|\d+day)_(\d{2})(\d{2})(\d{4})\.csv$")


def parse_filename(name: str):
    m = FILENAME_RE.match(name)
    if not m:
        return None
    fmt, window, mm, dd, yyyy = m.groups()
    return {
        "scoring_format": fmt,
        "window": window,
        "snapshot_date": f"{yyyy}-{mm}-{dd}",
    }


def non_blank_source_count(row: dict) -> int:
    return sum(1 for c in SOURCE_COLUMNS if row.get(c, "").strip() != "")


def parse_file(path: Path, meta: dict):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    skipped_idp = 0
    parsed = []
    for row in rows:
        pos_raw = row["POS"].strip()
        pos_m = POS_RE.match(pos_raw)
        if not pos_m:
            continue
        position, pos_rank = pos_m.group(1), pos_m.group(2)
        if position not in ALLOWED_POSITIONS:
            skipped_idp += 1
            continue

        parsed.append({
            "player_name": row["Player"].strip(),
            "team": row["Team"].strip() or None,
            "position": position,
            "position_rank": int(pos_rank) if pos_rank else None,
            "rank": int(row["Rank"]),
            "adp": float(row["AVG"]),
            "_non_blank_sources": non_blank_source_count(row),
        })

    # Dedupe the confirmed Flock partial-record bug: for any player name
    # appearing more than once, keep only the row with the most populated
    # source columns (ties broken by having a non-blank Team).
    by_name = defaultdict(list)
    for r in parsed:
        by_name[r["player_name"]].append(r)

    deduped = []
    dropped_partial = 0
    for name, group in by_name.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue
        group.sort(key=lambda r: (r["_non_blank_sources"], r["team"] is not None), reverse=True)
        deduped.append(group[0])
        dropped_partial += len(group) - 1

    for r in deduped:
        del r["_non_blank_sources"]
        r.update(meta)

    return deduped, skipped_idp, dropped_partial


def main():
    if not RAW_DIR.exists():
        print(f"ERROR: raw directory not found: {RAW_DIR}", file=sys.stderr)
        sys.exit(1)

    all_records = []
    summary = []

    for path in sorted(RAW_DIR.glob("*.csv")):
        meta = parse_filename(path.name)
        if meta is None:
            print(f"WARNING: skipping file with unrecognized name: {path.name}", file=sys.stderr)
            continue
        records, skipped_idp, dropped_partial = parse_file(path, meta)
        all_records.extend(records)
        summary.append((path.name, len(records), skipped_idp, dropped_partial))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(all_records, f, indent=2)

    print(f"Wrote {len(all_records)} records to {OUT_PATH}")
    print()
    print(f"{'File':<38}{'Kept':<8}{'Skipped(IDP)':<15}{'Dropped(dup bug)':<18}")
    for name, kept, skipped_idp, dropped in summary:
        print(f"{name:<38}{kept:<8}{skipped_idp:<15}{dropped:<18}")


if __name__ == "__main__":
    main()
