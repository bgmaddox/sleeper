# Legacy League — Interactive Web App Plan

## What We're Building

A hosted, password-protected interactive web experience for the Legacy League fantasy football league. League members visit a URL, log in with a shared password, and can explore the same custom-styled charts from the weekly write-up — but now interactive, filterable, and with animations.

---

## Why Not the Existing Dashboard

`FirstPyProject/` has a working Dash app, but the user was dissatisfied with the look. The problem: it uses the Bootstrap CYBORG dark theme with zero custom CSS. The charts have a polished custom aesthetic (`gridiron_ink` template — dark blue-grey, cyan text, Courier New) but the surrounding UI (buttons, dropdowns, sidebar) looks like a generic dark Bootstrap app. The fix is not to patch it — it's to rebuild the UI layer from scratch with CSS that matches the charts throughout.

The chart methods in `FirstPyProject/sleeper_core.py` are the golden asset and will be fully reused.

---

## Key Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Framework | Plotly Dash | Charts are Plotly figs — plug in directly; callbacks handle filtering |
| Styling | 100% custom CSS, no Bootstrap | Must match gridiron_ink throughout |
| Hosting | Render.com | Supports Python web apps, free tier available |
| Auth | Single shared password | Simple, no database needed |
| Data refresh | Manual script | Owner runs after each week; no automation complexity |
| New tab | Head-to-Head | Two-team comparison was the top interactivity request |
| Animation | Plotly `animation_frame` | Bar chart race for scores/standings, native to Plotly |

---

## Design Language

All CSS variables derived directly from the `gridiron_ink` Plotly template in `sleeper_core.py`:

```
Background (page):  #0f2030   (darkest)
Background (panel): #1e3d57   (cards/sidebar)
Background (chart): #163146   (matches chart bg exactly)
Text (primary):     #BDE2FF   (light cyan)
Text (secondary):   #7aa8c7   (muted cyan)
Borders/grid:       #3D5E78
Font:               Courier New, monospace
```

Every interactive control — dropdowns, sliders, buttons, checkboxes — will be styled to these variables. The result: UI chrome disappears into the aesthetic rather than fighting it.

---

## Tab Structure

### Existing tabs (ported from sleeper_core.py chart methods)

| Tab | What's in it |
|-----|-------------|
| **This Week** | Weekly matchup bar chart, points-over-weekend timeline, power rankings, luck chart |
| **Season** | Win progression snake graph (now animated!), points for/against, weekly wins breakdown, score distribution, bench strength, position radar |
| **Players** | Player point totals, violin distributions (starters vs bench), score trends, top performers |
| **All-Time** | Hall of Fame/Shame, highest-scoring losses, closest margins, cumulative team stats (2019–2025) |

### New tab

| Tab | What's in it |
|-----|-------------|
| **Head-to-Head** | Pick two teams → see their all-time record vs. each other, side-by-side score distributions, weekly score overlay, points for/against when matched up |

---

## New Features

### Animated SnakeGraph
The existing `Season.SnakeGraph()` shows cumulative win standings at a snapshot. Adding `animated=True` adds a Plotly play button that races through the season week by week — watching the standings evolve is exactly the kind of storytelling the user wants.

### Weekly Score Race (new chart)
A bar chart race (`WeeklyScoreRace()` — new method in `sleeper_core.py`) showing cumulative points by team, animated by week. Dramatic to watch, easy to implement with Plotly's `animation_frame` parameter.

### League Digest Landing Card
A hero section at the top of the app (above the tabs) showing the current week's headline stats: top scorer, biggest upset, tightest margin of victory. League members see something immediately engaging before they click into any tab.

### Styled Loading Spinners
Replace Dash's default `dcc.Loading` spinner with a custom CSS keyframe animation — a spinning ring in `#BDE2FF` that matches the `gridiron_ink` aesthetic. Defined in `assets/style.css`, no new library required.

### CSS Chart Reveal Animations
Add a `fade-in` keyframe to chart container divs in `style.css` so charts animate in as they load rather than popping in abruptly. ~10 lines of CSS.

### Deep-Link Support
Use `dcc.Location` to support URL query params so league members can share links to a specific week or comparison, e.g. `?week=9&tab=season`.

### Mobile Responsive
CSS grid layout: sidebar collapses to a top nav drawer on phones. Charts already respond to container width via Dash's `responsive=True`. Tap targets sized for thumbs.

---

## Password Protection

Login page renders before any content. On correct password submission, a signed cookie is set using `itsdangerous.URLSafeTimedSerializer` (no database, no user table). Sessions expire after 30 days. Password stored as `LEAGUE_PASSWORD` environment variable on Render.

---

## Project Structure (to be built)

```
Sleeper Project/
└── webapp/                     ← everything new goes here
    ├── app.py                  # Dash server, auth, root layout
    ├── requirements.txt
    ├── Procfile                # Render: "web: python app.py"
    ├── render.yaml             # Render deployment config
    ├── refresh.py              # Owner runs this to bust cache after each week
    ├── assets/
    │   └── style.css           # All custom CSS
    └── components/
        ├── login.py
        ├── sidebar.py
        └── tabs/
            ├── this_week.py
            ├── season.py
            ├── players.py
            ├── all_time.py
            └── head_to_head.py   ← new
```

`webapp/app.py` imports `sleeper_core` and `data_loader` from `../FirstPyProject/` — no code duplication.

---

## Deployment on Render.com

1. Sign up at render.com (free)
2. Connect GitHub repo (need to `git init` the project first)
3. Create a Web Service pointing to `webapp/`
4. Set env vars: `LEAGUE_PASSWORD`, `SECRET_KEY`
5. Optional: add a Render disk ($1/mo) to persist `.cache/` between deploys

Free tier sleeps after 15 min of inactivity — first visit has a ~15 second cold start. Upgrade to $7/mo for always-on if that's annoying.

URL will be something like `legacy-league.onrender.com`.

---

## Implementation Phases

### Phase 1 — Foundation
- [ ] Create `webapp/` scaffold
- [ ] Build CSS design system (all variables, layout, sidebar, tabs)
- [ ] Wire up auth (login page + session cookie)
- [ ] Port all 4 existing tabs using `sleeper_core.py` chart methods
- [ ] Verify local run looks right

### Phase 2 — New Features
- [ ] Head-to-Head tab
- [ ] Animated SnakeGraph (modify `sleeper_core.py`)
- [ ] WeeklyScoreRace animated chart (new method in `sleeper_core.py`)
- [ ] Mobile CSS pass

### Phase 3 — Deployment
- [ ] `git init` the project
- [ ] `Procfile` + `render.yaml`
- [ ] Render account setup, env vars, optional disk
- [ ] Test cold start, test on mobile
- [ ] Share URL with league

---

## Files That Will Change

| File | Action |
|------|--------|
| `webapp/` (entire folder) | Create from scratch |
| `FirstPyProject/sleeper_core.py` | Add `animated` param to `SnakeGraph()`, add `WeeklyScoreRace()` |
| `FirstPyProject/data_loader.py` | Minor updates if new cache path needed |
| `CLAUDE.md` | Already updated with this context |

**Not touching:** `FirstPyProject/dashboard.py`, `Sleeper_v2.ipynb`, `Sleeper.ipynb`

---

## One Remaining Decision

Custom domain (e.g. `legacyleague.gg` or similar) — can decide after deployment is working. Default Render subdomain is fine to start.
