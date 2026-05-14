#!/usr/bin/env python3
"""
Run this script after each week to bust the cached season data so the
dashboard picks up the latest scores on next page load.

Usage:
    python refresh.py            # busts current year cache
    python refresh.py 2024 9     # busts a specific year + week
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'FirstPyProject'))
import data_loader as dl
import sleeper_core as core

year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
week = int(sys.argv[2]) if len(sys.argv) > 2 else None

if week:
    dl.invalidate_week(year, week)
else:
    # Bust the full season cache for the year
    import glob, os
    pattern = os.path.join(os.path.dirname(dl.__file__), '.cache', f'season_data_{year}_*')
    removed = 0
    for f in glob.glob(pattern):
        os.remove(f)
        removed += 1
    print(f"Removed {removed} cached file(s) for {year}. Next page load will re-fetch from Sleeper API.")
