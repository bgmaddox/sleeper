"""Automatic pickup of a newly scored week.

The gap this closes: season pickles have no TTL, so once a year was cached it
stayed frozen until a human pressed SYNC. In 2026 that left Week 1 unscored on
the site for days after the games were played, with no mechanism anywhere that
would ever have noticed.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "webapp"))

os.environ.setdefault("SLEEPER_SKIP_EAGER_LOAD", "1")

app = pytest.importorskip("app", reason="webapp/app.py not importable")

YEAR = 4242


@pytest.fixture(autouse=True)
def clean_year():
    def _wipe():
        app._data.pop(YEAR, None)
        app._failed_years.discard(YEAR)
        app._loading_years.discard(YEAR)
        app._week_checked_at.pop(YEAR, None)
    _wipe()
    yield
    _wipe()


@pytest.fixture
def no_reload(monkeypatch):
    """Capture reload attempts instead of performing them."""
    started = []
    monkeypatch.setattr(app.dl, "invalidate_week", lambda *a, **k: None)

    class _FakeThread:
        def __init__(self, target=None, args=(), **kw):
            started.append(args[0] if args else None)

        def start(self):
            pass

    monkeypatch.setattr(app.threading, "Thread", _FakeThread)
    return started


def _loaded(weeks):
    return {"weeks": {w: object() for w in weeks}}


class TestNewestLoadedWeek:
    def test_zero_when_year_absent(self):
        assert app._newest_loaded_week(YEAR) == 0

    def test_zero_when_no_weeks(self):
        app._data[YEAR] = _loaded([])
        assert app._newest_loaded_week(YEAR) == 0

    def test_highest_week(self):
        app._data[YEAR] = _loaded([1, 2, 3])
        assert app._newest_loaded_week(YEAR) == 3


class TestCheckNewWeek:
    def test_rebuilds_when_sleeper_is_ahead(self, monkeypatch, no_reload):
        """The 2026 Week 1 case: nothing loaded, Sleeper has scored week 1."""
        app._data[YEAR] = _loaded([])
        monkeypatch.setattr(app.dl, "get_current_week", lambda y: 1)
        assert app._check_new_week(YEAR) is True
        assert no_reload == [YEAR], "a background reload should have started"
        assert YEAR not in app._data, "stale season must be dropped before reload"

    def test_no_rebuild_when_up_to_date(self, monkeypatch, no_reload):
        app._data[YEAR] = _loaded([1, 2])
        monkeypatch.setattr(app.dl, "get_current_week", lambda y: 2)
        assert app._check_new_week(YEAR) is False
        assert no_reload == []

    def test_no_rebuild_when_sleeper_is_behind(self, monkeypatch, no_reload):
        """A failed/0 reading must never wipe good data."""
        app._data[YEAR] = _loaded([1, 2, 3])
        monkeypatch.setattr(app.dl, "get_current_week", lambda y: 0)
        assert app._check_new_week(YEAR) is False
        assert app._newest_loaded_week(YEAR) == 3

    def test_throttled_within_interval(self, monkeypatch, no_reload):
        """A dozen open tabs must not become a dozen API calls a minute."""
        calls = []

        def counted(y):
            calls.append(y)
            return 0

        app._data[YEAR] = _loaded([1])
        monkeypatch.setattr(app.dl, "get_current_week", counted)
        for _ in range(5):
            app._check_new_week(YEAR)
        assert len(calls) == 1, "only the first check should reach the API"

    def test_throttle_expires(self, monkeypatch, no_reload):
        calls = []

        def counted(y):
            calls.append(y)
            return 0

        app._data[YEAR] = _loaded([1])
        monkeypatch.setattr(app.dl, "get_current_week", counted)
        app._check_new_week(YEAR)
        # Pretend the throttle window has passed.
        app._week_checked_at[YEAR] -= app._WEEK_CHECK_INTERVAL + 1
        app._check_new_week(YEAR)
        assert len(calls) == 2

    def test_skipped_while_loading(self, monkeypatch, no_reload):
        """The in-flight load owns the year; don't race it."""
        app._loading_years.add(YEAR)
        monkeypatch.setattr(app.dl, "get_current_week",
                            lambda y: pytest.fail("should not hit the API"))
        assert app._check_new_week(YEAR) is False

    def test_skipped_while_failed(self, monkeypatch, no_reload):
        """The retry backoff owns a failed year — don't bypass it."""
        app._failed_years.add(YEAR)
        monkeypatch.setattr(app.dl, "get_current_week",
                            lambda y: pytest.fail("should not hit the API"))
        assert app._check_new_week(YEAR) is False

    def test_api_error_is_swallowed(self, monkeypatch, no_reload):
        app._data[YEAR] = _loaded([1])
        def boom(y):
            raise RuntimeError("sleeper down")
        monkeypatch.setattr(app.dl, "get_current_week", boom)
        assert app._check_new_week(YEAR) is False
        assert app._newest_loaded_week(YEAR) == 1, "good data must survive"


class TestNflStateTtl:
    def test_state_is_not_frozen_at_import(self, monkeypatch):
        """It used to be fetched once at import and never again."""
        app._nfl_state = {}
        app._nfl_state_at = 0.0
        monkeypatch.setattr(app.dl, "fetch_state_json", lambda: {"leg": 7})
        assert app._state().get("leg") == 7

    def test_state_cached_within_ttl(self, monkeypatch):
        app._nfl_state = {}
        app._nfl_state_at = 0.0
        calls = []
        monkeypatch.setattr(app.dl, "fetch_state_json",
                            lambda: (calls.append(1), {"leg": 3})[1])
        app._state()
        app._state()
        assert len(calls) == 1

    def test_state_survives_a_failed_fetch(self, monkeypatch):
        """A timeout must not make the app forget what week it is."""
        app._nfl_state = {"leg": 5}
        app._nfl_state_at = 0.0
        def boom():
            raise RuntimeError("timeout")
        monkeypatch.setattr(app.dl, "fetch_state_json", boom)
        assert app._state() == {"leg": 5}


# ── One rebuild after the newest week settles ────────────────────────────────
#
# A week is first built in the small hours of Tuesday, when Sleeper scores it —
# before nflverse applies stat corrections. Nothing new gets scored after that,
# so without this the corrected stats never reached the site unless someone
# pressed SYNC. The rule: if the newest loaded week has passed its settle time
# (Tuesday SETTLE_HOUR ET) and the data was built before that, rebuild once.

from datetime import datetime

import pandas as pd

from side_bet_resolver import LEAGUE_TZ

# Week 2 of 2026: last game Monday Sep 21, so it settles Tue Sep 22 at noon ET.
SETTLES = datetime(2026, 9, 22, 12, tzinfo=LEAGUE_TZ)
BUILT_EARLY = datetime(2026, 9, 22, 1, 44, tzinfo=LEAGUE_TZ)
BUILT_LATE = datetime(2026, 9, 22, 20, 33, tzinfo=LEAGUE_TZ)
AFTER = datetime(2026, 9, 22, 20, 0, tzinfo=LEAGUE_TZ)
BEFORE = datetime(2026, 9, 22, 9, 0, tzinfo=LEAGUE_TZ)


def _settling(built_at):
    """Weeks 1–2 loaded, week 2's last game on Monday Sep 21."""
    return {
        "weeks": {1: object(), 2: object()},
        "breakout": {2: pd.DataFrame({"gameday": ["2026-09-17", "2026-09-21"]})},
        "built_at": built_at,
    }


class TestSettleRebuild:
    def test_due_when_built_before_settle(self):
        """The 2026 Week 2 case: built 1:44 AM Tuesday, now Tuesday evening."""
        app._data[YEAR] = _settling(BUILT_EARLY)
        assert app._settle_rebuild_due(YEAR, now=AFTER) is True

    def test_not_due_before_settle_time(self):
        """Tuesday morning: corrections may still be landing — wait."""
        app._data[YEAR] = _settling(BUILT_EARLY)
        assert app._settle_rebuild_due(YEAR, now=BEFORE) is False

    def test_not_due_once_rebuilt_after_settle(self):
        """Exactly once — a post-settle build must not loop forever."""
        app._data[YEAR] = _settling(BUILT_LATE)
        assert app._settle_rebuild_due(YEAR, now=AFTER) is False

    def test_not_due_without_build_time(self):
        entry = _settling(None)
        app._data[YEAR] = entry
        assert app._settle_rebuild_due(YEAR, now=AFTER) is False

    def test_not_due_when_year_absent(self):
        assert app._settle_rebuild_due(YEAR, now=AFTER) is False

    def test_not_due_without_gamedays(self):
        entry = _settling(BUILT_EARLY)
        entry["breakout"] = {2: pd.DataFrame()}
        app._data[YEAR] = entry
        assert app._settle_rebuild_due(YEAR, now=AFTER) is False

    def test_check_new_week_rebuilds_when_settle_due(self, monkeypatch, no_reload):
        app._data[YEAR] = _settling(BUILT_EARLY)
        monkeypatch.setattr(app.dl, "get_current_week", lambda y: 2)
        monkeypatch.setattr(app, "_settle_rebuild_due", lambda y: True)
        assert app._check_new_week(YEAR) is True
        assert no_reload == [YEAR]
        assert YEAR not in app._data

    def test_check_new_week_quiet_when_settled_build_is_fresh(self, monkeypatch, no_reload):
        app._data[YEAR] = _settling(BUILT_LATE)
        monkeypatch.setattr(app.dl, "get_current_week", lambda y: 2)
        monkeypatch.setattr(app, "_settle_rebuild_due", lambda y: False)
        assert app._check_new_week(YEAR) is False
        assert no_reload == []


class TestBuiltAt:
    def test_uses_cache_file_mtime(self, monkeypatch, tmp_path):
        """A restart reloads an old pickle — its age is the file's, not now."""
        f = tmp_path / "season.pkl"
        f.write_bytes(b"x")
        stamp = BUILT_EARLY.timestamp()
        os.utime(f, (stamp, stamp))
        monkeypatch.setattr(app.dl, "season_cache_path", lambda y: str(f))
        assert app._built_at(YEAR) == BUILT_EARLY

    def test_none_when_no_cache_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(app.dl, "season_cache_path",
                            lambda y: str(tmp_path / "missing.pkl"))
        assert app._built_at(YEAR) is None
