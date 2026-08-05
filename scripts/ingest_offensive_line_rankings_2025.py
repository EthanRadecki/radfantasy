"""
ingest_offensive_line_rankings_2025.py

Parses PFF's end-of-2025-season offensive line rankings (source:
https://www.pff.com/news/nfl-offensive-line-rankings-week-6-2025 -- despite
the "week-6" in that URL, this list represents PFF's rankings as of the end
of the 2025 season, per how it was provided) into
data/context/offensive_line_rankings_2025.json.

UNLIKE the 2026 preseason file (offensive_line_rankings_2026.json), this is
a SINGLE source, not a blend -- there's no consensus_rank to compute here,
just one PFF-graded ranking. Also unlike the 2026 file, this reflects
ACTUAL 2025 season performance, not a projection -- which makes it directly
poolable against real 2025 player/team production in player_season_stats.json
and team_season_stats.json for correlation analysis (e.g. "does O-line rank
predict RB fantasy output"), since both cover the same real, completed
season. The 2026 file is a projection for a season that hasn't happened yet
and shouldn't be joined against outcome data the same way.

Source format is just "<rank>. <team nickname>" per line, some wrapped in
markdown links -- team identified by nickname only (e.g. "Broncos", not
"Denver Broncos"), so this uses a nickname table rather than the full-name
table the other OL/ADP ingest scripts use.

Team code normalized to JAX/ARI (canonical, matches nflverse stats data) --
see ingest_offensive_line_rankings.py's docstring for the full explanation
of this project's JAC/JAX and ARZ/ARI crosswalk gap.
"""

import json
import re
import sys
from pathlib import Path

RAW_PATH = Path(__file__).resolve().parent.parent / "raw" / "ol_rankings" / "pff_2025_season_end.txt"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "context" / "offensive_line_rankings_2025.json"

NICKNAME_TO_CODE = {
    "raiders": "LV", "browns": "CLE", "chargers": "LAC", "dolphins": "MIA",
    "bengals": "CIN", "texans": "HOU", "cardinals": "ARI", "saints": "NO",
    "jaguars": "JAX", "titans": "TEN", "jets": "NYJ", "cowboys": "DAL",
    "panthers": "CAR", "packers": "GB", "vikings": "MIN", "buccaneers": "TB",
    "ravens": "BAL", "seahawks": "SEA", "falcons": "ATL", "commanders": "WAS",
    "lions": "DET", "patriots": "NE", "chiefs": "KC", "giants": "NYG",
    "steelers": "PIT", "eagles": "PHI", "bills": "BUF", "49ers": "SF",
    "rams": "LAR", "bears": "CHI", "colts": "IND", "broncos": "DEN",
}

LINE_RE = re.compile(r"^(\d+)\.\s+(?:\[([^\]]+)\]\([^)]+\)|(.+))$")


def main():
    if not RAW_PATH.exists():
        print(f"ERROR: {RAW_PATH} not found", file=sys.stderr)
        sys.exit(1)

    records = []
    for line in RAW_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if not m:
            print(f"WARNING: unparsed line: {line!r}", file=sys.stderr)
            continue
        rank = int(m.group(1))
        nickname = (m.group(2) or m.group(3)).strip().lower()
        if nickname not in NICKNAME_TO_CODE:
            print(f"WARNING: unrecognized nickname {nickname!r} on line: {line!r}", file=sys.stderr)
            continue
        records.append({
            "team": NICKNAME_TO_CODE[nickname],
            "season": 2025,
            "ol_rank": rank,
            "source": "PFF",
        })

    records.sort(key=lambda r: r["ol_rank"])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Wrote {len(records)} team records to {OUT_PATH}")


if __name__ == "__main__":
    main()
