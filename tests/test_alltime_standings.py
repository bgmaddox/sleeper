"""
All-time standings (AllTime.Standings) — career regular-season table.

Invariants rather than hardcoded numbers, so a new week or season never
breaks them. All data comes from .cache/.
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sleeper_core as core
import side_bet_resolver as sbr

FAR_FUTURE = datetime(2100, 1, 1, tzinfo=sbr.LEAGUE_TZ)
FAR_PAST   = datetime(2000, 1, 1, tzinfo=sbr.LEAGUE_TZ)


@pytest.fixture(scope="module")
def atp(alltime):
    return core.AllTimePlayoffs()


@pytest.fixture(scope="module")
def standings(alltime, atp):
    return alltime.Standings(atp.playoff_results, now=FAR_FUTURE)


def _regular(at):
    return at.Matches[at.Matches['Season'] == 'Regular']


class TestStandingsShape:
    def test_one_row_per_manager(self, alltime, standings):
        assert sorted(standings['team']) == sorted(_regular(alltime)['Team'].unique())

    def test_record_adds_up_to_games(self, standings):
        assert (standings['wins'] + standings['losses'] + standings['ties']
                == standings['games']).all()

    def test_league_wins_equal_losses(self, standings):
        assert standings['wins'].sum() == standings['losses'].sum()

    def test_league_points_for_equal_points_against(self, standings):
        assert standings['pf'].sum() == pytest.approx(standings['pa'].sum(), abs=1)

    def test_rank_is_by_wins(self, standings):
        assert list(standings['rank']) == list(range(1, len(standings) + 1))
        assert standings['wins'].is_monotonic_decreasing

    def test_seasons_match_the_years_played(self, alltime, standings):
        reg = _regular(alltime)
        for r in standings.itertuples():
            assert r.seasons == sorted(reg.loc[reg['Team'] == r.team, 'Year'].unique().astype(int))

    def test_consolation_games_do_not_count(self, alltime, standings):
        assert standings['games'].sum() == len(_regular(alltime))


class TestAllPlay:
    def test_all_play_is_zero_sum(self, standings):
        assert standings['ap_w'].sum() == pytest.approx(standings['ap_l'].sum())

    def test_all_play_games_are_opponents_per_week(self, alltime, standings):
        reg = _regular(alltime)
        n = reg.groupby(['Year', 'Week'])['Team'].transform('size')
        assert (standings['ap_w'] + standings['ap_l']).sum() == pytest.approx((n - 1).sum())

    def test_luck_is_win_pct_minus_all_play(self, standings):
        assert (standings['luck'] - (standings['win_pct'] - standings['ap_pct'])).abs().max() < 1e-3


class TestLiveWeeks:
    def test_current_season_waits_for_last_game(self, alltime):
        if not core.AllMatchesDict.get(core.CURRENT_SEASON):
            pytest.skip("no current-season cache")
        early = alltime.Standings(now=FAR_PAST)
        late = alltime.Standings(now=FAR_FUTURE)
        assert late['games'].sum() > early['games'].sum()
        assert all(core.CURRENT_SEASON not in s for s in early['seasons'])

    def test_past_seasons_always_count(self, alltime):
        early = alltime.Standings(now=FAR_PAST)
        past = _regular(alltime)
        past = past[past['Year'] != core.CURRENT_SEASON]
        assert early['games'].sum() == len(past)


class TestPlayoffColumns:
    def test_one_title_per_finished_season(self, atp, standings):
        finished = atp.playoff_results.loc[atp.playoff_results['placement'] == 1, 'year'].nunique()
        assert standings['titles'].sum() == finished

    def test_title_years_match_titles(self, standings):
        assert (standings['title_years'].map(len) == standings['titles']).all()

    def test_no_playoff_columns_without_results(self, alltime):
        st = alltime.Standings(now=FAR_FUTURE)
        assert (st[['playoffs', 'po_wins', 'titles']] == 0).all().all()


class TestUnfinishedSeasonBracket:
    """Sleeper seeds the current bracket from live standings all season."""

    def test_regular_season_in_progress_has_no_playoff_rows(self, atp):
        league_weeks = core.AllMatchesDict.get(core.CURRENT_SEASON, {})
        if not league_weeks or max(league_weeks) >= 14:
            pytest.skip("current season has reached the playoffs")
        assert core.CURRENT_SEASON not in set(atp.playoff_results['year'])

    def test_unplayed_games_are_not_losses(self, atp):
        g = atp.playoff_games
        assert not ((g['score'] == 0) & (g['opp_score'] == 0)).any()


class TestStandingsCard:
    def test_card_renders_a_row_per_manager(self, alltime, standings):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, os.path.join(root, "webapp"))
        os.environ.setdefault("SLEEPER_SKIP_EAGER_LOAD", "1")
        app = pytest.importorskip("app", reason="webapp/app.py not importable")

        card = app._alltime_standings_card(alltime)
        table = card.children[-1].children
        body = table.children[1]
        assert len(body.children) == len(alltime.Standings())
        assert table.to_plotly_json()['props'].get('data-sortable') == 'true'
