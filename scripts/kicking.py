"""
kicking.py

Fixes the long-standing kicker bug from the project history: nflverse's
standard load_player_stats() table is built around offensive counting stats
(pass attempts, carries, targets, special-teams TDs) and simply does not
carry field goal / PAT data, so kickers have always fallen out of every
"did this player play" filter built on that table.

The real fix, per nflfastR's own calculate_player_stats_kicking() approach,
is to derive kicking stats directly from play-by-play data instead of the
player_stats table: filter to play_type in ("field_goal", "extra_point"),
using the documented columns kicker_player_id / kicker_player_name /
kick_distance / field_goal_result / extra_point_result.

NOTE: this pulls load_pbp(), which is a much larger download than
load_player_stats() (every play of every game, not just box-score totals).
Expect this step to be the slow part of a full-history run.

NOT executed against real data in this environment (no network access) --
written against the documented nflfastR/nflreadpy pbp schema. Validate the
output (see validate_player_weekly_stats.py / validate_season_stats.py)
before trusting it, same as everything else in this pipeline.
"""

from collections import defaultdict

try:
    import nflreadpy as nfl
except ImportError:
    nfl = None


def _distance_bucket(distance) -> str:
    if distance is None:
        return "0-39"
    if distance >= 60:
        return "60+"
    if distance >= 50:
        return "50-59"
    if distance >= 40:
        return "40-49"
    return "0-39"


def _empty_kicking_record(name):
    return {
        "player_name": name,
        "fg_made": 0,
        "fg_attempts": 0,
        "fg_makes_by_distance": {"0-39": 0, "40-49": 0, "50-59": 0, "60+": 0},
        "pat_made": 0,
        "pat_attempts": 0,
    }


def load_kicking_stats_weekly(seasons) -> dict:
    """Returns {(kicker_player_id, season, week): kicking_record}."""
    if nfl is None:
        raise ImportError("nflreadpy is not installed")

    print(f"Fetching play-by-play for seasons={seasons} to derive kicking stats "
          f"(this is the slow step) ...")
    pbp = nfl.load_pbp(seasons=seasons)
    kick_plays = pbp.filter(pbp["play_type"].is_in(["field_goal", "extra_point"]))

    records: dict = defaultdict(lambda: None)

    for row in kick_plays.iter_rows(named=True):
        kicker_id = row.get("kicker_player_id")
        if not kicker_id:
            continue
        key = (kicker_id, row["season"], row["week"])
        if records[key] is None:
            records[key] = _empty_kicking_record(row.get("kicker_player_name"))
        rec = records[key]

        if row.get("play_type") == "field_goal":
            rec["fg_attempts"] += 1
            if row.get("field_goal_result") == "made":
                rec["fg_made"] += 1
                bucket = _distance_bucket(row.get("kick_distance"))
                rec["fg_makes_by_distance"][bucket] += 1
        elif row.get("play_type") == "extra_point":
            rec["pat_attempts"] += 1
            if row.get("extra_point_result") == "good":
                rec["pat_made"] += 1

    return dict(records)


def load_kicking_stats_season(seasons) -> dict:
    """Returns {(kicker_player_id, season): kicking_record}, aggregated across weeks."""
    weekly = load_kicking_stats_weekly(seasons)
    season_records: dict = defaultdict(lambda: None)

    for (kicker_id, season, _week), rec in weekly.items():
        key = (kicker_id, season)
        if season_records[key] is None:
            season_records[key] = _empty_kicking_record(rec["player_name"])
        agg = season_records[key]
        agg["fg_made"] += rec["fg_made"]
        agg["fg_attempts"] += rec["fg_attempts"]
        agg["pat_made"] += rec["pat_made"]
        agg["pat_attempts"] += rec["pat_attempts"]
        for bucket, n in rec["fg_makes_by_distance"].items():
            agg["fg_makes_by_distance"][bucket] += n

    return dict(season_records)
