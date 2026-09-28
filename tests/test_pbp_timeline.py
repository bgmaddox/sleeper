"""
Play-by-play points timeline (pbp_timeline.py).

Unit tests pin the attribution rules on hand-built plays. The 2025 tests
backtest them against the points Sleeper actually awarded: every team's
running total must end on its Sleeper score exactly (reconciliation), and the
reconciliation step must stay small for offensive players — that floor is what
makes the intra-game shape of the chart trustworthy, and it governs any change
to the rules. Measured 2026-09-28: 99.9% of 2025 offensive starter-weeks within
0.5 pts (2019: 99.7%, 2022: 100%).

PBP comes from .cache/ only; a week that isn't cached is skipped, not fetched.
Warm the cache with: .venv/bin/python -c "import data_loader as dl; dl.fetch_pbp_weeks(2025, range(1, 18))"
"""
import os

import numpy as np
import pandas as pd
import pytest

import data_loader as dl
import pbp_timeline as pt

SETTINGS = {
    'rec': 0.5, 'rec_yd': 0.1, 'rec_td': 6, 'rush_yd': 0.1, 'rush_td': 6,
    'pass_yd': 0.04, 'pass_td': 6, 'pass_int': -2, 'pass_2pt': 2, 'rec_2pt': 2,
    'rush_2pt': 2, 'fum': -1, 'fum_lost': -1, 'fgm_yds': 0.1, 'xpm': 1, 'xpmiss': -1,
    'fgmiss_30_39': -1, 'sack': 1, 'int': 2, 'fum_rec': 2, 'def_td': 6,
}

BACKTEST_FLOOR = 0.98
BACKTEST_WEEKS = range(1, 18)


def _plays(*rows):
    """Mini PBP frame: every PBP column present, unspecified values null."""
    base = {c: np.nan for c in dl.PBP_COLUMNS}
    base.update(game_id='2025_01_DAL_PHI', week=1, posteam='DAL', defteam='PHI',
                home_team='PHI', away_team='DAL', time_of_day='2025-09-05T00:30:00Z')
    frame = pd.DataFrame([{**base, 'play_id': i + 1, **r} for i, r in enumerate(rows)])
    return frame.astype({c: object for c in frame.columns if frame[c].isna().all()})


def _points(pbp):
    scored = pt.score(pt.play_stats(pbp, SETTINGS), SETTINGS)
    return scored.groupby('entity')['points'].sum().round(4).to_dict()


# ── Attribution rules ────────────────────────────────────────────────────────

def test_lost_fumble_costs_fum_and_fum_lost():
    pts = _points(_plays(dict(play_type='run', rusher_player_id='RB1', rushing_yards=3,
                              fumble=1, fumble_lost=1, fumbled_1_player_id='RB1',
                              fumbled_1_team='DAL', fumble_recovery_1_team='PHI')))
    assert pts['RB1'] == pytest.approx(0.3 - 2)
    assert pts['PHI'] == 2          # fum_rec for the recovering defense


def test_fumble_recovered_by_own_team_costs_only_fum():
    pts = _points(_plays(dict(play_type='run', rusher_player_id='RB1', rushing_yards=0,
                              fumble=1, fumbled_1_player_id='RB1',
                              fumbled_1_team='DAL', fumble_recovery_1_team='DAL')))
    assert pts == {'RB1': -1}


def test_field_goal_scores_by_distance():
    assert _points(_plays(dict(play_type='field_goal', kicker_player_id='K1',
                               field_goal_result='made', kick_distance=47))) == {'K1': 4.7}


def test_missed_field_goal_uses_league_distance_tier():
    assert _points(_plays(dict(play_type='field_goal', kicker_player_id='K1',
                               field_goal_result='missed', kick_distance=35))) == {'K1': -1}
    # 52 yards: this league has no fgmiss_50p key, so it costs nothing.
    assert _points(_plays(dict(play_type='field_goal', kicker_player_id='K1',
                               field_goal_result='missed', kick_distance=52))) == {}


def test_successful_two_point_pass_credits_both_players():
    pts = _points(_plays(dict(play_type='pass', passer_player_id='QB1', receiver_player_id='WR1',
                              pass_attempt=1, two_point_conv_result='success')))
    assert pts == {'QB1': 2, 'WR1': 2}


def test_touchdown_catch():
    pts = _points(_plays(dict(play_type='pass', passer_player_id='QB1', receiver_player_id='WR1',
                              pass_attempt=1, complete_pass=1, passing_yards=20, receiving_yards=20,
                              touchdown=1, pass_touchdown=1, td_player_id='WR1', td_team='DAL')))
    assert pts == {'QB1': pytest.approx(0.8 + 6), 'WR1': pytest.approx(0.5 + 2 + 6)}


def test_lateral_yards_go_to_the_lateral_receiver():
    pts = _points(_plays(dict(play_type='pass', passer_player_id='QB1', receiver_player_id='WR1',
                              complete_pass=1, passing_yards=23, receiving_yards=3,
                              lateral_receiver_player_id='RB1', lateral_receiving_yards=20)))
    assert pts['RB1'] == pytest.approx(2.0)


def test_sack_goes_to_defense_with_sleeper_abbreviation():
    pts = _points(_plays(dict(play_type='pass', posteam='SF', defteam='LA', sack=1,
                              passer_player_id='QB1')))
    assert pts == {'LAR': 1}


def test_play_times_are_eastern_and_fill_gaps():
    pbp = _plays(dict(time_of_day=None), dict(time_of_day='2025-09-05T00:31:00Z'),
                 dict(time_of_day=None))
    sched = pd.DataFrame({'game_id': ['2025_01_DAL_PHI'], 'gameday': ['2025-09-04'],
                          'gametime': ['20:20']})
    ts = pt.play_times(pbp, sched)
    assert list(ts) == [pd.Timestamp('2025-09-04 20:20'), pd.Timestamp('2025-09-04 20:31'),
                        pd.Timestamp('2025-09-04 20:31')]


# ── 2025 backtest ────────────────────────────────────────────────────────────

def _cached_weeks(year):
    return [w for w in BACKTEST_WEEKS
            if os.path.exists(dl._cache_path(dl.pbp_cache_key(year, w, final=True)))]


@pytest.fixture(scope='session')
def timelines_2025(season_2025):
    league, _, weeks = season_2025
    cached = _cached_weeks(2025)
    if not cached:
        pytest.skip('2025 play-by-play not cached — see module docstring')
    settings = dl.fetch_league_json(league.id)['scoring_settings']
    sched = dl.fetch_nfl_schedule(2025)
    out = {}
    for w in cached:
        if w in weeks:
            out[w] = (weeks[w].Breakout,
                      pt.team_timeline(weeks[w].Breakout, dl.fetch_pbp_week(2025, w), sched, settings))
    return out


def test_every_team_ends_on_its_sleeper_total(timelines_2025):
    for w, (breakout, tl) in timelines_2025.items():
        sleeper = breakout[breakout['starter'] == 1].groupby('team')['points'].sum()
        final = tl.groupby('team')['cum'].last()
        diff = (sleeper - final.reindex(sleeper.index)).abs()
        assert (diff < 0.01).all(), f'week {w}: {diff[diff >= 0.01].to_dict()}'


def test_play_attribution_backtest(timelines_2025):
    """Share of offensive starter-weeks whose reconciliation step is < 0.5 pts."""
    small = total = 0
    for w, (breakout, tl) in timelines_2025.items():
        adj = tl[tl['kind'] == 'final_adjust'].groupby(['team', 'player'])['delta'].sum()
        starters = breakout[(breakout['starter'] == 1) & (breakout['position'] != 'DEF')]
        for s in starters.itertuples():
            total += 1
            small += abs(adj.get((s.team, s.player), 0.0)) < 0.5
    rate = small / total
    print(f'\n2025 play attribution: {rate:.1%} of {total} offensive starter-weeks within 0.5 pts')
    assert rate >= BACKTEST_FLOOR


def test_every_play_falls_inside_its_week(timelines_2025):
    for w, (_, tl) in timelines_2025.items():
        ts = tl['ts']
        assert ts.notna().all()
        # Thursday opener to Monday night (or a Tuesday-morning finish).
        assert (ts.max() - ts.min()) < pd.Timedelta(days=6), f'week {w}: {ts.min()} → {ts.max()}'
        assert ts.min().dayofweek in (3, 4, 5, 6), f'week {w} starts {ts.min():%A}'


def test_timeline_contract(timelines_2025):
    _, tl = next(iter(timelines_2025.values()))
    assert list(tl.columns) == pt.TIMELINE_COLUMNS
    assert set(tl['kind']) <= {'anchor', 'play', 'final_adjust', 'no_pbp'}
    first = tl.groupby('team').head(1)
    assert (first['kind'] == 'anchor').all() and (first['cum'] == 0).all()
    assert tl.groupby('team')['ts'].apply(lambda s: s.is_monotonic_increasing).all()


def test_game_missing_from_pbp_lands_whole_score_at_scheduled_end(season_2025):
    """A partly published week: players in the missing game get one no_pbp step."""
    league, _, weeks = season_2025
    if 3 not in _cached_weeks(2025):
        pytest.skip('2025 week 3 play-by-play not cached')
    breakout = weeks[3].Breakout
    pbp = dl.fetch_pbp_week(2025, 3)
    dropped = pbp['game_id'].iloc[-1]                       # the week's last game
    tl = pt.team_timeline(breakout, pbp[pbp['game_id'] != dropped], dl.fetch_nfl_schedule(2025),
                          dl.fetch_league_json(league.id)['scoring_settings'])
    starters = breakout[breakout['starter'] == 1]
    in_dropped = starters[(starters['game_id'] == dropped) & (starters['points'].abs() >= 0.01)]
    no_pbp = tl[tl['kind'] == 'no_pbp']
    assert set(no_pbp['player']) == set(in_dropped['player'])
    final = tl.groupby('team')['cum'].last()
    assert ((starters.groupby('team')['points'].sum() - final).abs() < 0.01).all()


# ── Chart helpers ────────────────────────────────────────────────────────────

def test_axis_breaks_cut_only_long_gaps():
    ts = pd.to_datetime(['2025-09-04 20:20', '2025-09-04 21:15',        # Thursday night
                         '2025-09-04 22:15', '2025-09-04 23:10',
                         '2025-09-07 13:00', '2025-09-07 13:40'])       # Sunday
    breaks = pt.axis_breaks(ts)
    assert len(breaks) == 1
    assert breaks[0]['values'] == ['2025-09-04T23:25:00']
    hidden = pd.Timedelta(milliseconds=breaks[0]['dvalue'])
    assert hidden == pd.Timestamp('2025-09-07 12:45') - pd.Timestamp('2025-09-04 23:25')


def test_coalesce_merges_simultaneous_events():
    tl = pd.DataFrame({'ts': pd.to_datetime(['2025-09-07 13:00'] * 2 + ['2025-09-07 13:05']),
                       'team': 'a', 'matchup': 1, 'player': ['X', 'Y', 'X'],
                       'delta': [6.0, 1.0, 2.0], 'cum': [6.0, 7.0, 9.0],
                       'desc': ['X: TD catch', 'Y: XP', 'X: 20-yd catch'], 'kind': 'play'})
    out = pt.coalesce(tl)
    assert list(out['delta']) == [7.0, 2.0]
    assert list(out['cum']) == [7.0, 9.0]
    assert out['desc'].iloc[0] == 'X: TD catch<br>Y: XP'
