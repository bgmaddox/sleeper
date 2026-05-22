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
    data = requests.get("https://api.sleeper.app/v1/players/nfl").json()
    _save_cache(key, data)
    return data

def fetch_league_json(league_id: int) -> dict:
    key = f"league_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = requests.get(f"https://api.sleeper.app/v1/league/{league_id}").json()
    _save_cache(key, data)
    return data

def fetch_state_json() -> dict:
    """Current NFL season state: week (leg), season_type, season year.
    Returns keys: season, season_type, leg, display_week, season_start_date."""
    key = "nfl_state"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = requests.get("https://api.sleeper.app/v1/state/nfl").json()
    _save_cache(key, data)
    return data


def fetch_winners_bracket(league_id: int) -> list:
    """Winners bracket matchup objects for the league's playoff."""
    key = f"winners_bracket_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = requests.get(
        f"https://api.sleeper.app/v1/league/{league_id}/winners_bracket"
    ).json()
    _save_cache(key, data)
    return data

def fetch_losers_bracket(league_id: int) -> list:
    """Losers (consolation) bracket matchup objects for the league's playoff."""
    key = f"losers_bracket_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = requests.get(
        f"https://api.sleeper.app/v1/league/{league_id}/losers_bracket"
    ).json()
    _save_cache(key, data)
    return data

def fetch_transactions_json(league_id: int, week: int) -> list:
    """All transactions (trades, waivers, FA pickups) for a given week."""
    key = f"transactions_{league_id}_{week}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = requests.get(
        f"https://api.sleeper.app/v1/league/{league_id}/transactions/{week}"
    ).json()
    _save_cache(key, data)
    return data

def fetch_traded_picks_json(league_id: int) -> list:
    """All traded draft picks in the league's history."""
    key = f"traded_picks_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = requests.get(
        f"https://api.sleeper.app/v1/league/{league_id}/traded_picks"
    ).json()
    _save_cache(key, data)
    return data


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
        # Restore global dicts so Season methods work
        core.AllMatchesDict[year].update(cached["matches_snap"])
        core.AllBreakoutDict[year].update(cached["breakout_snap"])
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
            # Only keep weeks that have data (empty matchup JSON = season hasn't reached that week)
            if not wk.json:
                break
            weeks_dict[w] = wk
        except Exception as e:
            if verbose:
                print(f"\n  Week {w}: skipped ({e})")
            continue

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


def invalidate_week(year: int, week: int):
    """Remove season cache for `year` so it rebuilds from the Sleeper API on next load.
    Deleting the season pickle forces all weeks (including `week`) to be re-fetched."""
    import sleeper_core as core
    season_path = _cache_path(f"season_data_{year}_{18}")
    if os.path.exists(season_path):
        os.remove(season_path)
    print(f"Invalidated cache for {year} (will re-fetch all weeks including Week {week}).")
