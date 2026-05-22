"""
Chart method smoke tests.

Each test calls a chart method and verifies it returns a valid Plotly figure
with at least one data trace. These tests do NOT check visual correctness —
they only verify the method runs without crashing and produces something.

Marks:
  @pytest.mark.slow  — charts that render complex subplots (>5s expected)

Run just the fast tests:  pytest tests/test_charts.py -m "not slow"
Run everything:           pytest tests/test_charts.py
"""
import pytest
from plotly import graph_objects as go


def _is_valid_fig(fig) -> bool:
    """A figure is valid if it's a go.Figure with at least one data trace."""
    return isinstance(fig, go.Figure) and len(fig.data) > 0


# ── Week-level charts ─────────────────────────────────────────────────────────

class TestWeekCharts:

    def test_weekly_graph(self, week_obj):
        fig = week_obj.WeeklyGraph()
        assert _is_valid_fig(fig), "WeeklyGraph returned empty or invalid figure"

    def test_weekly_graph_has_data(self, week_obj):
        """WeeklyGraph uses a single combined bar trace (all teams in one trace, grouped by matchup color)."""
        fig = week_obj.WeeklyGraph()
        assert len(fig.data) >= 1
        # All 12 teams' data should be in the y-axis values
        all_y = [str(v) for trace in fig.data for v in (trace.y if trace.y is not None else [])]
        assert len(all_y) >= 12, f"Expected at least 12 team entries across all traces, got {len(all_y)}"


# ── Season-level charts ───────────────────────────────────────────────────────

class TestSeasonCharts:

    def test_season_points_for_against(self, sf):
        fig = sf.SeasonPointsForAgainst()
        assert _is_valid_fig(fig)

    def test_for_against_with_teams(self, sf):
        fig = sf.ForAgainstwithTeams()
        assert _is_valid_fig(fig)

    def test_brawny_bench(self, sf):
        fig = sf.BrawnyBench()
        assert _is_valid_fig(fig)

    def test_starter_performance_graph(self, sf):
        fig = sf.StarterPerformanceGraph()
        assert _is_valid_fig(fig)

    def test_violin_player_starters(self, sf, weeks_2024):
        last_week = max(weeks_2024.keys())
        fig = sf.ViolinPlayer(last_week, Starters=True)
        assert _is_valid_fig(fig)

    def test_violin_player_all(self, sf, weeks_2024):
        last_week = max(weeks_2024.keys())
        fig = sf.ViolinPlayer(last_week, Starters=False)
        assert _is_valid_fig(fig)

    def test_violin_position_starters(self, sf):
        fig = sf.ViolinPosition(Starters=True)
        assert _is_valid_fig(fig)

    def test_violin_position_all(self, sf):
        fig = sf.ViolinPosition(Starters=False)
        assert _is_valid_fig(fig)

    def test_top_players_qb(self, sf):
        fig = sf.TopPlayers(position='QB', threshold=100)
        assert _is_valid_fig(fig)

    def test_top_players_rb(self, sf):
        fig = sf.TopPlayers(position='RB', threshold=100)
        assert _is_valid_fig(fig)

    def test_position_strength_heatmap(self, sf):
        fig = sf.PositionStrengthHeatmap()
        assert _is_valid_fig(fig)

    @pytest.mark.slow
    def test_position_strength_polar(self, sf):
        """4x3 polar subplot grid — slow render expected."""
        fig = sf.PositionStengthPolar()   # typo in name until Task 2C renames it
        assert _is_valid_fig(fig)
        assert len(fig.data) == 12, "Should have one trace per team (12 polar subplots)"

    def test_epa_scatter(self, sf):
        fig = sf.EPAScatter()
        assert _is_valid_fig(fig)

    def test_wopr_treemap(self, sf):
        fig = sf.WOPRTreemap()
        assert _is_valid_fig(fig)

    def test_lineup_efficiency_chart(self, sf, weeks_2024):
        """LineupEfficiencyChart requires a week number."""
        last_week = max(weeks_2024.keys())
        fig = sf.LineupEfficiencyChart(last_week)
        assert _is_valid_fig(fig)

    @pytest.mark.slow
    def test_waiver_wire_bump(self, sf):
        fig = sf.WaiverWireBump()
        assert _is_valid_fig(fig)

    def test_weekly_wins_graph_breakout(self, sf, weeks_2024):
        last_week = max(weeks_2024.keys())
        fig = sf.WeeklyWinsGraphBreakout(last_week)
        assert _is_valid_fig(fig)


# ── AllTime-level charts ──────────────────────────────────────────────────────

class TestAllTimeCharts:

    def test_highest_scoring_losers(self, alltime):
        fig = alltime.HighestScoringLosers()
        assert _is_valid_fig(fig)

    def test_smallest_margins(self, alltime):
        fig = alltime.SmallestMargins()
        assert _is_valid_fig(fig)

    def test_hall_of_shame_team(self, alltime):
        fig = alltime.HallofShame_Team()
        assert _is_valid_fig(fig)

    def test_hall_of_fame_team(self, alltime):
        fig = alltime.HallofFame_Team()
        assert _is_valid_fig(fig)

    def test_hall_of_fame_player(self, alltime):
        fig = alltime.HallofFame_Player()
        assert _is_valid_fig(fig)

    def test_for_against_with_teams(self, alltime):
        fig = alltime.ForAgainstwithTeams()
        assert _is_valid_fig(fig)

    def test_top_scores_team_top(self, alltime):
        fig = alltime.TopScores(Top_Bottom='Top', Team_Player='Team')
        assert _is_valid_fig(fig)

    def test_top_scores_team_bottom(self, alltime):
        fig = alltime.TopScores(Top_Bottom='Bottom', Team_Player='Team')
        assert _is_valid_fig(fig)

    def test_top_scores_player_top(self, alltime):
        fig = alltime.TopScores(Top_Bottom='Top', Team_Player='Player')
        assert _is_valid_fig(fig)


# ── Post-Phase-2 charts (xfail until integrated) ─────────────────────────────
# These will start passing after Tasks 2B/2C/2D are complete.
# Remove the xfail mark when each task is done.

@pytest.mark.xfail(reason="Task 2C: PositionStrengthPolar renamed in Phase 2", strict=False)
def test_position_strength_polar_renamed(sf):
    """After Task 2C, method name should be PositionStrengthPolar (no typo)."""
    fig = sf.PositionStrengthPolar()
    assert _is_valid_fig(fig)
