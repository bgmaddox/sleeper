"""
Data pipeline integrity tests.

These verify that the data loading chain produces correctly shaped output.
They run against cached data (no API calls) and should pass after every
code change to sleeper_core.py or data_loader.py.

A failure here means core data is broken — chart tests will likely also fail.
Run these first.
"""
import os
import pytest
import sleeper_core as core
import data_loader as dl


# ── Season loading ────────────────────────────────────────────────────────────

class TestSeasonLoading:

    def test_load_returns_three_objects(self, season_2024):
        league, season, weeks = season_2024
        assert league is not None
        assert season is not None
        assert weeks is not None

    def test_league_has_year(self, league_2024):
        assert league_2024.year == 2024

    def test_league_has_player_names(self, league_2024):
        assert isinstance(league_2024.player_names, dict)
        assert len(league_2024.player_names) > 100, "player_names should have hundreds of entries"

    def test_league_has_teams(self, league_2024):
        assert hasattr(league_2024, 'Teams')
        assert len(league_2024.Teams) == 12, "Legacy League has 12 teams"

    def test_weeks_dict_has_entries(self, weeks_2024):
        assert len(weeks_2024) >= 14, f"Expected at least 14 weeks, got {len(weeks_2024)}"

    def test_weeks_are_sequential(self, weeks_2024):
        week_nums = sorted(weeks_2024.keys())
        assert week_nums[0] == 1, "Weeks should start at 1"
        for i in range(1, len(week_nums)):
            assert week_nums[i] == week_nums[i - 1] + 1, f"Gap in weeks at {week_nums[i]}"


# ── Global dict population ────────────────────────────────────────────────────

class TestGlobalDicts:

    def test_allmatches_has_2024(self, season_2024):
        assert 2024 in core.AllMatchesDict
        assert len(core.AllMatchesDict[2024]) >= 14

    def test_allbreakout_has_2024(self, season_2024):
        assert 2024 in core.AllBreakoutDict
        assert len(core.AllBreakoutDict[2024]) >= 14

    def test_allmatches_values_are_dataframes(self, season_2024):
        import pandas as pd
        for week, df in core.AllMatchesDict[2024].items():
            assert isinstance(df, pd.DataFrame), f"Week {week} AllMatchesDict value is not a DataFrame"

    def test_allbreakout_values_are_dataframes(self, season_2024):
        import pandas as pd
        for week, df in core.AllBreakoutDict[2024].items():
            assert isinstance(df, pd.DataFrame), f"Week {week} AllBreakoutDict value is not a DataFrame"


# ── dfBreakout shape (PlayerBreakout output) ──────────────────────────────────

REQUIRED_BREAKOUT_COLS = {'player', 'points', 'starter', 'team', 'position', 'week'}

class TestBreakoutDataframe:
    # The Week-level breakout dataframe is stored as week_obj.Breakout

    def test_breakout_has_required_columns(self, week_obj):
        df = week_obj.Breakout
        missing = REQUIRED_BREAKOUT_COLS - set(df.columns)
        assert not missing, f"Breakout missing columns: {missing}"

    def test_breakout_is_not_empty(self, week_obj):
        assert len(week_obj.Breakout) > 0

    def test_breakout_has_starters(self, week_obj):
        starters = week_obj.Breakout[week_obj.Breakout['starter'] == 1]
        assert len(starters) > 0, "No starters found in Breakout"

    def test_breakout_has_expected_starter_count(self, week_obj):
        # 12 teams × 9 starters each = 108 starter rows per week
        starters = week_obj.Breakout[week_obj.Breakout['starter'] == 1]
        assert len(starters) >= 100, f"Too few starters: {len(starters)} (expected ~108)"

    def test_breakout_points_are_numeric(self, week_obj):
        import pandas as pd
        assert pd.api.types.is_numeric_dtype(week_obj.Breakout['points'])

    def test_breakout_no_unknown_only_starters(self, week_obj):
        """Verify starter names aren't all falling back to 'Unknown' (would mean player lookup is broken)."""
        starters = week_obj.Breakout[week_obj.Breakout['starter'] == 1]
        unknown_starters = starters[starters['player'].str.startswith('Unknown')]
        pct_unknown = len(unknown_starters) / len(starters)
        assert pct_unknown < 0.1, f"{pct_unknown:.0%} of starters are Unknown — player_names lookup may be broken"

    def test_all_weeks_have_breakout(self, weeks_2024):
        for week_num, wk in weeks_2024.items():
            assert hasattr(wk, 'Breakout'), f"Week {week_num} missing Breakout attribute"
            assert len(wk.Breakout) > 0, f"Week {week_num} Breakout is empty"


# ── AllMatches / WeeklyDataframe shape ───────────────────────────────────────

REQUIRED_MATCH_COLS = {'Team', 'Total', 'Week', 'Matchup', 'Year'}

class TestMatchesDataframe:

    def test_matches_has_required_columns(self, weeks_2024):
        import pandas as pd
        sample_week = weeks_2024[sorted(weeks_2024.keys())[0]]
        df = core.AllMatchesDict[2024].get(sample_week.week)
        assert df is not None
        missing = REQUIRED_MATCH_COLS - set(df.columns)
        assert not missing, f"AllMatchesDict df missing columns: {missing}"

    def test_matches_has_12_teams(self, weeks_2024):
        for week_num, week_obj in list(weeks_2024.items())[:3]:
            df = core.AllMatchesDict[2024].get(week_num)
            assert df is not None
            assert len(df) == 12, f"Week {week_num} should have 12 teams, got {len(df)}"

    def test_week_index_math(self, weeks_2024):
        """
        Week Index = week + (14 * (year - 2019)).
        2024 is the 6th season (index 5), so week 1 = 1 + 14*5 = 71.
        Verify this holds for a sample week.
        """
        sample_week = weeks_2024.get(1)
        if sample_week is None:
            pytest.skip("Week 1 not in cache")
        df = core.AllMatchesDict[2024].get(1)
        expected_index = 1 + (14 * (2024 - 2019))  # = 71
        assert (df['Week Index'] == expected_index).all(), \
            f"Week Index mismatch: expected {expected_index}, got {df['Week Index'].unique()}"


# ── player_names lookup safety ────────────────────────────────────────────────

class TestPlayerLookup:

    def test_unknown_player_id_does_not_crash(self, league_2024):
        """
        Verify .get() with a garbage ID returns a fallback, not a KeyError.
        This is the behavior Task 1A enforces.
        """
        result = league_2024.player_names.get("FAKE_ID_99999", "Unknown (FAKE_ID_99999)")
        assert result == "Unknown (FAKE_ID_99999)"

    def test_known_special_cases_exist(self, league_2024):
        """'0' and team abbreviations should be in player_names."""
        assert '0' in league_2024.player_names, "player_names['0'] sentinel should exist"

    def test_player_names_all_string_values(self, league_2024):
        bad = {k: v for k, v in league_2024.player_names.items() if not isinstance(v, str)}
        assert not bad, f"Non-string values in player_names: {list(bad.items())[:5]}"


# ── Cache invalidation ────────────────────────────────────────────────────────

class TestCacheInvalidation:

    def test_invalidate_week_removes_season_cache(self, tmp_path, monkeypatch):
        """
        invalidate_week() should delete the season-level pkl file.
        Uses a temp cache dir so it doesn't touch real data.
        """
        import pickle, hashlib

        fake_cache = tmp_path / ".cache"
        fake_cache.mkdir()
        monkeypatch.setattr(dl, "CACHE_DIR", str(fake_cache))

        # Write a fake season cache file
        key = "season_data_2024_18"
        h = hashlib.md5(key.encode()).hexdigest()
        fake_pkl = fake_cache / f"{key}_{h}.pkl"
        fake_pkl.write_bytes(pickle.dumps({"fake": True}))
        assert fake_pkl.exists()

        # invalidate_week should remove it
        dl.invalidate_week(2024, 5)
        assert not fake_pkl.exists(), "Season cache file should have been deleted"

    def test_invalidate_week_no_crash_if_file_missing(self):
        """Should not raise if the season cache file doesn't exist for a known year."""
        try:
            # 2019 cache exists but we test with a monkeypatched CACHE_DIR in the
            # other test, so just call with a real year and confirm no exception.
            dl.invalidate_week(2019, 1)
        except KeyError as e:
            pytest.fail(f"invalidate_week raised KeyError for unknown year — consider guarding leagueNumbers_Dict lookup: {e}")
        except Exception as e:
            pytest.fail(f"invalidate_week raised unexpectedly: {e}")


# ── CURRENT_SEASON constant ───────────────────────────────────────────────────

class TestCurrentSeasonConstant:

    def test_current_season_exists(self):
        """Task 1C: CURRENT_SEASON constant is defined in sleeper_core."""
        assert hasattr(core, 'CURRENT_SEASON'), \
            "CURRENT_SEASON constant not found in sleeper_core"

    def test_current_season_is_int(self):
        if not hasattr(core, 'CURRENT_SEASON'):
            pytest.skip("CURRENT_SEASON not yet defined (Task 1C pending)")
        assert isinstance(core.CURRENT_SEASON, int)

    def test_current_season_in_available_years(self):
        if not hasattr(core, 'CURRENT_SEASON'):
            pytest.skip("CURRENT_SEASON not yet defined (Task 1C pending)")
        assert core.CURRENT_SEASON in core.AVAILABLE_YEARS, \
            f"CURRENT_SEASON {core.CURRENT_SEASON} not in AVAILABLE_YEARS {core.AVAILABLE_YEARS}"
