"""Failed season loads — visible state and bounded automatic retry.

The failure this guards against is the one that stranded the live Pi for five
days: the service started at boot before DNS/the clock were ready, the only
season that is never cached (the unplayed current one) failed its Sleeper API
call, and `_failed_years` was a terminal state with no retry and no UI. The tab
showed "Loading season data…" forever, and the error text went to a block
buffered stdout that never flushed.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "webapp"))

# app.py eagerly loads every season on import. An unplayed season is never
# cached, so without this the suite would hit the Sleeper API on every run.
os.environ.setdefault("SLEEPER_SKIP_EAGER_LOAD", "1")

app = pytest.importorskip("app", reason="webapp/app.py not importable")

YEAR = 4242  # never a real season, so no fixture can collide with it


@pytest.fixture(autouse=True)
def clean_year():
    """Wipe every trace of YEAR from the module-global load state."""
    def _wipe():
        app._data.pop(YEAR, None)
        app._failed_years.discard(YEAR)
        app._loading_years.discard(YEAR)
        app._load_errors.pop(YEAR, None)
        app._retry_at.pop(YEAR, None)
        app._attempts.pop(YEAR, None)
    _wipe()
    yield
    _wipe()


def _fail_once(monkeypatch, msg="boom"):
    """Make load_data_for_year raise, and run _load_bg synchronously."""
    def _boom(*a, **k):
        raise RuntimeError(msg)
    monkeypatch.setattr(app.dl, "load_data_for_year", _boom)


class TestBackoffSchedule:
    def test_first_failure_schedules_a_retry(self, monkeypatch):
        _fail_once(monkeypatch)
        app._load_bg(YEAR)
        assert YEAR in app._failed_years
        assert app._attempts[YEAR] == 1
        assert app._retry_pending(YEAR) is True

    def test_gives_up_after_the_last_delay(self, monkeypatch):
        """Bounded on purpose: a genuinely dead API must not be hammered."""
        _fail_once(monkeypatch)
        for _ in range(len(app._RETRY_DELAYS) + 1):
            app._retry_at[YEAR] = 0        # pretend the delay elapsed
            app._load_bg(YEAR)
        assert app._attempts[YEAR] == len(app._RETRY_DELAYS) + 1
        assert app._retry_pending(YEAR) is False
        assert YEAR in app._failed_years

    def test_delays_grow(self):
        assert list(app._RETRY_DELAYS) == sorted(app._RETRY_DELAYS)
        assert len(app._RETRY_DELAYS) >= 2

    def test_success_clears_all_failure_state(self, monkeypatch):
        _fail_once(monkeypatch)
        app._load_bg(YEAR)
        assert YEAR in app._failed_years

        monkeypatch.setattr(app.dl, "load_data_for_year",
                            lambda *a, **k: (None, None, {}))
        monkeypatch.setattr(app.core, "SideBet", lambda *a, **k: None)
        app._retry_at[YEAR] = 0
        app._load_bg(YEAR)

        assert YEAR not in app._failed_years
        assert YEAR not in app._load_errors
        assert YEAR not in app._retry_at
        assert YEAR not in app._attempts
        assert YEAR in app._data

    def test_error_text_is_recorded(self, monkeypatch):
        _fail_once(monkeypatch, "DNS go brrr")
        app._load_bg(YEAR)
        assert "DNS go brrr" in app._load_errors[YEAR]


class TestEnsureRespectsBackoff:
    def test_does_not_respawn_before_the_deadline(self, monkeypatch):
        spawned = []
        monkeypatch.setattr(app.threading, "Thread",
                            lambda **k: spawned.append(k) or _NoopThread())
        app._failed_years.add(YEAR)
        app._retry_at[YEAR] = app.time.monotonic() + 999
        app._ensure(YEAR)
        assert spawned == []

    def test_respawns_once_the_deadline_passes(self, monkeypatch):
        spawned = []
        monkeypatch.setattr(app.threading, "Thread",
                            lambda **k: spawned.append(k) or _NoopThread())
        app._failed_years.add(YEAR)
        app._retry_at[YEAR] = 0
        app._ensure(YEAR)
        assert len(spawned) == 1

    def test_terminal_failure_never_respawns(self, monkeypatch):
        """No _retry_at entry means the backoff is exhausted — stay quiet."""
        spawned = []
        monkeypatch.setattr(app.threading, "Thread",
                            lambda **k: spawned.append(k) or _NoopThread())
        app._failed_years.add(YEAR)
        app._retry_at.pop(YEAR, None)
        app._ensure(YEAR)
        assert spawned == []

    def test_loaded_year_never_respawns(self, monkeypatch):
        spawned = []
        monkeypatch.setattr(app.threading, "Thread",
                            lambda **k: spawned.append(k) or _NoopThread())
        app._data[YEAR] = {"weeks": {}}
        app._ensure(YEAR)
        assert spawned == []


class _NoopThread:
    def start(self):
        pass


class TestFailedStateIsVisible:
    def test_retrying_shows_a_spinner_that_says_so(self):
        app._failed_years.add(YEAR)
        app._retry_at[YEAR] = app.time.monotonic() + 999
        out = str(app._loading_placeholder(YEAR))
        assert "loading-msg" in out
        assert "retrying" in out.lower()

    def test_terminal_failure_shows_an_error_card_not_a_spinner(self):
        """The whole point: a dead load must never look like a live one."""
        app._failed_years.add(YEAR)
        app._load_errors[YEAR] = "certificate is not yet valid"
        out = str(app._loading_placeholder(YEAR))
        assert "error-msg-card" in out
        assert "loading-spinner" not in out

    def test_error_card_names_the_year_and_the_way_out(self):
        app._failed_years.add(YEAR)
        app._load_errors[YEAR] = "kaboom"
        out = str(app._loading_placeholder(YEAR))
        assert str(YEAR) in out
        assert "SYNC" in out
        assert "kaboom" in out

    def test_error_card_survives_a_missing_reason(self):
        app._failed_years.add(YEAR)
        out = str(app._loading_placeholder(YEAR))
        assert "error-msg-card" in out

    def test_healthy_year_still_gets_the_plain_spinner(self):
        out = str(app._loading_placeholder(YEAR))
        assert "loading-spinner" in out
        assert "error-msg-card" not in out

    def test_preseason_wins_over_a_stale_failed_flag(self):
        """Loaded-but-unplayed is a success; it must not render as an error."""
        app._data[YEAR] = {"league": None, "season": None, "weeks": {},
                           "sidebet": None, "matches": {}, "breakout": {}}
        app._failed_years.add(YEAR)
        out = str(app._loading_placeholder(YEAR))
        assert "ps-note" in out
        assert "error-msg-card" not in out


class TestRefreshClearsFailureState:
    def test_sync_resets_the_backoff(self, monkeypatch):
        monkeypatch.setattr(app.threading, "Thread", lambda **k: _NoopThread())
        monkeypatch.setattr(app.dl, "invalidate_week", lambda *a, **k: None)
        app._failed_years.add(YEAR)
        app._load_errors[YEAR] = "old"
        app._attempts[YEAR] = 99
        app._retry_at.pop(YEAR, None)

        app._refresh(1, YEAR)

        assert YEAR not in app._failed_years
        assert YEAR not in app._load_errors
        assert YEAR not in app._attempts
        assert YEAR not in app._retry_at
