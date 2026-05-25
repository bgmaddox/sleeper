"""
SideBet class smoke tests.

Tests verify: instantiation, config helper, all week chart methods return valid
figures, Scoreboard works, and no fig.show() calls remain in the class.

Run: pytest tests/test_sidebet.py -m "not slow" -q
"""
import re
import os
import sys
import pytest
from plotly import graph_objects as go

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import sleeper_core as core


def _is_valid_fig(fig) -> bool:
    return isinstance(fig, go.Figure) and len(fig.data) > 0


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sidebet_2025(season_2025):
    league, season, weeks = season_2025
    return core.SideBet(league, season, DictofWeeks=weeks)


@pytest.fixture(scope="module")
def week8_2025(season_2025):
    _, _, weeks = season_2025
    if 8 not in weeks:
        pytest.skip("Week 8 not in 2025 cache")
    return weeks[8]


@pytest.fixture(scope="module")
def week13_2025(season_2025):
    _, _, weeks = season_2025
    if 13 not in weeks:
        pytest.skip("Week 13 not in 2025 cache")
    return weeks[13]


# ── Instantiation ─────────────────────────────────────────────────────────────

class TestSideBetInstantiation:

    def test_creates_successfully(self, sidebet_2025):
        assert sidebet_2025 is not None

    def test_teamcolors_populated(self, sidebet_2025):
        assert isinstance(sidebet_2025.teamcolors, dict)
        assert len(sidebet_2025.teamcolors) > 0

    def test_league_year_is_2025(self, sidebet_2025):
        assert sidebet_2025.League.year == 2025


# ── Config helper ─────────────────────────────────────────────────────────────

class TestGetWeekConfig:

    def test_returns_correct_dict_for_known_week(self, sidebet_2025):
        cfg = sidebet_2025.get_week_config(5)
        assert cfg["name"] == "The Replacements"
        assert "bench" in cfg["desc"].lower()
        assert cfg["winner"] == "DirtyCommie"

    def test_returns_default_for_unknown_week(self, sidebet_2025):
        cfg = sidebet_2025.get_week_config(99)
        assert cfg["name"] == "Week 99"
        assert cfg["desc"] == ""
        assert cfg["winner"] == ""

    def test_all_14_weeks_have_config(self, sidebet_2025):
        season_cfg = core.SIDE_BET_SEASONS.get(2025, {})
        assert len(season_cfg) == 14
        for wk in range(1, 15):
            assert wk in season_cfg, f"Week {wk} missing from SIDE_BET_SEASONS[2025]"

    def test_each_config_has_required_keys(self, sidebet_2025):
        for wk, cfg in core.SIDE_BET_SEASONS[2025].items():
            assert "name" in cfg, f"Week {wk} missing 'name'"
            assert "desc" in cfg, f"Week {wk} missing 'desc'"
            assert "winner" in cfg, f"Week {wk} missing 'winner'"


# ── Week chart methods ────────────────────────────────────────────────────────

class TestWeekChartMethods:

    def test_week1_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week1(week8_2025, top=None)
        assert _is_valid_fig(fig), "Week1 returned empty or invalid figure"

    def test_week2_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week2(week8_2025)
        assert _is_valid_fig(fig), "Week2 returned empty or invalid figure"

    def test_week3_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week3(week8_2025)
        assert _is_valid_fig(fig), "Week3 returned empty or invalid figure"

    def test_week4_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week4(week8_2025)
        assert _is_valid_fig(fig), "Week4 returned empty or invalid figure"

    def test_week5_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week5(week8_2025)
        assert _is_valid_fig(fig), "Week5 returned empty or invalid figure"

    def test_week6_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week6(week8_2025)
        assert _is_valid_fig(fig), "Week6 returned empty or invalid figure"

    def test_week7_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week7(week8_2025)
        assert _is_valid_fig(fig), "Week7 returned empty or invalid figure"

    def test_week8_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week8(week8_2025)
        assert _is_valid_fig(fig), "Week8 returned empty or invalid figure"

    def test_week9_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week9(week8_2025)
        assert isinstance(fig, go.Figure), "Week9 should return a go.Figure (data or placeholder)"

    @pytest.mark.slow
    def test_week10_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week10(week8_2025)
        assert _is_valid_fig(fig), "Week10 returned empty or invalid figure"

    def test_week11_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week11(week8_2025)
        assert _is_valid_fig(fig), "Week11 returned empty or invalid figure"

    def test_week12_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week12(week8_2025)
        assert _is_valid_fig(fig), "Week12 returned empty or invalid figure"

    def test_week13_returns_figure(self, sidebet_2025, week13_2025):
        fig = sidebet_2025.Week13(week13_2025)
        assert _is_valid_fig(fig), "Week13 returned empty or invalid figure"

    def test_week14_returns_figure(self, sidebet_2025, week8_2025):
        fig = sidebet_2025.Week14(week8_2025)
        assert _is_valid_fig(fig), "Week14 returned empty or invalid figure"


# ── Scoreboard ────────────────────────────────────────────────────────────────

class TestScoreboard:

    def test_scoreboard_returns_figure(self, sidebet_2025):
        fig = sidebet_2025.Scoreboard()
        assert _is_valid_fig(fig), "Scoreboard returned empty or invalid figure"

    def test_scoreboard_tally_df_populated(self, sidebet_2025):
        sidebet_2025.Scoreboard()
        assert hasattr(sidebet_2025, 'Tally')
        assert len(sidebet_2025.Tally) > 0

    def test_scoreboard_winner_counts_match_config(self, sidebet_2025):
        """bgmaddox won weeks 7, 8, 12 = 3 wins."""
        sidebet_2025.Scoreboard()
        row = sidebet_2025.Tally[sidebet_2025.Tally['Team'] == 'bgmaddox']
        assert not row.empty, "bgmaddox not in tally"
        assert row.iloc[0]['Wins'] == 3


# ── Code inspection ───────────────────────────────────────────────────────────

class TestNoFigShow:

    def test_no_fig_show_in_sidebet_class(self):
        """Verify no fig.show() calls remain in the SideBet class."""
        src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sleeper_core.py')
        with open(src_path) as f:
            source = f.read()

        # Extract only the SideBet class block
        match = re.search(r'^class SideBet:.*', source, re.MULTILINE | re.DOTALL)
        assert match, "Could not locate SideBet class in sleeper_core.py"
        sidebet_block = match.group(0)

        count = sidebet_block.count('fig.show()')
        assert count == 0, f"Found {count} fig.show() call(s) in SideBet class"
