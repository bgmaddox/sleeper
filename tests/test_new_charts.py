"""Schedule swap matrix (Season) and close-game record (AllTime)."""
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import sleeper_core as core  # noqa: E402


# ── Schedule swap ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def season(season_2024):
    return season_2024[1]


def _regular(season):
    m = season.Matches
    return m[(m['Season'] == 'Regular') & m['Opp_team'].notna()]


def test_swap_diagonal_is_the_real_record(season):
    reg = _regular(season)
    last = int(reg['Week'].max())
    grid = season.ScheduleSwap(last)
    actual = reg.groupby('Team')['Won'].sum()
    for t in grid.index:
        assert grid.at[t, t] == actual[t], t


def test_swap_cell_matches_a_hand_count(season):
    """A plays B's schedule; the week B met A, A meets B instead."""
    reg = _regular(season)
    last = int(reg['Week'].max())
    grid = season.ScheduleSwap(last)
    a, b = grid.index[0], grid.index[1]
    score = reg.pivot_table(index='Week', columns='Team', values='Total')
    opp = reg.pivot(index='Week', columns='Team', values='Opp_team')
    wins = 0
    for w in score.index:
        o = opp.at[w, b]
        o = b if o == a else o
        wins += score.at[w, a] > score.at[w, o]
    assert grid.at[a, b] == wins


def test_swap_respects_through_week(season):
    grid = season.ScheduleSwap(3)
    assert grid.values.max() <= 3


def test_swap_chart_is_square_heatmap(season):
    fig = season.ScheduleSwapChart(10)
    hm = fig.data[0]
    assert isinstance(hm, go.Heatmap)
    assert len(hm.x) == len(hm.y) == len(core.roster_ids[2024])
    assert hm.zmid == 0


# ── Close games ──────────────────────────────────────────────────────────────

def test_close_record_is_zero_sum(alltime):
    rec = alltime.CloseGameRecord(threshold=5)
    assert rec['W'].sum() == rec['L'].sum()
    assert {'W', 'L', 'Pct'} <= set(rec.columns)


def test_close_record_counts_only_close_games(alltime):
    rec = alltime.CloseGameRecord(threshold=5)
    m = alltime.Matches
    close = m[(m['Abs Margin'] < 5) & m['Opp_team'].notna() & (m['Abs Margin'] > 0)]
    assert rec['W'].sum() == int((close['Won'] == 1).sum())


def test_close_record_chart(alltime):
    fig = alltime.CloseGameChart(threshold=5)
    assert len(fig.data) >= 1
    names = [n for tr in fig.data for n in tr.y]
    assert len(set(names)) == len(alltime.CloseGameRecord(threshold=5))


# ── Points by roster source ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def season25(season_2025):
    import data_loader as dl
    lid = core.leagueNumbers_Dict[2025]
    missing = [w for w in range(1, 12) if not os.path.exists(dl._cache_path(f"transactions_{lid}_{w}"))]
    did = dl.fetch_league_json(lid)['draft_id']
    if missing or not os.path.exists(dl._cache_path(f"draft_picks_{did}")):
        pytest.skip("2025 transactions/draft picks not cached")
    return season_2025[1]


def test_roster_source_adds_up_to_starter_points(season25):
    """Every starter point lands in exactly one source column."""
    src = season25.RosterSource(11, refresh_latest=False)
    starters = pd.concat(df.assign(week=w) for w, df in season25.Breakout_dict.items() if w <= 11)
    starters = starters[starters['starter'] == 1]
    real = starters.groupby('team')['points'].sum()
    assert (src.sum(axis=1) - real.reindex(src.index)).abs().max() < 0.01


def test_week_one_starters_are_mostly_drafted(season25):
    src = season25.RosterSource(1, refresh_latest=False)
    assert src['Drafted'].sum() / src.values.sum() > 0.85


def test_roster_source_chart(season25):
    fig = season25.RosterSourceChart(11, refresh_latest=False)
    assert {tr.name for tr in fig.data} <= set(core.Season.ROSTER_SOURCES)
    assert all(len(tr.y) == len(core.roster_ids[2025]) for tr in fig.data)
