# Legacy League — "Wow Factor" Implementation Plan

**Audience:** Full league, game-day first impressions. Desktop primary, mobile (portrait) required.  
**Goal:** Transform the dashboard from a functional analytics tool into something that feels like a broadcast product.  
**Constraint:** Keep all Python/Dash architecture. No framework swap.

---

## How to Execute This Plan (Agent Instructions)

Each phase below is designed to be run as a discrete subagent task. Always kill and restart the dev server after changes to verify. Phases that share no files can run in parallel — the execution diagram at the bottom is authoritative.

**Dev server command (always kill first):**
```bash
lsof -ti :8050 | xargs kill -9 2>/dev/null; sleep 1
cd webapp && source ../.venv/bin/activate && python app.py
```

---

## Phase 1 — Foundation: Plotly Template Fixes
**Priority: High | Effort: Low | Impact: High**  
**Parallelizable with: Phase 5, Phase 7**

The single biggest "pasted-on" problem is Plotly charts rendering with their own opaque backgrounds inside our dark cards. Fixing this makes all 42 existing charts feel native without touching a single chart method.

### 1A — Transparent chart backgrounds
In `FirstPyProject/sleeper_core.py`, find the `gridiron_ink` template definition and update:
```python
paper_bgcolor = 'rgba(0,0,0,0)'   # was '#163146'
plot_bgcolor  = 'rgba(0,0,0,0)'   # was '#163146'
```

### 1B — Global hover label style in the template
Add a `hoverlabel` block to the gridiron_ink template layout:
```python
hoverlabel=dict(
    bgcolor='#1a3a52',
    bordercolor='#2e526e',
    font=dict(family='Courier New', size=13, color='#BDE2FF'),
)
```
This eliminates the default gray hover boxes across all charts simultaneously.

### 1C — Font lock
Ensure `font=dict(family='Courier New', color='#BDE2FF')` is set at the template layout level. Fixes axis ticks, legends, and annotation fonts in one place.

### 1D — Legend style in template
```python
legend=dict(
    bgcolor='rgba(26,58,82,0.85)',
    bordercolor='#2e526e',
    borderwidth=1,
    font=dict(family='Courier New', size=12, color='#BDE2FF'),
)
```

---

## Phase 2 — Hover Redesign: Custom Hovertemplates
**Priority: High | Effort: Medium | Impact: High**  
**Depends on: Phase 1**

Phase 1 fixes the hover container. Phase 2 fixes the content. Plotly's default hover text is raw column names and raw numbers. Replace with rich, contextual content in each chart method.

### Always end templates with `<extra></extra>`
This removes the trace-name secondary box Plotly appends by default.

### Priority chart hovertemplates

**SnakeGraph** (line):
```python
hovertemplate="<b>%{fullData.name}</b><br>Week %{x}<br>Wins: <b>%{y}</b><extra></extra>"
```

**WeeklyGraph** (horizontal bar):
```python
hovertemplate="<b>%{y}</b><br>%{fullData.name}: <b>%{x:.2f} pts</b><extra></extra>"
```

**LuckChart** (scatter bubble):
```python
hovertemplate=(
    "<b>%{text}</b><br>"
    "Points For: <b>%{y:.1f}</b><br>"
    "Points Against: <b>%{x:.1f}</b><br>"
    "Wins: <b>%{marker.size}</b><extra></extra>"
)
```

**SeasonPointsForAgainst** (horizontal bar):
```python
hovertemplate="<b>%{y}</b><br>%{fullData.name}: <b>%{x:.1f}</b><extra></extra>"
```

**ScoreFrequencyGraph** (histogram):
```python
hovertemplate="Score range: <b>%{x}</b><br>Weeks in range: <b>%{y}</b><extra></extra>"
```

**ViolinPlayer** (violin):
```python
hovertemplate="<b>%{fullData.name}</b><br>Score: <b>%{y:.2f}</b><extra></extra>"
```

**PointsOverTheWeekend** (area/line):
```python
hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>Pts: <b>%{y:.2f}</b><extra></extra>"
```

**PositionStengthPolar** (radar):
```python
hovertemplate="<b>%{theta}</b><br>Strength: <b>%{r:.2f}</b><extra></extra>"
```

**Subagent task spec:** Read every chart method in `sleeper_core.py`. For each `px.*` or `go.*` call, add an appropriate `hovertemplate`. Apply via `update_traces()` or directly in the trace constructor.

---

## Phase 3 — Plotly Animations
**Priority: Medium | Effort: Medium | Impact: High**  
**Parallelizable with: Phase 2**

### 3A — SnakeGraph: Week-by-week animated build
```python
fig = px.line(df, x='Week', y='Total Wins', color='Team',
              animation_frame='Week',
              range_x=[0, week+1], range_y=[0, max_wins+1],
              template='gridiron_ink', line_shape='spline')

fig.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = 400
fig.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = 300
fig.layout.sliders[0].visible = False  # hide Plotly's slider; ours is the week slider
```

### 3B — WeeklyGraph + SeasonPointsForAgainst: Bar grow-in
```python
fig.update_layout(transition=dict(duration=500, easing='cubic-in-out'))
```

### 3C — LuckChart: Bubble inflate
```python
fig.update_layout(transition=dict(duration=600, easing='elastic-in-out'))
```

### 3D — ScoreTrends: Progressive line draw
Use Plotly's `frames` API to animate the line drawing left-to-right on first load. High-impact for the Players tab opener.

---

## Phase 4 — D3 Charts: Replacements & New Signature Visualizations
**Priority: High | Effort: High | Impact: Very High**  
**Depends on: Phase 1**

D3 is used only where animation is the primary value proposition and Plotly cannot match it. All D3 charts integrate via Dash **clientside callbacks** — the cleanest pattern for this stack.

### D3 Integration Pattern (applies to all 4D charts)
```python
# app.py — one dcc.Store per D3 chart, serialized from Python
dcc.Store(id='store-snake-data'),

app.clientside_callback(
    ClientsideFunction(namespace='d3charts', function_name='renderSnakeGraph'),
    Output('snake-graph-div', 'data-rendered'),
    Input('store-snake-data', 'data'),
)
```
```javascript
// webapp/assets/d3charts.js — all D3 functions live here
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.d3charts = {
    renderSnakeGraph: function(data) { /* ... */ return window.dash_clientside.no_update; },
    renderScoreRace:  function(data) { /* ... */ return window.dash_clientside.no_update; },
    renderBubbleMap:  function(data) { /* ... */ return window.dash_clientside.no_update; },
    renderHeatmap:    function(data) { /* ... */ return window.dash_clientside.no_update; },
    renderDraftBoard: function(data) { /* ... */ return window.dash_clientside.no_update; },
    renderChordDiagram: function(data) { /* ... */ return window.dash_clientside.no_update; },
};
```
D3 v7 is loaded via CDN in `webapp/assets/` as a local script file (not a CDN link in production — download and serve from assets).

---

### 4A — SnakeGraph → D3
**Tab: Season | Replaces existing Plotly chart | Prototype: `d3_snake_example.html`**

- Lines draw left-to-right over 2.5s on load and on week-change
- Vertical crosshair snaps to nearest week on hover
- Full-league ranked tooltip at each week
- End-of-line labels with mathematical collision avoidance
- Team colors passed from Python's `coastal_colorway` via `dcc.Store`
- Replay button re-triggers animation

**Data shape:**
```python
snake_data = {
    'teams': ['Maddox', ...],
    'colors': ['#4EC9FF', ...],
    'weeks': [0, 1, 2, ..., current_week],
    'series': {'Maddox': [0, 1, 1, 2, ...], ...}
}
```

---

### 4B — Score Race → D3
**Tab: Season | Brand new chart**

An animated bar chart race showing cumulative points scored, automatically playing week-by-week. The bars reorder and grow as the season progresses — the visual effect of watching the standings evolve in real time.

- 10 horizontal bars per team, colored by team color
- Bars animate width (cumulative score grows) and y-position (ranking reorder)
- Week counter in corner ticks up as the race plays
- Auto-plays on tab load; pauses on hover; week slider scrubs to any frame
- Winner bar gets a subtle gold pulse at the end

**Data shape:**
```python
race_data = {
    'weeks': [1, 2, ..., 18],
    'teams': ['Maddox', ...],
    'colors': [...],
    'cumulative': {'Maddox': [134.2, 267.8, ...], ...}
}
```

---

### 4C — NFL Team Contribution Bubble Map → D3
**Tab: This Week | Brand new chart**

A US map (topojson/albersUsa projection) with a bubble placed at each NFL team's stadium. Bubble size = total fantasy points generated by players on that NFL team for your league during the selected week. Color encodes whether that team ran hot (above their season average) or cold.

This is the most immediately engaging chart for casual league members — they can literally see where their points came from on a map.

- Bubbles animate in (scale from 0) when the week changes
- Hover shows NFL team name, total fantasy pts, top contributing player
- Animated transition as week slider moves — bubbles breathe in and out
- NFL team stadium coordinates are a hardcoded 32-row lookup dict (static, never changes)

**Data shape (Python serializes per week):**
```python
bubble_data = {
    'week': 7,
    'teams': [
        {
            'nfl_team': 'KC',
            'lat': 39.0489, 'lon': -94.4839,
            'fantasy_pts': 87.4,
            'season_avg': 61.2,
            'top_player': 'Patrick Mahomes',
            'top_player_pts': 38.1
        },
        ...  # one entry per NFL team with ≥1 rostered player
    ]
}
```

**Data computation (add to `sleeper_core.py` or `app.py`):**
```python
# From BreakoutDict[year][week], group starters by recent_team
nfl_contribution = (
    breakout_df[breakout_df['starter'] == 1]
    .groupby('recent_team')
    .agg(
        fantasy_pts=('points', 'sum'),
        top_player=('player', lambda x: x.loc[breakout_df['points'].idxmax()]),
        top_player_pts=('points', 'max')
    )
    .reset_index()
)
```

---

### 4D — Score Heatmap Calendar → D3
**Tab: Season | Brand new chart**

A 10-team × 18-week grid. Each cell is colored by how that team scored relative to their own season average — deep green for a great week, deep red for a disaster. Cells animate in left-to-right as weeks progress, giving the feel of a season being revealed.

Low effort for D3, high information density. Immediately shows hot streaks, cold spells, and bye-week craters at a glance.

- Cell color: diverging scale (red → neutral → green), anchored to each team's own mean
- Hover: shows exact score, opponent, W/L result, and points vs. average
- Week axis across the top, team axis down the left side
- Cells animate in column-by-column (week by week) on load
- Clicking a cell could highlight that team's row

**Data shape:**
```python
heatmap_data = {
    'teams': ['Maddox', ...],          # ordered by final record
    'weeks': [1, 2, ..., max_week],
    'scores': {
        'Maddox': {
            1: {'score': 134.2, 'avg': 121.4, 'won': True, 'opp': 'Rach', 'opp_score': 98.3},
            2: {...},
            ...
        },
        ...
    }
}
```

---

### 4E — Draft Board Replay → D3
**Tab: All-Time | Brand new chart**

Animates the draft in snake order: picks appear one at a time in their board position (round × pick slot). Team name and player name appear as each pick lands. After the full board is revealed, it transitions to a **"draft value realized"** overlay — each cell recolors by actual fantasy points scored (gold for elite, red for bust, gray for mediocre).

This chart tells a story your league members will replay every year. The reveal of who "won" the draft in hindsight is the narrative hook.

- Draft board is a round × pick grid (e.g., 15 rounds × 10 picks = 150 cells)
- Picks animate in at ~300ms each, snake order
- After full reveal: cells morph color to show realized value vs. draft position expectation
- Hover on any cell: player name, draft round/pick, total season points, position rank
- Draft data already available via `League.Draft()` from Sleeper API

**Data shape:**
```python
draft_data = {
    'year': 2024,
    'rounds': 15,
    'picks': [
        {
            'round': 1, 'pick': 1,
            'team': 'Maddox',
            'player': 'Christian McCaffrey',
            'position': 'RB',
            'total_pts': 287.4,
            'position_rank': 1,    # among all players at that position in the league
            'value_tier': 'elite'  # 'elite' | 'solid' | 'average' | 'bust'
        },
        ...
    ]
}
```

---

### 4F — Chord Diagram: NFL Franchise → Fantasy Owner → D3
**Tab: All-Time | Brand new chart | Highest Wow, Highest Effort**

A circular chord diagram where one half of the ring is the 32 NFL franchises and the other half is the 10 fantasy owners. Arcs flow between them, thickness proportional to total fantasy points generated. Each arc is colored by the fantasy owner's team color.

When someone says "I live and die by the Chiefs," this chart proves or disproves it with a thick arc between Kansas City and their name. D3 has a first-class `d3.chord()` layout built for exactly this.

- Arcs draw themselves on load, animating from 0 thickness to full
- Outer NFL team labels and fantasy owner labels around the ring
- Hover highlights all arcs connected to a team or owner, dims all others
- Filter by year (multi-year view by default, single year via dropdown)
- Only NFL teams with ≥1 fantasy point contributed are shown (eliminates clutter)

**Data shape:**
```python
chord_data = {
    'nfl_teams': ['KC', 'BUF', 'SF', ...],     # only teams with contributions
    'fantasy_owners': ['Maddox', 'Rach', ...],
    'colors': {
        'Maddox': '#4EC9FF',
        'Rach': '#FF6B6B',
        ...
    },
    # matrix[nfl_team_idx][owner_idx] = total fantasy points
    'matrix': [[87.4, 12.1, ...], ...]
}
```

**Note:** Build this last within Phase 4. It requires the most D3 expertise and has the most moving parts. Treat it as its own discrete subagent task.

---

### 4G — LuckChart → D3 (Optional Upgrade)
**Tab: This Week | Upgrades existing Plotly chart**

Only pursue if the Phase 3C Plotly transition on LuckChart feels insufficient after implementation. If done:
- Bubbles inflate from the chart center to their positions
- Quadrant lines and labels draw in after bubbles settle
- Crosshair tooltip follows cursor (not locked to bubble position like Plotly)

---

## Phase 5 — Page Animations (CSS + JS)
**Priority: Medium | Effort: Low-Medium | Impact: Medium-High**  
**Parallelizable with: Phase 1, Phase 7**

### 5A — Staggered card entry
```css
.chart-card:nth-child(1) { animation-delay: 0.00s; }
.chart-card:nth-child(2) { animation-delay: 0.08s; }
.chart-card:nth-child(3) { animation-delay: 0.16s; }
.chart-card:nth-child(4) { animation-delay: 0.24s; }
.chart-card:nth-child(5) { animation-delay: 0.32s; }
.chart-card:nth-child(6) { animation-delay: 0.40s; }
```

### 5B — Tab switch fade
```css
@keyframes tab-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.tab-content-area { animation: tab-fade-in 0.25s ease both; }
```
Trigger by toggling a key on `tab-content-area` div on tab change.

### 5C — Digest stat counter animation
```javascript
// webapp/assets/counter.js
function animateCounter(el, target, decimals, duration) {
    const start = performance.now();
    const update = (now) => {
        const elapsed = Math.min((now - start) / duration, 1);
        el.textContent = (elapsed * target).toFixed(decimals);
        if (elapsed < 1) requestAnimationFrame(update);
    };
    requestAnimationFrame(update);
}
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-count]').forEach(el => {
        animateCounter(el, +el.dataset.count, +el.dataset.decimals || 0, 800);
    });
});
```
Modify `_digest()` in `app.py` to add `data-count` and `data-decimals` attributes to numeric value elements.

### 5D — Topbar accent shimmer (plays once on load)
```css
@keyframes shimmer {
  0%   { background-position: -200% center; }
  100% { background-position:  200% center; }
}
.topbar-title {
  background: linear-gradient(90deg, #FFC300 30%, #ffe066 50%, #FFC300 70%);
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shimmer 2.5s linear 1;
}
```

### 5E — Power Rankings efficiency bar animate-in
The `.pr-bar-fill` already has `transition: width 0.45s ease`. Start bars at 0% width via CSS; a clientside callback sets final width via inline style after a short delay so the transition fires on mount.

### 5F — Mobile: bottom tab bar
```css
@media (max-width: 768px) {
  .main-tabs {
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 500;
    background: var(--bg-panel);
    border-top: 2px solid var(--accent);
    border-bottom: none;
    justify-content: space-around;
    padding: 0 !important;
  }
  .tab { flex: 1; text-align: center; padding: 12px 4px !important; font-size: 0.65rem !important; }
  .tab-content-area { padding-bottom: 72px; }
}
```

---

## Phase 6 — Continuity Tweaks (Small Polish)
**Priority: Low-Medium | Effort: Low | Impact: Medium**  
**Can run any time after Phase 1**

| Chart | Issue | Fix |
|-------|-------|-----|
| WeeklyGraph | "VS." annotations hardcoded — breaks on ≠6 matchups | Calculate y positions from matchup count |
| PositionStengthPolar | Radar subplot titles render in default white | Set `annotation.font.color = '#BDE2FF'` for all subplot titles |
| ViolinPlayer | 1000px height — painful to scroll past | Cap at 700px or add scroll within card |
| All bar charts | `marker_line_color='black'` is harsh against transparent bg | Change to `'rgba(0,0,0,0.25)'` |
| ScoreFrequencyGraph | Histogram rug overflows card bottom | Add `margin=dict(b=40)` |
| LuckChart | Quadrant labels may disappear on transparent bg | Add `bgcolor='rgba(26,58,82,0.7)'` to annotation text |

---

## Phase 7 — New Analytics Charts (Plotly)
**Priority: Medium | Effort: Low-Medium | Impact: High**  
**Parallelizable with: Phase 1, Phase 5**  
**Data source: `stats_player_week_2025.csv` columns: `passing_epa`, `rushing_epa`, `receiving_epa`, `target_share`, `wopr`, `fantasy_points`**

These are brand-new charts that expose the EPA and advanced efficiency data already in your CSV — data your league currently has no visibility into.

---

### 7A — EPA vs Fantasy Points Scatter
**Tab: Players**

Scatter plot where x = total EPA of a fantasy team's starters that week, y = fantasy points scored. One dot per team per week. Do teams with high-EPA lineups actually score more? Answered visually.

- Color by team, size by margin of victory
- Add a linear regression trend line
- Hover: team name, week, EPA total, fantasy score, W/L
- `passing_epa + rushing_epa + receiving_epa` summed per starter roster per week

**Data computation:**
```python
# From BreakoutSeason, join to weekly stats CSV on player_id + week
# Sum EPA columns for starters per team per week
# Join to AllMatchesDict for the total score
```

---

### 7B — Target Share / WOPR Treemap
**Tab: Players**

For each fantasy owner, a treemap of their WR and TE starters sized by `wopr` (Weighted Opportunity Rating — combines target share and air yards share). Instantly answers: are you winning on efficiency or riding garbage targets?

- One treemap per team (or a faceted grid of all 10 — use a dropdown to filter)
- Cell size = WOPR, cell color = fantasy points that player scored
- Hover: player name, target share, air yards share, WOPR, fantasy pts

**Plotly implementation:**
```python
fig = px.treemap(df, path=['team', 'player'], values='wopr',
                 color='fantasy_points', color_continuous_scale='RdYlGn',
                 template='gridiron_ink')
```

---

### 7C — Waiver Wire Bump Chart
**Tab: Season**

A bump chart (rank by cumulative points over time) for the top 15 undrafted/waiver-wire players. Shows which players went from unknown to season-changers — the narrative of who your league should have picked up.

Uses the same Plotly spline line format as SnakeGraph — nearly zero additional build cost since the chart type is identical. Rank = 1 at top, 15 at bottom. Lines cross and swap as the season progresses.

- Filter to players not rostered at the start of the season (draft data provides the exclusion list)
- Color by position (QB/RB/WR/TE)
- Hover: player name, position, week rank, cumulative points

---

### 7D — Lineup Efficiency Waterfall
**Tab: This Week**

For each team, a waterfall chart showing Actual Score → Optimal Score with the gap labeled "left on bench." Visually answers the question every fantasy player has after a loss: how much did your lineup management cost you?

- One waterfall bar per team, sorted by gap size (biggest self-inflicted damage first)
- Bar = actual score; ghost bar extends to optimal; gap highlighted in red
- Label: "+X.X pts left on bench"
- Hover: actual, optimal, efficiency %, key benched player who should have started

**Data:** `OptimalScoresByYear` is already computed in `sleeper_core.py`. Join with actual scores from `AllMatchesDict`.

```python
# In sleeper_core.py Season class — add method:
def LineupEfficiency(self, week):
    actuals  = {team: score for team, score in AllMatchesDict[self.year][week].groupby('Team')['Total'].sum().items()}
    optimals = OptimalScoresByYear[self.year][week]
    df = pd.DataFrame({'Team': list(actuals), 'Actual': list(actuals.values()),
                       'Optimal': [optimals[t] for t in actuals]})
    df['Gap'] = df['Optimal'] - df['Actual']
    df['Efficiency'] = df['Actual'] / df['Optimal']
    return df.sort_values('Gap', ascending=False)
```

---

## Execution Order (Recommended for Subagents)

```
┌──────────────────────────────────────────────────────────────────┐
│  PARALLEL BATCH 1 (fully independent — start all simultaneously)  │
│                                                                    │
│  Agent A: Phase 1  — Template fixes (sleeper_core.py)             │
│  Agent B: Phase 5  — Page animations (style.css, counter.js)      │
│  Agent C: Phase 7A — EPA Scatter (new chart, sleeper_core.py)     │
│  Agent D: Phase 7B — WOPR Treemap (new chart, sleeper_core.py)    │
│  Agent E: Phase 7C — Waiver Wire Bump (new chart, sleeper_core.py)│
└───────────────┬──────────────────────────────────────────────────┘
                │ Wait for Agent A (Phase 1) to finish
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  PARALLEL BATCH 2                                                  │
│                                                                    │
│  Agent F: Phase 2  — Hovertemplates (sleeper_core.py)             │
│  Agent G: Phase 3  — Plotly animations (sleeper_core.py)          │
│  Agent H: Phase 7D — Lineup Efficiency Waterfall (needs opt data) │
└───────────────┬──────────────────────────────────────────────────┘
                │ Verify server runs clean before proceeding
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  PARALLEL BATCH 3 — First D3 wave (simpler charts)               │
│                                                                    │
│  Agent I: Phase 4A — D3 SnakeGraph (replaces Plotly chart)        │
│  Agent J: Phase 4B — D3 Score Race (new, Season tab)              │
│  Agent K: Phase 4D — D3 Score Heatmap (new, Season tab)           │
└───────────────┬──────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  PARALLEL BATCH 4 — Second D3 wave (complex/new data)            │
│                                                                    │
│  Agent L: Phase 4C — D3 NFL Bubble Map (needs stadium coords)     │
│  Agent M: Phase 4E — D3 Draft Board Replay (All-Time tab)         │
└───────────────┬──────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  SEQUENTIAL — Most complex D3 chart, own task                     │
│                                                                    │
│  Agent N: Phase 4F — D3 Chord Diagram (All-Time tab)              │
│           Review output before merging to main                    │
└───────────────┬──────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  CLEANUP (any agent)                                              │
│  Phase 6 — Continuity tweaks                                      │
│  Phase 4G — LuckChart D3 upgrade (only if Phase 3C fell short)   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tab Placement Summary

| Tab | New/Changed Charts Added |
|-----|--------------------------|
| **This Week** | D3 NFL Bubble Map (4C), Lineup Efficiency Waterfall (7D) |
| **Season** | D3 SnakeGraph (4A), D3 Score Race (4B), D3 Score Heatmap (4D), Waiver Wire Bump (7C) |
| **Players** | EPA Scatter (7A), WOPR Treemap (7B) |
| **All-Time** | D3 Draft Board Replay (4E), D3 Chord Diagram (4F) |
| **Head-to-Head** | No new charts — existing H2H charts benefit from Phase 1+2 polish |

---

## Files Modified by Phase

| Phase | Files Touched |
|-------|--------------|
| 1 | `FirstPyProject/sleeper_core.py` (template dict only) |
| 2 | `FirstPyProject/sleeper_core.py` (all chart methods — hovertemplates) |
| 3 | `FirstPyProject/sleeper_core.py` (SnakeGraph, WeeklyGraph, LuckChart, ScoreTrends) |
| 4A–4G | `webapp/app.py` (stores + clientside callbacks), `webapp/assets/d3charts.js` (new) |
| 4C | `webapp/assets/stadium_coords.js` (new — 32-team lookup dict) |
| 5 | `webapp/assets/style.css`, `webapp/assets/counter.js` (new), `webapp/app.py` (minor) |
| 6 | `FirstPyProject/sleeper_core.py` (targeted per-chart fixes) |
| 7A–7D | `FirstPyProject/sleeper_core.py` (new chart methods), `webapp/app.py` (tab render functions) |

---

## Definition of Done

**Foundation**
- [ ] All 42 Plotly charts render with transparent backgrounds
- [ ] All hover tooltips match site color scheme (dark bg, gold border, monospace font)
- [ ] Custom hovertemplates on all priority charts

**Plotly Animations**
- [ ] SnakeGraph animates week-by-week as the slider moves
- [ ] WeeklyGraph and SeasonPointsForAgainst bars grow in on render
- [ ] LuckChart bubbles inflate on load

**D3 Charts**
- [ ] D3 SnakeGraph: lines draw left-to-right with crosshair hover (Season tab)
- [ ] D3 Score Race: bar chart race plays on Season tab load
- [ ] D3 NFL Bubble Map: US map with animated bubbles renders on This Week tab
- [ ] D3 Score Heatmap: 10×18 grid animates in week-by-week (Season tab)
- [ ] D3 Draft Board Replay: animated draft + value overlay (All-Time tab)
- [ ] D3 Chord Diagram: NFL → owner arcs with hover highlighting (All-Time tab)

**New Analytics Charts**
- [ ] EPA vs Fantasy Points scatter exists on Players tab
- [ ] WOPR Treemap exists on Players tab
- [ ] Waiver Wire Bump Chart exists on Season tab
- [ ] Lineup Efficiency Waterfall exists on This Week tab

**Page Polish**
- [ ] Chart cards stagger-fade in on tab switch
- [ ] Digest stats count up from zero on load
- [ ] Topbar title shimmers once on first load
- [ ] Mobile tab bar fixed to bottom of screen
- [ ] All charts verified at http://localhost:8050 on desktop Chrome + iOS Safari
