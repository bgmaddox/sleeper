# Survivor Tab — Implementation Plan

> **Status:** Planning complete. Ready for phased implementation.  
> **Target files:** `sleeper_core.py`, `data_loader.py`, `webapp/app.py`, `webapp/assets/style.css`, `tests/test_charts.py`, `tests/test_pipeline.py`

---

## Context for Agents

This is a Plotly Dash webapp (`webapp/app.py`, 2300+ lines) backed by a data-class layer
(`sleeper_core.py`) with a disk-caching layer (`data_loader.py`). All chart methods return
Plotly `Figure` objects — they never call `fig.show()`. Tab content functions return Dash
component trees. The app uses a single custom Plotly template `gridiron_ink` (dark navy theme).

**Before writing any code, read:**
- `CLAUDE.md` (project root) — testing conventions, run command, venv path
- `webapp/app.py` lines 1–30 — SECTION MAP (line anchors for every section)
- `sleeper_core.py` lines 1–80 — existing config dicts and class structure overview

**Venv:** `.venv/` at project root (Python 3.11). Activate: `source .venv/bin/activate`  
**Run tests:** `pytest tests/ -m "not slow" -q`  
**Run app:** `lsof -ti :8050 | xargs kill -9 2>/dev/null; sleep 1; cd webapp && source ../.venv/bin/activate && python app.py`

---

## API Research Findings

### Survivor League IDs (add to `sleeper_core.py`)
```python
SURVIVOR_LEAGUE_IDS = {
    2024: 1136802217681539072,
    2025: 1252050081251590144,
}
```

### Endpoints Used
- `GET https://api.sleeper.app/v1/league/{id}/rosters` — pick history + elimination data
- `GET https://api.sleeper.app/v1/league/{id}/users` — owner_id → display_name mapping

### Roster Metadata — CRITICAL FORMAT DIFFERENCES BETWEEN YEARS

The 2024 and 2025 leagues use **different metadata schemas** for elimination data.  
The `Survivor` class **must** handle both.

**2024 format:**
```json
{
  "metadata": {
    "eliminated_leg_id": "v1:regular:5",
    "is_eliminated": "true",
    "num_eliminations": "3",
    "points_by_leg": { "v1:regular:1": 1.0, "v1:regular:5": 0.0, ... },
    "previous_picks": { "v1:regular:1": ["KC"], "v1:regular:5": ["SEA"], ... }
  }
}
```

**2025 format** (revive mechanic — `num_revives_allowed: 1`):
```json
{
  "metadata": {
    "is_eliminated": "true",
    "lost_leg_ids": ["v1:regular:3", "v1:regular:13"],
    "points_by_leg": { "v1:regular:1": 1.0, "v1:regular:3": 0.0, ... },
    "previous_picks": { "v1:regular:1": ["DEN"], "v1:regular:3": ["ATL"], ... }
  }
}
```

**Key parsing rules:**
- `points_by_leg` value `1.0` = won, `0.0` = lost **or** no pick (post-elimination)
- `previous_picks` value `[]` (empty list) = no pick made — **filter these out entirely**
- Week key format: `"v1:regular:N"` — extract N with `int(key.split(':')[-1])`
- 2024 elimination week: `int(eliminated_leg_id.split(':')[-1])` — **guard for None** (non-eliminated players)
- 2025 elimination week: `int(lost_leg_ids[-1].split(':')[-1])` if `is_eliminated == "true"` else None
- 2025 revived players: `len(lost_leg_ids) == 2` and `is_eliminated == "true"` (lost twice = truly out); `len(lost_leg_ids) == 1` and `is_eliminated == "false"` = survived after using revive
- 2025 revive-loss week (first loss, came back): `int(lost_leg_ids[0].split(':')[-1])`

### NFL Schedule Data (for game result cross-reference)
`nfl_data_py` schedules have all needed columns. Team abbreviations **match exactly** with Survivor pick abbreviations (verified).

```python
import nfl_data_py as nfl
sched = nfl.import_schedules([year])
# Relevant cols: week, away_team, away_score, home_team, home_score
# Build lookup: {(team_abbr, week_num): (opponent_abbr, team_score, opp_score)}
```

The `result` column is from the home team perspective. Derive win/loss per team by checking
whether the picked team appears as `home_team` or `away_team` and comparing scores.

### 2025 Observed Data (useful for testing)
- 7 players: bgmaddox, RascalHazard, BMoreBallers88, RossLikeSauce, jhmad, InfiniteJess, sgmaddox
- **Week 3 was a mass-elimination** — ATL and GB both lost; 4+ players eliminated simultaneously
- bgmaddox: survived 12 weeks (revived after Wk3 ATL loss, finally out Wk13)
- BMoreBallers88: survived 11 weeks (revived after Wk5 BUF loss, out Wk11)
- All 7 players are `is_eliminated: "true"` (season complete)

---

## Existing Patterns to Follow

### Tab structure in `app.py`
```python
# Tab bar entry (around L882):
dcc.Tab(label='Survivor', value='tab-survivor', className='tab tab--survivor', selected_className='tab--selected'),

# Router (around L1183):
if tab == 'tab-survivor': return _tab_survivor(year)

# URL deep-link map (around L1213):
'survivor': 'tab-survivor'

# Tab function (add after _tab_sidebets ~L1853+):
def _tab_survivor(year): ...
```

### Chart card pattern (from existing tabs)
```python
_card([
    html.Div('Chart Title', className='chart-title'),
    html.Div('Subtitle text', className='chart-subtitle'),
    dcc.Graph(figure=fig, config={'displayModeBar': False}),
])
```

### Tab icon technique (from `style.css` ~L754)
Icons use `mask-image` on `::before` pseudo-elements with inline SVG data URIs.
New tab must be added to **three** existing selector blocks:
1. The shared `::before` sizing block (L756–L758)
2. The `tab--selected::before` color block (L774–L778)
3. The `hover::before` color block (L780–L784)
Then add one new block for the SVG itself, following the pattern at L787–L815.

---

## Bugs in Notebook Version to Fix

The existing `Survivor` class in `Sleeper_v2.ipynb` has these issues — **do not port them**:

1. `self.PickStatus = ... .reset_index` — missing `()`, stores method not result
2. `eliminated_leg_id` parsed without null guard — crashes for active (non-eliminated) players
3. No `owner_id` → `display_name` resolution — every output shows opaque IDs
4. Only handles 2024 metadata format — breaks entirely on 2025 `lost_leg_ids` structure
5. `DisplayLogos` helper is wired to notebook-style `fig.add_layout_image` but unused in any chart method

---

## Execution Order and Parallelization

```
[Phase 1: Data Layer]  ← must complete first, sequential
        │
        ├─────────────────────────────────────┐
        ▼                                     ▼
[Phase 2: Chart Methods]            [Phase 4: CSS + Icon]
  (one agent, sequential             (independent of Phase 2,
   within sleeper_core.py)            write to style.css only)
        │
        ▼
[Phase 3: App Tab]  ← needs Phase 2 complete
        │
        ▼
[Phase 5: Tests]    ← needs Phase 1 + 2 complete
```

**Phases 2 and 4 can run in parallel** — they touch different files.  
All other phases are sequential.

---

## Phase 1 — Data Layer

**Model:** `sonnet`  
**Files:** `sleeper_core.py`, `data_loader.py`  
**Tests to run after:** `pytest tests/ -m "not slow" -q`

### 1A — Config (sleeper_core.py)

Add `SURVIVOR_LEAGUE_IDS` dict near the other league config dicts (`leagueNumbers_Dict`,
`roster_ids`). Grep for `leagueNumbers_Dict` to find the exact location.

### 1B — Rewrite `Survivor` class (sleeper_core.py)

Replace the existing `Survivor` class entirely. Do not preserve any of the notebook version
except the `find_unpicked` logic (which is correct).

**`__init__(self, year)`**
- Takes `year` (int), not a `League` object
- Calls `fetch_survivor_rosters()` and `fetch_survivor_users()` from `data_loader`
- Builds `self.user_map`: `{owner_id: display_name}` from users JSON
- Calls `self._parse(rosters_json)`

**`_parse(self, rosters_json)`**
Builds two DataFrames:

`self.Picks` — one row per (player, week) where a pick was actually made:

| column | type | notes |
|--------|------|-------|
| `username` | str | resolved display name |
| `week` | int | 1–18 |
| `team_pick` | str | e.g. `"KC"` |
| `won` | bool | `points_by_leg` value == 1.0 |
| `is_fatal` | bool | True on the pick that caused final elimination |
| `is_revive_loss` | bool | True on first loss for revived players (2025 only) |

`self.Status` — one row per player:

| column | type | notes |
|--------|------|-------|
| `username` | str | |
| `weeks_survived` | int | count of rows in Picks where `won==True` |
| `final_week` | int\|None | week of final elimination; None if active |
| `is_eliminated` | bool | |
| `revived` | bool | True if player used their revive (2025) |
| `teams_used` | list[str] | all teams picked (wins + losses) |
| `teams_left` | list[str] | 32-team set minus `teams_used` |

Use the format detection logic described in API Research above. Both 2024 and 2025 formats
must produce identical column schemas.

**`get_game_results(self, year)`**
Returns a dict: `{(team_abbr, week): (opponent_abbr, team_score, opp_score)}`.
Uses `nfl_data_py.import_schedules([year])`. For each row in the schedule, add two
entries (one for home team, one for away team). Cache the schedule using
`data_loader.fetch_nfl_schedule(year)` (add that function if it doesn't exist).

**`find_unpicked(self, picked_list)`**
Keep as-is from notebook. Returns sorted list of the 32 team abbreviations not in `picked_list`.
The 32-team list uses `WAS` (not `WSH`).

### 1C — data_loader.py additions

Add these functions, following the existing caching pattern (MD5-keyed pickle in `.cache/`):

```python
def fetch_survivor_rosters(league_id: int) -> list:
    """GET /league/{id}/rosters, disk-cached."""

def fetch_survivor_users(league_id: int) -> list:
    """GET /league/{id}/users, disk-cached."""

def fetch_nfl_schedule(year: int) -> pd.DataFrame:
    """nfl_data_py.import_schedules([year]), disk-cached."""

def load_survivor_for_year(year: int) -> core.Survivor:
    """Build and return Survivor(year). Cache the built object as pickle."""
```

Cache keys should include the league_id (not just year) for rosters/users since survivor
leagues have different IDs from the main fantasy league.

---

## Phase 2 — Chart Methods

**Model:** `sonnet`  
**File:** `sleeper_core.py` — add all 6 as methods on the `Survivor` class  
**Prerequisite:** Phase 1 complete  
**Tests to run after:** `pytest tests/ -m "not slow" -q`

All methods return a Plotly `Figure` using the `gridiron_ink` template:
```python
fig = go.Figure(layout=go.Layout(template='gridiron_ink'))
```

### Chart 1: `pick_matrix_fig(self)` — Centerpiece

An annotated heatmap. Rows = players, columns = weeks (only weeks with at least one pick
across any player). Sort order: players sorted by `final_week` descending (longest survivors
at top), eliminated players at bottom sorted by `final_week` ascending.

Cell color encoding (use a numeric z matrix + custom colorscale):
- `2` = won (green `#2ecc71`)
- `1` = revive loss — lost but came back (amber `#f39c12`)
- `-1` = fatal loss (red `#e74c3c`)
- `0` = no pick / post-elimination (dark `#1a3a4a`)

Overlay each non-empty cell with the team abbreviation as text annotation.
Add a skull marker (💀 or `✕`) annotation on fatal-loss cells.
Do not show a colorbar. Remove axis tick marks; show player names on y-axis and week numbers on x-axis.

### Chart 2: `elimination_timeline_fig(self)` — Swim Lanes

Horizontal Gantt-style bar chart. One horizontal bar per player spanning Week 1 through
their `final_week` (or the last available week if still active). Color: `#2ecc71` (alive green).

For revived players: draw a short gap (0.3 week visual break) at the revive-loss week, then
resume the bar. Use two separate bar segments to achieve this.

Annotate the terminal end of each bar with the fatal team pick and game result string
(e.g., `"ATL — Lost 10-27"`). Retrieve results from `self.get_game_results()`.

Sort Y-axis by `final_week` descending (longest survivor at top).

### Chart 3: `weekly_carnage_fig(self)` — Eliminations Per Week

Simple vertical bar chart. X = week number, Y = number of players whose `final_week`
equals that week. Bar color: `#e74c3c`.

Annotate each bar with the team(s) that caused the eliminations that week
(the fatal picks for that week's eliminated players).

If `get_game_results()` is available, append the score to each team annotation
(e.g., `"ATL (L 10-27)"`).

### Chart 4: `team_graveyard_fig(self)` — 32-Team Usage Heatmap

A 4-row × 8-column grid of all 32 NFL teams. Use `go.Heatmap` or annotated scatter.
Arrange teams alphabetically left-to-right, top-to-bottom (or by division if preferred).

Color intensity = total number of picks on that team across all players and weeks.
Use a sequential colorscale (low = dark navy, high = bright blue-green matching `--accent`).

Hover text per cell: `"TEAM: N picks (X wins, Y losses)"`.
Teams that appear as a `is_fatal=True` pick get a subtle red border or overlay.

### Chart 5: `win_margin_fig(self, username)` — Per-Player Margin Waterfall

Takes `username` (str). Filters `self.Picks` to that player.

For each week the player made a pick:
- Winning weeks: green bar, height = team's margin of victory (team_score - opp_score from schedule)
- Fatal week: red bar, height = -(margin of defeat) so it goes below zero
- Revive-loss week: amber bar, height = -(margin of defeat)

X-axis: week numbers. Y-axis: point margin. Add a horizontal zero line.
Annotate each bar with the team abbreviation and opponent (e.g., `"KC vs BAL"`).

If game results are unavailable for a pick (schedule data gap), show the bar at height 1
(win) or -1 (loss) with a note in the hover.

### Chart 6: `longevity_leaderboard_fig(self, all_survivors: dict)` — Multi-Year Ranked Bar

Takes `all_survivors`: `{year: Survivor}` dict. Produces a grouped horizontal bar chart.

Y-axis: player usernames (union across all years). X-axis: weeks survived.
One bar group per player, one bar per year within the group.
Color each year's bars differently (use `coastal_colorway` from the template).

If a player didn't participate in a given year, show no bar (not a zero bar) for that year.
Sort players by total weeks survived across all years (descending).

---

## Phase 3 — App Tab

**Model:** `sonnet`  
**File:** `webapp/app.py`  
**Prerequisite:** Phases 1 and 2 complete  
**Tests to run after:** `pytest tests/ -m "not slow" -q`, then browser snapshot check

### 3A — Tab registration

Add to the three places described in "Existing Patterns to Follow":
1. Tab bar (`dcc.Tab` entry)
2. `_render_tab` router (`if tab == 'tab-survivor'`)
3. URL deep-link map (`'survivor': 'tab-survivor'`)

### 3B — `_tab_survivor(year)` function

Add after `_tab_sidebets()` (currently ~L1853). Structure:

```
Header row:
  - Chart title: "Survivor Pool"
  - Subtitle: "YEAR · N players · Winner or 'Season Complete'"
  - Year selector dropdown (values from SURVIVOR_LEAGUE_IDS keys, default = max year)

Row 1 (full width):
  - Pick Matrix (Chart 1) — the centerpiece

Row 2 (3 columns):
  - Elimination Timeline (Chart 2)
  - Weekly Carnage (Chart 3)
  - Team Graveyard (Chart 4)

Row 3 (2 columns):
  - Win Margin (Chart 5) with player dropdown
    - Dropdown: id='survivor-player-dropdown', options = usernames from Status
    - Default: first username in Status (longest survivor)
  - Longevity Leaderboard (Chart 6)
    - Pass all available years' Survivor objects

Loading pattern: wrap in `dcc.Loading` if data load takes >1s (follow side bets pattern)
```

**Player dropdown callback** — add as a new `@app.callback`:
```python
@app.callback(
    Output('survivor-win-margin-graph', 'figure'),
    Input('survivor-player-dropdown', 'value'),
    State('url', 'search'),
    prevent_initial_call=False,
)
def _survivor_win_margin(username, search): ...
```

This callback needs the `Survivor` object in scope. Load it via
`data_loader.load_survivor_for_year(year)` inside the callback using the year from the URL
or a `dcc.Store`. Follow the `_h2h()` callback pattern for how inner tab callbacks work.

### 3C — Update SECTION MAP

After adding the tab function, update the SECTION MAP in the `app.py` docstring (lines 7–30)
with the correct line number for `_tab_survivor()`.

---

## Phase 4 — CSS + Icon

**Model:** `haiku`  
**File:** `webapp/assets/style.css`  
**Prerequisite:** None (can run parallel with Phase 2)

### 4A — Add `.tab--survivor` to existing selector blocks

Find the three existing selector blocks (at ~L756, ~L774, ~L780) and add `.tab--survivor::before`
to each, following the identical pattern of the five existing tabs.

### 4B — Torch icon block

Add a new CSS block after the last existing tab icon block (~L815). The torch SVG:

```svg
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'>
  <path d='M9 11 Q7 6 12 2 Q14 6 13 8 Q16 5 15 11 Q14 13 12 14 Q10 13 9 11 Z'/>
  <line x1='10.5' y1='14' x2='13.5' y2='14'/>
  <path d='M10 14 L9.5 21'/>
  <path d='M14 14 L14.5 21'/>
  <line x1='9.7' y1='17.5' x2='14.3' y2='17.5'/>
  <line x1='8.5' y1='21' x2='15.5' y2='21'/>
</svg>
```

URL-encode this SVG for use as `mask-image` data URI, following the exact same pattern as
`.tab--week::before` at L787–L791. Both `-webkit-mask-image` and `mask-image` properties
required.

### 4C — Survivor-specific utility classes

Add to the bottom of the file:
```css
/* ── Survivor tab ──────────────────────────────────────────────────────────── */
.survivor-alive-badge   { color: #2ecc71; font-weight: 600; }
.survivor-out-badge     { color: #e74c3c; font-weight: 600; }
.survivor-revived-badge { color: #f39c12; font-weight: 600; }
```

---

## Phase 5 — Tests

**Model:** `haiku`  
**Files:** `tests/test_charts.py`, `tests/test_pipeline.py`  
**Prerequisite:** Phases 1 and 2 complete

### 5A — Pipeline tests (`test_pipeline.py`)

Add a `TestSurvivor` class with fixtures that load from `.cache/` (skip if cache missing,
following the existing skip pattern). Tests:

- `test_picks_columns` — `Survivor.Picks` has columns: `username`, `week`, `team_pick`, `won`, `is_fatal`, `is_revive_loss`
- `test_picks_no_empty_picks` — no rows where `team_pick` is None or empty string
- `test_status_columns` — `Survivor.Status` has all required columns
- `test_weeks_survived_positive` — all `weeks_survived` values > 0
- `test_username_resolution` — no `owner_id`-style strings (16+ digit numbers) appear in `username` column
- `test_2025_revive_data` — for year 2025, at least one player has `revived == True`
- `test_fatal_pick_unique_per_player` — each player has exactly 0 or 1 `is_fatal == True` row

### 5B — Chart smoke tests (`test_charts.py`)

Add a `TestSurvivorCharts` class. Each test instantiates `Survivor(year)` from cache and
calls one chart method, asserting it returns a `plotly.graph_objects.Figure`. Use year 2025.

- `test_pick_matrix_fig_returns_figure`
- `test_elimination_timeline_fig_returns_figure`
- `test_weekly_carnage_fig_returns_figure`
- `test_team_graveyard_fig_returns_figure`
- `test_win_margin_fig_returns_figure` — pass the first username from `Status`
- `test_longevity_leaderboard_fig_returns_figure` — pass `{2025: survivor}` as `all_survivors`

---

## Verification Checklist

After all phases complete, verify in this order (cheapest first):

1. `pytest tests/ -m "not slow" -q` — all pipeline + chart tests pass
2. Start app, navigate to Survivor tab in browser
3. `browser_snapshot` — confirm tab loads, pick matrix present, no error panels
4. `browser_console_messages` — no JS errors
5. Change year selector — confirm pick matrix reloads with different data
6. Change player dropdown (Win Margin chart) — confirm chart updates
7. `browser_take_screenshot` — only if layout or visual issue suspected

---

## Open Questions / Future Work

- **Pre-2024 years:** The group used Yahoo Fantasy Survivor for earlier seasons. Data may not
  be recoverable. If league IDs surface for other years, add them to `SURVIVOR_LEAGUE_IDS`
  and the `longevity_leaderboard_fig` will automatically incorporate them.
- **Active-season state:** During an in-progress season, some players won't have current-week
  picks yet. The pick matrix should gracefully show an empty cell for the current week with
  no pick text. The `[]` empty-list filter in `_parse()` handles this automatically.
- **2026 league ID:** Add when available. No code changes required beyond adding the ID to
  `SURVIVOR_LEAGUE_IDS` and clearing the survivor cache files.
