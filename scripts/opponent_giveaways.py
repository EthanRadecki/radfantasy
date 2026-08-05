"""
opponent_giveaways.py

Derives, per team per season, two offense-side vulnerability metrics used
only by D/ST strength-of-schedule (see generate_strength_of_schedule.py):
  - giveaways_per_game: (interceptions thrown + fumbles lost) / games played
  - sacks_allowed_per_game: sacks allowed / games played

These describe how exploitable a team's OFFENSE is -- the opposite framing
from every other SOS metric in this project, which describes how generous a
team's DEFENSE is. That's intentional: a good matchup for MY D/ST is an
opponent whose OFFENSE turns the ball over and gets sacked a lot, not an
opponent with a bad defense.

Derived from play-by-play (interception, fumble_lost, sack columns,
grouped by posteam -- the team on offense for that play), the same
technique kicking.py uses for field goals. Regular season only.

NOT executed in this environment (no network access). Written against the
documented nflreadpy pbp schema, verified 2026-08-04.
"""

from collections import defaultdict

try:
    import nflreadpy as nfl
except ImportError:
    nfl = None


def load_offensive_vulnerability(seasons) -> dict:
    """Returns {(team, season): {"giveaways_per_game": x, "sacks_allowed_per_game": x, "games": n}}."""
    if nfl is None:
        raise ImportError("nflreadpy is not installed")

    print(f"Fetching play-by-play for seasons={seasons} to derive giveaways/sacks-allowed ...")
    pbp = nfl.load_pbp(seasons=seasons)

    season_type_field = "season_type" if "season_type" in pbp.columns else "game_type"
    pbp = pbp.filter(pbp[season_type_field] == "REG")
    pbp = pbp.filter(pbp["posteam"].is_not_null())

    totals = defaultdict(lambda: {"giveaways": 0, "sacks_allowed": 0, "game_ids": set()})

    for row in pbp.iter_rows(named=True):
        key = (row["posteam"], row["season"])
        rec = totals[key]
        rec["game_ids"].add(row["game_id"])
        if row.get("interception"):
            rec["giveaways"] += 1
        if row.get("fumble_lost"):
            rec["giveaways"] += 1
        if row.get("sack"):
            rec["sacks_allowed"] += 1

    results = {}
    for key, rec in totals.items():
        games = len(rec["game_ids"])
        if games == 0:
            continue
        results[key] = {
            "giveaways_per_game": round(rec["giveaways"] / games, 2),
            "sacks_allowed_per_game": round(rec["sacks_allowed"] / games, 2),
            "games": games,
        }
    return results
