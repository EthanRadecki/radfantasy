"""
Quick diagnostic -- run this in your scripts/ folder (or anywhere with
nflreadpy installed). Just prints raw facts, doesn't write any files.
"""
import nflreadpy as nfl

print("Fetching 2010 play-by-play (single season, should be fast)...")
pbp = nfl.load_pbp(seasons=[2010])

print("\ncolumns available (first 30):", pbp.columns[:30])

print("\nAll distinct posteam values in 2010 pbp:")
posteams = sorted(set(pbp["posteam"].to_list()) - {None})
print(len(posteams), posteams)

print("\nAll distinct defteam values in 2010 pbp:")
defteams = sorted(set(pbp["defteam"].to_list()) - {None})
print(len(defteams), defteams)

print("\nAll distinct season_type values in 2010 pbp:")
print(sorted(set(pbp["season_type"].to_list()) - {None}))

print("\nRow count where posteam or defteam mentions Raiders-ish codes (OAK/LV/RAI):")
for code in ["OAK", "LV", "RAI"]:
    n = pbp.filter((pbp["posteam"] == code) | (pbp["defteam"] == code)).height
    print(f"  {code}: {n} rows")

print("\nSample of any row where home_team or away_team is Oakland-related (checking schedule-side columns if present):")
for col in ["home_team", "away_team"]:
    if col in pbp.columns:
        vals = sorted(set(pbp[col].to_list()) - {None})
        print(f"  {col} distinct values:", vals)
