"""
generate_team_weekly_stats.py

Fetches per-game team results from nflverse (via nflreadpy's load_schedules)
and writes data/stats/team_weekly_stats.json -- one record per team per
game (each real game produces two records, one per side).

    {
      "team": ..., "season": ..., "week": ...,
      "opponent": ..., "is_home": bool,
      "points_for": ..., "points_against": ..., "result": "W"|"L"|"T"
    }

SCOPE NOTE (same as the season pipeline): this is win/loss/points only, not
full team box-score stats (yards, turnovers, sacks) -- that's a different
nflverse data shape (load_team_stats()) and stays a deliberate follow-up for
whenever real D/ST fantasy scoring gets built.

Filters to regular season only (game_type/season_type == "REG") and drops
games with no final score (postponed / no-contest games, e.g. the 2022
Bills/Bengals game following Damar Hamlin's on-field cardiac arrest -- a
real historical anomaly, not a data bug).

NOT executed in this environment (no network access). Written against the
documented nflreadpy API verified 2026-08-04. Run locally, then run
validate_team_weekly_stats.py before trusting the output or expanding
SEASONS.
"""

import json
import sys
from pathlib import Path

try:
    import nflreadpy as nfl
except ImportError:
    print("ERROR: nflreadpy is not installed. Run:\n"
          "  pip install nflreadpy --break-system-packages", file=sys.stderr)
    sys.exit(1)

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "stats" / "team_weekly_stats.json"

# Full available history, validated on 2024 first -- see README.
SEASONS = list(range(1999, 2026))


def main():
    print(f"Fetching schedules for seasons={SEASONS} ...")
    df = nfl.load_schedules(seasons=SEASONS)

    game_type_field = "game_type" if "game_type" in df.columns else (
        "season_type" if "season_type" in df.columns else None
    )
    if game_type_field is None:
        print("ERROR: neither 'game_type' nor 'season_type' column found.", file=sys.stderr)
        sys.exit(1)

    before = df.height
    df = df.filter(df[game_type_field] == "REG")
    print(f"Filtered to regular season via '{game_type_field}': {before} -> {df.height} rows")

    before = df.height
    df = df.filter(df["home_score"].is_not_null() & df["away_score"].is_not_null())
    dropped = before - df.height
    if dropped:
        print(f"Dropped {dropped} game(s) with no final score "
              f"(postponed / no-contest, e.g. 2022 Bills/Bengals)")

    records = []
    for row in df.iter_rows(named=True):
        season, week = row["season"], row["week"]
        home, away = row["home_team"], row["away_team"]
        home_score, away_score = row["home_score"], row["away_score"]

        for team, opponent, is_home, pf, pa in [
            (home, away, True, home_score, away_score),
            (away, home, False, away_score, home_score),
        ]:
            if pf > pa:
                result = "W"
            elif pf < pa:
                result = "L"
            else:
                result = "T"
            records.append({
                "team": team,
                "season": season,
                "week": week,
                "opponent": opponent,
                "is_home": is_home,
                "points_for": pf,
                "points_against": pa,
                "result": result,
            })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2, default=str)

    print(f"Wrote {len(records)} team-game records to {OUT_PATH}")
    print("NEXT STEP: run validate_team_weekly_stats.py before trusting this output.")


if __name__ == "__main__":
    main()
