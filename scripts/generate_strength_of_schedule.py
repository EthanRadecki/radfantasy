"""
generate_strength_of_schedule.py

Computes 2026 strength-of-schedule rankings for five fantasy-relevant
groups: Passing (QB), Rushing (RB), Receiving-WR, Receiving-TE, Kicking (K),
and D/ST. Writes data/context/strength_of_schedule_2026.json.

METHODOLOGY -- read this before trusting the output.

For QB/RB/WR/TE/K SOS (five nearly-identical metrics, one position filter
each): for every team's 2026 opponent, look up how many BASELINE_SEASON
fantasy points (PPR) that opponent allowed per game to that position, then
average across all of the team's 2026 opponents. A team facing a schedule
of defenses that historically gave up a lot of points to (say) RBs gets an
"easy" rushing SOS. This is computed entirely from your own
player_weekly_stats.json -- it needs that file to already exist locally
for BASELINE_SEASON.

For D/ST SOS: fundamentally different question -- not "how generous is the
opponent's defense" but "how exploitable is the opponent's OFFENSE." Three
components, each averaged across a team's 2026 opponents using BASELINE_SEASON
data, then blended into one composite by averaging each component's 1-32
rank (same "blend into consensus" pattern as the ADP and OL-rankings
pipelines):
  1. opponent's average points scored/game (from team_weekly_stats.json)
     -- LOW is an easy matchup for your D/ST.
  2. opponent's giveaways/game: INTs thrown + fumbles lost (derived from
     play-by-play via opponent_giveaways.py) -- HIGH is easy.
  3. opponent's sacks allowed/game (same pbp derivation) -- HIGH is easy.

WHY THIS IS AN APPROXIMATION, NOT A PREDICTION: this uses last season's
ACTUAL defensive/offensive performance as a stand-in for "how good will this
team be in 2026" -- rosters, coaching staffs, and scheme all change between
seasons. Outlets like Sharp Football instead lean on preseason Vegas win
totals as their quality proxy specifically because those already price in
offseason changes; that data isn't something this project can pull
programmatically, so this is a deliberately more mechanical, fully
reproducible substitute. Rankings will disagree with Vegas-informed SOS,
especially for teams that changed a lot this offseason -- that's expected,
not a bug.

Every team's SOS is computed twice: full season, and "fantasy playoff weeks"
(15-17 only) -- a team's overall schedule can look fine while their playoff
stretch specifically is brutal, or the reverse.

NOT executed in this environment (no network access for the 2026 schedule
or the D/ST pbp derivation) -- but the position-SOS half of this CAN be
sanity-checked once you have player_weekly_stats.json locally, since that
part doesn't need network access at all. Written against the documented
nflreadpy API verified 2026-08-04. Run locally, then run
validate_strength_of_schedule.py before trusting the output.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opponent_giveaways import load_offensive_vulnerability

try:
    import nflreadpy as nfl
except ImportError:
    print("ERROR: nflreadpy is not installed. Run:\n"
          "  pip install nflreadpy --break-system-packages", file=sys.stderr)
    sys.exit(1)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_PATH = DATA_DIR / "context" / "strength_of_schedule_2026.json"

BASELINE_SEASON = 2025   # last completed season -- the "how good is this defense" proxy
SCHEDULE_SEASON = 2026   # the season we're building a schedule-difficulty rating for
PLAYOFF_WEEKS = {15, 16, 17}
SCORING_FORMAT = "ppr"   # which fantasy_points key to use from player_weekly_stats.json

POSITION_SOS_NAMES = {
    "QB": "passing_sos", "RB": "rushing_sos", "WR": "receiving_wr_sos",
    "TE": "receiving_te_sos", "K": "kicking_sos",
}


def load_points_allowed_by_position(season: int) -> dict:
    """Returns {(opponent_team, position): avg_fantasy_points_allowed_per_game}.

    IMPORTANT: this sums every position-X player's points from the SAME
    game before averaging across games -- it does NOT average over
    individual player-rows. A defense that gives up 15 to the starting RB
    and 2 to the backup in one game allowed 17 that game, not two separate
    "games" of 15 and 2. Averaging over raw player-rows instead of
    per-game totals was a real bug in an earlier version of this function:
    it silently measured "average output per RB appearance" (diluted by
    every committee back and garbage-time touch) rather than "total points
    a defense actually surrenders to the position per game," and produced
    numbers roughly half of a believable real-world points-allowed rate.
    """
    path = DATA_DIR / "stats" / "player_weekly_stats.json"
    if not path.exists():
        print(f"ERROR: {path} not found. Run generate_player_weekly_stats.py "
              f"for at least season {season} first.", file=sys.stderr)
        sys.exit(1)

    records = json.loads(path.read_text())
    records = [r for r in records if r["season"] == season]
    if not records:
        print(f"ERROR: no {season} rows in player_weekly_stats.json -- "
              f"regenerate it including that season.", file=sys.stderr)
        sys.exit(1)

    # Step 1: sum every position-X player's fantasy points allowed by a given
    # opponent in a SINGLE game (opponent_team, position, week).
    per_game_totals = defaultdict(float)
    weeks_seen = defaultdict(set)  # (opponent_team, position) -> {week, week, ...}
    for r in records:
        if not r.get("opponent_team"):
            continue
        game_key = (r["opponent_team"], r["position"], r["week"])
        per_game_totals[game_key] += r["fantasy_points"][SCORING_FORMAT]
        weeks_seen[(r["opponent_team"], r["position"])].add(r["week"])

    # Step 2: average those per-game totals across the season.
    result = {}
    for (opp, pos), weeks in weeks_seen.items():
        total = sum(per_game_totals[(opp, pos, wk)] for wk in weeks)
        result[(opp, pos)] = total / len(weeks)
    return result


def load_points_scored_by_team(season: int) -> dict:
    """Returns {team: avg_points_scored_per_game}."""
    path = DATA_DIR / "stats" / "team_weekly_stats.json"
    if not path.exists():
        print(f"ERROR: {path} not found. Run generate_team_weekly_stats.py "
              f"for at least season {season} first.", file=sys.stderr)
        sys.exit(1)

    records = [r for r in json.loads(path.read_text()) if r["season"] == season]
    if not records:
        print(f"ERROR: no {season} rows in team_weekly_stats.json.", file=sys.stderr)
        sys.exit(1)

    totals = defaultdict(lambda: {"points": 0, "games": 0})
    for r in records:
        totals[r["team"]]["points"] += r["points_for"]
        totals[r["team"]]["games"] += 1
    return {t: v["points"] / v["games"] for t, v in totals.items()}


def load_2026_schedule() -> dict:
    """Returns {team: [(week, opponent), ...]} for SCHEDULE_SEASON."""
    print(f"Fetching {SCHEDULE_SEASON} schedule ...")
    df = nfl.load_schedules(seasons=[SCHEDULE_SEASON])
    game_type_field = "game_type" if "game_type" in df.columns else "season_type"
    df = df.filter(df[game_type_field] == "REG")

    by_team = defaultdict(list)
    for row in df.iter_rows(named=True):
        by_team[row["home_team"]].append((row["week"], row["away_team"]))
        by_team[row["away_team"]].append((row["week"], row["home_team"]))
    return dict(by_team)


def rank_teams(values: dict, higher_is_easier: bool) -> dict:
    """values: {team: numeric}. Returns {team: rank} where 1 = easiest."""
    ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=higher_is_easier)
    return {team: i + 1 for i, (team, _) in enumerate(ordered)}


def average_for_weeks(schedule_entries, weeks_filter, lookup: dict, default=None):
    values = [lookup[opp] for wk, opp in schedule_entries
              if (weeks_filter is None or wk in weeks_filter) and opp in lookup]
    return round(sum(values) / len(values), 2) if values else default


def main():
    points_allowed = load_points_allowed_by_position(BASELINE_SEASON)
    points_scored = load_points_scored_by_team(BASELINE_SEASON)
    vulnerability = load_offensive_vulnerability([BASELINE_SEASON])
    schedule = load_2026_schedule()

    giveaways = {team: v["giveaways_per_game"] for (team, season), v in vulnerability.items()
                 if season == BASELINE_SEASON}
    sacks_allowed = {team: v["sacks_allowed_per_game"] for (team, season), v in vulnerability.items()
                     if season == BASELINE_SEASON}

    teams = sorted(schedule.keys())
    records = {team: {"team": team, "season": SCHEDULE_SEASON} for team in teams}

    # --- QB/RB/WR/TE/K SOS ---
    for position, sos_name in POSITION_SOS_NAMES.items():
        pos_lookup = {opp: val for (opp, pos), val in points_allowed.items() if pos == position}
        full_vals, playoff_vals = {}, {}
        for team in teams:
            full_vals[team] = average_for_weeks(schedule[team], None, pos_lookup)
            playoff_vals[team] = average_for_weeks(schedule[team], PLAYOFF_WEEKS, pos_lookup)

        full_ranked = rank_teams({t: v for t, v in full_vals.items() if v is not None}, higher_is_easier=True)
        playoff_ranked = rank_teams({t: v for t, v in playoff_vals.items() if v is not None}, higher_is_easier=True)

        for team in teams:
            records[team][sos_name] = {
                "full_season": {"value": full_vals[team], "rank": full_ranked.get(team)},
                "playoff_weeks": {"value": playoff_vals[team], "rank": playoff_ranked.get(team)},
            }

    # --- D/ST SOS (composite of 3 components) ---
    full_points, playoff_points = {}, {}
    full_give, playoff_give = {}, {}
    full_sacks, playoff_sacks = {}, {}
    for team in teams:
        full_points[team] = average_for_weeks(schedule[team], None, points_scored)
        playoff_points[team] = average_for_weeks(schedule[team], PLAYOFF_WEEKS, points_scored)
        full_give[team] = average_for_weeks(schedule[team], None, giveaways)
        playoff_give[team] = average_for_weeks(schedule[team], PLAYOFF_WEEKS, giveaways)
        full_sacks[team] = average_for_weeks(schedule[team], None, sacks_allowed)
        playoff_sacks[team] = average_for_weeks(schedule[team], PLAYOFF_WEEKS, sacks_allowed)

    def dst_composite(points_d, give_d, sacks_d):
        points_rank = rank_teams({t: v for t, v in points_d.items() if v is not None}, higher_is_easier=False)
        give_rank = rank_teams({t: v for t, v in give_d.items() if v is not None}, higher_is_easier=True)
        sacks_rank = rank_teams({t: v for t, v in sacks_d.items() if v is not None}, higher_is_easier=True)
        composite_value = {}
        for t in teams:
            ranks = [r.get(t) for r in (points_rank, give_rank, sacks_rank) if r.get(t) is not None]
            composite_value[t] = sum(ranks) / len(ranks) if ranks else None
        composite_rank = rank_teams({t: v for t, v in composite_value.items() if v is not None}, higher_is_easier=False)
        return points_rank, give_rank, sacks_rank, composite_value, composite_rank

    full_pr, full_gr, full_sr, full_cv, full_cr = dst_composite(full_points, full_give, full_sacks)
    po_pr, po_gr, po_sr, po_cv, po_cr = dst_composite(playoff_points, playoff_give, playoff_sacks)

    for team in teams:
        records[team]["dst_sos"] = {
            "full_season": {
                "composite_rank": full_cr.get(team),
                "avg_opponent_points_scored": {"value": full_points[team], "rank": full_pr.get(team)},
                "avg_opponent_giveaways_per_game": {"value": full_give[team], "rank": full_gr.get(team)},
                "avg_opponent_sacks_allowed_per_game": {"value": full_sacks[team], "rank": full_sr.get(team)},
            },
            "playoff_weeks": {
                "composite_rank": po_cr.get(team),
                "avg_opponent_points_scored": {"value": playoff_points[team], "rank": po_pr.get(team)},
                "avg_opponent_giveaways_per_game": {"value": playoff_give[team], "rank": po_gr.get(team)},
                "avg_opponent_sacks_allowed_per_game": {"value": playoff_sacks[team], "rank": po_sr.get(team)},
            },
        }

    out_records = [records[t] for t in teams]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out_records, f, indent=2)

    print(f"Wrote {len(out_records)} team records to {OUT_PATH}")
    print("NEXT STEP: run validate_strength_of_schedule.py before trusting this output.")


if __name__ == "__main__":
    main()
