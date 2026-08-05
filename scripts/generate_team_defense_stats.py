"""
generate_team_defense_stats.py

Fetches everything needed for real team D/ST fantasy scoring and writes
data/stats/team_defense_stats.json -- one record per team per week.

This is the data shape the original project handoff explicitly called out
as missing ("team_season_stats.json only has wins/losses/points for/against
-- not the sacks/turnovers/yards-allowed needed for real D/ST fantasy
scoring. That's a different nflverse data shape entirely and needs its own
script.") This is that script.

REWRITTEN (v2): the first version sourced sacks/interceptions/fumbles-
recovered/yards-allowed from load_team_stats() (official box-score
aggregates). That version had a real gap for OAK/SD/STL and was replaced
with a play-by-play-only approach (below).

REWRITTEN (v3): v2 still dropped ~900 historical Raiders/Chargers/Rams
team-weeks. Diagnosed directly (not guessed) via a live check of 2010
play-by-play: "LV" appears 2,799 times, "OAK" appears zero times, even
though the Raiders played in Oakland that season. CONFIRMED root cause:
nflverse's load_pbp() labels every play with the CURRENT-era franchise
code regardless of season (LV/LAC/LA always), while load_schedules()
(which team_weekly_stats.json was built from) uses season-accurate
historical codes (OAK pre-2020, SD pre-2017, STL pre-2016). v2's
play-by-play aggregation was actually working correctly all along and
producing real "LV"/"LAC"/"LA" keys for historical seasons -- they were
just silently dropped by the points_allowed cross-reference, since
team_weekly_stats.json's differently-coded keys never matched. Fixed here
with TEAM_CODE_ALIASES, applied only to the points_allowed lookup (the
side that needs to change to match pbp's convention).

METHODOLOGY -- everything from ONE play-by-play pass, no
load_team_stats() dependency at all:
  - sacks: sack==1, credited to defteam
  - interceptions: interception==1, credited to defteam
  - fumbles_recovered: fumble_lost==1 (the offense's lost fumble is, by
    definition, the defense's recovery), credited to defteam
  - yards_allowed: sum of yards_gained on play_type in ("pass","run"),
    credited to defteam (matches the standard "total net yards" definition
    -- passing yards + rushing yards -- used everywhere else in this
    project)
  - safeties, blocked kicks, def_tds: same as before, all from pbp

Points allowed still comes from your already-validated team_weekly_stats.json
(not refetched).

NOT IMPLEMENTED: "2pt return" -- see dst_scoring.py's docstring for why.
Every record's two_point_returns field is 0.

NOT executed in this environment (no network access). Written against the
documented nflreadpy pbp schema verified 2026-08-05. Run locally, then run
validate_team_defense_stats.py before trusting the output.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dst_scoring import calculate_dst_fantasy_points

try:
    import nflreadpy as nfl
except ImportError:
    print("ERROR: nflreadpy is not installed. Run:\n"
          "  pip install nflreadpy --break-system-packages", file=sys.stderr)
    sys.exit(1)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_PATH = DATA_DIR / "stats" / "team_defense_stats.json"

SEASONS = list(range(1999, 2026))

# CONFIRMED via direct diagnostic (2010 play-by-play): nflverse's load_pbp()
# labels every play with the CURRENT-era franchise code regardless of season
# -- "LV" appears 2,799 times in 2010 pbp, "OAK" appears zero times, even
# though the Raiders were in Oakland that season. load_schedules() (which
# team_weekly_stats.json was built from) instead uses season-accurate
# historical codes (OAK pre-2020, SD pre-2017, STL pre-2016). Without this
# alias, every historical Raiders/Chargers/Rams week gets silently dropped
# by the points_allowed lookup below, even though the pbp data is present.
TEAM_CODE_ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def normalize_team(code: str) -> str:
    return TEAM_CODE_ALIASES.get(code, code)


def load_points_allowed() -> dict:
    path = DATA_DIR / "stats" / "team_weekly_stats.json"
    if not path.exists():
        print(f"ERROR: {path} not found. Run generate_team_weekly_stats.py first.",
              file=sys.stderr)
        sys.exit(1)
    records = json.loads(path.read_text())
    return {(normalize_team(r["team"]), r["season"], r["week"]): r["points_against"] for r in records}


def load_defense_stats_from_pbp() -> dict:
    """Returns {(team, season, week): {sacks, interceptions, fumbles_recovered,
    yards_allowed, safeties, blocked_kicks, def_tds}} -- everything derived
    from one play-by-play pass."""
    print(f"Fetching play-by-play for seasons={SEASONS} to derive full D/ST stats "
          f"(this is the slow step) ...")
    pbp = nfl.load_pbp(seasons=SEASONS)

    season_type_field = "season_type" if "season_type" in pbp.columns else "game_type"
    pbp = pbp.filter(pbp[season_type_field] == "REG")

    totals = defaultdict(lambda: {
        "sacks": 0, "interceptions": 0, "fumbles_recovered": 0, "yards_allowed": 0,
        "safeties": 0, "blocked_kicks": 0, "def_tds": 0,
    })
    skipped = 0

    for row in pbp.iter_rows(named=True):
        season, week = row["season"], row["week"]
        if season is None or week is None:
            skipped += 1
            continue

        defteam = row.get("defteam")
        if defteam:
            key = (defteam, season, week)
            if row.get("sack"):
                totals[key]["sacks"] += 1
            if row.get("interception"):
                totals[key]["interceptions"] += 1
            if row.get("fumble_lost"):
                totals[key]["fumbles_recovered"] += 1
            if row.get("play_type") in ("pass", "run"):
                totals[key]["yards_allowed"] += row.get("yards_gained") or 0
            if row.get("safety"):
                totals[key]["safeties"] += 1
            if row.get("punt_blocked") or row.get("field_goal_result") == "blocked":
                totals[key]["blocked_kicks"] += 1

        if row.get("touchdown") and row.get("td_team") and row.get("posteam"):
            if row["td_team"] != row["posteam"]:
                totals[(row["td_team"], season, week)]["def_tds"] += 1

    if skipped:
        print(f"Skipped {skipped} play-by-play rows with a missing season/week "
              f"(a data-quality gap in the raw source, not a bug in this script)")

    return dict(totals)


def main():
    points_allowed = load_points_allowed()
    defense_stats = load_defense_stats_from_pbp()

    records = []
    skipped_no_points = 0

    for key, stats in sorted(defense_stats.items(), key=lambda kv: kv[0]):
        team, season, week = key
        if key not in points_allowed:
            skipped_no_points += 1
            continue

        raw_stats = {
            "sacks": stats["sacks"],
            "interceptions": stats["interceptions"],
            "fumbles_recovered": stats["fumbles_recovered"],
            "safeties": stats["safeties"],
            "blocked_kicks": stats["blocked_kicks"],
            "def_tds": stats["def_tds"],
            "two_point_returns": 0,
            "points_allowed": points_allowed[key],
            "yards_allowed": stats["yards_allowed"],
        }

        records.append({
            "team": team,
            "season": season,
            "week": week,
            "raw_stats": raw_stats,
            "fantasy_points": calculate_dst_fantasy_points(raw_stats),
        })

    if skipped_no_points:
        print(f"Skipped {skipped_no_points} team-weeks with no matching points_against "
              f"in team_weekly_stats.json (should be rare now -- investigate if this "
              f"number is large)")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Wrote {len(records)} team-week D/ST records to {OUT_PATH}")
    print("NEXT STEP: run validate_team_defense_stats.py before trusting this output.")


if __name__ == "__main__":
    main()
