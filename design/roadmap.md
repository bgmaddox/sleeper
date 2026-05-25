# Legacy League Webapp — Development Roadmap

**Created:** 2026-05-21  
**Last updated:** 2026-05-24  
**Status:** Active — Phases 1–4, 6–7 complete; Phase 3 partially done; 7C/7D deferred; Phase 8 TBD  
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
`pytest tests/ -m "not slow"` → **139 passed, 0 failed, 2 xfailed** (Week11 + Week14 intentionally xfail)

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

### Task 3C — Use fetch_state_json() to auto-detect current week in app

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

## Phase 7 — Side Bets Tab ✅ LARGELY COMPLETE (commit `c9af1b3`)

Tasks 7A, 7B, 7E, 7F, 7G, 7H done. Tasks 7C (Week11 transactions) and 7D (Week14 placeholder) remain deferred — both marked `xfail(strict=True)` in the test suite.

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

### Task 7C — Add Week11 chart method (transaction data) ⏸️ DEFERRED

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

### Task 7D — Add Week14 placeholder method ⏸️ DEFERRED

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
| Route `League.UsersJSONtoDF` through data_loader | Minor — direct `requests.get` calls in League.__init__ are only made once per year (season pickle captures everything). Low urgency. |
| Vectorize Pandas loops in `WeeklyDataframe`, `WeeklyWins`, `PlayerBreakout` | Performance impact negligible for 12-team 18-week dataset. Not worth the risk/effort. |
| Crosswalk Sleeper player IDs to GSIS IDs for ID-based stats join | Requires confirming nfl_data_py roster `espn_id` matches Sleeper's `espn_id`. Exploratory work needed first (see Task 3B). |
| `previous_league_id` auto-discovery | No urgency until 2026 season is created. See Task 3E. |
