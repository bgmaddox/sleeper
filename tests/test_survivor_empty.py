"""Survivor charts against a pool that has entrants but no picks yet.

This is the state every September: the league is renewed, people have joined,
and Week 1 hasn't kicked off. `team_graveyard_fig` was the one chart without an
empty guard, so it raised KeyError('team_pick') — and because the tab wraps each
chart in a try/except that renders the exception, the card displayed a literal
"⚠ 'team_pick'" to the league.
"""

import pandas as pd
import plotly.graph_objects as go
import pytest

import sleeper_core as core

PICK_COLS = ['username', 'week', 'team_pick', 'won', 'is_fatal', 'is_revive_loss']

CHART_METHODS = [
    'pick_matrix_fig',
    'elimination_timeline_fig',
    'weekly_carnage_fig',
    'team_graveyard_fig',
]


@pytest.fixture
def empty_pool():
    """A Survivor with 8 entrants and zero picks — no cache or network."""
    sv = core.Survivor.__new__(core.Survivor)
    sv.year = 2026
    sv.NFL_TEAMS = core.Survivor.NFL_TEAMS
    sv.user_map = {f'u{i}': f'player{i}' for i in range(8)}
    sv.Picks = pd.DataFrame([], columns=PICK_COLS)
    # Schema mirrors a real preseason Survivor.Status: nobody has picked, so
    # every entrant is alive with the full board still available.
    sv.Status = pd.DataFrame([
        {'username': f'player{i}', 'weeks_survived': 0, 'final_week': None,
         'is_eliminated': False, 'revived': False, 'teams_used': [],
         'teams_left': list(core.Survivor.NFL_TEAMS)}
        for i in range(8)
    ])
    return sv


@pytest.mark.parametrize('method', CHART_METHODS)
def test_chart_builds_without_raising(empty_pool, method):
    """Every Survivor chart must survive an empty pick set."""
    fig = getattr(empty_pool, method)()
    assert isinstance(fig, go.Figure)


@pytest.mark.parametrize('method', CHART_METHODS)
def test_chart_shows_no_error_text(empty_pool, method):
    """A guard that renders the exception is not a guard — the tab's per-chart
    try/except would happily draw '⚠ KeyError' and call it a chart."""
    fig = getattr(empty_pool, method)()
    text = str(fig.to_dict())
    assert '⚠' not in text
    assert 'team_pick' not in text


def test_graveyard_still_draws_when_picks_exist(empty_pool):
    """The empty guard must not swallow the real chart."""
    empty_pool.Picks = pd.DataFrame([
        {'username': 'player0', 'week': 1, 'team_pick': 'BUF',
         'won': True, 'is_fatal': False, 'is_revive_loss': False},
        {'username': 'player1', 'week': 1, 'team_pick': 'ARI',
         'won': False, 'is_fatal': True, 'is_revive_loss': False},
    ], columns=PICK_COLS)
    fig = empty_pool.team_graveyard_fig()
    assert fig.data, 'graveyard should draw traces once picks exist'
