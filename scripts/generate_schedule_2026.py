"""
generate_schedule_2026.py

Saves the raw 2026 schedule (every team's week-by-week opponent, including
byes) to data/context/schedule_2026.json. This is new -- generate_strength_of_schedule.py
already fetches this same schedule internally, but only ever kept the
aggregate SOS averages, never the raw per-team-week matchup list. This
script saves that raw list on its own so it can be displayed directly
(e.g. "show me the Eagles' full 2026 schedule").

Output format:
[
  {
    "team": "PHI",
    "weeks": [
      {"week": 1, "opponent": "DAL", "is_home": true, "is_bye": false},
      {"week": 2, "opponent": null, "is_home": null, "is_bye": true},
      ...
      {"week": 17, "opponent": "...", "is_home": false, "is_bye": false}
    ]
  },
  ...
]

Every team gets exactly one entry per week 1-17 -- a bye week still gets a
row (is_bye: true, opponent: null) rather than being silently absent, so
consumers never have to guess whether a missing week means "bye" or
"data gap."

NOT executed in this environment (no network access). Written against the
documented nflreadpy API. Run locally, no other dependencies needed (does
NOT require player_weekly_stats.json or team_weekly_stats.json -- this is
schedule-only data, much faster than the SOS pipeline).
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

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "context" / "schedule_2026.json"
SEASON = 2026


def main():
    print(f"Fetching {SEASON} schedule ...")
    df = nfl.load_schedules(seasons=[SEASON])

    game_type_field = "game_type" if "game_type" in df.columns else "season_type"
    df = df.filter(df[game_type_field] == "REG")

    # Build {team: {week: {opponent, is_home}}} from the schedule.
    by_team_week = {}
    for row in df.iter_rows(named=True):
        week, home, away = row["week"], row["home_team"], row["away_team"]
        by_team_week.setdefault(home, {})[week] = {"opponent": away, "is_home": True}
        by_team_week.setdefault(away, {})[week] = {"opponent": home, "is_home": False}

    teams = sorted(by_team_week.keys())
    max_week = max(w for weeks in by_team_week.values() for w in weeks)
    print(f"Found {len(teams)} teams, {max_week} regular season weeks")

    records = []
    for team in teams:
        weeks_played = by_team_week[team]
        weeks = []
        for week in range(1, max_week + 1):
            if week in weeks_played:
                weeks.append({
                    "week": week,
                    "opponent": weeks_played[week]["opponent"],
                    "is_home": weeks_played[week]["is_home"],
                    "is_bye": False,
                })
            else:
                weeks.append({"week": week, "opponent": None, "is_home": None, "is_bye": True})
        records.append({"team": team, "weeks": weeks})

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Wrote {len(records)} team schedules to {OUT_PATH}")


if __name__ == "__main__":
    main()
