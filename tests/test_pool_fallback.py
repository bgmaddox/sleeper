"""Pool tabs (Pick 'Em, Survivor) survive a slow or down Sleeper API.

The current season's pool pickle expires after _POOL_TTL. On 2026-11-18 the
refresh hit a 30 s read timeout and the Pick 'Em tab showed the raw error,
though a copy from minutes earlier was on disk. data_loader._load_pool now
serves that copy when the refresh fails.
"""
import os
import sys
import time

import pytest
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import data_loader as dl  # noqa: E402
import sleeper_core as core  # noqa: E402


class _Pool:
    def __init__(self, tag):
        self.tag = tag
        self.user_map = {}


def _timeout(year):
    raise requests.ReadTimeout("Read timed out. (read timeout=30)")


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "CACHE_DIR", str(tmp_path))
    return tmp_path


def _age(key, seconds):
    path = dl._cache_path(key)
    old = time.time() - seconds
    os.utime(path, (old, old))


def test_expired_copy_is_served_when_refresh_times_out(cache):
    year = core.CURRENT_SEASON
    dl._save_cache(f"pickem_{year}", _Pool("yesterday"))
    _age(f"pickem_{year}", dl._POOL_TTL + 60)
    assert dl._load_pool(f"pickem_{year}", year, _timeout).tag == "yesterday"


def test_fresh_build_replaces_expired_copy(cache):
    year = core.CURRENT_SEASON
    dl._save_cache(f"pickem_{year}", _Pool("yesterday"))
    _age(f"pickem_{year}", dl._POOL_TTL + 60)
    assert dl._load_pool(f"pickem_{year}", year, lambda y: _Pool("now")).tag == "now"
    assert dl._load_cache(f"pickem_{year}").tag == "now"


def test_no_cached_copy_still_raises(cache):
    with pytest.raises(requests.RequestException):
        dl._load_pool(f"pickem_{core.CURRENT_SEASON}", core.CURRENT_SEASON, _timeout)


def test_non_network_errors_are_not_masked(cache):
    """A bug in the build should surface, not be papered over by old data."""
    year = core.CURRENT_SEASON
    dl._save_cache(f"pickem_{year}", _Pool("yesterday"))
    _age(f"pickem_{year}", dl._POOL_TTL + 60)
    with pytest.raises(KeyError):
        dl._load_pool(f"pickem_{year}", year, lambda y: {}["boom"])
