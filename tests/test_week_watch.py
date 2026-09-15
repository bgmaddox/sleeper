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
