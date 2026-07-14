# Phase 4 — Styling & Front-End Review

**Question:** Is the visual layer (`webapp/assets/style.css` 1,361 lines, `webapp/assets/d3charts.js` 1,487 lines, the `gridiron_ink` Plotly template) coherent, and does the app hold up in the browser?

**Verdict: Yes, mostly.** The design system is unusually coherent for a hobby project — one palette, defined once in `:root`, echoed in the Plotly template and D3 renderers. The live app loaded all 8 tabs with **zero console errors, zero warnings, and zero error cards**. The real problems are: a handful of undefined CSS variables silently breaking the Playoffs card styling, heavy copy-paste duplication and listener/timer leaks in `d3charts.js`, and a mobile bottom-nav that renders as a huge vertical stack instead of a tab bar.

Live check method: server started per CLAUDE.md, login OK, all 8 tabs driven via Playwright (`browser_evaluate` tab-cycling + snapshots; 2 screenshots for the mobile question only). Graph counts per tab: This Week 6, Season 8, Players 6, All-Time 6, Playoffs 7, Side Bets 14, Survivor 6, Head-to-Head 2 (+4 stat cards). Chart smoke tests: `pytest tests/test_charts.py` → 36 passed.

---

## Findings (ranked by impact)

### 1. Undefined CSS variables — Playoffs & Side Bets cards silently lose their styling
Four variables are used via `var()` but never defined in `:root` (`style.css:6-24`):

| Variable | Where used | Effect |
|----------|-----------|--------|
| `--grid` | `style.css:1186, 1190, 1191, 1204, 1205` (playoff column header, round label, matchup card, divider, stats) | All borders in the Playoffs bracket cards resolve to **invalid → no border color** (falls back to `currentColor`) |
| `--text` | `style.css:1190, 1198, 1199, 1200, 1205` (playoff team name/score/eff, stats) | Text color falls back to inherited — happens to look OK but is luck, not design |
| `--card-bg` | `style.css:1319` (`.sidebet-nav-btn`) | Week-nav buttons get no background (invalid value → transparent) |
| `--chip-color` | `.team-chip` rules (`style.css:280-317`) | **Intentional** — set inline per chip from Python; not a bug |

The Playoffs CSS block (lines 1182–1218) was clearly written against a different variable naming scheme (`--grid`/`--text` instead of `--border`/`--text-main`). Fix is a 10-line find/replace.

### 2. The "41 dead classes" claim is real but overstated — ~19 are genuinely dead, ~22 are framework selectors
The grep (201 unique class selectors in CSS vs. `app.py` + `d3charts.js`) reproduces exactly 41 non-matches. But the prior pass didn't separate third-party DOM selectors from dead code:

**Not dead — they style Dash/library-generated DOM** (22): `Select-*` ×10 (react-select dropdowns, `style.css:541-568`), `rc-slider-*` ×8 (`style.css:572-647`), `js-plotly-plot`, `plot-container`, `dash-graph` (`style.css:925-928`), `is-focused`/`is-selected`.

**Genuinely dead** (~19), safe to delete:
- `.threshold-row`, `.threshold-label`, `.threshold-slider-wrap`, `.threshold-slider` — Top Players threshold filter, feature removed (`style.css:590-647`, ~58 lines)
- `.survivor-alive-badge`, `.survivor-out-badge`, `.survivor-revived-badge` (`style.css:842-844`) — Survivor status now drawn inside Plotly figures
- `.ctrl-team-header`, `.ctrl-teams`, `.ctrl-teams-row` (`style.css:239-253`) — old team-dropdown layout, replaced by team chips
- `.pr-th-sorted-asc`, `.pr-th-sorted-desc` (`style.css:1097-1098`) — sort-state classes never emitted by `app.py`'s Power Rankings table (sort arrows render but never show active state)
- `.btn-group` (`style.css:409`), `.tab-selected` (`style.css:745`, duplicate of `.tab--selected`), `.playoff-icon--star` (`style.css:1208-1210`; only `--trophy` is used, `app.py:1266`)
- The whole "Bootstrap row shim" block: `.row`, `.g-3`, `.col-12`, `.col-xl-6` (`style.css:1159-1167`) — the comment claims dcc.Tabs emits these classes; nothing in `app.py` or rendered DOM uses them

Roughly 100–120 lines of CSS can go. Low urgency, but the `pr-th-sorted-*` pair is worth a decision: either wire the sort-state class up in `app.py` or delete the arrows.

### 3. Mobile bottom-nav renders as a full-height vertical stack (verified at 390×844)
`style.css:1169-1180` pins `.main-tabs` to `position: fixed; bottom: 0` intending an app-style tab bar with `justify-content: space-around`. In the browser the computed style is `flex-direction: column` (Dash's `dcc.Tabs` sets its own vertical mobile layout that the override doesn't defeat), so **all 8 tabs stack vertically, each 384px wide, covering roughly the bottom half of a phone screen** and overlaying content. Screenshot confirmed. Also at 390px:
- The team-chip row (`style.css:261-268`, `flex-wrap: nowrap`) clips — the last chips ("RO", "IN") run off the controls card edge.
- `.tab-content-area { padding-bottom: 72px }` (`style.css:1179`) assumes a 1-row bar; with the actual stacked nav, content is buried.

Mobile handling *does exist* (three `@media` blocks: 869–873, 1037–1045, 1150–1157, 1169–1180, 1215–1218, 1265–1267 — column collapse, PR-table column hiding, digest stacking) and the column collapses work. The bottom nav is the one genuinely broken piece. Fix: `flex-direction: row !important` on `.main-tabs` in the 768px block, or drop the fixed-bottom idea and let tabs scroll horizontally.

### 4. `d3charts.js`: event-listener and timer leaks in `renderScoreRace`
`d3charts.js:341-343` — every render adds fresh `mouseenter`/`mouseleave` listeners to `#d3-race-container`. The container element persists across re-renders (only `innerHTML` is cleared, `d3charts.js:244`), so listeners **accumulate** each time the Season tab re-renders (year change, team-filter change). Each stale closure holds its own `playing`/`currentFrame` arrays.
`d3charts.js:329-338` — the `d3.interval` autoplay timer is only stopped when the animation reaches the final week. A re-render mid-animation orphans the old timer, which keeps firing every 800ms and running D3 transitions against **detached DOM nodes**. Practical impact is modest (friends-league, page reloads often) but it's a real leak, and the fix is small: store the timer/listeners on the container and tear down at the top of the renderer.

### 5. `d3charts.js`: unbounded retry stacking in `_waitForEl`
`d3charts.js:6-10` polls every 100ms for the target container; `renderScoreRace` passes `maxMs = 20000` (`d3charts.js:240` — 200 potential timeouts), others 3000. If the data store updates while the container is absent (tab not yet mounted), each callback invocation spawns its **own independent retry chain**, and when the container finally appears, every queued chain fires a full render back-to-back. No cancellation token, no dedupe. This is the likely mechanism behind any "chart rendered twice / animation restarts" jank on slow tab loads.

### 6. `d3charts.js`: 9 renderers, ~80% shared boilerplate, all copy-pasted
Every renderer (`d3charts.js:17, 234, 351, 470, 573, 722, 895, 1097, 1342`) repeats: the tab-guard + null-data guard, the container lookup + `_waitForEl` fallback + rebind dance (e.g. `d3charts.js:20-25`), margin/width/height with the same `<=0 → hardcoded fallback` pattern (`33-36`), SVG scaffold, axis styling (`fill: '#BDE2FF'`, `font-family: 'Courier New'`, `font-size: 11px`, `stroke: '#3D5E78'` — repeated ~30 times across the file), and a hand-built tooltip div (9 nearly identical copies: `174, 408, 517, 624, 756, 943, 1179, 1394`). A ~40-line helper module (`setupChart(id, tabValue, margins)` + `makeTooltip(container)` + a CSS class for axis text) would cut the file by several hundred lines and make the theme changeable in one place. Error handling is also inconsistent: `renderScoreRace` wraps in try/catch (`243, 346`), `renderSnakeGraph` does not — an exception there propagates into Dash's clientside callback machinery.

### 7. Theme colors are defined three times — CSS, Plotly template, and D3 string literals
The palette lives in `:root` (`style.css:6-24`), in `sleeper_core.py` (`ink_font`/`ink_text_color`/grid color, lines 48-113), and as raw hex strings sprinkled through `d3charts.js` (`#BDE2FF`, `#3D5E78`, `#6a9abf`, `#FFC300` — dozens of occurrences, e.g. `66, 75, 87, 280, 289`). D3 renders into the page, so it could read `getComputedStyle(document.documentElement).getPropertyValue('--text-main')` — or simpler, style axis text/lines with CSS classes. Today a palette tweak means editing three files. The colors *do* currently agree, which is why the app looks coherent.

### 8. Hardcoded hex colors inside style.css bypass its own variables
~15 hex literals appear outside `:root`: gradient stops `#0a1825/#1c3d55` (`style.css:69`), `#FFC300/#ffe066` in the shimmer title (`92`), toggle-checked text `#0d1e2e` (`389`, also `428`), dropdown hover states `#1e4060/#24516e` (`554-555`), digest gradient `#1a3a52/#163146/#12293e` (`672`), playoff matchup `#1C3C54` (`1191` — a *near-miss* for `--bg-card` `#1a3a52`), error text `#e87779` (`1022`), sidebet banner `#FFC300` (`1274`), and the off-theme flat-UI trio `#2ecc71/#e74c3c/#f39c12` (`842-844`, dead anyway). Most are deliberate shades, but `#1C3C54` and the survivor trio look like drift. Also `--danger` (`style.css:17`) is defined and never used — the error card hardcodes its own reds (`1019-1022`).

### 9. Head-to-Head tab is empty on first open
Live check: opening H2H shows only the two team-picker buttons (content length ~35 chars, 0 graphs, 0 stat cards) with defaults "BMoreBallers88 vs BillyRayGonnaGetcha" displayed but **not rendered**. Charts appear only after actively changing a selection (then: 4 stat cards + 2 charts, correct). Either fire the render callback on tab load with the default pair, or show an explicit "pick two teams" empty state. (Root cause is an `app.py` callback wiring issue, but the symptom is front-end UX; flag for Phase 3/7 dedupe.)

### 10. `gridiron_ink` template: contrast is good, but sizing defaults fight the dashboard
Contrast/readability is the theme's strength: `#BDE2FF` on `#163146` ≈ **9.7:1** (passes WCAG AAA); chart grid `#3D5E78` is subtle but visible; hover labels are readable. Two caveats:
- Muted text `#6a9abf` on panel backgrounds is ≈ 4.3:1 — fine for normal text, but it's used for the tiniest type in the app: 0.55–0.62rem (≈9px) uppercase letterspaced labels (`style.css:158-166, 461-475, 1246-1252`). Borderline legibility on non-retina screens.
- Template defaults are notebook-era, not dashboard-era: `height=1000` (`sleeper_core.py:~157`), `title font size=45` with `subtitle size=30`, x-tick font 20 / y-tick 15, `xaxis side='top'`, `margin t=130`. In cards these oversized titles/margins waste vertical space — visible on mobile where a single chart's title occupies two full lines at display size. `showlegend=False` as a template default also means every chart that needs a legend must remember to switch it back on.
- Courier New everywhere is a legitimate aesthetic choice and consistently applied (CSS `--font-main`, template `ink_font`, D3 literals). No finding beyond the triplication in #7.

### 11. Dash debug toolbar ships in the served app
The blue Dash dev-tools UI ("v4.0.0", Errors/Callbacks buttons, "Dash update available") is visible in every session — the server runs with `debug=True`. On mobile it overlaps the bottom nav (verified in screenshot). Cosmetic locally, but it exposes callback structure and should be off for any Pi deployment. (Also noted by Phase 5.)

### 12. `.team-chip` tooltip via `title` attr + CSS `::after` double-renders
`style.css:310-328` draws a styled tooltip from `attr(title)` on hover — but the native browser `title` tooltip still fires after ~1s, so users see both the styled chip tooltip and the OS tooltip. Use a `data-tip` attribute instead of `title` in `app.py` and read `attr(data-tip)`.

### 13. Chart-card animation `nth-child` stagger caps at 6
`style.css:890-895` staggers fade-up delays for cards 1–6 only; Side Bets renders 14+ cards and Playoffs 10 — cards 7+ all animate at delay 0 simultaneously, before earlier siblings finish. Harmless but the "cascade" effect visibly breaks on the busiest tabs. `animation-delay: calc()` with a custom property, or just accept the cap.

### 14. All-Time tab is the slow one — no loading affordance beyond spinner
During the live run, tabs rendered in <3.5s except All-Time, which showed 0 graphs at 3.5s and 6 graphs (10 cards) at ~9s, with no console errors. The generic `.loading-msg` spinner exists (`style.css:997-1014`) but during the gap the tab area is simply sparse. Perf root cause belongs to Phase 3 (`_ensure` blocking); the front-end improvement would be skeleton cards.

### 15. Duplicate/competing selector conventions
Minor coherence nits: `.tab--selected, .tab-selected` both defined (`style.css:745`) — only the former is real; `.btn-refresh` kept "for non-bar usage" (`style.css:411-430`) but no non-bar usage exists in `app.py` (only `.btn-refresh-hud` is used); two separate `@media (max-width: 768px)` blocks plus three more scattered later (869, 1037, 1150, 1169, 1215, 1265) — consolidating would prevent the kind of drift seen in #1.

---

## Highest-value visual improvements (short list)

1. **Fix the 4 undefined CSS variables** (`--grid`→`--border`, `--text`→`--text-main`, `--card-bg`→`--bg-card`) — 10 minutes, restores intended Playoffs/Side Bets styling. (#1)
2. **Fix the mobile bottom nav** — force `flex-direction: row` (or abandon fixed-bottom) and let the team-chip row wrap on small screens. This is the difference between "usable on a phone at the bar on Sunday" and not. (#3)
3. **Add teardown to `renderScoreRace` and a cancellation guard to `_waitForEl`** — stops the listener/timer accumulation and double-render jank. ~20 lines. (#4, #5)
4. **Extract D3 chart boilerplate** (`setupChart` + `makeTooltip` + CSS-class axis styling) — cuts `d3charts.js` by a few hundred lines and makes the theme single-source. Do together with reading colors from CSS variables. (#6, #7)
5. **Right-size the Plotly template for cards**: drop `height=1000`, title 45→~24, margins t=130→~60. Every tab gets denser and mobile improves for free. (#10)
6. **Delete the ~19 dead classes / ~120 dead lines** in `style.css` and the Bootstrap shim block. (#2)
7. **Render H2H with its default team pair on tab open.** (#9)

## What's genuinely good

- One palette, consistently applied across three technologies — the app reads as one designed object, which is rare at this scale of hand-rolled CSS.
- Main text contrast is AAA; chart legibility on the dark theme is strong.
- Zero console errors/warnings across all 8 tabs, zero error cards, all charts present — the front end is *functionally* solid right now.
- Real mobile intent exists (column collapse, PR-table column hiding, digest stacking all work); only the bottom nav is broken.
- The mask-image SVG icon system for tabs (`style.css:754-839`) is a clean, dependency-free pattern.
