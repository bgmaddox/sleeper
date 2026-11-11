"""Week 9 side bet, "The Old Man & Young Buck" (sleeper_core.old_man_young_buck).

The chart read an ``age`` column that Breakout never had, so every Old Man was
dropped and only rookies were drawn. It also hardcoded the 2025 rookie class.
Age now comes from birth_date at the player's gameday.
"""
import glob
import os
import pickle
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import sleeper_core as core  # noqa: E402


def _players():
    return pd.DataFrame([
        # player,      team,  starter, birth_date,   gameday,      rookie_year, points
        ('Vet',        'a',   1,       '1990-01-01', '2026-11-01', 2012.0,      20.0),
        ('Turns30',    'a',   1,       '1996-11-01', '2026-11-01', 2018.0,      5.0),   # 30 that day
        ('Almost30',   'b',   1,       '1996-11-02', '2026-11-01', 2018.0,      9.0),   # 30 tomorrow
        ('Rookie',     'b',   1,       '2003-05-05', '2026-11-01', 2026.0,      12.0),
        ('LastYearRk', 'b',   1,       '2002-05-05', '2026-11-01', 2025.0,      30.0),
        ('BenchVet',   'a',   0,       '1985-01-01', '2026-11-01', 2008.0,      40.0),
        ('DEF',        'a',   1,       None,         '2026-11-01', None,        8.0),
    ], columns=['player', 'team', 'starter', 'birth_date', 'gameday', 'rookie_year', 'points'])


def test_old_men_are_found_from_birth_date():
    got = core.old_man_young_buck(_players(), 2026).set_index('player')['Type'].to_dict()
    assert got == {'Vet': 'Old Man', 'Turns30': 'Old Man', 'Rookie': 'Young Buck'}


def test_missing_columns_return_none():
    assert core.old_man_young_buck(_players().drop(columns='birth_date'), 2026) is None


def test_2025_reproduces_the_recorded_winner():
    """JTizzzzle won 2025 week 9 by hand entry; the best old + best rookie sum agrees."""
    files = sorted(glob.glob(os.path.join(ROOT, '.cache', 'season_data_v3_2025_*')))
    if not files:
        pytest.skip('2025 season cache not present')
    with open(files[-1], 'rb') as f:
        weeks = pickle.load(f)['weeks']
    s = core.old_man_young_buck(weeks[9].Breakout, 2025)
    assert set(s['Type']) == {'Old Man', 'Young Buck'}
    best = s.groupby(['team', 'Type'])['points'].max().groupby('team').sum()
    assert best.idxmax() == 'JTizzzzle'
