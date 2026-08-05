"""
generate_player_season_stats.py

Fetches season-total player stats from nflverse (via nflreadpy), fixes the
kicker-drop bug by deriving kicking stats from play-by-play separately, and
writes data/stats/player_season_stats.json with a consistent schema:

    {
      "player_id": ..., "player_name": ..., "position": ..., "team": ...,
      "season": ..., "games_played": ...,
      "raw_stats": { ...counting stats..., possibly "kicking": {...} for K },
      "fantasy_points": {"standard": x, "half_ppr": x, "ppr": x}
    }

Scope: QB / RB / WR / TE / K only (IDP and O-line rows are dropped -- this
project is skill positions + K/DST only, same rule already applied to every
ADP source). Team defense (DST) scoring is NOT computed here -- that's a
different nflverse data shape (team box-score stats) and stays a separate
follow-up, same as called out in the original handoff.

Regular season only (summary_level="reg") -- deliberately avoids the
postseason-inclusion bug from earlier in this project's history.

NOT executed in this environment (no network access). Written against the
documented nflreadpy API verified 2026-08-04. Run locally, then run
validate_season_stats.py before trusting the output or expanding SEASONS.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import calculate_fantasy_points
from kicking import load_kicking_stats_season

try:
    import nflreadpy as nfl
except ImportError:
    print("ERROR: nflreadpy is not installed. Run:\n"
          "  pip install nflreadpy --break-system-packages", file=sys.stderr)
    sys.exit(1)

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "stats" / "player_season_stats.json"

# Full available history, validated on 2024 first -- see README.
SEASONS = list(range(1999, 2026))

ALLOWED_POSITIONS = {"QB", "RB", "WR", "TE", "K"}

# Maps our internal field name -> nflverse's actual column name, only where
# they differ. CONFIRMED via a direct diagnostic against real data: nflverse
# has no column literally named "interceptions" -- that name silently
# returned nothing via row.get(field), which "or 0" then masked as a
# legitimate zero. The real column is "passing_interceptions" (nflverse also
# has a separate "def_interceptions" for defensive picks, which is why a
# single generic "interceptions" was never going to be right). This means
# EVERY QB's interceptions were undercounted as 0 and every fantasy_points
# total was missing the -2/INT penalty until this fix. "interceptions" is
# kept as our own output key throughout this project (scoring.py, the site's
# JS) to avoid a wider rename -- only the source lookup changes here.
FIELD_SOURCE_MAP = {
    "attempts": "attempts", "passing_yards": "passing_yards", "passing_tds": "passing_tds",
    "interceptions": "passing_interceptions", "passing_2pt_conversions": "passing_2pt_conversions",
    "carries": "carries", "rushing_yards": "rushing_yards", "rushing_tds": "rushing_tds",
    "rushing_fumbles_lost": "rushing_fumbles_lost", "rushing_2pt_conversions": "rushing_2pt_conversions",
    "targets": "targets", "receptions": "receptions", "receiving_yards": "receiving_yards",
    "receiving_tds": "receiving_tds", "receiving_fumbles_lost": "receiving_fumbles_lost",
    "receiving_2pt_conversions": "receiving_2pt_conversions", "special_teams_tds": "special_teams_tds",
}


def extract_raw_stats(row: dict) -> dict:
    return {our_key: row.get(source_col) or 0 for our_key, source_col in FIELD_SOURCE_MAP.items()}


def main():
    print(f"Fetching player season stats for seasons={SEASONS} (summary_level='reg') ...")
    df = nfl.load_player_stats(seasons=SEASONS, summary_level="reg")

    if "position" not in df.columns:
        print("ERROR: expected 'position' column not found -- schema may have "
              "changed. Inspect df.columns before proceeding.", file=sys.stderr)
        sys.exit(1)

    before = df.height
    df = df.filter(df["position"].is_in(list(ALLOWED_POSITIONS)))
    print(f"Filtered to {ALLOWED_POSITIONS}: {before} -> {df.height} rows "
          f"(dropped {before - df.height} IDP/O-line/other rows)")

    kicking_by_player_season = load_kicking_stats_season(SEASONS)

    id_field = "player_id" if "player_id" in df.columns else "gsis_id"
    name_field = "player_display_name" if "player_display_name" in df.columns else "player_name"

    records = []
    for row in df.iter_rows(named=True):
        raw_stats = extract_raw_stats(row)
        kicking_stats = None

        if row["position"] == "K":
            kicking_stats = kicking_by_player_season.get((row[id_field], row["season"]))
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
            "games_played": row.get("games") or row.get("games_played"),
            "headshot_url": row.get("headshot_url"),
            "raw_stats": raw_stats,
            "fantasy_points": calculate_fantasy_points(raw_stats, kicking_stats),
        })

    # Kickers with zero offensive-table rows still won't appear above (they
    # were never in load_player_stats to begin with) -- add them in from the
    # pbp-derived kicking data directly so the bug is actually fixed, not
    # just patched for kickers who happened to have a stray offensive stat.
    seen_keys = {(r["player_id"], r["season"]) for r in records}
    added = 0
    for (player_id, season), kicking_stats in kicking_by_player_season.items():
        if (player_id, season) in seen_keys:
            continue
        raw_stats = {field: 0 for field in FIELD_SOURCE_MAP}
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
            "team": None,  # not available from pbp kicking aggregation alone
            "season": season,
            "games_played": None,
            "headshot_url": None,  # not available from pbp kicking aggregation alone
            "raw_stats": raw_stats,
            "fantasy_points": calculate_fantasy_points(raw_stats, kicking_stats),
        })
        added += 1
    print(f"Added {added} kicker season(s) that were missing from load_player_stats entirely")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2, default=str)

    print(f"Wrote {len(records)} records to {OUT_PATH}")
    print("NEXT STEP: run validate_season_stats.py before trusting this output.")


if __name__ == "__main__":
    main()
