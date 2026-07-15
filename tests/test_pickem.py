"""Tests for the PickEm class (Session 11): data shape, scoring math, chart smoke."""

import plotly.graph_objects as go
import pytest

import sleeper_core as core


# ── Config ────────────────────────────────────────────────────────────────────

class TestPickEmConfig:

    def test_pickem_league_ids(self):
        assert core.PICKEM_LEAGUE_IDS == {2025: 1263903606336139264}

    def test_keys_are_ints(self):
        assert all(isinstance(k, int) for k in core.PICKEM_LEAGUE_IDS)


# ── Parsing (synthetic rosters — no cache/network needed) ────────────────────

def _make_pickem(rosters, user_map):
    """Build a PickEm without hitting the network."""
    pe = core.PickEm.__new__(core.PickEm)
    pe.year = 2025
    pe.user_map = user_map
    pe._parse(rosters)
    return pe


SYNTH_ROSTERS = [
    {'owner_id': 'u1', 'metadata': {'points_by_leg': {
        'v1:regular:1': 10.0, 'v1:regular:2': 8.0, 'v1:regular:3': 12.0}}},
    {'owner_id': 'u2', 'metadata': {'points_by_leg': {
        'v1:regular:1': 10.0, 'v1:regular:2': 9.0, 'v1:regular:3': 7.0}}},
]
SYNTH_USERS = {'u1': 'alice', 'u2': 'bob'}


class TestPickEmParse:

    @pytest.fixture(scope="class")
    def pe(self):
        return _make_pickem(SYNTH_ROSTERS, SYNTH_USERS)

    def test_data_shape(self, pe):
        # 3 weeks + week-0 anchor per player
        assert len(pe.Data) == 8
        assert list(pe.Data.columns) == ['username', 'week', 'points', 'ScoreYTD']

    def test_week_zero_anchor(self, pe):
        wk0 = pe.Data[pe.Data['week'] == 0]
        assert len(wk0) == 2
        assert (wk0['ScoreYTD'] == 0).all()

    def test_cumsum(self, pe):
        alice = pe.Data[pe.Data['username'] == 'alice'].sort_values('week')
        assert list(alice['ScoreYTD']) == [0.0, 10.0, 18.0, 30.0]

    def test_totals_sorted_descending(self, pe):
        assert list(pe.Totals.index) == ['alice', 'bob']
        assert pe.Totals['alice'] == 30.0
        assert pe.Totals['bob'] == 26.0

    def test_weeks_won_ties_split(self, pe):
        # Week 1 tied (0.5 each), alice wins week 3, bob wins week 2
        assert pe.WeeksWon['alice'] == pytest.approx(1.5)
        assert pe.WeeksWon['bob'] == pytest.approx(1.5)
        assert pe.WeeksWon.sum() == pytest.approx(pe.n_weeks)

    def test_n_weeks(self, pe):
        assert pe.n_weeks == 3

    def test_unknown_owner_falls_back_to_id(self):
        pe = _make_pickem(
            [{'owner_id': 'ghost', 'metadata': {'points_by_leg': {'v1:regular:1': 5.0}}}],
            {},
        )
        assert set(pe.Data['username']) == {'ghost'}

    def test_empty_rosters(self):
        pe = _make_pickem([], {})
        assert pe.Data.empty
        assert pe.n_weeks == 0
        assert isinstance(pe.score_race_fig(), go.Figure)
        assert isinstance(pe.weekly_points_fig(), go.Figure)
        assert isinstance(pe.leaderboard_fig(), go.Figure)

    def test_missing_metadata(self):
        pe = _make_pickem([{'owner_id': 'u1', 'metadata': None}], SYNTH_USERS)
        # Only the week-0 anchor row
        assert len(pe.Data) == 1
        assert pe.Totals.empty


# ── Real 2025 data (cache-backed, skips if absent) ───────────────────────────

class TestPickEm2025:

    def test_all_players_present(self, pickem_2025):
        assert len(pickem_2025.Totals) == 6

    def test_full_season(self, pickem_2025):
        assert pickem_2025.n_weeks == 18

    def test_weeks_won_sums_to_season(self, pickem_2025):
        assert pickem_2025.WeeksWon.sum() == pytest.approx(18.0)

    def test_ytd_matches_totals(self, pickem_2025):
        finals = pickem_2025.Data.groupby('username')['ScoreYTD'].max()
        for name, total in pickem_2025.Totals.items():
            assert finals[name] == pytest.approx(total)


# ── Chart smoke tests ─────────────────────────────────────────────────────────

class TestPickEmCharts:

    def test_score_race_fig(self, pickem_2025):
        fig = pickem_2025.score_race_fig()
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 6  # one line per player

    def test_weekly_points_fig(self, pickem_2025):
        fig = pickem_2025.weekly_points_fig()
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 1

    def test_leaderboard_fig(self, pickem_2025):
        fig = pickem_2025.leaderboard_fig()
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 1
        assert len(fig.data[0].y) == 6
