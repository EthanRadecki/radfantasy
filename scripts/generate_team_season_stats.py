"""
generate_team_season_stats.py

Fetches per-game team results from nflverse (via nflreadpy's load_schedules)
and aggregates to season totals, writing data/stats/team_season_stats.json:

    {
      "team": ..., "season": ...,
      "wins": ..., "losses": ..., "ties": ..., "games_played": ...,
      "points_for": ..., "points_against": ..., "point_differential": ...
    }

Independent of generate_team_weekly_stats.py by design (each generate_*.py
is self-contained and re-runnable on its own) even though it computes a
superset of the same underlying game data -- this deliberately avoids a
runtime dependency between the two pipelines.

Same scope note, REG-only filter, and no-contest-game handling as
generate_team_weekly_stats.py -- see that file's docstring for the reasoning.

NOT executed in this environment (no network access). Written against the
documented nflreadpy API verified 2026-08-04. Run locally, then run
validate_team_stats.py before trusting the output or expanding SEASONS.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

try:
    import nflreadpy as nfl
except ImportError:
    print("ERROR: nflreadpy is not installed. Run:\n"
          "  pip install nflreadpy --break-system-packages", file=sys.stderr)
    sys.exit(1)

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "stats" / "team_season_stats.json"

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

    teams = defaultdict(lambda: defaultdict(lambda: {
        "wins": 0, "losses": 0, "ties": 0,
        "points_for": 0, "points_against": 0, "games_played": 0,
    }))

    for row in df.iter_rows(named=True):
        season = row["season"]
        home, away = row["home_team"], row["away_team"]
        home_score, away_score = row["home_score"], row["away_score"]

        for team, pf, pa in [(home, home_score, away_score), (away, away_score, home_score)]:
            rec = teams[team][season]
            rec["points_for"] += pf
            rec["points_against"] += pa
            rec["games_played"] += 1
            if pf > pa:
                rec["wins"] += 1
            elif pf < pa:
                rec["losses"] += 1
            else:
                rec["ties"] += 1

    records = []
    for team, by_season in teams.items():
        for season, rec in by_season.items():
            records.append({
                "team": team,
                "season": season,
                **rec,
                "point_differential": rec["points_for"] - rec["points_against"],
            })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2, default=str)

    print(f"Wrote {len(records)} team-season records to {OUT_PATH}")
    print("NEXT STEP: run validate_team_stats.py before trusting this output.")


if __name__ == "__main__":
    main()
