# tests/test_config.py
# Session 7 regression tests: league config extracted to config/*.json.
# Guards the loader (int-key conversion, file presence) and the values the
# rest of the pipeline depends on.

import json
import os

import pytest
import requests

import sleeper_core as core
import data_loader as dl

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


class TestConfigFiles:
    def test_config_files_exist_and_parse(self):
        for fname in ("roster_ids.json", "league_ids.json", "side_bet_seasons.json",
                      "aliases.json"):
            path = os.path.join(CONFIG_DIR, fname)
            assert os.path.exists(path), f"missing {fname}"
            with open(path, encoding="utf-8") as f:
                json.load(f)  # raises on invalid JSON


class TestSeasonRolloverIntegrity:
    """Adding a season is a config-only edit; these catch a half-finished one."""

    def test_every_league_year_has_a_roster_map(self):
        missing = [y for y in core.AVAILABLE_YEARS if not core.roster_ids.get(y)]
        assert not missing, f"years in league_ids.json with no roster_ids entry: {missing}"

    def test_roster_slots_are_contiguous_from_one(self):
        """League size varies by year (2020 had 10 teams), but slots are always
        1..N with no gaps — colors are assigned by slot index."""
        wrong = {y: sorted(slots) for y, slots in core.roster_ids.items()
                 if sorted(slots) != list(range(1, len(slots) + 1))}
        assert not wrong, f"non-contiguous roster slots: {wrong}"

    def test_no_duplicate_managers_within_a_season(self):
        dupes = {y: names for y, slots in core.roster_ids.items()
                 if len(set(names := list(slots.values()))) != len(names)}
        assert not dupes, f"duplicate manager in a single season: {dupes}"

    def test_current_season_is_a_known_year(self):
        assert core.CURRENT_SEASON in core.AVAILABLE_YEARS

    def test_current_season_is_the_latest(self):
        """CURRENT_SEASON gates optimal-lineup and coloring for the in-progress year;
        if it lags behind the newest league ID the new season is treated as finished."""
        assert core.CURRENT_SEASON == max(core.AVAILABLE_YEARS)

    def test_webapp_current_year_matches_core(self):
        """webapp/app.py derives CURRENT_YEAR from core — guard against re-hardcoding."""
        import re
        app_path = os.path.join(os.path.dirname(CONFIG_DIR), "webapp", "app.py")
        with open(app_path, encoding="utf-8") as f:
            src = f.read()
        m = re.search(r"^CURRENT_YEAR\s*=\s*(.+)$", src, re.M)
        assert m, "CURRENT_YEAR assignment not found in webapp/app.py"
        assert "core.CURRENT_SEASON" in m.group(1), \
            f"CURRENT_YEAR should derive from core.CURRENT_SEASON, got: {m.group(1).strip()}"

    def test_per_year_global_dicts_cover_every_year(self):
        """Week.__init__ indexes these bare — a missing year is a hard KeyError."""
        for name, d in [("AllMatchesDict", core.AllMatchesDict),
                        ("AllBreakoutDict", core.AllBreakoutDict),
                        ("OptimalScoresByYear", core.OptimalScoresByYear)]:
            assert sorted(d) == core.AVAILABLE_YEARS, f"{name} does not cover AVAILABLE_YEARS"


class TestRosterIds:
    def test_all_years_present_with_int_keys(self):
        assert sorted(core.roster_ids) == core.AVAILABLE_YEARS
        for year, slots in core.roster_ids.items():
            assert isinstance(year, int)
            assert all(isinstance(s, int) for s in slots)
            assert all(isinstance(n, str) for n in slots.values())

    def test_known_values(self):
        assert core.roster_ids[2019][1] == "bgmaddox"
        assert core.roster_ids[2019][3] == "akbrown29"
        assert core.roster_ids[2025][9] == "cosmodromedary"
        assert core.roster_ids[2022][12] == "Just_Here_For_The_Snacks"

    def test_2024_equals_2023_but_is_not_the_same_object(self):
        # The old module had `roster_ids_2024 = roster_ids_2023` — same dict
        # object, so mutating one year silently changed the other.
        assert core.roster_ids[2024] == core.roster_ids[2023]
        assert core.roster_ids[2024] is not core.roster_ids[2023]

    def test_full_league_years_have_12_slots(self):
        for year in (2019, 2021, 2022, 2023, 2024, 2025):
            assert len(core.roster_ids[year]) == 12
        assert len(core.roster_ids[2020]) == 10  # short year


class TestLeagueIds:
    def test_league_ids(self):
        assert core.leagueNumbers_Dict[2019] == 464552024260734976
        assert core.leagueNumbers_Dict[2025] == 1252049821154410496
        assert sorted(core.leagueNumbers_Dict) == core.AVAILABLE_YEARS

    def test_survivor_league_ids(self):
        assert core.SURVIVOR_LEAGUE_IDS == {
            2024: 1136802217681539072,
            2025: 1252050081251590144,
            2026: 1399999661581819904,
        }

    def test_available_years_derived(self):
        assert core.AVAILABLE_YEARS == list(range(2019, 2027))


class TestSideBetSeasons:
    def test_all_years_and_week_shape(self):
        assert sorted(core.SIDE_BET_SEASONS) == core.AVAILABLE_YEARS
        for year, weeks in core.SIDE_BET_SEASONS.items():
            for wk, cfg in weeks.items():
                assert isinstance(wk, int)
                assert set(cfg) == {"name", "desc", "winner"}, f"{year} wk {wk}"

    def test_known_values(self):
        assert core.SIDE_BET_SEASONS[2019][1]["name"] == "Hot Start"
        assert core.SIDE_BET_SEASONS[2019][1]["winner"] == "SweetDizzzzzle"
        assert core.SIDE_BET_SEASONS[2025][1]["name"] == "I'm Flying, Jack!"


class TestIOHardening:
    def test_get_json_has_timeout_and_status_check(self, monkeypatch):
        calls = {}

        class FakeResp:
            def raise_for_status(self):
                calls["status_checked"] = True

            def json(self):
                return {"ok": True}

        def fake_get(url, timeout=None):
            calls["timeout"] = timeout
            return FakeResp()

        monkeypatch.setattr(dl.requests, "get", fake_get)
        assert dl._get_json("https://example.invalid/x") == {"ok": True}
        assert calls["timeout"] == dl.REQUEST_TIMEOUT
        assert calls.get("status_checked")

    def test_week_loop_network_error_fails_year_load(self, monkeypatch):
        # A RequestException during Week construction must abort the year load
        # (RuntimeError), not silently skip the week and cache a partial season.
        def boom(self, w, league):
            raise requests.ConnectionError("simulated blip")

        monkeypatch.setattr(core.Week, "__init__", boom)
        monkeypatch.setattr(dl, "_load_cache", lambda key: None)
        monkeypatch.setattr(dl, "_save_cache", lambda key, value: None)
        monkeypatch.setattr(dl, "fetch_player_data", lambda: {"x": 1})
        monkeypatch.setattr(core, "League", lambda year, league_id: object())
        with pytest.raises(RuntimeError, match="week 1"):
            dl.load_data_for_year(2023, verbose=False)
