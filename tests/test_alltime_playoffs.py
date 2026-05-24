"""
Phase 6 — AllTimePlayoffs tests.

TestAllTimePlayoffsData   — 6A: aggregator shape/integrity
TestAllTimePlayoffsCharts — 6B-D, 6F: chart smoke tests

All tests load from .cache/ — no API calls during test runs.
Requires at least 2024 season cache to be present.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import data_loader as dl
import sleeper_core as core
from plotly import graph_objects as go


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def atp():
    """AllTimePlayoffs built from whatever years are in cache."""
    path = dl._cache_path("season_data_2024_18")
    if not os.path.exists(path):
        pytest.skip("2024 cache not found — start the app once to build it")
    # Load at least 2024 so AllMatchesDict is populated
    dl.load_data_for_year(2024, verbose=False)
    return core.AllTimePlayoffs()


def _is_valid_fig(fig) -> bool:
    return isinstance(fig, go.Figure) and len(fig.data) > 0


# ── 6A: Data aggregator ───────────────────────────────────────────────────────

class TestAllTimePlayoffsData:

    def test_class_exists(self):
        assert hasattr(core, 'AllTimePlayoffs')

    def test_instantiates(self, atp):
        assert atp is not None

    def test_has_playoff_results(self, atp):
        assert hasattr(atp, 'playoff_results')

    def test_has_playoff_games(self, atp):
        assert hasattr(atp, 'playoff_games')

    def test_results_is_dataframe(self, atp):
        import pandas as pd
        assert isinstance(atp.playoff_results, pd.DataFrame)

    def test_games_is_dataframe(self, atp):
        import pandas as pd
        assert isinstance(atp.playoff_games, pd.DataFrame)

    def test_results_has_required_columns(self, atp):
        required = {'year', 'team', 'reg_season_rank', 'round_exit',
                    'placement', 'wins', 'losses'}
        assert required.issubset(atp.playoff_results.columns), \
            f"Missing columns: {required - set(atp.playoff_results.columns)}"

    def test_games_has_required_columns(self, atp):
        required = {'year', 'week', 'round', 'match_id', 'team', 'score',
                    'opponent', 'opp_score', 'won', 'bracket', 'placement_game'}
        assert required.issubset(atp.playoff_games.columns), \
            f"Missing columns: {required - set(atp.playoff_games.columns)}"

    def test_results_not_empty(self, atp):
        assert len(atp.playoff_results) > 0, "playoff_results is empty"

    def test_games_not_empty(self, atp):
        assert len(atp.playoff_games) > 0, "playoff_games is empty"

    def test_results_has_six_teams_per_year(self, atp):
        per_year = atp.playoff_results.groupby('year').size()
        assert (per_year == 6).all(), \
            f"Expected 6 teams per year in results:\n{per_year}"

    def test_games_has_fourteen_games_per_year(self, atp):
        # 7 winners + 7 losers = 14 matchups × 2 rows each = 28 rows per year
        per_year = atp.playoff_games.groupby('year').size()
        assert (per_year == 28).all(), \
            f"Expected 28 game rows per year (14 games × 2 teams):\n{per_year}"

    def test_no_null_team_names_in_results(self, atp):
        nulls = atp.playoff_results['team'].isna().sum()
        assert nulls == 0, f"{nulls} null team names in playoff_results"

    def test_no_null_team_names_in_games(self, atp):
        nulls = atp.playoff_games['team'].isna().sum()
        assert nulls == 0, f"{nulls} null team names in playoff_games"

    def test_team_names_are_known_managers(self, atp):
        all_known = set(name for yr_map in core.roster_ids.values()
                        for name in yr_map.values())
        unknown = set(atp.playoff_results['team'].unique()) - all_known
        assert not unknown, f"Unknown team names in results: {unknown}"

    def test_placements_are_valid(self, atp):
        valid = {1, 2, 3, 4, 5, 6}
        placed = atp.playoff_results.dropna(subset=['placement'])
        invalid = set(placed['placement'].unique()) - valid
        assert not invalid, f"Invalid placement values: {invalid}"

    def test_exactly_one_champion_per_year(self, atp):
        champs = (atp.playoff_results[atp.playoff_results['placement'] == 1]
                  .groupby('year').size())
        assert (champs == 1).all(), \
            f"Expected exactly one champion per year:\n{champs}"

    def test_reg_season_rank_in_valid_range(self, atp):
        ranks = atp.playoff_results['reg_season_rank']
        assert ranks.between(1, 12).all(), \
            f"reg_season_rank out of 1-12 range: {ranks[~ranks.between(1, 12)].unique()}"

    def test_round_exit_in_valid_range(self, atp):
        exits = atp.playoff_results['round_exit']
        assert exits.between(1, 3).all(), \
            f"round_exit out of 1-3 range: {exits[~exits.between(1, 3)].unique()}"

    def test_both_brackets_present_in_games(self, atp):
        brackets = set(atp.playoff_games['bracket'].unique())
        assert brackets == {'winners', 'losers'}, \
            f"Expected both brackets, got: {brackets}"

    def test_scores_are_numeric(self, atp):
        assert atp.playoff_games['score'].dtype.kind == 'f', "score column should be float"
        assert atp.playoff_games['opp_score'].dtype.kind == 'f'

    def test_won_column_is_boolean_like(self, atp):
        assert atp.playoff_games['won'].dtype == bool or \
               atp.playoff_games['won'].isin([True, False]).all()


# ── 6B-D, 6F: Chart smoke tests ───────────────────────────────────────────────

class TestAllTimePlayoffsCharts:

    def test_playoff_pedigree_returns_figure(self, atp):
        fig = atp.PlayoffPedigree()
        assert _is_valid_fig(fig), "PlayoffPedigree returned empty or invalid figure"

    def test_playoff_pedigree_has_four_traces(self, atp):
        fig = atp.PlayoffPedigree()
        assert len(fig.data) == 4, \
            f"Expected 4 overlay bar traces, got {len(fig.data)}"

    def test_playoff_win_rate_returns_figure(self, atp):
        fig = atp.PlayoffWinRate()
        assert _is_valid_fig(fig), "PlayoffWinRate returned empty or invalid figure"

    def test_playoff_win_rate_is_horizontal_bar(self, atp):
        fig = atp.PlayoffWinRate()
        assert fig.data[0].orientation == 'h'

    def test_seeding_scatter_returns_figure(self, atp):
        fig = atp.SeedingScatter()
        assert _is_valid_fig(fig), "SeedingScatter returned empty or invalid figure"

    def test_seeding_scatter_y_axis_inverted(self, atp):
        fig = atp.SeedingScatter()
        # Playoff finish 1 should be at the top → yaxis range starts high
        y_range = fig.layout.yaxis.range
        assert y_range is not None
        assert y_range[0] > y_range[1], "Y axis should be inverted (1 at top)"

    def test_path_to_glory_returns_figure(self, atp):
        fig = atp.PathToGlory()
        assert _is_valid_fig(fig), "PathToGlory returned empty or invalid figure"

    def test_path_to_glory_one_trace_per_year(self, atp):
        fig = atp.PathToGlory()
        years_with_champs = atp.playoff_results[
            atp.playoff_results['placement'] == 1
        ]['year'].nunique()
        assert len(fig.data) == years_with_champs, \
            f"Expected {years_with_champs} traces (one per champion), got {len(fig.data)}"
