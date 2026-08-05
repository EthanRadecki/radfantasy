"""
split_player_weekly_stats.py

Splits data/stats/player_weekly_stats.json (125MB, over GitHub's 100MB
per-file limit) into one file per season: data/stats/player_weekly/2025.json,
2024.json, etc. Run this once, then commit the split files instead of the
single giant one.

Usage: run from your scripts/ folder (or anywhere -- it finds the file via
a path relative to this script, same convention as everything else here).
"""

import json
from collections import defaultdict
from pathlib import Path

IN_PATH = Path(__file__).resolve().parent.parent / "data" / "stats" / "player_weekly_stats.json"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "stats" / "player_weekly"


def main():
    print(f"Reading {IN_PATH} ...")
    records = json.loads(IN_PATH.read_text())
    print(f"Loaded {len(records)} records")

    by_season = defaultdict(list)
    for r in records:
        by_season[r["season"]].append(r)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for season, recs in sorted(by_season.items()):
        out_path = OUT_DIR / f"{season}.json"
        with open(out_path, "w") as f:
            json.dump(recs, f)
        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(f"  {season}: {len(recs)} records, {size_mb:.1f} MB -> {out_path}")

    print()
    print(f"Wrote {len(by_season)} season files to {OUT_DIR}")
    print("Next steps:")
    print("  1. git rm --cached data/stats/player_weekly_stats.json")
    print("  2. rm data/stats/player_weekly_stats.json   (remove the giant file from disk)")
    print("  3. git add data/stats/player_weekly/")
    print("  4. git commit -m 'split weekly stats by season to stay under GitHub file size limit'")
    print("  5. git push origin main")
    print()
    print("Update index.html's fetch calls to pull from data/stats/player_weekly/<year>.json")
    print("instead of the single big file -- e.g. fetch('data/stats/player_weekly/2025.json')")
    print("for current-season data, only fetching other years when actually needed.")


if __name__ == "__main__":
    main()
