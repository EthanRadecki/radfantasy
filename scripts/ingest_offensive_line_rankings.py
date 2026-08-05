"""
ingest_offensive_line_rankings.py

Parses four manually-saved 2026 preseason offensive-line ranking sources
into a single blended file: data/context/offensive_line_rankings_2026.json

This is the first "predictive/contextual" data source for the project
(offensive line quality as a proxy for player-performance projections),
per the context handoff's open item. Same ingest_*.py convention as ADP:
raw files under raw/ol_rankings/ are the source of truth, never edited by
this script.

FOUR SOURCES, blended the same way FantasyPros blends ADP sources into a
consensus number:
  - fantasypros_2026.txt   -- narrative rankings, numbered 1-32, no scores.
  - stackedfantasy_2026.txt -- tiered rankings (Elite/Above Average/Solid/
    Below Average/Bottom Tier) with a per-team uncertainty label, no scores.
  - pff_4for4_2026.tsv     -- the only source with actual quantitative
    grades: separate run-block and pass-block grades/ranks plus an overall
    grade/rank. Column identity (which column is run-block vs pass-block)
    was confirmed by cross-referencing 4for4's own published top-5
    run-blocking list (Rams, 49ers, Broncos, Cowboys, Colts) against the
    raw table's rank values -- the source table's header row didn't survive
    the copy/paste, so this was verified rather than assumed.
  - ftnfantasy_2026.txt    -- rank order only (numbered list); the site's
    per-team narrative breakdowns weren't available in what was pasted, so
    this source contributes rank only, same as FantasyPros/StackedFantasy.

TEAM CODE NORMALIZATION: sources disagree on team codes for two franchises.
4for4 uses "JAX" and "ARZ"; this project's FantasyPros ADP data uses "JAC"
and "ARI" (FantasyPros' own convention, seen directly in the raw ADP files).
"JAX" and "ARI" are treated as canonical here (matching nflverse's stats
data), with "JAC" and "ARZ" recognized as source-specific aliases. THIS
MEANS: joining this file against adp_fantasypros.json by team code will
currently fail silently for Jacksonville and Arizona unless one side is
remapped first -- flagging this the same way the original handoff flagged
the player-name crosswalk as real, ongoing work.

CONSENSUS RANK: average of every source's rank for that team (FantasyPros
rank, StackedFantasy rank, 4for4 overall_rank, FTN rank) -- same "blend
multiple sources into one AVG number" pattern already used for ADP.
"""

import json
import re
import sys
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "raw" / "ol_rankings"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "context" / "offensive_line_rankings_2026.json"

# Canonical codes match nflverse's stats data (JAX, ARI), not FantasyPros'
# ADP convention (JAC, ARZ) -- see module docstring.
TEAM_NAME_TO_CODE = {
    "arizona cardinals": "ARI", "atlanta falcons": "ATL", "baltimore ravens": "BAL",
    "buffalo bills": "BUF", "carolina panthers": "CAR", "chicago bears": "CHI",
    "cincinnati bengals": "CIN", "cleveland browns": "CLE", "dallas cowboys": "DAL",
    "denver broncos": "DEN", "detroit lions": "DET", "green bay packers": "GB",
    "houston texans": "HOU", "indianapolis colts": "IND", "jacksonville jaguars": "JAX",
    "kansas city chiefs": "KC", "las vegas raiders": "LV", "los angeles chargers": "LAC",
    "los angeles rams": "LAR", "miami dolphins": "MIA", "minnesota vikings": "MIN",
    "new england patriots": "NE", "new orleans saints": "NO", "new york giants": "NYG",
    "new york jets": "NYJ", "philadelphia eagles": "PHI", "pittsburgh steelers": "PIT",
    "seattle seahawks": "SEA", "san francisco 49ers": "SF", "tampa bay buccaneers": "TB",
    "tennessee titans": "TEN", "washington commanders": "WAS",
}

# Aliases seen directly in source data that map onto the canonical codes above.
CODE_ALIASES = {"JAC": "JAX", "ARZ": "ARI"}


def normalize_code(code: str) -> str:
    code = code.strip().upper()
    return CODE_ALIASES.get(code, code)


def team_name_to_code(name: str) -> str:
    key = name.strip().lower()
    if key not in TEAM_NAME_TO_CODE:
        raise ValueError(f"Unrecognized team name: {name!r}")
    return TEAM_NAME_TO_CODE[key]


def parse_fantasypros(path: Path) -> dict:
    """Returns {team_code: rank}."""
    text = path.read_text()
    results = {}
    for match in re.finditer(r"^(\d+)\)\s+(.+)$", text, re.MULTILINE):
        rank, name = int(match.group(1)), match.group(2).strip()
        results[team_name_to_code(name)] = rank
    return results


def parse_stackedfantasy(path: Path) -> dict:
    """Returns {team_code: {"rank": int, "tier": str, "uncertainty": str}}."""
    lines = [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]
    tier_headers = {"Elite", "Above Average", "Solid", "Below Average", "Bottom Tier"}

    results = {}
    current_tier = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line in tier_headers:
            current_tier = line
            i += 2  # skip the "N teams" line that follows every tier header
            continue
        if line.isdigit():
            rank = int(line)
            team_name = lines[i + 1]
            uncertainty_line = lines[i + 3]  # rank, team, description, uncertainty
            uncertainty = uncertainty_line.replace(" uncertainty", "")
            results[team_name_to_code(team_name)] = {
                "rank": rank, "tier": current_tier, "uncertainty": uncertainty,
            }
            i += 4
            continue
        i += 1
    return results


def parse_pff_4for4(path: Path) -> dict:
    """Returns {team_code: {run_block: {...}, pass_block: {...}, overall: {...}}}."""
    lines = path.read_text().splitlines()
    header, rows = lines[0].split("\t"), lines[1:]
    results = {}
    for row in rows:
        if not row.strip():
            continue
        fields = dict(zip(header, row.split("\t")))
        code = normalize_code(fields["team"])
        results[code] = {
            "run_block": {
                "grade": float(fields["run_block_grade"]),
                "rank": int(fields["run_block_rank"]),
            },
            "pass_block": {
                "grade": float(fields["pass_block_grade"]),
                "rank": int(fields["pass_block_rank"]),
            },
            "overall": {
                "grade": float(fields["overall_grade"]),
                "rank": int(fields["overall_rank"]),
            },
        }
    return results


def parse_ftnfantasy(path: Path) -> dict:
    """Returns {team_code: rank}."""
    results = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d+)\.\s+(.+)$", line)
        if not m:
            continue
        rank, name = int(m.group(1)), m.group(2).strip()
        results[team_name_to_code(name)] = rank
    return results


def main():
    fp = parse_fantasypros(RAW_DIR / "fantasypros_2026.txt")
    sf = parse_stackedfantasy(RAW_DIR / "stackedfantasy_2026.txt")
    pff = parse_pff_4for4(RAW_DIR / "pff_4for4_2026.tsv")
    ftn = parse_ftnfantasy(RAW_DIR / "ftnfantasy_2026.txt")

    all_codes = set(fp) | set(sf) | set(pff) | set(ftn)
    print(f"Parsed: FantasyPros={len(fp)}, StackedFantasy={len(sf)}, "
          f"4for4/PFF={len(pff)}, FTN={len(ftn)}, union={len(all_codes)} teams")

    records = []
    for code in sorted(all_codes):
        source_ranks = [r for r in [
            fp.get(code), sf.get(code, {}).get("rank"),
            pff.get(code, {}).get("overall", {}).get("rank"), ftn.get(code),
        ] if r is not None]

        records.append({
            "team": code,
            "season": 2026,
            "sources": {
                "fantasypros": {"rank": fp.get(code)},
                "stackedfantasy": sf.get(code),
                "pff_4for4": pff.get(code),
                "ftnfantasy": {"rank": ftn.get(code)},
            },
            "consensus_rank": round(sum(source_ranks) / len(source_ranks), 2) if source_ranks else None,
            "sources_available": len(source_ranks),
        })

    records.sort(key=lambda r: (r["consensus_rank"] is None, r["consensus_rank"]))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Wrote {len(records)} team records to {OUT_PATH}")
    missing = [r["team"] for r in records if r["sources_available"] < 4]
    if missing:
        print(f"WARNING: teams missing from at least one source: {missing}")


if __name__ == "__main__":
    main()
