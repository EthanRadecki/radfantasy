"""
Quick diagnostic -- run this in your scripts/ folder. Read-only, doesn't
write any files. Checks the RAW nflreadpy data directly for a known QB's
interceptions, to see whether the bug is in what nflreadpy returns, or in
how generate_player_season_stats.py extracts it.
"""
import nflreadpy as nfl

print("Fetching 2025 player season stats (summary_level='reg')...")
df = nfl.load_player_stats(seasons=[2025], summary_level="reg")

print("\nDoes 'interceptions' appear in df.columns?", "interceptions" in df.columns)
print("Full column list:", df.columns)

print("\nJosh Allen 2025 row, raw from nflreadpy:")
allen = df.filter(df["player_display_name"] == "Josh Allen") if "player_display_name" in df.columns else df.filter(df["player_name"] == "Josh Allen")
for row in allen.iter_rows(named=True):
    print("  interceptions:", row.get("interceptions"))
    print("  passing_yards:", row.get("passing_yards"))
    print("  passing_tds:", row.get("passing_tds"))
    print("  position:", row.get("position"))

print("\nLeague-wide: sum of 'interceptions' across ALL 2025 rows (any position):")
total = sum(r.get("interceptions") or 0 for r in df.iter_rows(named=True))
print(" ", total, "(should be several hundred, real QBs threw many INTs in 2025)")
