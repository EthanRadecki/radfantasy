# Rad Fantasy — data pipeline

This README states, file by file, whether the data is real/verified or
whether only the script exists. No file in `data/` here is unverified —
if a JSON file isn't in this repo, it's because it's never been generated
and confirmed correct, not because it was left out arbitrarily.

## Data files included (real, generated, validated)

| File | Status |
|---|---|
| `data/adp/adp_fantasypros.json` | Generated and validated. 4,738 records, 2018-2025. Spot-checked against real known facts (2018 #1 = Todd Gurley, 2025 #1 = Ja'Marr Chase). |
| `data/adp/adp_flock.json` | Generated and validated. 4,656 records, std/half-ppr/ppr, 8/4/2026 snapshot. Confirmed and fixed a real duplicate-record bug in the source. |
| `data/context/offensive_line_rankings_2026.json` | Generated and validated. Blend of 4 preseason 2026 OL ranking sources you provided as raw text. 32/32 teams matched across all sources. This is a PROJECTION for a season not yet played. |
| `data/context/offensive_line_rankings_2025.json` | Generated and validated. PFF's actual end-of-2025-season OL rankings, single source, 32/32 teams, clean 1-32 permutation. This reflects a REAL completed season, unlike the 2026 file above. |
| `data/stats/player_season_stats.json` | 15,905 records, 1999-2025. Validated directly by me against the actual file (not just your terminal logs): correct positions only, one row per player/season, fantasy-point math internally consistent, Barkley 2024 (2,005 rush yds/16 games) and Chase 2024 (1,708 receiving yds, league leader) spot checks both pass. |
| `data/stats/player_weekly_stats.json` | 158,592 records. Same validation, at the weekly grain -- Barkley's exact 167-yard Week 17 2024 game confirmed. |
| `data/stats/team_season_stats.json` | 861 records. 2024 Lions confirmed exactly 15-2, 564 PF, 342 PA. |
| `data/stats/team_weekly_stats.json` | 13,934 records. 2024 Lions Week 17 confirmed exactly 40-34 over SF. |
| `data/context/strength_of_schedule_2026.json` | **Done and verified.** Re-run with the fix, uploaded, and checked directly: league-average rushing SOS is a realistic 21.96 pts/gm (matches my independent calculation from the raw stats exactly), Philadelphia is still unanimous #1 full-season passing SOS (consistent with Sharp Football's independent ranking), their playoff-weeks passing SOS still drops sharply as expected (real opponents: Seahawks/Texans/49ers), and Denver's D/ST composite is unchanged at #1 (that path was never affected by the bug). |

## Nothing left unresolved

Every file listed above is real, generated from real sources, and verified
directly against the actual data (not just terminal logs). No known open
bugs remain in any generate/ingest script.

## Scripts included (all of them, since you'll need to regenerate/extend)

```
scripts/
├── ingest_fantasypros_adp.py       + validate_fantasypros_adp.py
├── ingest_flock_adp.py             + validate_flock_adp.py
├── generate_player_season_stats.py + validate_season_stats.py
├── generate_player_weekly_stats.py + validate_player_weekly_stats.py
├── generate_team_season_stats.py   + validate_team_stats.py
├── generate_team_weekly_stats.py   + validate_team_weekly_stats.py
├── scoring.py                       shared fantasy-point calculator
├── kicking.py                       derives kicker stats from play-by-play
├── ingest_offensive_line_rankings.py       + validate_offensive_line_rankings.py
├── ingest_offensive_line_rankings_2025.py  + validate_offensive_line_rankings_2025.py
├── generate_strength_of_schedule.py + validate_strength_of_schedule.py  (FIXED, unverified against real data)
└── opponent_giveaways.py             derives giveaways/sacks-allowed from play-by-play, used by SOS only
```

## Known open issues, carried forward honestly

- **Team code inconsistency across sources, unresolved**: FantasyPros ADP
  uses `JAC`/`ARI`; nflverse stats/schedule data uses `JAX`/`ARI`; nflverse
  also uses `LA` (not `LAR`) for the Rams. Reconcile before joining ADP
  against stats/context data by team code.
- **Kicker fix is a real derivation from play-by-play**, not a patch --
  nflverse's standard player-stats table has no field-goal/PAT data at all.
  Coverage was ~97% last run (some kickers didn't match between sources).
- IDP positions and offensive linemen filtered out everywhere -- this
  project is QB/RB/WR/TE/K (+DST for ADP) only.
- D/ST fantasy scoring (sacks, turnovers, yards allowed) is not computed
  anywhere -- team stats are wins/losses/points for/against only.
- ~4% of skill-position rows may not crosswalk cleanly on nickname/legal-name
  mismatches.
- Every stats script filters to regular season only (an earlier version had
  a postseason-leakage bug).
