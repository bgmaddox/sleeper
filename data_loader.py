# data_loader.py
# Handles loading and disk-caching all Sleeper league data.
# First load hits the Sleeper API and nfl_data_py (slow).
# Subsequent loads read from .cache/ (fast).

import os
import pickle
import hashlib
import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

REQUEST_TIMEOUT = 30  # seconds — a hung Sleeper call should fail, not freeze a year load


def _get_json(url: str):
    """GET a JSON API endpoint with a timeout and HTTP status check.
    Raises requests.RequestException on timeout/connection failure/4xx/5xx
    instead of silently caching an error payload."""
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ── Low-level cache helpers ───────────────────────────────────────────────────

def _cache_path(key: str) -> str:
    h = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{key.replace('/', '_')}_{h}.pkl")

def _load_cache(key: str):
    path = _cache_path(key)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None

def _save_cache(key: str, value):
    path = _cache_path(key)
    with open(path, "wb") as f:
        pickle.dump(value, f)

def clear_cache():
    """Delete all cached files."""
    for fname in os.listdir(CACHE_DIR):
        os.remove(os.path.join(CACHE_DIR, fname))
    print("Cache cleared.")


# ── Sleeper API helpers ───────────────────────────────────────────────────────

def fetch_player_data() -> dict:
    key = "nfl_players"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json("https://api.sleeper.app/v1/players/nfl")
    _save_cache(key, data)
    return data

def fetch_league_json(league_id: int) -> dict:
    key = f"league_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(f"https://api.sleeper.app/v1/league/{league_id}")
    _save_cache(key, data)
    return data

def fetch_sleeper_gsis_crosswalk(year: int) -> dict:
    """Returns {sleeper_player_id: gsis_id} for all players with a known mapping.
    Built from nfl_data_py rosters which carry a sleeper_id column alongside
    the GSIS player_id used in the stats CSV. Cached per season year."""
    import nfl_data_py as nfl
    key = f"sleeper_gsis_xwalk_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    rosters = nfl.import_rosters([year])
    xwalk = (
        rosters[rosters['sleeper_id'].notna()]
        [['sleeper_id', 'player_id']]
        .drop_duplicates(subset=['sleeper_id'])
    )
    result = dict(zip(xwalk['sleeper_id'].astype(str), xwalk['player_id']))
    _save_cache(key, result)
    return result

def fetch_league_users_json(league_id: int) -> list:
    """League member users (display_name, user_id, metadata) for a given league."""
    key = f"league_users_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(f"https://api.sleeper.app/v1/league/{league_id}/users")
    _save_cache(key, data)
    return data

def fetch_state_json() -> dict:
    """Current NFL season state: week (leg), season_type, season year.
    Returns keys: season, season_type, leg, display_week, season_start_date.
    Not cached — always fetches fresh so leg reflects the actual current week."""
    return _get_json("https://api.sleeper.app/v1/state/nfl")


def fetch_winners_bracket(league_id: int) -> list:
    """Winners bracket matchup objects for the league's playoff."""
    key = f"winners_bracket_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(
        f"https://api.sleeper.app/v1/league/{league_id}/winners_bracket"
    )
    _save_cache(key, data)
    return data

def fetch_losers_bracket(league_id: int) -> list:
    """Losers (consolation) bracket matchup objects for the league's playoff."""
    key = f"losers_bracket_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(
        f"https://api.sleeper.app/v1/league/{league_id}/losers_bracket"
    )
    _save_cache(key, data)
    return data

def fetch_transactions_json(league_id: int, week: int) -> list:
    """All transactions (trades, waivers, FA pickups) for a given week."""
    key = f"transactions_{league_id}_{week}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(
        f"https://api.sleeper.app/v1/league/{league_id}/transactions/{week}"
    )
    _save_cache(key, data)
    return data

def fetch_traded_picks_json(league_id: int) -> list:
    """All traded draft picks in the league's history."""
    key = f"traded_picks_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(
        f"https://api.sleeper.app/v1/league/{league_id}/traded_picks"
    )
    _save_cache(key, data)
    return data

def fetch_survivor_rosters(league_id: int) -> list:
    """Survivor pool rosters (pick history + elimination metadata)."""
    key = f"survivor_rosters_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    _save_cache(key, data)
    return data

def fetch_survivor_users(league_id: int) -> list:
    """Survivor pool users (owner_id → display_name mapping)."""
    key = f"survivor_users_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(f"https://api.sleeper.app/v1/league/{league_id}/users")
    _save_cache(key, data)
    return data

def fetch_matchups_json(league_id: int, week: int) -> list:
    """Fetch raw Sleeper matchup JSON for a given week (cached to disk)."""
    key = f"matchups_{league_id}_{week}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(
        f"https://api.sleeper.app/v1/league/{league_id}/matchups/{week}"
    )
    _save_cache(key, data)
    return data

def fetch_nfl_schedule(year: int):
    """NFL regular-season schedule from nfl_data_py, disk-cached."""
    import pandas as pd
    import nfl_data_py as nfl
    key = f"nfl_schedule_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    sched = nfl.import_schedules([year])
    _save_cache(key, sched)
    return sched

def load_survivor_for_year(year: int):
    """Build and return a Survivor object for the given year, disk-cached."""
    import sleeper_core as core
    key = f"survivor_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    s = core.Survivor(year)
    _save_cache(key, s)
    return s


# ── High-level data loading ───────────────────────────────────────────────────

def load_data_for_year(year: int, max_week: int = 18, verbose: bool = True):
    """
    Load a full season (League + all Week objects + Season).
    Returns (league_obj, season_obj, weeks_dict) where weeks_dict = {week_num: Week}.
    Everything is disk-cached — only the first call hits the API.
    """
    import sleeper_core as core

    # Seed global NFL player lookup
    if not core.NFLPlayerData:
        if verbose:
            print("Loading NFL player data…")
        core.NFLPlayerData.update(fetch_player_data())

    league_id = core.leagueNumbers_Dict[year]
    cache_key = f"season_data_{year}_{max_week}"

    cached = _load_cache(cache_key)
    if cached is not None:
        if verbose:
            print(f"[cache] Loaded {year} from disk.")
        # Trim trailing weeks with no actual matchups (matchup_id=None for all entries).
        # Fixes caches built before this check existed (e.g. 2021–2024 with phantom week 18).
        for wk_num in sorted(cached["weeks"].keys(), reverse=True):
            wk = cached["weeks"][wk_num]
            if wk.json and all(m.get('matchup_id') is None for m in wk.json):
                del cached["weeks"][wk_num]
            else:
                break
        # Restore global dicts so Season methods work
        core.AllMatchesDict[year].update(cached["matches_snap"])
        core.AllBreakoutDict[year].update(cached["breakout_snap"])
        # OptimalScoresByYear is populated as a Week-construction side effect, so
        # unpickled caches leave it empty (blank playoff efficiency badges).
        # Each cached Week carries its OptimalScoresDF — restore from those.
        for wk_num, wk in cached["weeks"].items():
            opt_df = getattr(wk, "OptimalScoresDF", None)
            if opt_df is not None:
                core.OptimalScoresByYear.setdefault(year, {})[wk_num] = opt_df
        # Always refresh teamcolors so cached objects pick up current slot-based palette
        cached["season"].SetTeamColors()
        return cached["league"], cached["season"], cached["weeks"]

    if verbose:
        print(f"Fetching {year} from Sleeper API…")

    league_obj = core.League(year, league_id)

    weeks_dict = {}
    for w in range(1, max_week + 1):
        if verbose:
            print(f"  Week {w}/{max_week}…", end="\r")
        try:
            wk = core.Week(w, league_obj)
        except requests.RequestException as e:
            # A network blip would otherwise leave a silent hole in the season —
            # fail the whole year load so the caller can retry, not cache a lie.
            raise RuntimeError(
                f"Failed to fetch {year} week {w} from the Sleeper API: {e}"
            ) from e
        # Only keep weeks that have data (empty matchup JSON = season hasn't reached that week)
        if not wk.json:
            break
        # Skip weeks where every entry has matchup_id=None (Sleeper returns roster
        # score data for all NFL weeks even after the fantasy season ends)
        if all(m.get('matchup_id') is None for m in wk.json):
            break
        weeks_dict[w] = wk

    if verbose:
        print(f"\n  Building Season object…")

    season_obj = core.Season(league_obj)
    season_obj.Update()

    payload = {
        "league": league_obj,
        "weeks": weeks_dict,
        "season": season_obj,
        "matches_snap": {k: v.copy() for k, v in core.AllMatchesDict[year].items()},
        "breakout_snap": {k: v.copy() for k, v in core.AllBreakoutDict[year].items()},
    }
    _save_cache(cache_key, payload)
    if verbose:
        print(f"[cache] Saved {year} to disk.")

    return league_obj, season_obj, weeks_dict


def get_current_week(year: int) -> int:
    """Return the last scored week for the given season year."""
    import sleeper_core as core
    try:
        league_id = core.leagueNumbers_Dict[year]
        settings = fetch_league_json(league_id)
        return int(settings.get("settings", {}).get("last_scored_leg", 1) or 1)
    except Exception:
        return 1


def load_playoff_probs(year: int) -> dict | None:
    """
    Returns {as_of_week: list[TeamPlayoffSnapshot]} for weeks 9 through playoff_week_start-1.

    For completed seasons: computes all weeks once and caches each independently.
    For the current season: only computes weeks where data exists (≤ max completed week).
    Returns None if data is unavailable (year not loaded, season too early).
    """
    import sleeper_core as core

    try:
        league, season, weeks = load_data_for_year(year, verbose=False)
    except Exception:
        return None

    playoff_start = int(league.league_settings.get('settings.playoff_week_start', 15))
    max_completed = max(weeks.keys()) if weeks else 0

    result = {}
    for as_of_week in range(core.PlayoffCalculator.EARLY_WEEK_THRESHOLD, playoff_start):
        if as_of_week > max_completed:
            break

        week_key = f"playoff_probs_{year}_{as_of_week}"
        cached = _load_cache(week_key)
        if cached is not None:
            result[as_of_week] = cached
            continue

        try:
            calc = core.PlayoffCalculator(league, season, as_of_week)
            snapshots = calc.compute()
            _save_cache(week_key, snapshots)
            result[as_of_week] = snapshots
        except Exception:
            continue

    return result if result else None


def invalidate_week(year: int, week: int):
    """Remove season cache for `year` so it rebuilds from the Sleeper API on next load.
    Deleting the season pickle forces all weeks (including `week`) to be re-fetched."""
    import sleeper_core as core
    season_path = _cache_path(f"season_data_{year}_{18}")
    if os.path.exists(season_path):
        os.remove(season_path)
    print(f"Invalidated cache for {year} (will re-fetch all weeks including Week {week}).")
