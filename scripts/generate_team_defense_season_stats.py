"""
generate_team_defense_season_stats.py

Aggregates data/stats/team_defense_stats.json (weekly) into season totals:
data/stats/team_defense_season_stats.json.

IMPORTANT: this sums each week's ALREADY-COMPUTED fantasy_points to get a
season total -- it does NOT re-apply the points-allowed/yards-allowed tier
tables to season-total points/yards. Those tiers are inherently a
per-game bonus (you get graded on each game's defensive performance, not on
your cumulative season yards-allowed), so summing the 17 correct weekly
numbers is the right way to get a season total. The raw counting stats
(sacks, interceptions, etc.) are also summed for reference/analysis, but
points_allowed and yards_allowed are summed as informational season totals
only -- they're not meant to be re-run through the tier tables.

Depends on data/stats/team_defense_stats.json already existing (run
generate_team_defense_stats.py first).
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IN_PATH = DATA_DIR / "stats" / "team_defense_stats.json"
OUT_PATH = DATA_DIR / "stats" / "team_defense_season_stats.json"

SUM_FIELDS = ["sacks", "interceptions", "fumbles_recovered", "safeties",
              "blocked_kicks", "def_tds", "two_point_returns", "points_allowed", "yards_allowed"]


def main():
    if not IN_PATH.exists():
        print(f"ERROR: {IN_PATH} not found. Run generate_team_defense_stats.py first.",
              file=sys.stderr)
        sys.exit(1)

    weekly = json.loads(IN_PATH.read_text())

    totals = defaultdict(lambda: {f: 0 for f in SUM_FIELDS} | {"fantasy_points": 0.0, "games_played": 0})
    for r in weekly:
        key = (r["team"], r["season"])
        t = totals[key]
        for f in SUM_FIELDS:
            t[f] += r["raw_stats"][f]
        t["fantasy_points"] += r["fantasy_points"]
        t["games_played"] += 1

    records = []
    for (team, season), t in totals.items():
        raw_stats = {f: t[f] for f in SUM_FIELDS}
        records.append({
            "team": team,
            "season": season,
            "games_played": t["games_played"],
            "raw_stats": raw_stats,
            "fantasy_points": round(t["fantasy_points"], 2),
        })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Wrote {len(records)} team-season D/ST records to {OUT_PATH}")
    print("NEXT STEP: run validate_team_defense_stats.py before trusting this output.")


if __name__ == "__main__":
    main()
