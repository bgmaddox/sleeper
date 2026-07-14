# Fix Plan — Issues.md

**Status: ALL TASKS COMPLETE** — committed `41094a3` on 2026-05-20.

Generated from `design/Issues.md`. Organized for sequential AI agent execution.
Each task identifies the exact file, line range, what to change, and how to verify.

---

## Reading guide

- **File refs** use `sleeper_core.py` and `webapp/app.py` — both in the project root / webapp/.
- Line numbers are approximate (based on the SECTION MAP in `app.py`'s docstring and grep results at plan-write time). Always grep/read to confirm before editing.
- Run the app to verify after each phase: `lsof -ti :8050 | xargs kill -9 2>/dev/null; sleep 1; cd webapp && source ../.venv/bin/activate && python app.py`

---

## Phase 1 — Style standardization (low risk, no logic changes)

These are pure layout/styling tweaks with no data-path risk.

---

### ✅ Task 1A — Fix "vs" annotation vertical positions in Matchups chart

**File:** `sleeper_core.py` — `WeeklyGraph()` method (~line 860)

**Problem:** The 6 "VS." annotations have hardcoded `yref='paper'` y-positions. The top 4 are correctly centered in their matchup bands, but the bottom 2 are too low.

**Current values (grep for the annotation list):**
```python
y=[0.93, 0.76, 0.58, 0.41, 0.21, 0.04]
```

**Expected centered positions** for 6 equal bands on paper coords:
- Band centers (bottom to top): 0.083, 0.25, 0.417, 0.583, 0.75, 0.917
- Descending order: `[0.917, 0.75, 0.583, 0.417, 0.25, 0.083]`

**Change:** Adjust the bottom two values only (top 4 are acceptable):
- `0.21` → `0.25`
- `0.04` → `0.09`

**Verify:** Navigate to This Week tab → Matchups chart. All 6 "VS." labels should appear vertically centered in their respective matchup bands.

---

### ✅ Task 1B — Standardize horizontal bar chart y-axis font sizes

**Standard to enforce:** `tickfont=dict(size=16)` on all `yaxes` of horizontal bar charts.

**Files and methods to update:**

| Method | File | Current y-axis size | Action |
|--------|------|-------------------|--------|
| `SeasonPointsForAgainst()` | `sleeper_core.py` ~L2753 | `12` | Change to `16` |
| `LineupEfficiencyChart()` | `sleeper_core.py` ~L3061 | Not set (uses annotations) | If y-axis tick labels exist, add `tickfont=dict(size=16)` |
| `HallofFame_Team()` | `sleeper_core.py` ~L3589 | `16` | Already correct — confirm |
| `HallofFame_Player()` | `sleeper_core.py` ~L3622 | `16` | Already correct — confirm |
| `HallofShame_Team()` | `sleeper_core.py` ~L3556 | `16` | Already correct — confirm |
| `HighestScoringLosers()` | `sleeper_core.py` ~L3477 | `18` | Change to `16` |
| `SmallestMargins()` | `sleeper_core.py` ~L3524 | None (showticklabels=False) | No change needed |

For `SeasonPointsForAgainst`, find `update_yaxes` and change:
```python
# before
figPFA.update_yaxes(tickfont=dict(size=12, ...))
# after
figPFA.update_yaxes(tickfont=dict(size=16, ...))
```

**Verify:** Open Season tab → "Points For & Against". Open This Week → "Lineup Efficiency". Open All-Time tab and check all horizontal bar charts. Labels should be consistently readable without any appearing undersized.

---

### ✅ Task 1C — Review and fix dtick values

**Problem:** `WeeklyWinsGraphBreakout()` has `dtick=3` on both axes, which skips tick marks on short seasons and looks inconsistent.

**File:** `sleeper_core.py` — `WeeklyWinsGraphBreakout()` (~line 1831)

**Changes:**
- X-axis (weeks, range 0–18): Change `dtick=3` → `dtick=1` so every week label is shown. The faceted small-multiple layout has enough space.
- Y-axis (wins, range 0–18): Change `dtick=3` → `dtick=2` so ticks appear at 0, 2, 4, 6... A season rarely exceeds 14 wins, so this avoids a crowded axis while remaining readable.

**Player Points dtick (Season > Players):** The `PlayerPoints()` method uses hardcoded `tickvals=[5, 10, 15]` on its x-axis. This is acceptable for a points-per-player chart but review whether points can exceed 15 in a single week. If a player ever scores 20+, a bar would extend past the last tick. Consider changing to `dtick=5` with `rangemode='tozero'` instead of fixed tickvals. Only change this if the current rendering looks clipped.

**Verify:** Season tab → "Weekly Wins · Breakout". Week numbers on the x-axis should appear at every week (1, 2, 3...) and win counts should tick at 0, 2, 4...

---

## Phase 2 — Bug fixes

These require investigation before editing. Read the actual data before patching.

---

### ✅ Task 2A — Fix "Scoring Distribution" showing "No data for this week range"

**File:** `sleeper_core.py` — `ViolinPlayer()` (~line 2110)

**Root cause:** The method filters with `self.Starters[self.Starters['week'].isin(WeekRange)]`. If the actual column name in `self.Starters` is different (e.g., `week_x`, `week_NFL`, or `Week`), the filter returns an empty DataFrame, triggering the "No data" fallback.

**Investigation step (do this first):**
Add a temporary print immediately inside `ViolinPlayer()` before the filter:
```python
print("Starters columns:", self.Starters.columns.tolist() if self.Starters is not None else "None")
print("BreakoutSeason columns:", self.BreakoutSeason.columns.tolist() if self.BreakoutSeason is not None else "None")
print("WeekRange:", list(WeekRange))
if self.Starters is not None and not self.Starters.empty:
    print("Starters['week'] sample:", self.Starters.iloc[0].to_dict() if 'week' in self.Starters.columns else "NO 'week' COLUMN")
```

Restart the app, navigate to Players tab, note the terminal output, then remove the prints and apply the correct column name in the filter.

**Fix:** Once the correct column name is confirmed, update the filter:
```python
# Change 'week' to whatever the actual column name is
df = self.Starters[self.Starters['<actual_col>'].isin(WeekRange)]
```

**Verify:** Players tab → "Scoring Distribution". Should display violin/box plots for each player. Toggle between "Starters Only" and "All Rostered" — both should render data.

---

### ✅ Task 2B — Fix missing top bars in "Highest-Scoring Losses"

**File:** `sleeper_core.py` — `HighestScoringLosers()` (~line 3477)

**Problem:** "Whole bars seem to be missing, mostly the top bar in the pairs." In grouped horizontal bar charts, the second trace (Winners) appears above the first (Losers) for each y-category. These bars are likely being clipped or the `Opp_team` column lookup is failing silently.

**Investigation steps:**
1. Check if `TopTenLosers['Opp_team']` exists — the `Matches` DataFrame must have an `Opp_team` column. If it doesn't exist, the `marker_color` list comprehension will raise a KeyError that is silently caught and returns an empty bar.
2. Check if `barmode` is set — `go.Figure()` defaults to `'relative'` not `'group'`. With `barmode='relative'`, both traces stack on the same y-position. Add `figLosers.update_layout(barmode='group')` explicitly.
3. Check the x-axis range — if the winner score exceeds the auto-computed range, the bar gets clipped. Add `figLosers.update_xaxes(rangemode='tozero')` and remove any manual range limits.

**Likely fix:**
```python
figLosers.update_layout(barmode='group')
figLosers.update_xaxes(rangemode='tozero', autorange=True)
```

Also verify `Opp_team` exists in `self.Matches` — if not, the color list must fall back gracefully:
```python
# Safe fallback if Opp_team doesn't exist
opp_colors = [self.teamcolors.get(t, '#BDE2FF') for t in TopTenLosers.get('Opp_team', pd.Series([''] * len(TopTenLosers)))]
```

**Verify:** All-Time tab → "Highest-Scoring Losses". Each row should show two bars side by side: the loser's score (left/shorter) and the winner's score (right/longer).

---

### ✅ Task 2C — Fix label clipping in "All-Time Points For & Against"

**File:** `sleeper_core.py` — `ForAgainstwithTeams()` (~line 3655 in AllTime class)

**Problem:** Top axis label clipped by container; y-axis team name labels clipped on the left.

**Current margin:** `dict(t=100, b=100, l=220, r=40)`

**Fix:**
```python
# Increase top margin for subplot titles and left margin for long team+player combo labels
figTeamPoints.update_layout(margin=dict(t=140, b=100, l=320, r=40))
```

Also check the subplot title font — `update_annotations(font_size=25)` styles the subplot titles. If the title row is still clipped, reduce font to 20 or reduce `vertical_spacing` from `.1` to `.08`.

**Verify:** All-Time tab → "All-Time Points For & Against". Both "Points With..." and "Points vs..." subplot labels must be fully visible at the top. Y-axis labels (e.g., "TeamA w/ Patrick Mahomes") should not be cut on the left edge.

---

### ✅ Task 2D — Investigate and fix Season tab D3 charts not rendering

**Affected charts:** "Season Score Race", "Season Heatmap", "Draft Board Replay" (all in Season tab)

**Architecture:** Server-side callback `_populate_d3_stores()` in `app.py` (~L1767) populates `store-race-data` and `store-heatmap-data`. A separate callback `_populate_draft_data()` (~L2124) populates `store-draft-data`. Clientside callbacks in `d3charts.js` receive these stores and render into `d3-race-container`, `d3-heatmap-container`, `d3-draft-container`.

**Investigation approach:**
1. Add `traceback.print_exc()` and explicit print statements inside the `except` blocks of `_populate_d3_stores` and `_populate_draft_data` to catch silent failures.
2. Add temporary Dash `Output` returns that print the data shape to the browser (or just log to terminal) to confirm the stores are being populated.
3. Open the browser console (F12 → Console) when on the Season tab and look for JavaScript errors from `d3charts.js`.

**Common failure points to check:**
- `sf.Matches` or `sf.teamcolors` is None or empty when the callback fires
- Column name mismatches (e.g., `'Week'` vs `'week'` in the matches DataFrame)
- `league_data.Draft()` returning None for the selected year (some years may not have draft data)
- D3 container element not yet in the DOM when the clientside callback fires (the `_waitForEl` helper in d3charts.js should handle this, but check the timeout — currently 20000ms)
- JavaScript namespace mismatch: confirm `window.dash_clientside.d3charts.renderScoreRace` etc. are defined (check for JS parse errors)

**Fix once root cause is identified:** Apply targeted fix. If data population is failing, fix the server callback. If JS rendering is failing, fix the relevant function in `d3charts.js`.

**Verify:** Season tab → scroll down past "Top Scorers · Points Race". Score Race bar chart animation, Heatmap grid, and Draft Board grid should all render with data.

---

### ✅ Task 2E — Investigate All-Time D3 charts not rendering

**Affected charts:** Everything below "All-Time Points For & Against" (choropleth, territory map, arc connections, chord diagram — all D3-based)

**Architecture:** `_populate_choropleth_data()` (~L2196) and `_populate_chord_data()` (~L2254) in `app.py` populate `store-choropleth-data` and `store-chord-data`. Clientside callbacks route these to 4 containers.

**Investigation approach (same pattern as Task 2D):**
1. Add `traceback.print_exc()` in the `except` blocks of both population callbacks.
2. Confirm both callbacks fire on `tab-alltime` — check their `Input('tabs', 'value')` trigger condition.
3. Open browser console on All-Time tab. Look for JS errors.
4. Temporarily add `print(f"[choropleth] data size: {len(str(data))}")` after data is built to confirm it's reaching the store.

**Fix:** Apply targeted fix based on findings. Common issues are the same as 2D above, plus: AllTime data (`core.AllTime()`) may fail to build if some years are missing from `_data`, which would cascade to empty stores.

**Verify:** All-Time tab → all 4 D3 charts below the Plotly charts should render (choropleth map, territory map, arc connections, chord diagram).

---

## Phase 3 — UI changes

---

### ✅ Task 3A — Replace Top Players threshold slider with a number input box

**Problem:** The current `dcc.Slider` for minimum points threshold is visually out of place. Replace it with a simple numeric input that blends with the chart card.

**File:** `webapp/app.py` — `_tab_players()` function (~L1258–1280)

**Current layout (the threshold row):**
```python
html.Div([
    html.Div('MIN TOTAL PTS', className='threshold-label'),
    html.Div([
        dcc.Slider(
            id='top-players-threshold',
            min=0, max=300, step=25, value=50,
            marks={0: '0', 100: '100', 200: '200', 300: '300'},
            tooltip={'placement': 'top', 'always_visible': True},
            className='threshold-slider',
        ),
    ], className='threshold-slider-wrap'),
], className='threshold-row'),
```

**Replace with:**
```python
html.Div([
    html.Span('Min pts threshold:', className='threshold-label'),
    dcc.Input(
        id='top-players-threshold',
        type='number',
        value=50,
        min=0,
        step=1,
        debounce=True,
        className='threshold-input',
        style={
            'width': '80px',
            'background': 'rgba(255,255,255,0.07)',
            'border': '1px solid rgba(189,226,255,0.25)',
            'borderRadius': '6px',
            'color': '#BDE2FF',
            'fontFamily': 'Courier New, monospace',
            'fontSize': '14px',
            'padding': '4px 8px',
            'marginLeft': '10px',
        }
    ),
], className='threshold-row', style={'display': 'flex', 'alignItems': 'center', 'margin': '8px 0 16px'}),
```

**Update the callback** (`_update_top_players` at ~L1750): The callback already reads `thresh` from the slider's value — `dcc.Input` with the same `id` will feed the same `Input('top-players-threshold', 'value')`. No callback changes needed as long as the id stays the same.

**CSS:** If the inline styles above aren't enough, add to `webapp/assets/style.css`:
```css
.threshold-input:focus {
    outline: none;
    border-color: rgba(189, 226, 255, 0.55);
}
```

**Verify:** Players tab → "Top Players" card. A small numeric input box should appear below the position toggle. Changing the value and pressing Enter (debounce) should reload the chart filtered to players above that threshold. The box should visually blend with the dark card background.

---

### ✅ Task 3B — Color team names in All-Time y-axis labels

**Problem:** Y-axis labels on All-Time charts contain team names. Want the team name portion colored to match the team's assigned color.

**Scope:** This applies to charts where the y-axis label contains a team name as part of a composite string (e.g., "**TeamA**\nW3 2023" in `HighestScoringLosers`, "TeamA w/ Patrick Mahomes" in `ForAgainstwithTeams`).

**Plotly limitation:** Native `yaxis.tickfont` applies one color to all tick labels. Per-label coloring requires replacing tick labels with colored `annotations`.

**Implementation approach (per chart):**

For charts like `HallofFame_Team`, `HallofFame_Player`, `HallofShame_Team`, `HighestScoringLosers`:

1. Hide the default y-axis tick labels: `fig.update_yaxes(showticklabels=False)`
2. Add one annotation per bar using `fig.add_annotation()` positioned at `x=0, xref='paper', xanchor='right'` for each y-category, with `font_color` set to the team's color from `self.teamcolors`.

**Example pattern:**
```python
fig.update_yaxes(showticklabels=False)
for i, (label, team) in enumerate(zip(y_labels, team_list)):
    color = self.teamcolors.get(team, '#BDE2FF')
    fig.add_annotation(
        x=0,
        y=label,
        xref='paper',
        yref='y',
        text=f'<b>{label}</b>',
        showarrow=False,
        xanchor='right',
        font=dict(color=color, size=16, family='Courier New'),
        xshift=-8,
    )
```

**Note:** This is the most complex change in the plan. Do this last. Each chart has different y-label formats and must be handled individually. Test one chart (suggest `HallofShame_Team` first, as it's the simplest) before applying to the others.

**Verify:** All-Time tab → hover over each bar chart. The team name portion of each y-axis label should appear in the team's assigned color. Non-team text (week, year, player name) stays in the default text color.

---

## Suggested execution order

1. **1A** (VS. annotations) — isolated, 2-line change, easy win
2. **1B** (font standardization) — multi-method but mechanical, no logic risk
3. **1C** (dtick) — 2-line change per chart
4. **2A** (ViolinPlayer data bug) — investigate first, fix second
5. **2B** (HighestScoringLosers missing bars) — investigate then fix
6. **2C** (ForAgainstwithTeams margin) — single layout change
7. **3A** (Top Players input) — UI swap, self-contained
8. **2D** (Season D3 charts) — requires browser debugging
9. **2E** (All-Time D3 charts) — same pattern as 2D
10. **3B** (colored y-axis labels) — most complex, do last

---

## Notes for the implementing agent

- After each task, restart the server and visually confirm the fix before moving on.
- The `_strip()` helper in `app.py` removes `width` and sets `height` — chart-level `update_layout` calls that set `height` in sleeper_core.py will be overridden. Margin and font changes are not stripped.
- `self.teamcolors` in `Season` and `AllTime` is a dict keyed by team username (display name), not roster_id. Ensure color lookups use the same key format as the y-label values.
- The `MARGIN_HBAR` constant in `sleeper_core.py` is `dict(t=130, b=100, l=200, r=40)`. Use it for consistency when adding left margin to charts — or update the constant itself if the standard changes.
- Don't change `WeeklyGraph()` annotations from hardcoded to dynamic unless the league size is expected to change. The 12-team structure has been stable.
