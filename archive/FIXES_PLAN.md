# UI Fixes Plan
_Agent-ready implementation guide. Each issue is self-contained with file locations and specific changes._

---

## Season Tab

### S-1. ✅ Points For & Against — Y-axis label clipping
**Fixed:** `webapp/app.py` → `_tab_season()`
- `_strip()` was overriding the chart's own `l=230` margin to `l=80`. Now applies `_strip(fig, 680)` then immediately re-calls `.update_layout(margin=dict(l=250, t=60, b=80))` to restore left space.

---

### S-2. ✅ Position Strength — replaced polar grid with heatmap
**Fixed:** `sleeper_core.py` → new `PositionStrengthHeatmap()` method; `webapp/app.py` → `_tab_season()`
- Added `PositionStrengthHeatmap()` to `Season` class: builds a `go.Heatmap` with positions on x-axis, teams on y-axis sorted by total z-score.
- Color scale: red (below average) → neutral blue → green (above average), centered at 0.
- Each cell shows z-score and raw avg pts. Team names on y-axis use per-team colors.
- Height is dynamic: `max(500, n_teams * 52 + 100)`. Left margin preserved at `l=200` (bypasses `_strip()`).
- `_tab_season()` now calls `PositionStrengthHeatmap()` instead of `PositionStengthPolar()`.

---

### S-3. Score Race + Heatmap — intermittent loading
**Partial fix:** `webapp/assets/d3charts.js` → `renderScoreRace()`, `renderHeatmap()`
- Increased `_waitForEl` timeout from 12 s → **20 s** on both.
- Root cause may also involve data timing — add `print(f'[d3] race_data built…')` logging in `_populate_d3_stores()` to confirm data is flowing if issue persists after test.

---

## Players Tab

### P-1. ✅ Score Distribution (Violin) — blank chart
**Fixed:** `sleeper_core.py` → `ViolinPlayer()` ~line 2110; `webapp/app.py` → `_tab_players()`
- Added empty-df guard before `px.violin()`: returns a friendly "No data" figure when df is empty.
- Changed team color lookup from `self.teamcolors[title_text]` → `self.teamcolors.get(title_text, '#BDE2FF')` to prevent `KeyError` from mismatched team names.
- Fixed annotation indentation (was inconsistently indented inside the for-loop).
- Added `traceback.print_exc()` in the violin except block.

---

### P-4. ✅ Weekly Score Trends — chart below rendering on top
**Fixed:** `webapp/app.py` → `_tab_players()`
- Changed to explicit `html.Div` card with `style={'minHeight': '660px'}` to reserve layout space before Plotly renders.
- Set `config={'responsive': False}` on the graph to prevent auto-resize jitter.
- Height increased from 580 → 600.

---

### P-5. ✅ EPA Chart — x-axis label overlap
**Fixed:** `sleeper_core.py` → `EPAScatter()`
- Increased `title_standoff` from `20` → `40` and bottom margin from `80` → `100`.

---

### P-6. ✅ Top Players — pill-style threshold filter
**Fixed:** `webapp/app.py` → `_tab_players()`; `webapp/assets/style.css`
- Replaced plain `html.Label + dcc.Slider` with a styled `.threshold-row` container.
- Label changed from "Min games played:" to a gold pill badge reading **"MIN TOTAL PTS"**.
- Added CSS classes `.threshold-row`, `.threshold-label`, `.threshold-slider-wrap`, `.threshold-slider` with:
  - Gold (`#FFC300`) track, handle glow, and tooltip border
  - Pill badge with amber background and border
  - Courier New font throughout
- Slider range expanded: 0–300, step 25, marks at 0/100/200/300.

---

## All-Time Tab

### A-1. ✅ Draft Board Replay — moved to Season tab
**Fixed:** `webapp/app.py` → `_tab_alltime()`, `_tab_season()`, `_populate_draft_data()`; `webapp/assets/d3charts.js` → `renderDraftBoard()`
- Removed Draft Board card from `_tab_alltime()`.
- Added Draft Board card at the bottom of `_tab_season()`.
- `_populate_draft_data()`: tab guard changed `tab-alltime` → `tab-season`.
- `renderDraftBoard()` JS: tab guard changed `tab-alltime` → `tab-season`; retry callback now correctly passes `tabValue`; timeout increased to 20 s.

---

### A-2. ✅ Hall of Fame bar charts — names clipped + team colors
**Fixed:** `webapp/app.py` → `_tab_alltime()` → `_alltime_meta` loop
- After `_strip(fig, 700)`, applies `.update_layout(margin=dict(l=280, t=60, b=80))` for HallofFame and HallofShame charts.
- Team colors already wired via `color_discrete_map=self.teamcolors` and `AllTime.SetTeamColors()` using `get_alltime_teamcolors()` — confirmed correct.
- Added `traceback.print_exc()` in the except block.

---

### A-3. ✅ Half-width All-Time charts → full width
**Fixed:** `webapp/app.py` → `_tab_alltime()` → `_alltime_meta`
- Changed `half=True` → `half=False` for: HallofShame_Team, HighestScoringLosers, SmallestMargins, ForAgainstwithTeams.
- All six All-Time charts now render full width.

---

### A-4. Bottom 4 D3 graphs (Choropleth, Territory, Arc, Chord) — not loading
**Partial fix:** `webapp/assets/d3charts.js`; `webapp/app.py`
- Increased `_waitForEl` timeout from 3 s → **20 s** in all four renderers.
- Fixed `renderChordDiagram` retry: was passing `data` only; now passes `data, tabValue`.
- Added `traceback.print_exc()` to both `_populate_choropleth_data()` and `_populate_chord_data()` in `app.py`.
- If charts still don't load: open browser DevTools console on the All-Time tab and look for `[Choropleth]`, `[Chord]` log output to isolate whether the issue is data, timing, or the CDN atlas fetch.

---

## Remaining from Previous Plan

### Luck Chart — title overlap + corner label size (partial)
- **Title overlap ("This Week Only"):** Investigate whether `LuckChart()` sets an internal fig title in the This Week codepath; if so, set `title=None` in the callback.
- **Corner label size:** Standardize YTD (currently 20) and This Week (currently 18) both to 18.
