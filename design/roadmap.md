# Legacy League Webapp — Development Roadmap

**Created:** 2026-05-21  
**Status:** Active  
**Supersedes:** `design/fix-plan.md` (all tasks complete as of commit `41094a3`)

This document is the single source of truth for planned work. Update status inline as tasks complete.

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

## Phase 1 — Code Quality & Robustness (Current)

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

## Phase 2 — Graph Integration (Orphaned Methods)

Adds three existing-but-unwired chart methods to the UI, cleans up two redundant ones.

---

### Task 2A — Delete redundant Season methods

**File:** `sleeper_core.py`

**Delete these two method definitions entirely:**
- `WholeSeasonBarGraph()` (~line 1932) — stacked weekly bar chart; redundant with Win Progression and Points For/Against
- `WeekYTDTotalsPercents()` (~line 1962) — stacked percentage bar; same problem

Both methods are confirmed unreferenced by `app.py` and `data_loader.py`. Safe to delete.

**Verify:** `grep` confirms no remaining references. App loads without errors.

---

### Task 2B — Fix typo and add StarterPerformanceGraph to Season tab

**File:** `sleeper_core.py` and `webapp/app.py`

**Part 1 — sleeper_core.py:** No code changes needed. Method is complete and functional.

**Part 2 — app.py, Season tab (`_tab_season`):**

Add a new chart card after the existing bench/efficiency charts. Uses `self.BreakoutSeason` (already populated by `Season.Update()`), so no new data dependencies.

```python
try:
    fig = sf.StarterPerformanceGraph()
    cards.append(_card(_strip(fig, 1200), 'Starter Points by Position',
                       subtitle='Total fantasy points scored by starters, broken down by position'))
except Exception as e:
    traceback.print_exc()
    cards.append(_card(_err(str(e)), 'Starter Points by Position'))
```

**Note on `_strip()`:** `StarterPerformanceGraph` sets `height=1200` internally. `_strip()` will reset margins. If the chart appears clipped, add a post-strip margin override in the rendering pipeline (same pattern as `ForAgainstwithTeams` at app.py ~line 1328).

**Verify:** Season tab shows a horizontal stacked bar chart of starter points by position, sorted by total points.

---

### Task 2C — Fix typo and add PositionStrengthPolar to Season tab

**File:** `sleeper_core.py` and `webapp/app.py`

**Part 1 — sleeper_core.py, rename method and clean internal typos:**
- Rename `PositionStengthPolar` → `PositionStrengthPolar` (fix the missing 'r')
- Rename the internal variable typos for consistency: `PosistionAvg` → `PositionAvg`, `PosistionPolar` → `PositionPolar` (these are local variables only, no external references to update)

**Part 2 — app.py, Season tab:**

The method calls `self.PositionStrengthCalculator()` internally, which sets `self.PosistionPivot_scaled` and `self.PosistionPivot_Standard_scaled`. These attributes don't exist until that method runs, so guard against `AttributeError`:

```python
try:
    fig = sf.PositionStrengthPolar()
    cards.append(_card(_strip(fig, 1400), 'Positional Strength',
                       subtitle='Each team\'s scoring by position as z-scores vs league average'))
except Exception as e:
    traceback.print_exc()
    cards.append(_card(_err(str(e)), 'Positional Strength'))
```

**Note:** This is a 4×3 grid of 12 polar subplots — a heavy render. Set height generously (1400px+). If render time is unacceptable, consider lazy-loading via a callback rather than building at tab-render time.

**Verify:** Season tab shows a 4×3 polar chart grid. Each panel represents one team, with positional z-scores as the radar shape.

---

### Task 2D — Extend violin toggle to include ViolinPosition (by-position view)

**File:** `webapp/app.py` — Players tab violin card and its callback

**Current toggle:** 2 options — `starters` / `all`  
**New toggle:** 4 options — `starters` / `all` / `pos_starters` / `pos_all`

The first two call `sf.ViolinPlayer(...)` (existing). The last two call `sf.ViolinPosition(Starters=True/False)` (the orphaned method).

**Part 1 — Update the toggle UI** (in `_tab_players`, where the violin card is built):
```python
dcc.RadioItems(id='violin-toggle', options=[
    {'label': 'Starters (By Team)',    'value': 'starters'},
    {'label': 'All Rostered (By Team)', 'value': 'all'},
    {'label': 'Starters (By Position)', 'value': 'pos_starters'},
    {'label': 'All (By Position)',      'value': 'pos_all'},
], value='starters', className='toggle-group', inline=True),
```

**Part 2 — Update the violin callback** (grep for `@app.callback` with `violin-toggle` as input):

Add two new branches:
```python
elif toggle == 'pos_starters':
    fig = sf.ViolinPosition(Starters=True)
elif toggle == 'pos_all':
    fig = sf.ViolinPosition(Starters=False)
```

**Note:** `ViolinPosition` uses `self.BreakoutSeason` or `self.Starters` — both available on the season object. The chart has its own margins set internally (`margin=dict(t=140, b=100, l=120, r=40)`). Confirm `_strip()` doesn't clobber these in the callback's return path.

**Verify:** Players tab violin toggle shows all 4 options. Switching to a by-position option shows faceted violin plots split by QB/RB/WR/TE/K/DEF.

---

## Phase 3 — API & Data Robustness

Deeper improvements to data quality, matching, and future-proofing.

---

### Task 3A — Carry player_id through dfBreakout

**File:** `sleeper_core.py` — `PlayerBreakout()` and `WeeklyDataframe()`

**Background:** Sleeper matchup data uses `player_id` as the primary key. The current code converts IDs to names immediately and discards the ID. Keeping `player_id` as a column in `dfBreakout` enables:
- Same-name player disambiguation (e.g., two "Michael Thomas" players in the same league era)
- Future crosswalk to other data sources
- Debugging name-match failures silently swallowed by left joins

**Fix:** In `PlayerBreakout()`, when iterating over the matchup JSON to build `dfBreakout`, add `player_id` as a column alongside `player_name`. Requires reading the actual code carefully before editing — the exact row-building logic determines where to insert this.

**Constraint:** Do not change the `player_week_id` join key (still name-based — see Phase 3B for why).

**Verify:** `dfBreakout` columns include `player_id`. Existing chart output is unchanged.

---

### Task 3B — Document name-matching fragility (no code change yet)

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

### Task 3D — Add transaction data fetching to data_loader

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

## Phase 4 — Playoff Bracket Feature

*Future phase. Scoped here for planning purposes.*

**Goal:** Visualize the playoff bracket for any season on the All-Time tab (or a new "Playoffs" sub-tab).

**API endpoints needed:**
- `GET /v1/league/<league_id>/winners_bracket` — returns bracket matchup objects with `r` (round), `m` (match ID), `t1`/`t2` (roster IDs), `w`/`l` (winner/loser roster IDs)
- `GET /v1/league/<league_id>/losers_bracket` — same structure for consolation bracket

**Bracket object key fields:**
```json
{ "r": 1, "m": 1, "t1": 3, "t2": 6, "w": null, "l": null }
```
Teams may also be referenced as `{ "w": <match_id> }` (winner of prior match) rather than a direct roster ID — the rendering logic needs to resolve these.

**Data fetchers to add (to data_loader.py, Task 3D already handles transactions):**
```python
def fetch_winners_bracket(league_id: int) -> list: ...
def fetch_losers_bracket(league_id: int) -> list: ...
```

**Visualization options:**
- D3.js bracket tree (consistent with existing D3 chord/race charts)
- Plotly nested annotations (simpler but less flexible)

**Considerations:**
- Bracket structure varies by league size and format — must handle 4-team, 6-team, and 8-team playoffs
- Roster IDs must be mapped to team names via the existing roster_ids dict
- Historical brackets (2019–2024) are fully settled; only the current year bracket may have nulls

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

## Deferred / Backlog

| Item | Notes |
|------|-------|
| Route `League.UsersJSONtoDF` through data_loader | Minor — direct `requests.get` calls in League.__init__ are only made once per year (season pickle captures everything). Low urgency. |
| Vectorize Pandas loops in `WeeklyDataframe`, `WeeklyWins`, `PlayerBreakout` | Performance impact negligible for 12-team 18-week dataset. Not worth the risk/effort. |
| Crosswalk Sleeper player IDs to GSIS IDs for ID-based stats join | Requires confirming nfl_data_py roster `espn_id` matches Sleeper's `espn_id`. Exploratory work needed first (see Task 3B). |
| `previous_league_id` auto-discovery | No urgency until 2026 season is created. See Task 3E. |
