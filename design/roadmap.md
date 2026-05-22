# Legacy League Webapp — Development Roadmap

**Created:** 2026-05-21  
**Last updated:** 2026-05-21 (end of session)  
**Status:** Active — Phase 3 is next  
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

## Phase 3 — API & Data Robustness (Current)

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

## Phase 4 — Playoffs Tab (Current)

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

**File:** `data_loader.py`

Added `fetch_winners_bracket(league_id)` and `fetch_losers_bracket(league_id)` — same cached GET pattern as other fetchers.

---

### Task 4B — Playoff processing in sleeper_core.py

**File:** `sleeper_core.py`

Add a `Playoffs` class (or methods on `Season`) that:
1. Reads `playoff_week_start` from `league_json['settings']` — no hardcoding
2. Fetches winners and losers bracket JSON via data_loader
3. Resolves `t1_from`/`t2_from` references (winner/loser of match X) to actual roster IDs
4. Maps roster IDs → team names via `roster_ids[year]`
5. Joins scores from `AllMatchesDict[year][week]` for playoff weeks
6. Joins best player and bench points from `AllBreakoutDict[year][week]` for winners bracket
7. Produces two structured dicts — one per bracket — keyed by round then match:
   ```python
   {
     1: [{'match': 1, 'team1': 'Brett', 'score1': 142.3, 'team2': 'Kyle', 'score2': 138.1, 'winner': 'Brett', 'best_player': 'CeeDee Lamb (38.2)', 'bench_left': 24.1}],
     2: [...],
     3: [...]
   }
   ```

**Scores join note:** `AllMatchesDict[year][week]` has one row per matchup with `Team`, `Score`, `matchup_id`. Join by matching both roster IDs in the bracket entry to the same `matchup_id` in that week's dataframe.

---

### Task 4C — Winners bracket cards (app.py)

**File:** `webapp/app.py` — new `_tab_playoffs()` function

Two-column layout. Left column: winners bracket cards, 3 rounds stacked top-to-bottom.

Each card shows:
- Team names and scores, winner highlighted
- Round label (Wild Card / Semifinals / Championship)
- Placement label for p=3/p=5 games (3rd Place / 5th Place)
- Best player of the game (name + points)
- Bench points left (starter points that were available on bench)

Round 2 has 3 cards — lay them out as: [Semi 1] [Semi 2] [5th Place] or stack vertically.

---

### Task 4D — Losers bracket cards (app.py)

**File:** `webapp/app.py` — within `_tab_playoffs()`

Right column alongside winners bracket. Same card component but minimal:
- Team names and scores only
- Winner highlighted
- Round label

No best player, no bench points.

---

### Task 4E — Analytics charts (sleeper_core.py + app.py)

**File:** `sleeper_core.py` — chart methods on `Playoffs` class  
**File:** `webapp/app.py` — render below bracket cards

Three charts, winners bracket only:

1. **Champion's road** — horizontal bar chart showing the champion's score in each round vs. their opponent's score. One set of bars per round (3 rounds).

2. **Playoff heat check** — for each playoff team, their average points in last 3 regular season weeks (weeks 12–14) vs. their playoff average. Grouped bar chart. Shows who peaked at the right time.

3. **Bench points left** — per playoff game across both brackets (winners only), how many points were left on each team's bench. Stacked or grouped bar, one bar per team per game.

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
