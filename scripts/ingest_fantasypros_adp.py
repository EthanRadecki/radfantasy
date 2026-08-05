"""
ingest_fantasypros_adp.py

Parses manually-downloaded FantasyPros "Average Draft Position" text exports
(one per year, tab-separated, copy-pasted from the FantasyPros site) into a
single clean JSON file: data/adp/adp_fantasypros.json

Source of truth = the raw .txt files in raw/fantasypros_adp/. This script is
re-run whenever those files change; it never modifies them.

Known source-format quirks handled here:
  - Header formatting is inconsistent across years: some years paste each
    column name on its own line (2018, 2019, 2021, 2022, 2024), others paste
    the header as a single tab-separated row (2020, 2023, 2025). We never
    parse the header directly -- we detect data rows structurally (first
    tab-separated field is an integer rank) and skip everything else.
  - The number and identity of contributing source columns (ESPN, MFL, FFC,
    RTSports, Fantrax, DW, Sleeper, CBS, NFL...) varies by year. We don't
    care which sources are present -- we only need the consensus AVG value,
    identified as the field matching \\d+\\.\\d+ (a decimal number), since
    every other field is either a blank or a plain integer rank.
  - 2025 has one extra trailing "Real-Time" column after AVG. Ignored.
  - Free-agent rows have no "TEAM (BYE)" suffix -- just a bare player name.
  - Team defense rows are named "<City> <Mascot> DST (<bye>)" -- the team
    identity has to be resolved from the full franchise name, not a 2-3
    letter code like every other row.
  - IDP and offensive-line rows leak into every year's export (CB, DB, DE,
    DL, DT, LB, OL, OT position codes have been observed). This project is
    skill positions + K/DST only -- IDP and OL/OT are always filtered out.
"""

import json
import re
import sys
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "raw" / "fantasypros_adp"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "adp" / "adp_fantasypros.json"

ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DST"}

AVG_FIELD_RE = re.compile(r"^\d+(\.\d+)?$")
DECIMAL_RE = re.compile(r"^\d+\.\d+$")
POS_RE = re.compile(r"^([A-Z]+)(\d+)?$")
NAME_TEAM_BYE_RE = re.compile(r"^(.*?)\s+([A-Za-z.]{2,4})\s+\((\d+)\)\s*$")

# Full franchise name -> current-era team abbreviation, covering every
# relocation/rename seen in the 2018-2025 FantasyPros exports.
TEAM_NAME_TO_ABBR = {
    "arizona cardinals": "ARI", "atlanta falcons": "ATL", "baltimore ravens": "BAL",
    "buffalo bills": "BUF", "carolina panthers": "CAR", "chicago bears": "CHI",
    "cincinnati bengals": "CIN", "cleveland browns": "CLE", "dallas cowboys": "DAL",
    "denver broncos": "DEN", "detroit lions": "DET", "green bay packers": "GB",
    "houston texans": "HOU", "indianapolis colts": "IND", "jacksonville jaguars": "JAC",
    "kansas city chiefs": "KC", "las vegas raiders": "LV", "oakland raiders": "LV",
    "los angeles chargers": "LAC", "san diego chargers": "LAC",
    "los angeles rams": "LAR", "st. louis rams": "LAR",
    "miami dolphins": "MIA", "minnesota vikings": "MIN", "new england patriots": "NE",
    "new orleans saints": "NO", "new york giants": "NYG", "new york jets": "NYJ",
    "philadelphia eagles": "PHI", "pittsburgh steelers": "PIT", "seattle seahawks": "SEA",
    "san francisco 49ers": "SF", "tampa bay buccaneers": "TB", "tennessee titans": "TEN",
    "washington redskins": "WAS", "washington football team": "WAS",
    "washington commanders": "WAS",
}


def resolve_dst_team(full_name: str) -> str | None:
    key = full_name.strip().lower()
    return TEAM_NAME_TO_ABBR.get(key)


def parse_name_team_bye(raw: str, position: str):
    """Returns (player_name, team, bye_week)."""
    raw = raw.strip()
    m = NAME_TEAM_BYE_RE.match(raw)
    if not m:
        # No "(BYE)" suffix at all -> free agent, no team/bye info.
        return raw, None, None

    name_part, code, bye = m.group(1).strip(), m.group(2), int(m.group(3))

    if position == "DST":
        # code here is the literal "DST", not a team abbreviation --
        # the real team identity is the franchise name in name_part.
        team = resolve_dst_team(name_part)
        return name_part, team, bye

    return name_part, code.upper(), bye


def parse_year_file(path: Path, year: int):
    raw_text = path.read_bytes().decode("utf-8", errors="replace")
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    records = []
    skipped_idp = 0
    skipped_unparsed = 0

    for line in lines:
        if not line.strip():
            continue
        fields = line.split("\t")
        if not fields[0].strip().isdigit():
            continue  # header / title line, not a data row

        rank = int(fields[0].strip())
        if len(fields) < 3:
            skipped_unparsed += 1
            continue

        name_team_bye_raw = fields[1]
        pos_raw = fields[2].strip()

        pos_m = POS_RE.match(pos_raw)
        if not pos_m:
            skipped_unparsed += 1
            continue
        position, pos_rank = pos_m.group(1), pos_m.group(2)

        if position not in ALLOWED_POSITIONS:
            skipped_idp += 1
            continue

        # AVG is the only field (besides rank) containing a decimal point.
        avg = None
        for f in fields[3:]:
            f = f.strip()
            if DECIMAL_RE.match(f):
                avg = float(f)
        if avg is None:
            skipped_unparsed += 1
            continue

        player_name, team, bye_week = parse_name_team_bye(name_team_bye_raw, position)

        records.append({
            "year": year,
            "rank": rank,
            "player_name": player_name,
            "team": team,
            "bye_week": bye_week,
            "position": position,
            "position_rank": int(pos_rank) if pos_rank else None,
            "adp": avg,
        })

    return records, skipped_idp, skipped_unparsed


def main():
    if not RAW_DIR.exists():
        print(f"ERROR: raw directory not found: {RAW_DIR}", file=sys.stderr)
        sys.exit(1)

    all_records = []
    summary = {}

    for path in sorted(RAW_DIR.glob("*_adp.txt")):
        m = re.match(r"(\d{4})_adp\.txt", path.name)
        if not m:
            continue
        year = int(m.group(1))
        records, skipped_idp, skipped_unparsed = parse_year_file(path, year)
        all_records.extend(records)
        summary[year] = {
            "rows_kept": len(records),
            "rows_skipped_idp_or_ol": skipped_idp,
            "rows_skipped_unparsed": skipped_unparsed,
            "dst_rows_unresolved_team": sum(
                1 for r in records if r["position"] == "DST" and r["team"] is None
            ),
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(all_records, f, indent=2)

    print(f"Wrote {len(all_records)} records to {OUT_PATH}")
    print()
    print(f"{'Year':<6}{'Kept':<8}{'Skipped(IDP/OL)':<18}{'Skipped(unparsed)':<18}{'DST unresolved':<15}")
    for year in sorted(summary):
        s = summary[year]
        print(f"{year:<6}{s['rows_kept']:<8}{s['rows_skipped_idp_or_ol']:<18}"
              f"{s['rows_skipped_unparsed']:<18}{s['dst_rows_unresolved_team']:<15}")


if __name__ == "__main__":
    main()
