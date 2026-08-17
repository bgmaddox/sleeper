# Legacy League Webapp — Development Roadmap

**Created:** 2026-05-21  
**Last updated:** 2026-08-16  
**Status:** Active — Phases 1–4, 6–9 complete; historical side bets (2019–2024) complete.
Phase 11 (2026 season rollover) planned, not started. Task 3E is no longer blocked —
the 2026 league exists and its `previous_league_id` chain was verified.  
**Supersedes:** `design/fix-plan.md` (all tasks complete as of commit `41094a3`)

This document is the single source of truth for planned work. Update status inline as tasks complete.

---

## Session Summary (2026-05-21)

### Completed this session
- All Phase 1 tasks (1A–1G) — committed as `065de71`
- All Phase 2 tasks (2A–2D) — **not yet committed** (see below)
- Discovered and fixed a critical data bug in `PlayerBreakout` — **not yet committed**

### Pending commit
The following changes are staged but uncommitted:
- Phase 2 graph integrations (2A–2D in `sleeper_core.py` + `webapp/app.py`)
- `PlayerBreakout` position column bug fix (see Bug Fix Log below)
- `tests/test_charts.py` xfail marker removed from `test_position_strength_polar_renamed`

### Test suite status (as of 2026-05-21)
`pytest tests/ -m "not slow"` → **55 passed, 0 failed, 0 xfailed**

### Test suite status (as of 2026-05-24)
`pytest tests/ -m "not slow"` → **141 passed, 0 failed, 0 xfailed**

---

## Bug Fix Log

### BUG: PlayerBreakout — wrong `position` column used by all charts

**Discovered:** 2026-05-21 session  
**Fixed in:** `sleeper_core.py` — `PlayerBreakout()` (~line 630)  
**Symptoms:** DEF missing from all position charts (NaN instead of 'DEF'), phantom "CB" category in violin charts (Michael Thomas name collision), Season tab bottom charts failing intermittently, "All Rostered" violin missing half its position categories.

**Root cause:** Three sequential merges on `dfBreakout` produced a naming collision:
1. Build rows → `dfBreakout['position']` = Sleeper fantasy position (QB/WR/RB/TE/K/DEF) ✓
2. Merge with `self.league.Rosters` — Rosters also has a `position` column (NFL roster positions: DB/OL/DL/WR/LB etc.). With no `suffixes` specified, pandas renamed dfBreakout's column to `position_x` and Rosters' to `position_y`. The original Sleeper `position` was gone.
3. Merge with `WeeklyNFLData` using `suffixes=('','_NFL')` — nflverse stats has a `position` column (WR/RB/QB/TE/K, **no DEF** for team defenses). This landed as `position`, shadowing `position_x`. Result: all charts used the wrong column.

**Fix:**
```python
# Line 630 — add suffixes to Rosters merge to preserve the Sleeper position column
dfBreakout = dfBreakout.merge(self.league.Rosters, on='player_name', how='left', suffixes=('', '_roster'))

# After WeeklyNFLData merge — deduplicate rows from name collisions
# (e.g., WR Michael Thomas and CB Michael Thomas both match "Michael Thomas - 8")
dfBreakout = dfBreakout.drop_duplicates(subset=['team_x', 'player', 'week'])
```

**Column structure after fix:**
- `position` = Sleeper fantasy position (QB/WR/RB/TE/K/DEF) — **use this in charts**
- `position_roster` = nflverse roster position (DB/OL/DL/LB/etc.) — not for fantasy use
- `position_NFL` = nflverse weekly stats position (WR/RB/QB/TE/K, NaN for DEF) — for stats-side analysis only

**Cache impact:** 2024 and 2025 season caches were cleared and rebuilt. All other year caches (2019–2023) also have the old broken column structure and will produce wrong data if those charts are used. **Clear them before doing position-dependent work on historical years, or add a cache version check.**

**Verified:** `BreakoutSeason['position'].unique()` → `['QB', 'WR', 'RB', 'K', 'TE', 'DEF']`, 0 NaN rows, 0 CB rows. All 55 tests pass.

---

## Reading Guide

- Line numbers are approximate — always grep/read to confirm before editing.
- Run the app to verify after each phase:
  ```bash
  lsof -ti :8050 | xargs kill -9 2>/dev/null; sleep 1
  cd webapp && source ../.venv/bin/activate && python app.py
  ```
- `sleeper_core.py` and `data_loader.py` are at the project root; `app.py` is in `webapp/`.

---

## Phase 1 — Code Quality & Robustness ✅ COMPLETE (commit `065de71`)

Low-risk, no visual changes. Makes the codebase safer and future-proof before adding new features.

---

### Task 1A — Fix unsafe player name lookup (KeyError risk)

**File:** `sleeper_core.py` — `WeeklyDataframe()` (~line 661)

**Problem:** `starters_with_names = [self.league.player_names[player] for player in starters]`  
Direct dict indexing crashes if Sleeper returns an unknown player ID (new player, practice squad move mid-week, etc.). The whole week's data load fails on a `KeyError`.

**Fix:** Replace with `.get()` and a safe fallback:
```python
starters_with_names = [self.league.player_names.get(player, f"Unknown ({player})") for player in starters]
```
The fallback includes the ID so we can identify and investigate mystery players in logs.

**Verify:** App loads all seasons without error. If an unknown ID exists in historical data, it shows as "Unknown (ID)" rather than crashing.

---

### Task 1B — Fix SeasonMultiplier to not require annual updates

**File:** `sleeper_core.py` — `WeeklyDataframe()` (~line 703)

**Problem:**
```python
SeasonMultiplier = {2019:0, 2020:1, 2021:2, 2022:3, 2023:4, 2024:5, 2025:6}
WeeklyDf['Week Index'] = self.week + (14 * SeasonMultiplier[self.year])
```
This dict will `KeyError` the moment 2026 season data is loaded. It requires manual update every year.

**Fix:** Replace the dict lookup with arithmetic. The pattern is simply `year - 2019`:
```python
WeeklyDf['Week Index'] = self.week + (14 * (self.year - 2019))
```
Delete the `SeasonMultiplier` dict entirely — no more annual maintenance.

**Verify:** All-Time tab charts render correctly; week index values for each year should be unchanged.

---

### Task 1C — Replace hardcoded current-year checks with a constant

**File:** `sleeper_core.py` — top of file and three check sites

**Problem:** Three places check `if self.year != 2025` or `if self.year == 2025`. When 2026 season starts, these silently do the wrong thing (skips OptimalTeams for 2025, colors break, etc.).

**Locations to update:**
- Line 493: `if self.year != 2025: self.OptimalTeams()`
- Line 641: `if self.year != 2025: dfBreakout['color'] = dfBreakout['team'].map(self.teamcolors)`
- Line 816: (confirm exact condition with grep before editing)

**Fix:** Add a single constant near the top of the file (just below the imports section):
```python
CURRENT_SEASON = 2025   # Update this once per year when new season begins
```
Then replace all `!= 2025` / `== 2025` checks with `!= CURRENT_SEASON` / `== CURRENT_SEASON`.

**Note:** Before changing each check, read the surrounding code to confirm the intent is "skip for the in-progress season" (not some other year-specific rule). Document any exceptions inline.

**Verify:** App loads 2025 season with same behavior as before. Update `CURRENT_SEASON` to 2026 and confirm 2025 now behaves like a completed season.

---

### Task 1D — Remove dead stub methods from Week class

**File:** `sleeper_core.py` — `Week` class

**Problem:** Two methods are dead code:
- `ImportPlayerData()`: Duplicates `data_loader.fetch_player_data()`. Never called from outside the class after init was refactored.
- `ImportFixes()`: Empty stub — just `self.json` on a single line with no side effects.

**Fix:** Delete both method definitions entirely.

**Verify:** App loads without errors (confirming nothing called these).

---

### Task 1E — Add `fetch_state_json()` to data_loader

**File:** `data_loader.py`

**Purpose:** The Sleeper `/v1/state/nfl` endpoint returns the current NFL week, season type, and season year in a single lightweight call. This eliminates hardcoded or inferred "current week" logic everywhere in the app and handles the off-season state correctly.

**Response shape:**
```json
{ "season": "2025", "leg": 14, "season_type": "regular", "display_week": 15 }
```
- `leg` = actual current week number  
- `display_week` = may differ from `leg` (e.g., during bye weeks)
- `season_type`: `"pre"`, `"regular"`, `"post"`

**Fix:** Add to `data_loader.py` after the existing `fetch_league_json` function:
```python
def fetch_state_json() -> dict:
    """Current NFL season state — week, season type, season year."""
    key = "nfl_state"
    cached = _load_cache(key)
    if cached is not None:
        return cached
    data = requests.get("https://api.sleeper.app/v1/state/nfl").json()
    _save_cache(key, data)
    return data
```

**Note on cache TTL:** The existing cache has no expiry — a pickle written Monday stays fresh indefinitely. For state data that changes weekly, consider adding a timestamp check or just deleting the `nfl_state` cache key at session start. This is low priority for now; manual `invalidate_week` already busts the season cache when needed.

**Verify:** `data_loader.fetch_state_json()` returns a dict with `leg`, `season`, and `season_type` keys.

---

### Task 1F — Fix broken `invalidate_week` matchup cache path

**File:** `data_loader.py` — `invalidate_week()` (~line 142)

**Problem:** The function tries to delete a `matchup_{league_id}_{week}` cache file, but no such file is ever written (individual week matchup JSON is not separately cached — the whole season is one pickle). The `matchup_` delete is dead code and will silently do nothing.

**Fix:** Remove the dead matchup-level delete block. Keep only the season-level cache invalidation, which is what actually works:
```python
def invalidate_week(year: int, week: int):
    """Remove season cache for `year` so it rebuilds from the Sleeper API on next load."""
    import sleeper_core as core
    season_path = _cache_path(f"season_data_{year}_{18}")
    if os.path.exists(season_path):
        os.remove(season_path)
    print(f"Invalidated cache for {year} (will re-fetch all weeks including Week {week}).")
```

**Verify:** Calling `invalidate_week(2025, 14)` removes `season_data_2025_18.pkl`. The app reloads 2025 from the API on next startup.

---

### Task 1G — Fix TopScores color column case mismatch (Player mode crashes)

**File:** `sleeper_core.py` — `TopScores()` (~line 3272)

**Problem:** `px.bar(..., color='Team')` is hardcoded for all four branches. The Team branches (`TopTeamScores`, `BottomTeamScores`) come from `self.Matches` which has a capitalized `'Team'` column — correct. But the Player branches (`TopPlayerScores`, `BottomPlayerScores`) come from `self.Breakout` which has lowercase `'team'` — causing a `ValueError` crash every time the Player view is rendered.

**Confirmed by test:** `test_top_scores_player_top` is marked `xfail(strict=True)` and will flip to a pass once this is fixed.

**Root cause:** `self.Matches` uses `'Team'` (capitalized) while `self.Breakout` uses `'team'` (lowercase) — a schema inconsistency baked in at data-build time. A conditional color column is a patch; normalizing at the source is the right fix.

**Fix:** In `TopPlayerScoresProcessing()`, rename `'team'` → `'Team'` when building the player score dataframes so all four score dataframes share a consistent `'Team'` column before `TopScores` ever sees them. `TopScores` then uses `color='Team'` unconditionally — no branching needed:

```python
# In TopPlayerScoresProcessing, after building TopPlayerScores:
self.TopPlayerScores = self.TopPlayerScores.rename(columns={'team': 'Team'})
self.BottomPlayerScores = self.BottomPlayerScores.rename(columns={'team': 'Team'})
```

`TopScores` itself needs no changes — `color='Team'` already works for Team branches and will now work for Player branches too.

**Verify:** `TopScores(Top_Bottom='Top', Team_Player='Player')` returns a valid figure. The `xfail` test flips to `XPASS` and should be promoted to a normal passing test. Confirm `TopScores('Bottom', 'Team')` still works too.

---

## Phase 2 — Graph Integration (Orphaned Methods) ✅ COMPLETE (pending commit)

Adds three existing-but-unwired chart methods to the UI, cleans up two redundant ones.

---

### Task 2A — Delete redundant Season methods ✅ DONE

**File:** `sleeper_core.py`

`WholeSeasonBarGraph()` and `WeekYTDTotalsPercents()` deleted. No remaining references.

---

### Task 2B — Add StarterPerformanceGraph to Season tab ✅ DONE

**Files changed:** `webapp/app.py` — `_tab_season()`

Added after PositionStrengthHeatmap block. Uses `fig.update_layout(title=None, width=None, height=1200, margin=dict(t=20, b=80, l=160, r=40))` — margins applied directly (not via `_strip()`) to avoid clipping the tall horizontal bar chart. No `sleeper_core.py` changes needed; method was already complete.

---

### Task 2C — Rename PositionStengthPolar → PositionStrengthPolar and add to Season tab ✅ DONE

**Files changed:** `sleeper_core.py` (method rename only), `webapp/app.py` — `_tab_season()`

- Method renamed in `sleeper_core.py`. Internal variable typos (`PosistionAvg`, `PosistionPolar`, etc.) are local-only and left as-is — harmless.
- Added after StarterPerformanceGraph block with `height=1400`. No `_strip()` — layout applied directly.
- `test_position_strength_polar_renamed` in `tests/test_charts.py` promoted from `@pytest.mark.xfail` to a normal passing test.

---

### Task 2D — Extend violin toggle to 4-way (by-team + by-position) ✅ DONE

**File changed:** `webapp/app.py` — `_tab_players()` toggle UI and `_update_violin` callback

Toggle values: `starters` / `all` → call `sf.ViolinPlayer(week, Starters=...)` at height 1000  
New values: `pos_starters` / `pos_all` → call `sf.ViolinPosition(Starters=...)` at height 1200  
Subtitle updated to mention the by-position option. Callback branches on `mode in ('starters', 'all')` vs else.

---

## Phase 3 — API & Data Robustness (deferred — see Phase 6 for next active work)

Deeper improvements to data quality, matching, and future-proofing.

**⚠️ Before starting Phase 3:** The 2019–2023 season caches still have the old broken `position` column structure (position=NaN for DEF, `position_x`/`position_y` naming). They were not cleared when the PlayerBreakout bug was fixed. Any Phase 3 work that touches position-dependent data in historical seasons should clear those caches first:
```bash
rm .cache/season_data_2019_*.pkl .cache/season_data_2020_*.pkl .cache/season_data_2021_*.pkl .cache/season_data_2022_*.pkl .cache/season_data_2023_*.pkl
```
The All-Time tab aggregates all years — if it's broken on historical position data, this is why.

---

### Task 3A — Carry player_id through dfBreakout ✅ DONE

**File:** `sleeper_core.py` — `PlayerBreakout()` and `WeeklyDataframe()`

**Background:** Sleeper matchup data uses `player_id` as the primary key. The current code converts IDs to names immediately and discards the ID. Keeping `player_id` as a column in `dfBreakout` enables:
- Same-name player disambiguation (e.g., two "Michael Thomas" players in the same league era)
- Future crosswalk to other data sources
- Debugging name-match failures silently swallowed by left joins

**Fix:** In `PlayerBreakout()`, when iterating over the matchup JSON to build `dfBreakout`, add `player_id` as a column alongside `player_name`. Requires reading the actual code carefully before editing — the exact row-building logic determines where to insert this.

**Constraint:** Do not change the `player_week_id` join key (still name-based — see Phase 3B for why).

**Verify:** `dfBreakout` columns include `player_id`. Existing chart output is unchanged.

---

### Task 3B — Document name-matching fragility ✅ DONE

**Background:** The nflverse stats CSV (`stats_player_week_2025.csv`) uses GSIS player IDs — a different system than Sleeper's own IDs. No direct ID-based crosswalk exists. The current name-based join (`player_week_id = player_display_name + ' - ' + week`) is the only practical approach without a separate crosswalk table.

**Known fragile cases:**
- Name suffix handling: `Jr.`, `Sr.`, `II`, `III` — mostly handled by existing regex strip, but inconsistently applied across both sides of the join
- Punctuation differences: "D.K. Metcalf" (Sleeper) vs "DK Metcalf" (nflverse)
- DST teams: handled via special-case abbreviation mapping, but relocated/renamed franchises are a risk
- Mid-season player additions not yet in the local NFLPlayerData cache

**Action:** Create `design/name_matching_audit.md` cataloging actual mismatches found in `dfBreakout` (rows where NFL stat columns are null despite the player having a real game). Run a quick diagnostic: `dfBreakout[dfBreakout['passing_yards'].isna() & dfBreakout['starter'] == 1]` to surface starters with no matched stats.

**Future fix direction:** If nfl_data_py's `import_rosters()` includes `espn_id`, and Sleeper's player endpoint includes `espn_id`, a crosswalk becomes possible. This would make the join ID-based and eliminate name fragility entirely.

---

### Task 3C — Use fetch_state_json() to auto-detect current week in app ✅ DONE

**File:** `webapp/app.py`

**Depends on:** Task 1E (adding `fetch_state_json()` to data_loader)

**Problem:** The app currently uses a hardcoded or heuristic approach to determine the default week selection in the sidebar. The `/v1/state/nfl` endpoint gives us the exact current `leg` (week) and `season_type` reliably.

**Fix:** On app startup (in the boot callback or data initialization), call `data_loader.fetch_state_json()` and store `leg` and `season_type` for use in:
- Setting the default week dropdown value
- Disabling the week selector during off-season
- Showing an "off-season" message when `season_type == "pre"`

**Verify:** On startup, the week selector defaults to the actual current NFL week. During off-season, behavior is graceful.

---

### Task 3D — Add transaction data fetching to data_loader ✅ DONE

**File:** `data_loader.py`

**Purpose:** The `/v1/league/<league_id>/transactions/<round>` endpoint returns all trades, waiver pickups, and free agent signings per week. Adding a cached fetcher now makes this data available for future features (SideBet waiver analysis, trade history charts) without requiring a full refactor later.

**Fix:** Add two functions:
```python
def fetch_transactions_json(league_id: int, week: int) -> list:
    """All transactions (trades, waivers, FA) for a given week."""
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
```

Do not wire these into any existing data loading flow yet — they are for future use.

**Verify:** Both functions return valid list data when called manually.

---

### Task 3E — Auto-discover historical league IDs via previous_league_id

**File:** `sleeper_core.py` — `leagueNumbers_Dict`

**Background:** Every Sleeper league object includes a `previous_league_id` field that chains to the prior season's league. The current code hardcodes all 7 season IDs in `leagueNumbers_Dict`.

**Current:**
```python
leagueNumbers_Dict = {2019: ..., 2020: ..., ..., 2025: ...}
```

**Future fix:** On first run for a new season, if `year + 1` is missing from the dict, follow `previous_league_id` backwards from the known 2025 league ID to rebuild the chain. This eliminates the annual maintenance step of adding a new league ID.

**Implementation note:** This requires `data_loader.fetch_league_json()` to already be in place (it is). The chain traversal runs once and gets cached. Adds resilience when a new season starts.

**Defer until:** 2026 season is created on Sleeper (no urgency now).

---

## Phase 4 — Playoffs Tab ✅ COMPLETE

**Goal:** New "Playoffs" tab with matchup cards for winners and losers brackets, plus analytics charts for the winners bracket.

**Layout:**
- Year driven by the global sidebar year selector (no separate control)
- Top half: two-column bracket cards — Winners (left, full treatment) / Losers (right, scores only)
- Bottom half: analytics charts (winners bracket only)

**Bracket data shape (verified against 2025 league):**
```json
{ "r": 1, "m": 1, "t1": 4, "t2": 5, "w": 5, "l": 4 }
{ "r": 2, "m": 3, "t1": 10, "t2": 5, "t2_from": {"w": 1}, "w": 10, "l": 5 }
{ "r": 3, "m": 6, "p": 1, "t1": 10, "t2": 9, "w": 9, "l": 10 }
```
- `r`: round (1=wild card, 2=semis, 3=championship week)
- `m`: match ID used by `t1_from`/`t2_from` references
- `p`: placement (1=champion, 3=3rd place, 5=5th place) — only on placement games
- `t1`/`t2`: roster IDs (direct) or resolved from `t1_from`/`t2_from` refs
- `w`/`l`: winner/loser roster IDs (null only for current in-progress year)

**Match count for 6-team format:**
- R1: 2 matches (wild card)
- R2: 3 matches (2 semis + 5th place game)
- R3: 2 matches (championship + 3rd place game)
- Same structure mirrors in losers bracket

**Playoff weeks:** derived from `league_json['settings']['playoff_week_start']` (currently 15) — not hardcoded.

---

### Task 4A — Add bracket fetchers to data_loader ✅ DONE

Added `fetch_winners_bracket(league_id)` and `fetch_losers_bracket(league_id)`.

---

### Task 4B — Playoff processing in sleeper_core.py ✅ DONE

`Playoffs` class added to `sleeper_core.py`. Reads `playoff_week_start` from league settings, resolves `t1_from`/`t2_from` refs, maps roster IDs → team names, joins scores from `AllMatchesDict`, joins best player and bench points from `AllBreakoutDict`.

---

### Task 4C — Winners bracket cards ✅ DONE

Two-column bracket layout in `_tab_playoffs()`. Winners bracket (left): team names/scores, winner highlighted, round labels, best player, bench points left, lineup efficiency bar, score differential bar. SVG icons (star = best player, trophy = champion) via CSS mask-image technique.

---

### Task 4D — Losers bracket cards ✅ DONE

Right column: team names, scores, winner highlighted, round label. No best player or bench detail.

---

### Task 4E — Analytics charts ✅ DONE

Three charts below bracket cards (winners bracket only):
1. **Champion's Road** — horizontal bar, champion vs. opponent score by round
2. **Playoff Heat Check** — last 3 regular season weeks avg vs. playoff avg, grouped bar
3. **Bench Points Left** — horizontal bar, bench points stranded per team per game

**Additional work beyond original spec (all committed in `7373411` and earlier):**
- Dynamic week scrubber: week buttons derived from actual league data; visual separator between regular season and playoff weeks; orphaned phantom weeks (Sleeper returns matchup_id=None entries after season ends) trimmed in both fresh loads and cached data in `data_loader.py`
- Team chip filter: fixed three initialization points (dcc.Dropdown value, `_boot` callback, `_year_changed` callback) to use `None` (all teams active / unfiltered) instead of `[]`; established consistent `None` = pass-through vs. `[]` = empty result paradigm in `_filter_season`
- Playoff bracket UI polish: horizontal matchup card layout, proportional score bar with centerline tick, card height standardization, y-axis label clipping fixes across all three analytics charts, abbreviated round names for BenchPointsLeft

---

## This Week Tab — Power Rankings Enhancements ✅ COMPLETE (commits `eaccab8`, `7373411`)

Work completed 2026-05-23. Changes in `webapp/app.py`, `webapp/assets/style.css`, and new `webapp/assets/tablesort.js`.

### Standings Rank column
Added a `Rank` column (leftmost) showing each team's actual league standings position — sorted by wins descending, then season points-for as tiebreaker. Gold/silver/bronze medal colors for top 3. The existing `#` column was relabeled `Pwr` (power rank) and rendered in smaller muted text to signal it's the derived/secondary metric.

### Sortable column headers
All columns except the change indicator (↑/↓) and Streak now have click-to-sort behavior:
- Headers show stacked CSS border-triangle icons (▲▼) in `var(--border)` muted color; the active sort direction highlights in `var(--text-main)` blue
- Each `<td>` carries a `data-val` attribute with its raw numeric (or string) sort value
- `webapp/assets/tablesort.js` — new file; uses `MutationObserver` to re-attach click handlers after each Dash re-render so sorting survives year/week changes without any Dash callbacks
- String sort supported via `data-sort-type="str"` on the Team column

---

## Phase 5 — SideBet Feature

*Superseded by Phase 7, which replaces the original Phase 5 scope. Phase 7 focuses on the weekly side bet game and a dedicated tab; FAAB/trade analytics remain as backlog items below.*

---

## Phase 6 — All-Time Playoff Analytics ✅ COMPLETE (commits `fb08678`, `7cec76d`)

**Goal:** Add five playoff-specific charts aggregating bracket and score data across all seasons (2019–2025).

**Final placement:** Charts moved to the Playoffs tab (bottom section) after initial build placed them on All-Time tab. `7cec76d` also fixed half-width chart layout CSS.

**Data dependency:** Each year's bracket data is already fetchable via `data_loader.fetch_winners_bracket(league_id)` and `fetch_losers_bracket(league_id)` (Task 4A). Playoff week scores are in `AllMatchesDict[year][week]` for playoff weeks. The `Playoffs` class (Phase 4B) handles a single year — Phase 6 needs a multi-year aggregation layer.

---

### Task 6A — AllTimePlayoffs aggregator in sleeper_core.py ✅ DONE

**File:** `sleeper_core.py` — new method(s) on or alongside `AllTime`

This is the data foundation all five charts depend on. Build a function (or `AllTime` method) that iterates over all available years and produces two flat dataframes:

**`playoff_results` dataframe** — one row per team per playoff appearance:
```
year | team | reg_season_rank | playoff_seed | round_exit | placement | wins | losses | scores_by_round
```
- `reg_season_rank`: standings rank at end of regular season (wins then PF — same logic as the power rankings table Rank column)
- `playoff_seed`: position in bracket (1–6 for 6-team format)
- `round_exit`: last round played (1=wild card, 2=semis, 3=finals)
- `placement`: final finish (1=champion, 2=runner-up, 3=3rd, etc.)
- `scores_by_round`: list of scores per round played

**`playoff_games` dataframe** — one row per team per playoff game:
```
year | week | round | match | team | score | opponent | opp_score | won | placement_game | bracket
```
- `bracket`: "winners" or "losers"
- `placement_game`: True if this was a 3rd/5th place game

**Implementation notes:**
- Use `roster_ids[year]` to map roster numbers → team names
- Resolve `t1_from`/`t2_from` references same way the existing `Playoffs` class does
- Scores come from `AllMatchesDict[year][week]` — match teams by `matchup_id` within each playoff week
- Teams that didn't make the playoffs in a given year simply have no row for that year
- Handle years where bracket data may be incomplete (e.g., in-progress season) gracefully with a try/except and skip

**Verify:** `playoff_results` has one row per team per year they made playoffs. `playoff_games` has two rows per game (one per team). Cross-check: total games in `playoff_games` for a 6-team bracket = 7 winners + 7 losers = 14 per year.

---

### Task 6B — Chart 1: Playoff Appearances Leaderboard ✅ DONE

**Type:** Horizontal grouped bar chart  
**Data source:** `playoff_results` — group by `team`, count appearances / semifinal appearances (round_exit >= 2) / championship appearances (round_exit == 3) / wins (placement == 1)  
**File:** `sleeper_core.py` — new chart method; `webapp/app.py` — add to `_tab_alltime()`

**Design:**
- Y axis: manager names, sorted by total appearances descending
- X axis: count (0–7 max, one per season)
- Four bars per manager: appearances (muted), semifinals (medium), finals appearances (bright), championships (gold `#FFC300`)
- Legend below chart
- Title: "Playoff Pedigree"

**Edge cases:** Managers who've never made the playoffs don't appear. If the same person has used different display names across years (unlikely but possible), they'll show as separate entries — acceptable for now.

---

### Task 6C — Chart 2: Playoff Win Rate ✅ DONE

**Type:** Horizontal bar chart  
**Data source:** `playoff_games` — for each team, `wins / (wins + losses)` in non-placement games (placement games skew the stat since both teams "lost" to get there)  
**File:** `sleeper_core.py` — new chart method; `webapp/app.py` — add to `_tab_alltime()`

**Design:**
- Y axis: manager names, sorted by win rate descending
- X axis: win rate (0–1, formatted as %)
- Bar annotated with raw record (e.g., "4-2") at end of bar
- Color: gradient or threshold-based (≥ 0.60 green, 0.40–0.59 yellow, < 0.40 red)
- Minimum 2 games played to appear (filters out managers with only 1 playoff game)
- Title: "Playoff Win Rate"
- Subtitle: "Winners and losers bracket, placement games excluded"

---

### Task 6D — Chart 3: Regular Season Rank vs. Playoff Finish ✅ DONE

**Type:** Scatter plot  
**Data source:** `playoff_results` — one dot per (year, team) pair  
**File:** `sleeper_core.py` — new chart method; `webapp/app.py` — add to `_tab_alltime()`

**Design:**
- X axis: regular season rank (1–12, inverted so 1 is on left — best seed on left)
- Y axis: playoff placement (1–6, inverted so 1 is at top — champion on top)
- Each dot colored by team (use `teamcolors`)
- Dot annotated with year (small font) or revealed on hover
- Reference diagonal line showing "finished where seeded" — deviations above it are upsets
- Title: "Does Seeding Matter?"
- Subtitle: "Regular season rank vs. playoff finish, all seasons"

**Note:** Only the 6 playoff participants per year appear. Regular season rank uses the same wins-then-PF tiebreaker as the power rankings Rank column.

---

### Task 6E — Chart 4: Playoff Records Card ✅ DONE

**Type:** Native HTML card (same pattern as existing All-Time records cards)  
**Data source:** `playoff_games`  
**File:** `webapp/app.py` — new `_playoff_records_card()` helper; add to `_tab_alltime()`

**Records to surface:**
| Stat | Description |
|------|-------------|
| Highest playoff score | Best single-game score in any playoff matchup |
| Lowest playoff score | Worst score in a playoff win (survived despite low score) |
| Biggest blowout | Largest margin of victory in a playoff game |
| Closest game | Smallest winning margin in a playoff game |
| Most playoff wins all-time | Manager with most total wins across all playoff appearances |
| Most championships | Manager with most titles (could tie with Chart 1 but shows prominently here) |

**Design:** Matches the existing `_digest` / league digest card aesthetic — grid of stat pills, monospace font, team color accents on the team names.

---

### Task 6F — Chart 5: Championship Road Scores ✅ DONE

**Type:** Grouped bar chart  
**Data source:** `playoff_results` filtered to `placement == 1`; scores from `playoff_games`  
**File:** `sleeper_core.py` — new chart method; `webapp/app.py` — add to `_tab_alltime()`

**Design:**
- X axis: playoff round (Wild Card / Semis / Championship) — 3 groups
- Y axis: points scored
- One bar pair per year: champion score (colored by team) + opponent score (muted gray)
- Bars within each round grouped by year
- Champion's bar labeled with their name + year
- Title: "Path to Glory"
- Subtitle: "Champion scores by round, all seasons"

**Alternative if grouped bars get too crowded (7 years × 3 rounds):** Facet by round (3 small charts side by side), one bar per year within each facet. Decide after seeing how dense it looks.

---

### Layout in All-Time tab

Add a section header ("Playoff History") dividing the existing records cards from the new playoff charts. Order:

1. Playoff Records Card (6E) — top, full width, quick visual hit
2. Playoff Appearances Leaderboard (6B) — half width left
3. Playoff Win Rate (6C) — half width right
4. Regular Season Rank vs. Playoff Finish (6D) — full width
5. Championship Road Scores (6F) — full width, bottom

---

## Phase 7 — Side Bets Tab ✅ COMPLETE (commit `c9af1b3`)

Tasks 7A–7H all complete. Test suite: 141 passed, 0 xfailed.

**Goal:** Surface the weekly side bet game as a first-class feature — a dedicated "Side Bets" tab showing all week challenges with their charts and results, plus a "Side Bet of the Week" card on the existing This Week tab.

**What the side bet game is:** Each week has a unique challenge (e.g., "team with the most offensive TDs," "best DEF/K combo," "starter closest to 21 pts without going over"). The winner gets $20 from the prize pool. The player with the most weekly wins at the end of the year wins the Side Bet Championship.

**Current state of the `SideBet` class (`sleeper_core.py` ~line 4224):**
- Methods exist for Weeks 1–10, 12, 13 (Week11 and Week14 are missing entirely)
- The `Scoreboard()` method has the challenge definitions and season tally hardcoded as literal strings — this needs to move to a structured config
- **6 bugs** must be fixed before any method can be safely called from the webapp (see Task 7A)
- None of it is wired into `app.py` at all

---

### Task 7A — Fix `SideBet` class bugs and make all methods webapp-safe ✅ DONE

**File:** `sleeper_core.py` — `SideBet` class (~line 4224)

This is the prerequisite for everything else. Fix all methods to be callable from the Dash webapp without side effects.

**Bug 1 — `Week2` and `Week3` call `fig.show()` instead of returning**
Both methods display the figure to a notebook and return `None`. Change both to `return fig` (remove `fig.show()`).

**Bug 2 — `Week1` uses undefined globals**
`Week1` references a global `Week` variable (should be `WeekObj.week`) and `position_list` (a global list defined elsewhere in the notebook context but not in the webapp). Fix by using `WeekObj.week` for the title and replacing `position_list` with the actual column list derived from `WeekObj.WeeklyNoMatches` (drop non-position columns like `Total`, `Won`, `Week`, `Opp`, `Matchup`).

**Bug 3 — `Week10` hardcodes `roster_ids_2025`**
Line 5045: `person = roster_ids_2025[i]` — hard-coded to 2025. Replace with `self.League.roster_ids[self.League.year]` (same pattern used elsewhere in the codebase). Also fix the annotation on line 5077 for the same reason.

**Bug 4 — `Week12` wrong column name**
Line 5139: `cols = ['team','player','completions', 'attempts', 'recent_teams']` — `recent_teams` (plural) doesn't exist; the correct column is `recent_team`. Fix the column reference.

**Bug 5 — `Week5Graph` is dead duplicate code**
`Week5Graph` (line 4788) is a leftover notebook prototype that duplicates `Week1`'s logic, references undefined globals, and calls `fig.show()`. Delete the entire method.

**Bug 6 — `gridiron_ink` template missing from several methods**
`Week1`, `Week6`, `Week9` use default Plotly styling instead of `template='gridiron_ink'`. Add `template='gridiron_ink'` to their `px.bar()` / `go.Figure()` calls to match the app's visual theme. Also remove the hardcoded non-theme colors in `Week5` (`xaxis title color='red'`, `yaxis title color='green'`).

**Verify:** Each `WeekN()` method returns a Plotly figure object. No method calls `fig.show()`. Calling `SideBet(league, season).Week5(week_obj)` from a Python shell returns a figure with no exceptions.


---

### Task 7B — Move side bet config out of `Scoreboard()` into a structured dict ✅ DONE

**File:** `sleeper_core.py` — new module-level constant `SIDE_BET_SEASONS`

**Problem:** The challenge definitions (names, descriptions, winners) are hardcoded strings inside `Scoreboard()`. This makes them impossible to access by week number or year, and requires editing method internals to update each season.

**Fix:** Define a `SIDE_BET_SEASONS` dict near the top of `sleeper_core.py` (alongside `leagueNumbers_Dict` and `roster_ids`). Structure:

```python
SIDE_BET_SEASONS = {
    2025: {
        1:  {"name": "I'm Flying, Jack!",         "desc": "Team with the highest score (starters only)",                                                  "winner": "cosmodromedary"},
        2:  {"name": "Look At These TDs",          "desc": "Team with the most offensive touchdowns scored",                                               "winner": "DirtyCommie"},
        3:  {"name": "Big Helpers, Too",           "desc": "Most combined points with starting D/ST & Kicker",                                            "winner": "jhuntmadd"},
        4:  {"name": "Blackjack",                  "desc": "Team with a starter closest to 21 points without going over",                                 "winner": "sgmaddox & jhuntmadd"},
        5:  {"name": "The Replacements",           "desc": "Team with the highest total points for their bench",                                           "winner": "DirtyCommie"},
        6:  {"name": "The Boom & Bust",            "desc": "Largest point differential between single highest and lowest-scoring starter",                 "winner": "eegrady"},
        7:  {"name": "Campus Rush Week",           "desc": "Highest total rush yards for team (active or bench)",                                          "winner": "bgmaddox"},
        8:  {"name": "All Hands on Deck",          "desc": "Team with the most starting players who score over 15 points",                                 "winner": "bgmaddox"},
        9:  {"name": "The Old Man & Young Buck",   "desc": "Best combined score from a starting player over 30 and a rookie",                             "winner": "JTizzzzle"},
        10: {"name": "NFL Franchise Week",         "desc": "Team with highest point total of players from the same NFL franchise (active or bench)",       "winner": "DirtyCommie"},
        11: {"name": "Please Not the Jets",        "desc": "Trade Deadline Week — team with the most trades this season wins",                             "winner": "jhuntmadd & BMoreBallers88"},
        12: {"name": "Go Long",                    "desc": "Starting QB with the highest completion % (over 10 throws)",                                   "winner": "bgmaddox"},
        13: {"name": "Coffee's For Closers",       "desc": "Team that beats its opponent by the smallest margin of victory",                               "winner": ""},
        14: {"name": "Breaking of the Tie",        "desc": "If needed — choose 3 non-QB players; highest combined total wins",                            "winner": ""},
    }
}
```

Add a helper method to `SideBet`:
```python
def get_week_config(self, week: int) -> dict:
    """Returns {"name": ..., "desc": ..., "winner": ...} for the given week, or empty defaults."""
    return SIDE_BET_SEASONS.get(self.League.year, {}).get(week, {"name": f"Week {week}", "desc": "", "winner": ""})
```

Update `Scoreboard()` to derive its table and tally from `SIDE_BET_SEASONS[year]` instead of hardcoded lists.

**Historical data note:** Only 2025 data is in `SIDE_BET_SEASONS` at launch. Back-filling prior years (2019–2024) is a future update once that data is gathered — add each year as a new key when ready. The tab gracefully handles missing years (see Task 7G).

**Verify:** `SideBet(league, season).get_week_config(5)` returns the correct dict for Week 5. `Scoreboard()` produces the same visual output as before using the new config source.

---

### Task 7C — Add Week11 chart method (transaction data) ✅ DONE

**File:** `sleeper_core.py` — `SideBet.Week11()`

**Challenge:** "Please Not the Jets" — team with the most trades this season wins.

**Data source:** Transaction data from `data_loader.fetch_transactions_json()` (already implemented in Phase 3D). Trades have `"type": "trade"` and `"status": "complete"`.

**Method logic:**
1. Fetch transactions for all weeks 1–11 for the current league year using `fetch_transactions_json(league_id, week)` — the league_id is `self.League.league_id`
2. Filter to `type == "trade"` and `status == "complete"`
3. Count trades per roster_id (each trade JSON has a `roster_ids` list) — map roster IDs to team names via `self.League.roster_ids[year]`
4. Return a horizontal bar chart (Plotly, `template='gridiron_ink'`) showing trade count per team, sorted descending, with the winner highlighted

**Winner determination:** The app's computed trade count is the authoritative result — no manual override field. Because of this, data quality matters: before marking a winner, verify that the transaction fetch returns complete data for all 12 teams and all weeks 1–11 (check for any `None` or empty responses). Add a data completeness check in the method — if any week returns an error response, log a warning and surface it in the chart subtitle rather than silently producing a wrong result.

**Note:** If `fetch_transactions_json` returns empty or errors for a week (no transactions that week), handle gracefully — just treat as 0 trades for that week.

**Verify:** `Week11(week_obj)` returns a figure. Trade counts match what's actually in the league.

---

### Task 7D — Add Week14 placeholder method ✅ DONE

**File:** `sleeper_core.py` — `SideBet.Week14()`

Week 14 is a manual tiebreaker — "choose 3 non-QB players; highest combined total wins." There's no programmatic winner determination. Add a method that returns a simple informational chart:
- A horizontal bar chart showing all starters' points for Week 14 (same data as Week 1's layout — total score per team, starters only), so the winner can be found visually
- Subtitle: "Tiebreaker — top combined score from 3 non-QB starters"

This gives the tab something to display for Week 14 without pretending there's an automated result.

---

### Task 7E — Wire SideBet into data loading ✅ DONE

**File:** `webapp/app.py` — data initialization block (~line 300) and helper functions

**Currently:** `_data[year]` stores `{'league': ..., 'season': ..., 'weeks': ...}`. `SideBet` is never instantiated.

**Fix:** After building `season` and `weeks`, instantiate `SideBet` and store it:
```python
from sleeper_core import SideBet
sb = SideBet(league, season, DictofWeeks=weeks)
_data[year]['sidebet'] = sb
```

Add a helper (alongside existing `_season()` and `_week()`):
```python
def _sidebet(year):
    d = _data.get(year)
    return d['sidebet'] if d and 'sidebet' in d else None
```

**Verify:** After app startup, `_sidebet(2025)` returns a `SideBet` instance. No existing tabs are affected.

---

### Task 7F — Add "Side Bet of the Week" card to This Week tab ✅ DONE

**File:** `webapp/app.py` — `_tab_week()`

Add a card at the bottom of the This Week tab showing the current week's side bet challenge. This is a lightweight addition — no new callbacks needed.

**Layout (native Dash HTML, no new chart initially):**
```
┌─────────────────────────────────────────────────────────┐
│  SIDE BET · WEEK 7                                      │
│  Campus Rush Week                                       │
│  Highest total rush yards for team (active or bench)    │
│                                                         │
│  [chart for that week's side bet]                       │
│                                                         │
│  Winner: bgmaddox                    [trophy icon]      │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**
1. Call `_sidebet(year)` — if None, show a loading placeholder
2. Get the week's config via `sb.get_week_config(week)`
3. Call the appropriate chart method (`sb.Week1(week_obj)`, `sb.Week2(week_obj)`, etc.) via a dispatch dict:
   ```python
   WEEK_METHODS = {1: 'Week1', 2: 'Week2', ..., 13: 'Week13', 14: 'Week14'}
   method_name = WEEK_METHODS.get(week)
   fig = getattr(sb, method_name)(week_obj) if method_name else None
   ```
4. Wrap in a `chart-card chart-col-full` div with the challenge name as the card title and the description as the subtitle
5. If a winner exists in the config, append a small winner badge below the chart using the existing SVG trophy icon pattern

**Edge case:** Week 11 `Week11()` needs transaction data which is fetched separately from `WeekObj`. Pass `week_obj` plus the league_id so the method can look up transactions internally (it already has `self.League.league_id`).

**Verify:** This Week tab for any week 1–13 shows a side bet card with the correct challenge and chart.

---

### Task 7G — New "Side Bets" tab ✅ DONE

**File:** `webapp/app.py` — add `tab-sidebets` to the tabs list and implement `_tab_sidebets()`

**Year selector behavior:** The Side Bets tab always displays 2025 data regardless of which year is selected in the sidebar — until historical configs are added to `SIDE_BET_SEASONS`. If the selected year has no config entry, show the 2025 data with a small banner: "Showing 2025 — historical data for [year] not yet available." Once prior-year configs are added, the tab becomes year-aware automatically (no code changes needed beyond the config dict).

**Tab header:** Add after "All-Time" and before "Head-to-Head":
```python
dcc.Tab(label='Side Bets', value='tab-sidebets', className='tab tab--sidebets', selected_className='tab--selected'),
```
Wire into the main tab callback: `if tab == 'tab-sidebets': return _tab_sidebets(year, week)`

**Tab layout — top to bottom:**

**Section 1: Championship Scoreboard (full width)**

A D3-rendered leaderboard showing each team's win tally and prize earnings for the season. This is the one place D3 adds clear value over Plotly — we want custom styling with inline prize amounts, medal colors, and animated bar transitions.

- Deliver the tally data as a Dash `dcc.Store` (JSON) and render via a new `d3charts.js` function `renderSideBetLeaderboard(storeId, containerId)`
- Each row: team name (colored) | win-count bar (gold fill, animated width) | wins label | prize total
- Sort descending by wins; top 3 get gold/silver/bronze accent colors
- If two teams are tied, show them at equal width

**Section 2: Week navigator (dedicated slider)**

A week scrubber row styled identically to the existing `week-scrubber` at the top of the app, but scoped to this tab. Clicking a week button scrolls the page to that week's card (via a `window.location.hash` or `scrollIntoView` approach in a small clientside callback — no server round-trip needed).

- Button labels: "W1" through "W14" (or actual week numbers matching `SIDE_BET_SEASONS`)
- Highlight the button for the currently selected year's last completed week
- The week with no winner yet gets a subtle "upcoming" style

**Section 3: Week cards (all weeks, in order)**

One card per week, rendered in a single pass (no lazy loading — 14 charts is acceptable, and users will want to scroll through them). Each card:

```
┌──────────────────────────────────────────────────────┐
│  WEEK 5  ·  The Replacements              [anchor id]│
│  Team with the highest total bench points            │
│                                                      │
│  [Plotly chart]                                      │
│                                                      │
│  Winner: DirtyCommie  🏆                             │
└──────────────────────────────────────────────────────┘
```

- Card has an `id=f'sidebet-week-{week}'` anchor for the scroll-to behavior
- Winner row uses the existing SVG trophy icon if a winner is set; shows "TBD" in muted text if empty
- Cards where no chart method exists yet (e.g., if a week is still in progress) show a placeholder message instead of erroring

**CSS additions needed (`style.css`):**
- `.sidebet-leaderboard` — container for the D3 leaderboard
- `.sidebet-week-nav` — the week button row (can reuse `week-scrubber` styles with minor tweaks)
- `.sidebet-winner-badge` — winner row styling (team color accent, trophy icon)
- `.sidebet-tbd` — muted "TBD" styling for incomplete weeks

**Verify:** Tab loads for 2025. All 13 available charts render. The week navigator scrolls to the correct card. The leaderboard shows accurate win counts and prize totals. Tab gracefully handles weeks with no chart method.

---

### Task 7H — Tests ✅ DONE

**File:** `tests/test_sidebet.py` (new file)

**Tests to write:**
- `test_sidebet_instantiation` — `SideBet(league, season, weeks)` creates successfully, `teamcolors` is populated
- `test_get_week_config` — returns correct dict for a known week; returns default for an unknown week
- `test_week_methods_return_figures` — parametrized over weeks 1–14 (skip Week11 if transactions not cached); each returns a Plotly `go.Figure`, not None
- `test_scoreboard_returns_figure` — `Scoreboard()` returns a figure without raising
- `test_no_fig_show_called` — (code inspection) grep `sleeper_core.py` for `fig.show()` inside the `SideBet` class block and assert count == 0

Use `pytest.skip` if week cache is missing (same pattern as existing tests). Mark Week11 and Week14 as `@pytest.mark.xfail(strict=True)` until those methods are implemented.

---

### Implementation order

1. **7A** (bug fixes) → **7B** (config) → **7E** (wire into data loading) — these three are sequential prerequisites
2. **7C** and **7D** (missing week methods) — can be done alongside 7B
3. **7H** (tests) — write alongside 7A/7B so bugs are caught before wiring up
4. **7F** (This Week card) — once 7A/7B/7E are done
5. **7G** (new tab) — last, builds on everything above

---

| Item | Notes |
|------|-------|
| Route `League.UsersJSONtoDF` through data_loader | ✅ Done — `SettingsJSONtoDF` and `UsersJSONtoDF` now use `fetch_league_json` / `fetch_league_users_json`. |
| Crosswalk Sleeper player IDs to GSIS IDs for ID-based stats join | ✅ Done — `nfl_data_py` rosters carry a `sleeper_id` column (no `espn_id` needed). `fetch_sleeper_gsis_crosswalk(year)` added to data_loader; `PlayerBreakout` now joins on GSIS ID + week instead of display name + week. 100% coverage for fantasy skill positions. |
| `previous_league_id` auto-discovery | No urgency until 2026 season is created. See Task 3E. |

---

## Historical Side Bets (2019–2024) ✅ COMPLETE (commit `0a87d03`)

Backfilled `SIDE_BET_SEASONS` with challenge names, descriptions, and winners for all 6 prior seasons. Parser script at `scripts/parse_sidebet_xlsx.py` documents the extraction process. Permanent pytest invariant `test_sidebet_winners_match_rosters` validates all 7 years. No app code changes were required — the Side Bets tab is year-config-driven.

**One post-migration fix:** 2019 weeks 3 and 11 used `RReclam` (parser output) but that person's 2019 Sleeper username was `GurlyGirls`; corrected in `sleeper_core.py`.

---

## Phase 8 — Playoff Probability Calculator ✅ COMPLETE

Added a **Playoff Calculator** card to the **This Week** tab (after Power Rankings). Shows each team's probability of making the playoffs, week-over-week probability trend, and games to root for. Algorithm uses NumPy bitmask enumeration over all remaining-schedule outcomes. `PlayoffCalculator` class lives in `sleeper_core.py`.

---

## Phase 9 — Survivor Tab ✅ COMPLETE

New **Survivor** tab surfacing the league's survivor pool pick history and elimination tracking. Data sourced from a separate Sleeper survivor league via `SURVIVOR_LEAGUE_IDS` (2024–2025). Fetchers added to `data_loader.py`; tab implemented in `webapp/app.py`.

---

## Phase 10 — Champion Badges

**Goal:** Display a personalized SVG champion badge at the top of three tabs — Playoffs (League Champion), Side Bets (Side Bet Champion), and Survivor (Survivor Champion) — for the currently selected year. The badge uses a custom-designed SVG template; Python reads and modifies the template at runtime to inject the correct year and winner's team name before embedding it in the Dash layout.

**Why this approach:** The badge is an Affinity Designer asset exported as SVG with real `<text>` elements (not path-converted). Python's `xml.etree.ElementTree` can parse it, find the right nodes, swap their text content, and re-serialize the SVG. The modified SVG is base64-encoded into a data URI for an `<img>` tag — no file writes at runtime, no static asset management, no Dash routing complexity.

**Prerequisite:** User provides the 2019 template SVG (`Legacy League Winners Badge.svg` or equivalent). Save it to `webapp/assets/badges/champion_badge_template.svg`. This file is the single source of truth for all years and all three badge types — the template is champion-agnostic; only the year and team name `<text>` nodes change.

---

### Task 10A — Save the SVG template and confirm its text element structure

**Action:** Copy the provided 2019 badge SVG to `webapp/assets/badges/champion_badge_template.svg`.

Then confirm the SVG has the expected four `<text>` elements by running:
```bash
grep "<text" webapp/assets/badges/champion_badge_template.svg
```

**Expected structure (four `<text>` elements total):**
1. `"C"` — oversized decorative first letter of CHAMPION; do not touch
2. `"HAMPION"` — rest of the word CHAMPION; do not touch
3. Year — a 4-digit number (e.g., `"2019"`); this is the year field
4. Team name — the remaining element (not "C", not "HAMPION", not 4 digits); this is the winner field

**Identification logic an agent must use:**
- Year element: `<text>` whose text content matches `^\d{4}$` (exactly 4 digits, nothing else)
- Team name element: `<text>` whose text content does NOT match `^\d{4}$` AND is not `"C"` AND does not contain `"AMPION"` (case-insensitive guard for both "HAMPION" and "CHAMPION" variants)
- "C" and "HAMPION" elements are identified by exact content match — they must never be modified

If the grep output shows a different structure (e.g., CHAMPION is a single `<text>` element, or team name is in a `<tspan>` child), adjust the parsing logic in Task 10B accordingly before writing any code. The structural check here must happen first.

**Verify:** Four `<text>` elements present. Year and team name elements are unambiguously identifiable.

---

### Task 10B — Write `_render_badge(year, team_name)` helper in `webapp/app.py`

**File:** `webapp/app.py` — add near the top of the file alongside other helper functions (after imports, before tab functions)

**What this function does:**
1. Reads `webapp/assets/badges/champion_badge_template.svg` once (consider module-level caching — read the file once at import time and store in a module variable `_BADGE_SVG_RAW`, so repeated tab renders don't re-read from disk)
2. Parses the SVG with `xml.etree.ElementTree` — SVG uses the `http://www.w3.org/2000/svg` namespace, so all tag lookups must use the namespace prefix: `{http://www.w3.org/2000/svg}text`
3. Iterates over all `<text>` elements and applies the identification logic from Task 10A to find the year node and the team name node
4. Replaces `.text` on the year node with `str(year)` and `.text` on the team name node with `team_name`
5. Re-serializes the modified tree to a string with `ET.tostring(root, encoding='unicode')`
6. Base64-encodes it and returns an HTML `<img>` tag string as a `dash_html_components.Img` element:
   ```python
   import base64
   encoded = base64.b64encode(svg_string.encode('utf-8')).decode('utf-8')
   return html.Img(src=f"data:image/svg+xml;base64,{encoded}", className="champion-badge")
   ```

**Function signature:**
```python
def _render_badge(year: int, team_name: str) -> html.Img:
    """Returns a Dash Img element with the champion badge SVG modified for the given year and team."""
```

**Edge case — no champion yet:** If `team_name` is empty or None (e.g., the current in-progress season), return `None` so the caller can conditionally omit the badge from the layout. Do not render a badge with a blank or "TBD" team name — the badge is a celebration asset, not a placeholder.

**Note on ElementTree and SVG namespaces:** `ET.parse()` will register the SVG namespace automatically, but `ET.tostring()` may emit `ns0:` prefixes instead of the original `svg:` prefix if the namespace wasn't pre-registered. Fix this by calling `ET.register_namespace('', 'http://www.w3.org/2000/svg')` (and any other namespaces present in the file) before parsing. This preserves the original namespace prefixes and prevents the SVG from breaking in the browser.

**Verify:** `_render_badge(2025, "bgmaddox")` returns a `html.Img` element whose `src` attribute decodes to a valid SVG string containing `2025` and `bgmaddox` in the correct `<text>` nodes. Confirm "C" and "HAMPION" elements are unchanged.

---

### Task 10C — Add champion data lookups for each tab

Each tab needs to know who the champion was for the selected year before it can call `_render_badge`. The data already exists in the app — this task just documents where to find it.

**Playoffs champion** (`_tab_playoffs`):
- Source: `AllTimePlayoffs` data, specifically `playoff_results` dataframe already built during Phase 6
- Lookup: `playoff_results[(playoff_results['year'] == year) & (playoff_results['placement'] == 1)]['team'].iloc[0]`
- If the current season is in progress and `playoff_results` has no row with `placement == 1` for that year, return None (no badge)

**Side Bet champion** (`_tab_sidebets`):
- Source: `SIDE_BET_SEASONS[year]` dict (already in `sleeper_core.py`)
- Logic: Count wins per team across all weeks (a "win" is any week where `"winner"` is non-empty). The team with the most wins is the champion. If there is a tie at season end, show both names joined with " & " (this already exists as a pattern in the data — e.g., `"sgmaddox & jhuntmadd"`)
- If no year entry exists in `SIDE_BET_SEASONS`, return None
- Implement as a helper: `_sidebet_champion(year: int) -> str | None` — keeps the tab function clean

**Survivor champion** (`_tab_survivor`):
- Source: Survivor tab data loaded from `SURVIVOR_LEAGUE_IDS` — the last surviving team for the given year
- If survivor data for the year is unavailable or the pool is still in progress, return None

---

### Task 10D — Add badge to Playoffs tab

**File:** `webapp/app.py` — `_tab_playoffs(year)`

**Placement:** At the very top of the tab's returned layout, before the bracket cards. The badge should be visually prominent but not full-page-width.

**Layout:**
```
┌──────────────────────────────────────────────┐
│  [champion badge SVG — centered, ~300px tall] │
│         2025 LEAGUE CHAMPION                  │
└──────────────────────────────────────────────┘
[existing bracket cards below]
```

**Implementation:**
1. Look up the champion using the `playoff_results` approach from Task 10C
2. If champion is found, call `_render_badge(year, team_name)`; wrap the result in a `html.Div` with `className="champion-badge-container"`
3. If no champion (in-progress year or missing data), omit the container entirely — do not show an empty space or placeholder
4. Prepend the badge container to the existing layout list returned by `_tab_playoffs`

**CSS:** The badge container should center the image horizontally and constrain it so it doesn't overwhelm the page. Target `max-height: 320px; width: auto` on the `<img>` itself. The container adds `display: flex; justify-content: center; padding: 24px 0 16px 0`.

---

### Task 10E — Add badge to Side Bets tab

**File:** `webapp/app.py` — `_tab_sidebets(year)`

**Same pattern as Task 10D.** The Side Bet Champion is the team with the most weekly wins in the selected year. Use `_sidebet_champion(year)` from Task 10C.

**Placement:** Above the championship scoreboard (D3 leaderboard), so the badge appears as the hero element when the tab loads. The scoreboard directly below it reinforces the win-tally context.

**Constraint:** Only show the badge if the year is in `SIDE_BET_SEASONS` and at least one week has a winner recorded. A year with only empty `"winner"` fields (e.g., a future or in-progress season) gets no badge.

---

### Task 10F — Add badge to Survivor tab

**File:** `webapp/app.py` — `_tab_survivor(year)`

**Same pattern.** Survivor champion = last team standing. Look up from survivor data for the selected year.

**Placement:** Top of the tab, above the pick history grid/table.

**Constraint:** Only show for years where the survivor pool concluded (i.e., there is a single surviving team with all others eliminated). If the pool is still active, no badge.

---

### Task 10G — CSS additions

**File:** `webapp/assets/style.css`

Add the following classes:

```css
.champion-badge-container {
    display: flex;
    justify-content: center;
    padding: 24px 0 16px 0;
}

.champion-badge {
    max-height: 320px;
    width: auto;
    /* Prevent the SVG from stretching on wide viewports */
    max-width: 600px;
}
```

No other style changes needed — the SVG carries its own colors and typography from the original Affinity design.

---

### Task 10H — Tests

**File:** `tests/test_charts.py` or a new `tests/test_badges.py`

Tests to write:
- `test_render_badge_returns_img` — `_render_badge(2025, "bgmaddox")` returns a `dash.html.Img` object (not None)
- `test_render_badge_year_injected` — decode the `src` data URI and confirm the SVG string contains `"2025"` in a `<text>` element
- `test_render_badge_team_injected` — confirm `"bgmaddox"` appears in the decoded SVG
- `test_render_badge_champion_preserved` — confirm `"C"` and `"HAMPION"` (or `"CHAMPION"` if the template uses a single element) are unchanged
- `test_render_badge_none_on_empty_name` — `_render_badge(2025, "")` and `_render_badge(2025, None)` both return `None`
- `test_sidebet_champion_known_year` — `_sidebet_champion(2025)` returns a non-empty string for a year with complete data
- `test_sidebet_champion_missing_year` — `_sidebet_champion(1999)` returns `None` gracefully

---

### Implementation order

1. **10A** — Confirm SVG template structure before writing any code. If the structure differs from what's described here, update 10B's parsing logic before proceeding.
2. **10B** — Write and unit-test `_render_badge()` in isolation before wiring it into any tab.
3. **10C** — Identify and test the champion lookup logic for each tab type.
4. **10D / 10E / 10F / 10G** — Wire badge into each tab; can be done in parallel once 10B and 10C are solid.
5. **10H** — Tests should be written alongside 10B and 10C, not after.

**Do not proceed past 10A if the SVG structure check fails or is ambiguous.** An incorrect parse that silently corrupts the "C"/"HAMPION" elements will produce a broken badge that's hard to debug visually.

---

## Phase 11 — 2026 Season Rollover + Preseason Hero

**Created:** 2026-08-16
**Status:** 11A–11E and 11G complete. 11F: tests done, **deploy outstanding**.
Test suite: **295 passed, 1 skipped** (baseline before this work was 242 passed; the
one skip is pre-existing and unrelated). Nothing committed yet.
**Goal:** Make the app load the 2026 season (renewed, `pre_draft` as of this writing),
unify two managers who renamed themselves, and give the preseason a deliberate empty
state instead of blank charts.

### Verified facts (checked against the live Sleeper API, 2026-08-16)

| Fact | Value |
|---|---|
| 2026 league ID | `1386215157826347008` |
| `previous_league_id` | `1252049821154410496` (chains correctly to 2025) |
| Status / teams | `pre_draft`, 12 rosters |
| `roster_positions` | Unchanged from 2025 — `LINEUP_SLOTS` still validates |
| `playoff_week_start` | 15 (unchanged) |
| Draft | Created (`1386215157843124224`), `start_time: null` — not scheduled |
| Week 1 kickoff | NE @ SEA, **2026-09-09 20:20 ET** (from `nfl.import_schedules([2026])`) |
| Roster slots 1–12 | Identical membership to 2025 |
| Survivor / Pick 'Em 2026 | **Do not exist** — main league only |

**Two managers renamed themselves:** `jhuntmadd` → `jhmad`, `InfiniteJesse` → `InfiniteJess`.

### Decisions taken

- **Survivor / Pick 'Em:** not renewed yet. Leave 2026 out of `survivor_leagues` and
  `pickem_leagues`; both tabs already fall back to `max(...)` and will keep showing 2025.
- **Renames:** adopt the *new* display names as canonical and add an alias map, so
  history unifies under the current name everywhere. (The cheaper option — writing the
  old names into `roster_ids.json` for 2026 — was considered and rejected.)
- **Preseason hero:** animated countdown, auto-retiring when Week 1 data lands.

---

### Task 11A — Derive the per-year global dicts ✅ COMPLETE

**File:** `sleeper_core.py` — lines ~322–349

`Matches_2019 … Matches_2025`, `AllMatchesDict`, `AllBreakoutDict`,
`OptimalScoresByYear`, `AllMatchesList`, `AllSeasonsBreakoutList` are hand-enumerated
through 2025. `Week.__init__` indexes them bare — `AllMatchesDict[self.year]` (`:768`),
`AllBreakoutDict[self.year]` (`:652`), `OptimalScoresByYear[self.year]` (`:822`) — so
constructing a single 2026 `Week` raises `KeyError`.

**Fix:** derive all three from `AVAILABLE_YEARS`:
```python
AllMatchesDict      = {y: {} for y in AVAILABLE_YEARS}
AllBreakoutDict     = {y: {} for y in AVAILABLE_YEARS}
OptimalScoresByYear = {y: {} for y in AVAILABLE_YEARS}
AllMatchesList          = list(AllMatchesDict.values())
AllSeasonsBreakoutList  = list(AllBreakoutDict.values())
```
Delete the `Matches_YYYY` / `Breakout_Matches_YYYY` / `OptimalScoresYYYY` module-level
names. Same class of fix as Task 1B (`SeasonMultiplier`); this block was missed then.
Retires the annual edit permanently.

**Verify:** every year in `AVAILABLE_YEARS` loads; All-Time charts unchanged.

---

### Task 11B — Alias map for renamed managers ✅ COMPLETE

**New file:** `config/aliases.json` — variant → canonical (current display name):
```json
{ "jhuntmadd": "jhmad", "InfiniteJesse": "InfiniteJess" }
```

**New helper:** `sleeper_core.canonical_name(name)` — returns `ALIASES.get(name, name)`.
Loaded at import next to the other `config/*.json` reads.

Apply at every point a manager name enters the system. Known surfaces:
- `roster_ids` load (`:270`) — normalize **all** years, so 2019–2025 display as the new names
- `SIDE_BET_SEASONS` `winner` fields — 14 occurrences in `config/side_bet_seasons.json`
- `Survivor.user_map` (`:5244`) and `PickEm.user_map` (`:5730`) — live API `display_name`
- `League.OwnerIDDict` (`:415`) and `League.Teams` (`:457`)
- `special_hosts2` (`:3813`) — contains a literal `'jhuntmadd'`
- `tests/test_optimal.py:25` — fixture key `'jhuntmadd'`
- Colorway comments at `:69` / `:74` are cosmetic; update for accuracy

Team colors are slot-based and roster slots are unchanged, so palettes are unaffected.

**Verify:** grep for `jhuntmadd` and `InfiniteJesse` returns only `config/aliases.json`.
Head-to-Head shows 12 managers, not 14. All-Time win totals for the two renamed managers
equal the sum of their pre- and post-rename records.

---

### Task 11C — Config and constants ✅ COMPLETE

- `config/league_ids.json` → `"2026": 1386215157826347008` under `leagues` only
- `config/roster_ids.json` → 2026 block, slots 1–12, using the **new** display names
- `config/side_bet_seasons.json` → `"2026": {}` placeholder until challenges are chosen
- `sleeper_core.py:39` → `CURRENT_SEASON = 2026`
- `webapp/app.py:101` → `CURRENT_YEAR = 2026`
- `webapp/app.py:2102` → `else 2025` becomes `else max(core.SIDE_BET_SEASONS)`

`CURRENT_SEASON` and `CURRENT_YEAR` must move in the same commit — they gate
optimal-lineup computation (`:549`) and team coloring (`:649`) for the in-progress season.

**Optional, now unblocked:** Task 3E (`previous_league_id` auto-discovery). The chain was
verified to resolve. Would make next August a zero-edit rollover.

---

### Task 11D — Preseason empty state ✅ COMPLETE

**Load path: DONE.** The plan assumed the only breakage was an empty `weeks_dict`.
Verified against the live 2026 league, the preseason path actually broke in four
places, three of them earlier than expected. All four are fixed:

1. **`League.__init__` 404'd** (`sleeper_core.py:417`). nflverse only publishes
   `stats_player_week_{year}.csv` once a season has been played, so the League object
   could not even be constructed. Now `League._fetch_weekly_stats` falls back to an
   empty frame carrying the previous season's columns and warns. (`import_schedules`
   and `import_rosters` *do* have 2026 data — only the weekly stats CSV is missing.)
2. **`Week()` was constructed before the emptiness check** (`data_loader.py`). Sleeper
   returns roster stubs pre-draft, so `Week.PlayerBreakout()` raised
   `KeyError: 'team'`. The raw matchup JSON is now inspected via the (already cached)
   `fetch_matchups_json` *before* constructing a Week.
3. **`Season.Update()` raised on zero weeks** — `pd.concat([])` is a `ValueError`.
   `AllMatchesConcat` and `BreakoutConcat` now return empty-but-typed frames.
4. **Empty seasons are no longer cached.** There is no TTL on season pickles, so a
   preseason snapshot would have frozen 2026 as permanently empty.

**UI half: DONE.** Selecting 2026 used to show "Loading season data…" forever —
`_boot` polled until `_weeks(year)` was truthy and only stopped early for
`_failed_years`, so it could not tell "loaded, zero weeks" from "still loading".

- `_is_preseason(year)` — `year in _data and not weeks`. Reads `_data` directly rather
  than via `_weeks()`, which would call `_ensure()` and spawn loader threads during
  render.
- `_boot` now stops the poller on that condition.
- `_loading_placeholder(year)` returns the compact `_preseason_note()` instead of the
  spinner. All 12 call sites pass `year`; the bare call still works.
- `_tab_week` returns the full hero, checked *before* `_season`/`_week` so it doesn't
  kick off a pointless load.
- Playoffs / All-Time / Side Bets / Head-to-Head keep working off 2019–2025 data.
- The year selector and week scrubber already handled preseason — the scrubber renders
  "PRE-SEASON" and all 12 team chips appear.

**Also added:** `SLEEPER_SKIP_EAGER_LOAD=1`. `app.py` eagerly loads every season at
import (`webapp/app.py:394`), and an unplayed season is deliberately never cached, so
importing the module in tests hit the Sleeper API on every run.

---

### Task 11E — Kickoff countdown hero ✅ COMPLETE

Renders on This Week whenever the selected year has no weeks. Self-retiring: it
disappears once Week 1 data lands, so there is no cleanup task.

- `data_loader.season_kickoff_ms(year)` returns epoch ms (UTC) for the first Week 1
  kickoff, derived from the cached NFL schedule — **not hardcoded**. nflverse publishes
  `gameday`/`gametime` in US Eastern; the helper localizes then converts to UTC.
  Verified: 2026 → `2026-09-09 20:20 EDT` (NE @ SEA). Returns `None` on any failure and
  the hero falls back to a "schedule not published yet" line.
- `webapp/assets/kickoff.js` ticks the clock, following the `counter.js` pattern
  (data attribute + `MutationObserver` re-attach, because Dash swaps DOM without a
  page reload). Adds `.is-live` at zero.
- Champion banner raises in (`ps-banner-raise`); all 12 managers listed.
- Defending champion resolved via `Playoffs.winners[3]` placement 1. Reads the prior
  season off disk when cached (~0.15s pickle read) because the eager loader does the
  current year first, so 2025 isn't in `_data` when the hero first renders — and the
  hero disables the boot poller, so nothing would re-render to pick the banner up
  later. Warms in the background and skips the banner when not cached; never blocks
  the render thread on an API call.

**Animation: DVD-screensaver bounce** (changed from the original field-goal arc at the
user's request). The ball crosses the box at constant speed and reflects off all four
walls, so it carries the same "will it hit the corner?" tension as the old idle screens.

- Two independent `alternate` animations, no JS: `ps-drift-x` on the full-width track,
  `ps-drift-y` on the ball. Both `linear` — easing reads as a lob, not a bounce.
- Durations 5.3s / 3.7s. **53 and 37 are both prime, so the axes only realign every
  196s** — a dead-on corner hit lands about every 3.3 minutes, with near-misses around
  37s and 159s. Matching or simply-related durations would lock the path to a fixed
  diagonal and the corner would either happen every loop or never. Keep them awkward.
- `.ps-ball` carries `-1.9s` negative delay so the ball doesn't start *in* a corner and
  give the payoff away on load.
- `.ps-field` gained a border and inset background — the bounce only reads if there are
  visible walls to reflect off.
- **The ball is absolutely positioned inside the track, not inline.** As an
  `inline-block` it inherited `text-align: center` from `.ps-hero` and started at the
  middle of the box, so the entire bounce sat in the right half and ran off the edge.
  The zero-height track also hung it below its own baseline. `position: absolute;
  left: 0; bottom: 0` removes both dependencies.
- Travel distances derive from `--ps-field-h` / `--ps-field-border` / `--ps-inset` /
  `--ps-ball-size` on `.ps-field` rather than being hand-tuned, so the geometry stays
  correct if any of them change. Measured in-browser: the ball clears all four walls by
  exactly **5px**, at field widths from 280px to 520px.

**Three bugs found in review of the first version, all fixed:**

1. **The goalpost was upside down** — it used `border-top`, which closes the shape at
   the top and draws a doorframe. A goalpost opens *upward*: base post from the turf to
   the crossbar (`border-bottom`), uprights continuing above it. Base post attaches via
   `top: 100%` so the two pieces stay joined at any size.
2. **The ball barely moved sideways.** `translate(46%, …)` resolves percentages against
   *the element's own box* — on a ~24px ball that was ~11px of drift against 120px of
   lift, so it read as purely vertical. Hence the track/ball split: percentages on a
   `width: 100%` track are field-relative and stay correct at any width.
3. **`kickoff.js` hung the browser tab.** `render()` writes `textContent`, which is
   itself a childList mutation, so a `MutationObserver` reacting to any `addedNodes`
   re-entered `start()` → `tick()` → `render()` forever. Observer callbacks are
   microtasks, so the loop never yielded and the page never painted. Fixed by matching
   element nodes only (`nodeType === 1`) *and* only when a `[data-kickoff]` element
   actually enters the DOM — the same guard `counter.js` relies on — plus skipping
   `textContent` writes when the value is unchanged. Verified in jsdom both ways: the
   old version exceeded 5000 observer calls in 2.5s, the fixed version makes 4.

**`prefers-reduced-motion` guard shipped with it**, and it covers the pre-existing
animations too — the stylesheet had none before. The countdown keeps updating under
reduced motion; only movement is removed, and the ball parks in the corner rather than
freezing mid-flight.

**Two countdowns: draft and Week 1.** `_countdown_block(label, target_ms, pending)`
renders each one and handles three states — live digits, `COMPLETE` once the date has
passed, and a pending chip (`TBD` / `SCHEDULE PENDING`) when there is no date. A block
with no date carries no `data-kickoff`, so the ticker skips it; `kickoff.js` already
looped over every `[data-kickoff]` on the page, so adding a second countdown needed
**no JS change**.

`data_loader.draft_start_ms(year)` resolves the draft date:
1. Sleeper's draft `start_time` (authoritative — scheduling the draft on Sleeper is all
   that's needed, no config edit).
2. `config/season_dates.json` override, for pinning a date before it's on Sleeper.
3. Otherwise `None` → the hero shows TBD.

`fetch_draft_json` **only caches once `start_time` is set.** Caching an unscheduled
draft would pin the hero to TBD forever, since these pickles have no TTL — the same trap
as caching an unplayed season. Verified: 2026 returns `None` and writes no cache entry;
2025 resolves to its real draft (2025-09-01 21:02 EDT) through the Sleeper path.

**Champion banner labels the season** (`2025 CHAMPION`, not `DEFENDING CHAMPION`). The
bare label misled a reader into thinking the wrong season's champion was shown — a
season spanning two calendar years makes "defending" genuinely ambiguous. The data was
correct: cosmodromedary won 2025; DirtyCommie won 2024.

---

### Task 11F — Tests ✅ / deploy ⛔ NOT DONE

**Tests: DONE** (53 added, suite now **295 passed / 1 skipped**, from a 242-passed
baseline). The single skip is pre-existing and unrelated
(`test_pipeline.py:428`, "too many values to unpack").

New files: `tests/test_aliases.py` (16), `tests/test_preseason.py` (22).
New classes: `TestSeasonRolloverIntegrity` in `tests/test_config.py`,
`TestPreseasonSeason` + `TestCacheDurability` in `tests/test_pipeline.py`.

The preseason guards were mutation-checked — each new test was confirmed to fail with
its guard removed. Two test-quality problems were found and fixed along the way:
- `test_empty_season_is_not_cached` passed only by luck of ordering; it asserted *no*
  cache write at all, but `load_data_for_year` legitimately seeds `nfl_players`. Now
  scoped to `season_data_*` keys.
- `test_carries_a_kickoff_timestamp` depended on a schedule pickle being on disk. Now
  pins `season_kickoff_ms` so it asserts the markup contract, not the cache state.

**Deploy: NOT done.** Before deploying:
- The name fingerprint (11B) invalidated every season pickle. `.cache/` was rebuilt
  locally; the Pi's `.cache/` is **not** git-tracked and must be re-rsynced, or the Pi
  refetches all seven seasons from the API on first request.
- 2026 is deliberately never cached, so each Pi restart refetches it (~5s). That is what
  makes it notice when Week 1 lands.
- Ship 11G with this — the Pi's gunicorn threads are exactly the concurrency that
  corrupts caches, and it is the one change here that prevents silent data loss.

#### Original 11F notes

Add to `tests/test_pipeline.py`:
- preseason: empty `weeks_dict` does not raise and does not write a cache file
- config integrity: every year in `league_ids.json["leagues"]` has a `roster_ids.json` entry
- alias: `canonical_name` is idempotent, and no legacy name survives in loaded config

Then `pytest tests/ -m "not slow" -q`, commit, push,
`ssh rachett 'bash ~/deploy.sh sleeper'`, and re-rsync `.cache/` (not git-tracked).

### Task 11G — Atomic cache writes ✅ COMPLETE (unplanned)

**Not in the original plan — found by accident, and it is the most serious defect this
phase turned up.**

`_save_cache` pickled straight into the destination path. Any overlap between writers
leaves a truncated file visible to readers, and `_load_cache` then raised
`EOFError: Ran out of input` rather than treating it as a miss. During this session —
with the dev server, several pytest processes and a couple of scripts all warming the
same keys — **43 of ~170 cache files were corrupted**, including season pickles, the
NFL schedule, matchups, transactions and the survivor cache. The symptom was not an
obvious crash: `season_kickoff_ms` swallowed the `EOFError` in its broad `except` and
silently returned `None`, so the hero rendered without a countdown and the test suite
hung and failed in ways that looked unrelated.

**This is a live production risk, not just a local one.** The Pi serves the app under
gunicorn with 4 threads and eagerly loads every season on boot, so two workers warming
the same key overlap in exactly the same way.

Fix in `data_loader.py`:
- `_save_cache` writes to a `tempfile.mkstemp` in the same directory, then `os.replace`
  into place — atomic on POSIX and Windows, so readers see the old file or the new one
  and never a partial. Temp file is cleaned up if pickling raises.
- `_load_cache` catches `EOFError` / `UnpicklingError` / `AttributeError` / `ImportError`,
  logs, deletes the bad file, and returns `None` so the next call rebuilds. Caches now
  self-heal instead of poisoning every consumer.

Guarded by `TestCacheDurability` in `tests/test_pipeline.py` (truncated file reads as a
miss, bad file is removed, a failed write leaves the previous value intact, no temp
files left behind, round-trip).

**Cleanup performed:** all 43 corrupt files deleted and rebuilt (seasons 2019–2025,
survivor 2024–2025, pick 'em 2025). All 174 cache files verified readable.

---

---

---

### Implementation order

1. **11A** first — nothing else can be verified against 2026 until a `Week` constructs.
2. **11B** before 11C, so the 2026 config is written into an already-aliased world.
3. **11C** — flip the constants together; confirm 2025 now behaves as a completed season.
4. **11D** before 11E — the hero needs a reliable "no weeks yet" signal.
5. **11E** — reduced-motion guard in the same commit as the animation.
6. **11F** alongside, not after.
7. **11G** emerged mid-phase; it is independent of the rest and could ship on its own.

---

### What this phase changed about the plan

Worth recording, because the original plan was wrong in instructive ways:

- **Preseason breaks in four places, not one.** The plan assumed an empty `weeks_dict`.
  In fact `League.__init__` 404s outright (nflverse publishes no weekly stats until a
  season is played), `Week()` was constructed before the emptiness check and raised
  `KeyError` on pre-draft roster stubs, `Season.Update()` raised on `pd.concat([])`, and
  only then did the empty-cache problem appear. See 11D.
- **The visible symptom of an unhandled empty season is a hang, not an error.** Nothing
  could distinguish "loaded, zero weeks" from "still loading", so the tab polled forever.
  Worth remembering the next time a state looks like it's "still loading".
- **Renames touch far more than the roster config.** Eight surfaces, including 14 side
  bet `winner` fields, seven of which are compound (`"jhuntmadd & BMoreBallers88"`) and
  would have been silently missed by a whole-string alias lookup.
- **Two diagnoses in this phase were wrong on the first pass.** The browser hang was
  blamed on the Playwright MCP backend when it was an infinite `MutationObserver` loop
  in our own JS — the isolation test was invalid because the browser was already wedged
  from a prior load. The test-suite hang was blamed on a networked test when it was
  cache corruption. In both cases the correct move was the one taken second: reproduce
  the failure deliberately and confirm it disappears when the suspected cause is removed.
