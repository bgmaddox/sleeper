"""
Shared pytest fixtures for the Legacy League test suite.

All fixtures load from the .cache/ directory — no API calls are made.
If a required cache file is missing, the fixture skips the test rather
than hitting the network. Run the app once to populate the cache first.

Session scope means each fixture loads once and is reused across all tests
in the session, keeping the suite fast (~30s for the full run).
"""
import sys
import os

# Project root on the path so imports work from the tests/ subdirectory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import data_loader as dl
import sleeper_core as core


def _cache_exists(year: int) -> bool:
    path = dl._cache_path(f"season_data_{year}_18")
    return os.path.exists(path)


@pytest.fixture(scope="session")
def season_2024():
    """
    Load 2024 season from cache. Returns (league, season, weeks).
    Skips if cache is missing — run the app first to populate it.
    """
    if not _cache_exists(2024):
        pytest.skip("2024 cache not found — start the app once to build it")
    league, season, weeks = dl.load_data_for_year(2024, verbose=False)
    return league, season, weeks


@pytest.fixture(scope="session")
def season_2025():
    """Load 2025 (current/in-progress) season from cache."""
    if not _cache_exists(2025):
        pytest.skip("2025 cache not found — start the app once to build it")
    league, season, weeks = dl.load_data_for_year(2025, verbose=False)
    return league, season, weeks


@pytest.fixture(scope="session")
def league_2024(season_2024):
    return season_2024[0]


@pytest.fixture(scope="session")
def sf(season_2024):
    """The 2024 Season object — used by most chart smoke tests."""
    return season_2024[1]


@pytest.fixture(scope="session")
def weeks_2024(season_2024):
    """Dict of {week_num: Week object} for 2024."""
    return season_2024[2]


@pytest.fixture(scope="session")
def week_obj(weeks_2024):
    """A single mid-season Week object (week 8) for chart tests."""
    available = sorted(weeks_2024.keys())
    # Pick week 8 if available, otherwise the midpoint
    target = 8 if 8 in available else available[len(available) // 2]
    return weeks_2024[target]


@pytest.fixture(scope="session")
def alltime(season_2024):
    """
    AllTime object populated with all cached seasons.
    Loads each cached year into the global AllMatchesDict / AllBreakoutDict
    that AllTime depends on, then returns the AllTime instance.
    """
    for year in core.AVAILABLE_YEARS:
        if _cache_exists(year):
            dl.load_data_for_year(year, verbose=False)

    at = core.AllTime()
    at.Update()
    return at


@pytest.fixture(scope="session")
def survivor_2025():
    """Survivor object for 2025 season. Skips if cache is missing."""
    path = dl._cache_path("survivor_2025")
    if not os.path.exists(path):
        pytest.skip("survivor 2025 cache not found — run data_loader.load_survivor_for_year(2025) once to build it")
    return dl.load_survivor_for_year(2025)


@pytest.fixture(scope="session")
def survivor_2024():
    """Survivor object for 2024 season. Skips if cache is missing."""
    path = dl._cache_path("survivor_2024")
    if not os.path.exists(path):
        pytest.skip("survivor 2024 cache not found — run data_loader.load_survivor_for_year(2024) once to build it")
    return dl.load_survivor_for_year(2024)


@pytest.fixture(scope="session")
def playoff_calc_2024(season_2024):
    """PlayoffCalculator for 2024 season at as_of_week=12 (weeks 1–11 complete, weeks 12–14 remaining)."""
    league, season, _ = season_2024
    return core.PlayoffCalculator(league, season, as_of_week=12)


@pytest.fixture(scope="session")
def playoff_snapshots_2024(playoff_calc_2024):
    """Pre-computed playoff snapshots for 2024 at week 12. Completed season → deterministic results."""
    return playoff_calc_2024.compute()
