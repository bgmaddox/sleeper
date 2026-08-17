"""Preseason state — a renewed season with no weeks played (Tasks 11D/11E).

The failure this guards against is not an exception, it's a hang: before the fix,
selecting a renewed-but-unplayed season showed "Loading season data…" forever,
because nothing could distinguish "loaded, zero weeks" from "still loading".
"""

import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "webapp"))

# app.py eagerly loads every season on import. An unplayed season is never
# cached, so without this the suite would hit the Sleeper API on every run.
os.environ.setdefault("SLEEPER_SKIP_EAGER_LOAD", "1")

import sleeper_core as core  # noqa: E402
import data_loader as dl  # noqa: E402

app = pytest.importorskip("app", reason="webapp/app.py not importable")


def _must_not_be_called(*args, **kwargs):
    raise AssertionError("load_data_for_year must not run on the render thread")


@pytest.fixture
def empty_year():
    """CURRENT_SEASON registered as loaded-but-unplayed; restored afterwards."""
    year = core.CURRENT_SEASON
    had = year in app._data
    prev = app._data.get(year)
    app._data[year] = {"league": None, "season": None, "weeks": {}, "sidebet": None,
                       "matches": {}, "breakout": {}}
    yield year
    if had:
        app._data[year] = prev
    else:
        app._data.pop(year, None)


class TestIsPreseason:
    def test_false_when_year_not_loaded(self):
        """Not-yet-loaded must stay False, or the spinner is skipped too early."""
        year = 4242
        app._data.pop(year, None)
        assert app._is_preseason(year) is False

    def test_true_when_loaded_with_no_weeks(self, empty_year):
        assert app._is_preseason(empty_year) is True

    def test_false_when_weeks_exist(self, empty_year):
        app._data[empty_year]["weeks"] = {1: object()}
        assert app._is_preseason(empty_year) is False

    def test_does_not_trigger_a_load(self, monkeypatch):
        """_is_preseason must be side-effect free — it runs during render."""
        called = []
        monkeypatch.setattr(app, "_ensure", lambda y: called.append(y))
        app._is_preseason(4242)
        assert called == []


class TestLoadingPlaceholder:
    def test_spinner_when_not_preseason(self):
        out = app._loading_placeholder(4242)
        assert "loading-msg" in str(out)

    def test_preseason_note_when_empty(self, empty_year):
        out = app._loading_placeholder(empty_year)
        rendered = str(out)
        assert "ps-note" in rendered
        assert "loading-msg" not in rendered

    def test_spinner_when_year_omitted(self):
        """Back-compat: the bare call must still work."""
        assert "loading-msg" in str(app._loading_placeholder())


class TestBootStopsPolling:
    """The actual hang. _boot's 6th output is the interval's `disabled` flag."""

    DISABLED_IDX = 5

    def test_keeps_polling_while_loading(self, monkeypatch):
        year = 4242
        app._data.pop(year, None)
        app._failed_years.discard(year)
        monkeypatch.setattr(app, "_weeks", lambda y: {})
        out = app._boot(1, year)
        assert out[self.DISABLED_IDX] is False, "should still be polling"

    def test_stops_polling_when_loaded_but_empty(self, empty_year, monkeypatch):
        monkeypatch.setattr(app, "_weeks", lambda y: {})
        out = app._boot(1, empty_year)
        assert out[self.DISABLED_IDX] is True, \
            "a loaded-but-unplayed season must stop the poller, not spin forever"

    def test_stops_polling_when_failed(self, monkeypatch):
        year = 4243
        app._data.pop(year, None)
        app._failed_years.add(year)
        monkeypatch.setattr(app, "_weeks", lambda y: {})
        try:
            out = app._boot(1, year)
            assert out[self.DISABLED_IDX] is True
        finally:
            app._failed_years.discard(year)


class TestPreseasonHero:
    def test_renders_core_elements(self, empty_year):
        rendered = str(app._preseason_hero(empty_year))
        assert "ps-hero" in rendered
        assert str(empty_year) in rendered
        assert "KICKOFF" in rendered

    def test_lists_every_manager(self, empty_year):
        rendered = str(app._preseason_hero(empty_year))
        for name in core.roster_ids[empty_year].values():
            assert name in rendered, f"{name} missing from preseason hero"

    def test_carries_a_kickoff_timestamp(self, empty_year, monkeypatch):
        """The countdown target is data-driven; JS reads it from the attribute.

        Pinned rather than read from the schedule cache — this asserts the markup
        contract, not whether a pickle happens to be on disk.
        """
        monkeypatch.setattr(app.dl, "season_kickoff_ms", lambda y: 1788999600000)
        rendered = str(app._preseason_hero(empty_year))
        assert "data-kickoff" in rendered
        assert "1788999600000" in rendered

    def test_survives_missing_champion(self, empty_year, monkeypatch):
        monkeypatch.setattr(app, "_defending_champion", lambda y: None)
        assert "ps-hero" in str(app._preseason_hero(empty_year))

    def test_survives_missing_schedule(self, empty_year, monkeypatch):
        monkeypatch.setattr(app.dl, "season_kickoff_ms", lambda y: None)
        rendered = str(app._preseason_hero(empty_year))
        assert "ps-hero" in rendered
        # Each countdown now carries its own pending state instead of one
        # shared fallback line.
        assert "ps-clock-pending" in rendered
        assert "SCHEDULE PENDING" in rendered

    def test_this_week_tab_uses_hero(self, empty_year):
        rendered = str(app._tab_week(empty_year, 1, None))
        assert "ps-hero" in rendered
        assert "loading-msg" not in rendered


class TestCountdownBlock:
    """Draft and Week 1 each get a countdown; the draft date may not exist yet."""

    def test_pending_when_no_date(self):
        out = str(app._countdown_block("DRAFT", None, pending="TBD"))
        assert "TBD" in out
        assert "data-kickoff" not in out, "a dateless block must not be picked up by the ticker"

    def test_live_when_future(self):
        future = int(time.time() * 1000) + 86_400_000
        out = str(app._countdown_block("DRAFT", future))
        assert f"data-kickoff': '{future}'" in out or str(future) in out
        assert "ps-clock-cell" in out

    def test_complete_when_past(self):
        past = int(time.time() * 1000) - 86_400_000
        out = str(app._countdown_block("DRAFT", past))
        assert "COMPLETE" in out
        assert "data-kickoff" not in out, "a finished countdown must not keep ticking"

    def test_hero_renders_both_countdowns(self, empty_year, monkeypatch):
        monkeypatch.setattr(app.dl, "draft_start_ms", lambda y: None)
        monkeypatch.setattr(app.dl, "season_kickoff_ms", lambda y: 1788999600000)
        out = str(app._preseason_hero(empty_year))
        assert out.count("ps-countdown'") == 2, "expected a draft and a kickoff block"
        assert "DRAFT" in out and "WEEK 1 KICKOFF" in out
        assert "TBD" in out, "unscheduled draft should read TBD"

    def test_hero_survives_both_dates_missing(self, empty_year, monkeypatch):
        monkeypatch.setattr(app.dl, "draft_start_ms", lambda y: None)
        monkeypatch.setattr(app.dl, "season_kickoff_ms", lambda y: None)
        out = str(app._preseason_hero(empty_year))
        assert "ps-hero" in out
        assert "TBD" in out and "SCHEDULE PENDING" in out


class TestDraftStartMs:
    def test_unscheduled_draft_is_not_cached(self, monkeypatch, tmp_path):
        """Caching a null start_time would pin the hero to TBD forever — there is
        no TTL on these pickles."""
        monkeypatch.setattr(dl, "CACHE_DIR", str(tmp_path))
        monkeypatch.setattr(dl, "_get_json", lambda url: {"draft_id": "x", "start_time": None})
        dl.fetch_draft_json("x")
        assert dl._load_cache("draft_x") is None, "unscheduled draft must not be cached"

    def test_scheduled_draft_is_cached(self, monkeypatch, tmp_path):
        monkeypatch.setattr(dl, "CACHE_DIR", str(tmp_path))
        monkeypatch.setattr(dl, "_get_json", lambda url: {"start_time": 1756774923278})
        dl.fetch_draft_json("y")
        assert dl._load_cache("draft_y") is not None

    def test_override_used_when_sleeper_has_none(self, monkeypatch):
        monkeypatch.setattr(dl, "fetch_league_json", lambda lid: {"draft_id": None})
        monkeypatch.setattr(dl, "_override_draft_ms", lambda y: 123456789)
        assert dl.draft_start_ms(core.CURRENT_SEASON) == 123456789

    def test_sleeper_wins_over_override(self, monkeypatch):
        monkeypatch.setattr(dl, "fetch_league_json", lambda lid: {"draft_id": "d"})
        monkeypatch.setattr(dl, "fetch_draft_json", lambda d: {"start_time": 999})
        monkeypatch.setattr(dl, "_override_draft_ms", lambda y: 111)
        assert dl.draft_start_ms(core.CURRENT_SEASON) == 999

    def test_malformed_override_is_ignored(self, monkeypatch):
        monkeypatch.setattr(dl, "fetch_league_json", lambda lid: {"draft_id": None})
        import json as _json
        monkeypatch.setattr(_json, "load", lambda f: {"2026": {"draft": "not-a-date"}})
        assert dl.draft_start_ms(2026) is None

    def test_current_season_draft_is_unscheduled_or_valid(self):
        """Contract check against the real config/Sleeper: either None or sane ms."""
        ms = dl.draft_start_ms(core.CURRENT_SEASON)
        assert ms is None or (isinstance(ms, int) and ms > 1_000_000_000_000)


class TestDefendingChampion:
    def test_returns_none_when_prior_year_absent(self):
        app._data.pop(4241, None)
        assert app._defending_champion(4242) is None

    def test_resolves_from_disk_when_prior_year_not_loaded(self, empty_year):
        """Cold-start regression: the eager loader does the current year first,
        so the prior season isn't in _data when the hero first renders. Since
        the hero also disables the boot poller, a miss here means the banner
        never appears at all."""
        prev = empty_year - 1
        if not os.path.exists(dl.season_cache_path(prev)):
            pytest.skip(f"no cached season data for {prev}")
        had = prev in app._data
        saved = app._data.pop(prev, None)
        try:
            champ = app._defending_champion(empty_year)
            assert champ, f"expected a {prev} champion resolved from disk cache"
            assert champ in set(core.roster_ids[prev].values())
        finally:
            if had:
                app._data[prev] = saved

    def test_does_not_block_on_uncached_prior_year(self, monkeypatch, empty_year):
        """If the prior season isn't cached, warm it in the background and skip
        the banner — never block the render thread on an API call."""
        prev = empty_year - 1
        saved = app._data.pop(prev, None)
        # Point the cache probe at a path that cannot exist, and stub _ensure so
        # its background warm-up thread doesn't muddy what we're measuring here.
        monkeypatch.setattr(app.dl, "season_cache_path",
                            lambda *a, **k: "/nonexistent/no-such-season.pkl")
        warmed = []
        monkeypatch.setattr(app, "_ensure", lambda y: warmed.append(y))
        monkeypatch.setattr(app.dl, "load_data_for_year", _must_not_be_called)
        try:
            assert app._defending_champion(empty_year) is None
            assert warmed == [prev], "prior season should be warmed in the background"
        finally:
            if saved is not None:
                app._data[prev] = saved


class TestSeasonKickoff:
    def test_returns_epoch_ms_for_a_scheduled_season(self):
        ms = dl.season_kickoff_ms(core.CURRENT_SEASON)
        if ms is None:
            pytest.skip("no NFL schedule cached for the current season")
        assert isinstance(ms, int)
        # Sanity: Week 1 kickoff falls in Aug-Oct of that season year.
        import datetime
        dt = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc)
        assert dt.year == core.CURRENT_SEASON
        assert 8 <= dt.month <= 10

    def test_returns_none_for_unknown_season(self):
        assert dl.season_kickoff_ms(1899) is None


class TestLogoAsset:
    """The logo used to point at raw.githubusercontent.com on a `master` branch
    that doesn't exist, for a file that was never committed — so it 404'd and the
    header icon was broken. It must stay a local asset."""

    def test_logo_url_is_local(self):
        assert not app.LOGO_URL.startswith("http"), \
            f"logo must be served locally, got {app.LOGO_URL}"
        assert app.LOGO_URL.startswith(app.URL_BASE), \
            "logo path must sit under URL_BASE so it resolves under a subpath deploy"

    def test_logo_file_exists(self):
        name = app.LOGO_URL.rsplit("/", 1)[-1]
        path = os.path.join(ROOT, "webapp", "assets", name)
        assert os.path.exists(path), f"missing asset {path}"
        assert os.path.getsize(path) > 1024, "logo file looks empty or truncated"

    def test_logo_is_a_real_png(self):
        name = app.LOGO_URL.rsplit("/", 1)[-1]
        path = os.path.join(ROOT, "webapp", "assets", name)
        with open(path, "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n", "not a valid PNG"

    def test_logo_is_git_tracked(self):
        """The original break was an uncommitted file. If it isn't tracked, it
        won't reach the Pi."""
        import subprocess
        name = app.LOGO_URL.rsplit("/", 1)[-1]
        r = subprocess.run(["git", "ls-files", "--error-unmatch", f"webapp/assets/{name}"],
                           cwd=ROOT, capture_output=True)
        if r.returncode != 0:
            pytest.skip("asset not committed yet (expected before the initial commit)")


class TestReducedMotion:
    def test_stylesheet_has_a_reduced_motion_guard(self):
        """The hero loops for weeks; shipping it without this is not acceptable."""
        css = os.path.join(ROOT, "webapp", "assets", "style.css")
        with open(css, encoding="utf-8") as f:
            text = f.read()
        assert "prefers-reduced-motion" in text
