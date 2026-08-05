"""
generate_player_weekly_stats.py

Fetches week-by-week player stats from nflverse (via nflreadpy), fixes the
kicker-drop bug via play-by-play-derived kicking stats, and writes
data/stats/player_weekly_stats.json. Same schema/scope/rationale as
generate_player_season_stats.py -- see that file's docstring for the full
explanation of the kicker fix and position scope. This file only calls out
what's different at the weekly grain.

Each record is one player's one game:
    {
      "player_id": ..., "player_name": ..., "position": ..., "team": ...,
      "season": ..., "week": ..., "opponent_team": ...,
      "raw_stats": {...}, "fantasy_points": {...}
    }

Regular season only (filters season_type/game_type == "REG") -- same
postseason-inclusion bug this project has hit before.

NOT executed in this environment (no network access). Written against the
documented nflreadpy API verified 2026-08-04. Run locally, then run
validate_player_weekly_stats.py before trusting the output or expanding
SEASONS.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import calculate_fantasy_points
from kicking import load_kicking_stats_weekly

try:
    import nflreadpy as nfl
except ImportError:
    print("ERROR: nflreadpy is not installed. Run:\n"
          "  pip install nflreadpy --break-system-packages", file=sys.stderr)
    sys.exit(1)

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "stats" / "player_weekly_stats.json"

# Full available history, validated on 2024 first -- see README.
SEASONS = list(range(1999, 2026))

ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}

RAW_STAT_FIELDS = [
    "attempts", "passing_yards", "passing_tds", "interceptions", "passing_2pt_conversions",
    "carries", "rushing_yards", "rushing_tds", "rushing_fumbles_lost", "rushing_2pt_conversions",
    "targets", "receptions", "receiving_yards", "receiving_tds",
    "receiving_fumbles_lost", "receiving_2pt_conversions",
    "special_teams_tds",
]


def extract_raw_stats(row: dict) -> dict:
    return {field: row.get(field) or 0 for field in RAW_STAT_FIELDS}


def main():
    print(f"Fetching player weekly stats for seasons={SEASONS} ...")
    df = nfl.load_player_stats(seasons=SEASONS, summary_level="week")

    season_type_field = "season_type" if "season_type" in df.columns else (
        "game_type" if "game_type" in df.columns else None
    )
    if season_type_field is None:
        print("ERROR: neither 'season_type' nor 'game_type' column found -- "
              "cannot safely filter to regular season.", file=sys.stderr)
        sys.exit(1)

    before = df.height
    df = df.filter(df[season_type_field] == "REG")
    print(f"Filtered to regular season via '{season_type_field}': "
          f"{before} -> {df.height} rows")

    if "position" not in df.columns:
        print("ERROR: expected 'position' column not found.", file=sys.stderr)
        sys.exit(1)

    before = df.height
    df = df.filter(df["position"].is_in(list(ALLOWED_POSITIONS)))
    print(f"Filtered to {ALLOWED_POSITIONS}: {before} -> {df.height} rows "
          f"(dropped {before - df.height} IDP/O-line/other rows)")

    kicking_by_player_week = load_kicking_stats_weekly(SEASONS)

    id_field = "player_id" if "player_id" in df.columns else "gsis_id"
    name_field = "player_display_name" if "player_display_name" in df.columns else "player_name"
    opp_field = "opponent_team" if "opponent_team" in df.columns else None

    records = []
    covered_keys = set()

    for row in df.iter_rows(named=True):
        key = (row[id_field], row["season"], row["week"])
        covered_keys.add(key)

        raw_stats = extract_raw_stats(row)
        kicking_stats = None
        if row["position"] == "K":
            kicking_stats = kicking_by_player_week.get(key)
            if kicking_stats:
                raw_stats["kicking"] = {
                    "fg_made": kicking_stats["fg_made"],
                    "fg_attempts": kicking_stats["fg_attempts"],
                    "fg_makes_by_distance": kicking_stats["fg_makes_by_distance"],
                    "pat_made": kicking_stats["pat_made"],
                    "pat_attempts": kicking_stats["pat_attempts"],
                }

        records.append({
            "player_id": row[id_field],
            "player_name": row[name_field],
            "position": row["position"],
            "team": row.get("team") or row.get("recent_team"),
            "season": row["season"],
            "week": row["week"],
            "opponent_team": row.get(opp_field) if opp_field else None,
            "raw_stats": raw_stats,
            "fantasy_points": calculate_fantasy_points(raw_stats, kicking_stats),
        })

    # Same fix as the season pipeline: kickers who never had a row in
    # load_player_stats at all still need to show up, sourced purely from
    # play-by-play.
    added = 0
    for key, kicking_stats in kicking_by_player_week.items():
        if key in covered_keys:
            continue
        player_id, season, week = key
        raw_stats = {field: 0 for field in RAW_STAT_FIELDS}
        raw_stats["kicking"] = {
            "fg_made": kicking_stats["fg_made"],
            "fg_attempts": kicking_stats["fg_attempts"],
            "fg_makes_by_distance": kicking_stats["fg_makes_by_distance"],
            "pat_made": kicking_stats["pat_made"],
            "pat_attempts": kicking_stats["pat_attempts"],
        }
        records.append({
            "player_id": player_id,
            "player_name": kicking_stats["player_name"],
            "position": "K",
            "team": None,
            "season": season,
            "week": week,
            "opponent_team": None,
            "raw_stats": raw_stats,
            "fantasy_points": calculate_fantasy_points(raw_stats, kicking_stats),
        })
        added += 1
    print(f"Added {added} kicker game(s) that were missing from load_player_stats entirely")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2, default=str)

    print(f"Wrote {len(records)} records to {OUT_PATH}")
    print("NEXT STEP: run validate_player_weekly_stats.py before trusting this output.")


if __name__ == "__main__":
    main()
