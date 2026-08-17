# data_loader.py
# Handles loading and disk-caching all Sleeper league data.
# First load hits the Sleeper API and nfl_data_py (slow).
# Subsequent loads read from .cache/ (fast).

import os
import json
import pickle
import hashlib
import tempfile
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
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except (EOFError, pickle.UnpicklingError, AttributeError, ImportError) as e:
        # A truncated or otherwise unreadable pickle must read as a cache miss,
        # not crash the caller. Drop it so the next call rebuilds cleanly.
        print(f"[cache] Discarding unreadable cache {os.path.basename(path)}: {e}")
        try:
            os.remove(path)
        except OSError:
            pass
        return None


def _save_cache(key: str, value):
    """Write atomically: pickle to a temp file in the same directory, then
    os.replace() it into place.

    Writing straight to the destination leaves a truncated file visible to any
    concurrent reader if two writers overlap or a write is interrupted — which
    is not hypothetical here. The app eagerly loads every season on boot, the Pi
    serves it under gunicorn with several threads, and a test run or a second
    process warming the same key will collide. os.replace is atomic on POSIX and
    Windows, so readers see either the old file or the new one, never a partial.
    """
    path = _cache_path(key)
    fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, prefix=".tmp-", suffix=".pkl")
    try:
        with os.fdopen(fd, "wb") as f:
            pickle.dump(value, f)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

def _name_fingerprint(year: int) -> str:
    """Short hash of the manager-name inputs baked into a cached season.

    Cached Week/Season objects carry manager names inside their dataframes. When
    config/roster_ids.json or config/aliases.json changes, those pickles go stale
    in a way nothing else detects: name lookups silently fall through to
    sentinels (blank colors, reg_season_rank=999) instead of raising. Folding the
    names into the cache key makes a rename self-invalidating.
    """
    import sleeper_core as core
    payload = json.dumps(
        [sorted(core.roster_ids.get(year, {}).items()),
         sorted(core.NAME_ALIASES.items())],
        sort_keys=True,
    )
    return hashlib.md5(payload.encode()).hexdigest()[:8]


def season_cache_key(year: int, max_week: int = 18) -> str:
    """The cache key for a season pickle. Single source of truth.

    load_data_for_year, invalidate_week, and the test fixtures all need this
    string to agree. When it was rebuilt by hand in each place, adding the name
    fingerprint broke the ↺ refresh button and every fixture at once.
    """
    return f"season_data_{year}_{max_week}_{_name_fingerprint(year)}"


def season_cache_path(year: int, max_week: int = 18) -> str:
    """Filesystem path for a season pickle. See season_cache_key."""
    return _cache_path(season_cache_key(year, max_week))


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

def fetch_pickem_rosters(league_id: int) -> list:
    """Pick 'Em pool rosters (weekly scores in points_by_leg metadata)."""
    key = f"pickem_rosters_{league_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    _save_cache(key, data)
    return data

def fetch_pickem_users(league_id: int) -> list:
    """Pick 'Em pool users (owner_id → display_name mapping)."""
    key = f"pickem_users_{league_id}"
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

def season_kickoff_ms(year: int):
    """Epoch milliseconds (UTC) of the first kickoff of `year`'s Week 1, or None.

    Drives the preseason countdown. Derived from the published NFL schedule
    rather than hardcoded, so it stays correct if the schedule shifts and needs
    no edit next season. nflverse publishes gameday/gametime in US Eastern.
    """
    import pandas as pd
    try:
        sched = fetch_nfl_schedule(year)
        wk1 = sched[sched['week'] == 1]
        if wk1.empty:
            return None
        stamps = pd.to_datetime(
            wk1['gameday'].astype(str) + ' ' + wk1['gametime'].astype(str),
            errors='coerce',
        ).dropna()
        if stamps.empty:
            return None
        first = stamps.min()
        # Localize to Eastern, then convert to UTC for a browser-safe epoch.
        if first.tzinfo is None:
            first = first.tz_localize('America/New_York')
        return int(first.tz_convert('UTC').timestamp() * 1000)
    except Exception:
        # A missing/renamed schedule column must not take down the tab.
        return None


def fetch_draft_json(draft_id) -> dict:
    """Sleeper draft object.

    Deliberately only cached once `start_time` is set. An unscheduled draft has
    `start_time: null`, and with no TTL on these pickles, caching that would pin
    the hero to "TBD" forever even after the draft was scheduled — the same trap
    as caching an unplayed season.
    """
    key = f"draft_{draft_id}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = _get_json(f"https://api.sleeper.app/v1/draft/{draft_id}")
    if data.get("start_time"):
        _save_cache(key, data)
    return data


def _override_draft_ms(year: int):
    """Manual draft date from config/season_dates.json, or None."""
    import pandas as pd
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "config", "season_dates.json")
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        raw = (cfg.get(str(year)) or {}).get("draft")
        if not raw:
            return None
        stamp = pd.Timestamp(raw)
        if stamp.tzinfo is None:                      # bare local time -> Eastern
            stamp = stamp.tz_localize("America/New_York")
        return int(stamp.tz_convert("UTC").timestamp() * 1000)
    except Exception:
        # A malformed override must not take the tab down; fall through to TBD.
        return None


def draft_start_ms(year: int):
    """Epoch milliseconds (UTC) of the draft, or None when it isn't scheduled.

    Sleeper wins when the commissioner has set a start time there, so scheduling
    the draft in Sleeper is all that's needed and no config edit is required.
    config/season_dates.json is the fallback for showing a date before then.
    """
    import sleeper_core as core
    try:
        league_id = core.leagueNumbers_Dict[year]
        settings = fetch_league_json(league_id)
        draft_id = settings.get("draft_id")
        if draft_id:
            start = fetch_draft_json(draft_id).get("start_time")
            if start:
                return int(start)
    except Exception:
        pass
    return _override_draft_ms(year)


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

def load_pickem_for_year(year: int):
    """Build and return a PickEm object for the given year, disk-cached."""
    import sleeper_core as core
    key = f"pickem_{year}"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    p = core.PickEm(year)
    _save_cache(key, p)
    return p


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
    cache_key = season_cache_key(year, max_week)

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
        # Inspect the raw matchup JSON *before* building the Week. Sleeper returns
        # roster stubs for a league that hasn't played yet (pre_draft/preseason),
        # and Week.PlayerBreakout() raises KeyError on those empty frames. This
        # fetch is cached, so testing first costs nothing.
        try:
            raw = fetch_matchups_json(league_id, w)
        except requests.RequestException as e:
            raise RuntimeError(
                f"Failed to fetch {year} week {w} from the Sleeper API: {e}"
            ) from e
        # No data at all = the season hasn't reached this week.
        if not raw:
            break
        # Every entry matchup_id=None: Sleeper keeps returning roster score data
        # for all NFL weeks after the fantasy season ends, and before it starts.
        if all(m.get('matchup_id') is None for m in raw):
            break

        try:
            wk = core.Week(w, league_obj)
        except requests.RequestException as e:
            # A network blip would otherwise leave a silent hole in the season —
            # fail the whole year load so the caller can retry, not cache a lie.
            raise RuntimeError(
                f"Failed to fetch {year} week {w} from the Sleeper API: {e}"
            ) from e
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
    # Never cache a season with no weeks. There is no TTL on these pickles, so a
    # preseason snapshot would freeze the year as permanently empty — the app
    # would keep serving "no data" for weeks after Week 1 was actually played,
    # until someone hit the ↺ refresh button.
    if weeks_dict:
        _save_cache(cache_key, payload)
        if verbose:
            print(f"[cache] Saved {year} to disk.")
    elif verbose:
        print(f"[cache] Skipped saving {year} — no weeks played yet (preseason).")

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

    A checkpoint at week W reflects all results through week W; later weeks are
    simulated as 50/50 even if since played (see PlayoffCalculator docstring),
    so retroactively computed checkpoints are genuine reconstructed odds.

    For completed seasons: computes all weeks once and caches each independently.
    For the current season: only computes weeks where data exists (≤ max completed week).
    Returns None if data is unavailable (year not loaded, season too early).
    Cache key is versioned (v2) — v1 snapshots predate the fold-in/simulate
    semantics and collapse to 0%/100% when computed retroactively.
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

        week_key = f"playoff_probs_v2_{year}_{as_of_week}_{_name_fingerprint(year)}"
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
    season_path = season_cache_path(year)
    if os.path.exists(season_path):
        os.remove(season_path)
    print(f"Invalidated cache for {year} (will re-fetch all weeks including Week {week}).")
