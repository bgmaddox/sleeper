"""What the Survivor and Pick 'Em charts actually show, not just that they build.

Each class here pins a defect that shipped to the live site in Sept 2026:

- The schedule was pickled with no expiry in August, before any game had a
  score, so every margin read "(no data)" and every fatal pick lost its score.
- The Pick Matrix colorscale bands did not line up with its z codes: a fatal
  pick drew as an empty cell and a missing pick drew as a fatal one.
- The Team Graveyard drew bottom-up (ARI last) and replaced a fatal team's
  name with a bare ✕.
- The Elimination Timeline drew a negative-width bar for a Week 1 revive and
  every span one week short.
- Pools pickled before an alias existed kept the old display name forever, so
  the Longevity Leaderboard listed BMoreBallers88 and BMoreBaller88 as two
  people.
- The Pick 'Em race plotted cumulative totals (161–176 on a 0–180 axis — the
  lines sat on top of each other), had no legend, and the leaderboard colored
  players by rank.
"""

import pandas as pd
import pytest

import data_loader as dl
import sleeper_core as core

GREEN, AMBER, RED = (core.Survivor.OUTCOME_COLORS[k] for k in ('win', 'revive', 'fatal'))
EMPTY = core.Survivor.OUTCOME_COLORS['none']


# ── Synthetic Survivor pool (2025+ revive format) ────────────────────────────

def _roster(owner, picks, lost=(), eliminated=False):
    """picks: {week: (team, won)}."""
    return {'owner_id': owner, 'metadata': {
        'is_eliminated': 'true' if eliminated else 'false',
        'lost_leg_ids': [f'regular:{w}' for w in lost],
        'previous_picks': {f'regular:{w}': [t] for w, (t, _) in picks.items()},
        'points_by_leg': {f'regular:{w}': 1.0 if won else 0.0
                          for w, (_, won) in picks.items()},
    }}


ROSTERS = [
    _roster('a', {1: ('KC', True), 2: ('BUF', True)}),                       # clean
    _roster('b', {1: ('LAC', False), 2: ('SF', True)}, lost=[1]),            # revived wk 1
    _roster('c', {1: ('LAC', False), 2: ('TB', False)}, lost=[1, 2], eliminated=True),
    _roster('d', {1: ('LAC', False), 2: ('TB', False)}, lost=[1, 2], eliminated=True),
    _roster('e', {1: ('NYG', True)}),                                        # no wk 2 pick
]
USERS = {'a': 'alice', 'b': 'bob', 'c': 'carl', 'd': 'dan', 'e': 'eve'}
RESULTS = {('TB', 2): ('ATL', 10.0, 20.0), ('KC', 1): ('DEN', 27.0, 20.0)}


@pytest.fixture
def pool():
    sv = core.Survivor.__new__(core.Survivor)
    sv.year = 2026
    sv.user_map = USERS
    sv._parse(ROSTERS)
    sv.get_game_results = lambda: RESULTS
    return sv


def _cell_color(fig, player, week):
    """The colorscale color a heatmap cell actually renders in."""
    hm = fig.data[0]
    z = hm.z[list(hm.y).index(player)][list(hm.x).index(week)]
    pos = (z - hm.zmin) / (hm.zmax - hm.zmin)
    # Discrete scale: stops come in (lo, color), (hi, color) pairs.
    stops = hm.colorscale
    for (lo, color), (hi, _) in zip(stops[::2], stops[1::2]):
        if lo <= pos < hi or pos == hi == 1:
            return color
    raise AssertionError(f'no band for z={z} (pos {pos:.3f})')


class TestPickMatrixColors:
    def test_fatal_pick_is_red(self, pool):
        assert _cell_color(pool.pick_matrix_fig(), 'carl', 2) == RED

    def test_missing_pick_is_empty_not_red(self, pool):
        assert _cell_color(pool.pick_matrix_fig(), 'eve', 2) == EMPTY

    def test_revive_loss_is_amber(self, pool):
        assert _cell_color(pool.pick_matrix_fig(), 'bob', 1) == AMBER

    def test_win_is_green(self, pool):
        assert _cell_color(pool.pick_matrix_fig(), 'alice', 1) == GREEN


class TestTeamGraveyard:
    def test_reads_top_down(self, pool):
        """Alphabetical grid: ARI belongs in the top-left, not the bottom."""
        fig = pool.team_graveyard_fig()
        assert fig.layout.yaxis.autorange == 'reversed'
        assert fig.data[0].text[0][0].startswith('ARI')

    def test_fatal_team_keeps_its_name(self, pool):
        texts = [t for row in pool.team_graveyard_fig().data[0].text for t in row]
        assert 'TB ✕' in texts
        assert '✕' not in texts


class TestEliminationTimeline:
    def _bars(self, fig, player):
        return sorted(((b.base[0], b.base[0] + b.x[0], b.marker.color)
                       for b in fig.data if b.y[0] == player))

    def test_no_negative_widths(self, pool):
        """A Week 1 revive used to produce a bar from 1 to 0.85."""
        assert all(b.x[0] > 0 for b in pool.elimination_timeline_fig().data)

    def test_span_covers_whole_weeks(self, pool):
        bars = self._bars(pool.elimination_timeline_fig(), 'alice')
        assert bars[0][0] == 0.5 and bars[-1][1] == 2.5

    def test_revive_week_is_amber_and_fatal_week_red(self, pool):
        bars = self._bars(pool.elimination_timeline_fig(), 'carl')
        assert [c for *_, c in bars] == [AMBER, RED]

    def test_fatal_label_has_score(self, pool):
        fig = pool.elimination_timeline_fig()
        labels = [t for b in fig.data if b.y[0] == 'carl' for t in (b.text or []) if t]
        assert labels == ['TB — Lost 10-20']


class TestWeeklyCarnage:
    def test_repeat_fatal_picks_are_grouped(self, pool):
        fig = pool.weekly_carnage_fig()
        assert list(fig.data[0].text) == ['TB ×2 (L 10-20)']


class TestScheduleExpiry:
    @pytest.fixture
    def captured(self, monkeypatch):
        seen = {}

        def fake_load(key, max_age=None):
            seen['max_age'] = max_age
            return pd.DataFrame()

        monkeypatch.setattr(dl, '_load_cache', fake_load)
        return seen

    def test_current_season_expires(self, captured):
        """Scores arrive all season; an August pickle has none of them."""
        dl.fetch_nfl_schedule(core.CURRENT_SEASON)
        assert captured['max_age'] == dl._SCHEDULE_TTL

    def test_past_season_is_permanent(self, captured):
        dl.fetch_nfl_schedule(core.CURRENT_SEASON - 1)
        assert captured['max_age'] is None


# ── Names are re-canonicalised on load ───────────────────────────────────────

class TestLoaderCanonicalNames:
    def test_survivor_old_alias(self, monkeypatch, pool):
        pool.Status.loc[0, 'username'] = 'BMoreBallers88'
        pool.Picks.loc[pool.Picks['username'] == 'alice', 'username'] = 'BMoreBallers88'
        monkeypatch.setattr(dl, '_load_cache', lambda key, max_age=None: pool)
        sv = dl.load_survivor_for_year(2024)
        assert 'BMoreBallers88' not in set(sv.Status['username']) | set(sv.Picks['username'])
        assert 'BMoreBaller88' in set(sv.Status['username'])

    def test_pickem_old_alias(self, monkeypatch):
        pe = _make_pickem({'u1': 'BMoreBallers88', 'u2': 'jhuntmadd'})
        monkeypatch.setattr(dl, '_load_cache', lambda key, max_age=None: pe)
        out = dl.load_pickem_for_year(2025)
        assert set(out.Totals.index) == {'BMoreBaller88', 'jhmad'}
        assert set(out.WeeksWon.index) == {'BMoreBaller88', 'jhmad'}
        assert set(out.Data['username']) == {'BMoreBaller88', 'jhmad'}


class TestLongevityLegend:
    def test_year_legend_is_shown(self, pool):
        """The theme hides legends; without one the year colors are unreadable."""
        fig = pool.longevity_leaderboard_fig({2025: pool, 2026: pool})
        assert fig.layout.showlegend is True


# ── Pick 'Em ─────────────────────────────────────────────────────────────────

def _make_pickem(user_map, legs=None):
    legs = legs or {
        'u1': {'regular:1': 10.0, 'regular:2': 8.0, 'regular:3': 12.0},
        'u2': {'regular:1': 11.0, 'regular:3': 7.0},        # skipped week 2
    }
    pe = core.PickEm.__new__(core.PickEm)
    pe.year = 2025
    pe.user_map = user_map
    pe._parse([{'owner_id': o, 'metadata': {'points_by_leg': l}} for o, l in legs.items()])
    return pe


@pytest.fixture
def pickem():
    return _make_pickem({'u1': 'bgmaddox', 'u2': 'sgmaddox'})


class TestBehindLeader:
    def _series(self, fig):
        return {t.name: dict(zip(t.x, t.y)) for t in fig.data}

    def test_leader_is_zero_and_nobody_is_ahead(self, pickem):
        s = self._series(pickem.behind_leader_fig())
        for wk in (1, 2, 3):
            vals = [s[p][wk] for p in s]
            assert max(vals) == 0
            assert all(v <= 0 for v in vals)

    def test_gap_values(self, pickem):
        """Wk1 11 vs 10; wk2 sgmaddox skips (stays 11) vs 18; wk3 18 vs 30."""
        s = self._series(pickem.behind_leader_fig())
        assert s['bgmaddox'] == {0: 0, 1: -1, 2: 0, 3: 0}
        assert s['sgmaddox'] == {0: 0, 1: 0, 2: -7, 3: -12}

    def test_legend_is_shown(self, pickem):
        assert pickem.behind_leader_fig().layout.showlegend is True


class TestPickEmColors:
    def test_colors_follow_the_manager(self, pickem):
        league = core.get_alltime_teamcolors()
        race = {t.name: t.line.color for t in pickem.behind_leader_fig().data}
        assert race == {'bgmaddox': league['bgmaddox'], 'sgmaddox': league['sgmaddox']}

    def test_leaderboard_matches_race(self, pickem):
        race = {t.name: t.line.color for t in pickem.behind_leader_fig().data}
        bar = pickem.leaderboard_fig().data[0]
        assert dict(zip(bar.y, bar.marker.color)) == race

    def test_color_does_not_follow_rank(self):
        """Swap who's winning; each player keeps their color."""
        a = _make_pickem({'u1': 'bgmaddox', 'u2': 'sgmaddox'},
                         {'u1': {'regular:1': 12.0}, 'u2': {'regular:1': 5.0}})
        b = _make_pickem({'u1': 'bgmaddox', 'u2': 'sgmaddox'},
                         {'u1': {'regular:1': 5.0}, 'u2': {'regular:1': 12.0}})
        ca, cb = (dict(zip(p.leaderboard_fig().data[0].y,
                           p.leaderboard_fig().data[0].marker.color)) for p in (a, b))
        assert ca == cb

    def test_weeks_won_label_is_readable(self):
        pe = _make_pickem({'u1': 'bgmaddox', 'u2': 'sgmaddox', 'u3': 'jhmad'},
                          {'u1': {'regular:1': 9.0}, 'u2': {'regular:1': 9.0},
                           'u3': {'regular:1': 9.0}})
        labels = pe.leaderboard_fig().data[0].text
        assert all('0.333' not in t for t in labels)
        assert all('⅓' in t for t in labels)
