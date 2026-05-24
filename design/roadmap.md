# Legacy League Webapp — Development Roadmap

**Created:** 2026-05-21  
**Last updated:** 2026-05-23  
**Status:** Active — Phase 4 complete; Phase 6 planned next; Phase 3/5 deferred  
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

### Test suite status
`pytest tests/ -m "not slow"` → **55 passed, 0 failed, 0 xfailed**

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

## This Week Tab — Power Rankings Enhancements ⚠️ UNCOMMITTED

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

*Future phase. The `SideBet` class in `sleeper_core.py` (~lines 3728–4791) is the starting point.*

**Goal:** Surface side bet tracking, waiver/trade activity, and engagement metrics as a dedicated tab or modal.

**API endpoints needed:**
- `GET /v1/league/<league_id>/transactions/<round>` — per-week trades, waivers, FA pickups (Task 3D fetcher covers this)
- `GET /v1/league/<league_id>/traded_picks` — historical traded pick chain (Task 3D covers this)
- Draft data already fetched via `fetch_draft_picks_json()`

**Key transaction fields:**
```json
{
  "type": "trade",            // or "free_agent" or "waiver"
  "status": "complete",
  "adds": { "player_id": roster_id },
  "drops": { "player_id": roster_id },
  "draft_picks": [...],       // picks exchanged in trades
  "waiver_budget": [{ "sender": 2, "receiver": 3, "amount": 55 }],
  "settings": { "waiver_bid": 44 }   // FAAB bid amount
}
```

**Potential SideBet charts/features:**
- FAAB spend tracker (cumulative waiver budget spent per team, per season)
- Trade frequency heatmap (who trades with whom, how often)
- Waiver wire add/drop history per team
- "Most active" manager leaderboard
- Trade value analysis (points scored by traded players, pre/post trade)

**Pre-work before implementation:**
- Review and update the existing `SideBet` class — much of it may be out of date with the current data schema
- Confirm `leagueNumbers_Dict` has all years needed for transaction history pull
- Transaction data must be fetched for all 18 weeks × 7 seasons = 126 API calls on first load (all cached after that)

---

## Phase 6 — All-Time Playoff Analytics

**Goal:** Add five playoff-specific charts to the All-Time tab, aggregating bracket and score data across all seasons (2019–2025).

**Where they live:** Bottom of the All-Time tab, below the existing hall-of-fame / records cards. No new tab needed.

**Data dependency:** Each year's bracket data is already fetchable via `data_loader.fetch_winners_bracket(league_id)` and `fetch_losers_bracket(league_id)` (Task 4A). Playoff week scores are in `AllMatchesDict[year][week]` for playoff weeks. The `Playoffs` class (Phase 4B) handles a single year — Phase 6 needs a multi-year aggregation layer.

---

### Task 6A — AllTimePlayoffs aggregator in sleeper_core.py

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

### Task 6B — Chart 1: Playoff Appearances Leaderboard

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

### Task 6C — Chart 2: Playoff Win Rate

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

### Task 6D — Chart 3: Regular Season Rank vs. Playoff Finish

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

### Task 6E — Chart 4: Playoff Records Card

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

### Task 6F — Chart 5: Championship Road Scores

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

## Deferred / Backlog

| Item | Notes |
|------|-------|
| Route `League.UsersJSONtoDF` through data_loader | Minor — direct `requests.get` calls in League.__init__ are only made once per year (season pickle captures everything). Low urgency. |
| Vectorize Pandas loops in `WeeklyDataframe`, `WeeklyWins`, `PlayerBreakout` | Performance impact negligible for 12-team 18-week dataset. Not worth the risk/effort. |
| Crosswalk Sleeper player IDs to GSIS IDs for ID-based stats join | Requires confirming nfl_data_py roster `espn_id` matches Sleeper's `espn_id`. Exploratory work needed first (see Task 3B). |
| `previous_league_id` auto-discovery | No urgency until 2026 season is created. See Task 3E. |
