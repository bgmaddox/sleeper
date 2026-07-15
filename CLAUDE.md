# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Testing Convention

Write tests before or during implementation — not after. For any new class, method, or data pipeline change:
- Add tests to `tests/test_pipeline.py` (data shape/integrity) or `tests/test_charts.py` (chart smoke tests) or a new file if the feature is large enough to warrant it (e.g., `tests/test_playoffs.py`)
- Use `@pytest.mark.xfail(strict=True)` for tests targeting code that doesn't exist yet — they document the expected contract and flip to passing once implemented
- Run `pytest tests/ -m "not slow" -q` after every meaningful change to catch regressions early

All tests load from `.cache/` — no API calls during test runs. If a cache file is missing, fixtures use `pytest.skip` rather than failing.

## Browser Verification (Playwright)

Screenshots are expensive — each image costs ~1,000–4,000 tokens and burns quota fast. Use this hierarchy:

1. **pytest** — covers logic correctness; use this first and most often
2. **`browser_snapshot`** — returns a text accessibility tree (rendered content, visible elements) at ~200–400 tokens; use for "did the tab load, is the chart present, any error panels"
3. **`browser_console_messages`** — catches React/JS errors after page load with no visual cost
4. **`browser_evaluate`** — run JS to check DOM state programmatically (e.g., count chart cards, read a value) instead of looking at a picture
5. **`browser_take_screenshot`** — only when the issue is explicitly visual (layout, CSS, sizing)

Default to steps 1–4. Only reach for a screenshot when a text-based check genuinely can't answer the question.

## Keeping Docs Current

After any edit to `webapp/app.py`:
- If a function is added, removed, or moves more than ~20 lines, update the **SECTION MAP** in `app.py`'s docstring (top of file) with the correct line numbers.

After any directory reorganization:
- Update `.claude/structure.md` to reflect the new layout.

## Running the App

**Legacy League webapp:**
```bash
# Kill any existing server first — port 8050 lingers even after background tasks "fail"
lsof -ti :8050 | xargs kill -9 2>/dev/null; sleep 1
cd webapp && source ../.venv/bin/activate && python app.py
# Open http://localhost:8050  (password: LEAGUE_PASSWORD in the project-root .env)
```

Always kill before restarting. Confirm with `curl -s -o /dev/null -w "%{http_code}" http://localhost:8050/login` (expect 200).

Run the server in the background so the session stays interactive. After code changes, kill and restart — there is no hot reload.

Activate the venv if running other scripts: `source .venv/bin/activate` (Python 3.12, venv at `Sleeper Project/.venv/`).

To bust stale cache for a week: call `data_loader.invalidate_week(year, week)` or delete `.cache/` files manually.

## Project Layout

```
sleeper_core.py     — All data classes, API logic, 30+ chart methods
data_loader.py      — Disk-cache layer (.cache/*.pkl) around sleeper_core
webapp/             — The live Dash web app (active development)
  app.py            — Flask/Dash server, all callbacks, tab layout
  assets/
    style.css       — CSS design system (gridiron_ink variables)
    d3charts.js     — D3 clientside chart renderers
    d3.min.js       — D3 v7 library
Data/               — NFL player stats CSVs
Photos&Videos/      — League logos and media assets
Sleeper_v3.ipynb    — Thin wrapper notebook: imports sleeper_core + data_loader for interactive charts (no logic of its own)
scripts/            — One-shot utility scripts (e.g. parse_sidebet_xlsx.py)
design/             — Active planning docs (roadmap.md)
archive/            — Superseded files: old dashboards, completed plans, prototypes
```

**Import path:** `webapp/app.py` adds the project root to `sys.path`, so it imports `sleeper_core` and `data_loader` directly from the root.

## Architecture

**Data flow:**
```
Dash callback → data_loader.load_data_for_year(year)
    → checks .cache/ (pickle) → miss: Sleeper API + nfl_data_py
    → League(year) → Week objects → Season.Update()
    → chart methods return Plotly figures → Dash renders tabs
```

### sleeper_core.py — key classes

- **`League(year, league_id)`** — bootstraps settings, users, roster IDs, NFL schedule/stats
- **`Week(league, week_num)`** — one week of matchups; builds matchup dataframes and per-player breakouts
- **`Season(league, weeks_dict)`** — aggregates all weeks; 30+ chart methods
- **`AllTime()`** — concatenates seasons 2019–2025 for historical charts
- **`Playoffs(league, season)`** — resolves bracket refs, maps roster IDs → names, joins scores and best-player data
- **`AllTimePlayoffs()`** — aggregates bracket + score data across all seasons; produces `playoff_results` and `playoff_games` dataframes for the all-time charts
- **`SideBet(league, season, DictofWeeks)`** — per-week side bet charts (Week1–Week14 methods); reads config from `SIDE_BET_SEASONS`
- **`PlayoffCalculator`** — computes per-team playoff probabilities via bitmask enumeration; drives the Playoff Calculator card on This Week tab

Global dicts populated as objects are built:
- `AllMatchesDict[year][week]` — matchup dataframes
- `AllBreakoutDict[year][week]` — player-level stat dataframes
- `OptimalScoresByYear[year][week]` — best possible lineup score per team

Key config dicts (loaded at import from `config/*.json` — edit the JSON, not the module):
- `leagueNumbers_Dict` — year → Sleeper league ID (`config/league_ids.json`)
- `roster_ids` — year → {roster_num: username} for 2019–2025 (`config/roster_ids.json`)
- `SIDE_BET_SEASONS` — year → {week → {name, desc, winner}} for 2019–2025 (`config/side_bet_seasons.json`)
- `SURVIVOR_LEAGUE_IDS` — year → Sleeper survivor league ID, 2024–2025 (`config/league_ids.json`)

### Dashboard tabs

1. **This Week** — weekly matchups, points timeline, power rankings, luck chart (YTD / This Week toggle), Side Bet of the Week card, Playoff Calculator card
2. **Season** — win progression (wins / points toggle), points for/against (avg line toggle), scoring frequency (all/wins/losses toggle), bench strength (season / by-week toggle)
3. **Players** — player points, violin distributions (4-way toggle: starters / all rostered / by-position starters / by-position all), score trends, top players (QB/RB/WR/TE toggle)
4. **Playoffs** — winners + losers bracket cards, analytics charts (Champion's Road, Playoff Heat Check, Bench Points Left), all-time playoff history charts (Playoff Pedigree, Win Rate, Seeding vs. Finish, Records, Path to Glory)
5. **All-Time** — hall of fame/shame, highest-scoring losses, closest margins, cumulative stats
6. **Side Bets** — season scoreboard (D3 leaderboard), week navigator, per-week challenge cards with charts; supports all years in `SIDE_BET_SEASONS` (2019–2025)
7. **Survivor** — survivor pool pick history and elimination tracking (2024–2025)
8. **Head-to-Head** — all-time matchup history between two selected teams

### Theming

Custom Plotly template `gridiron_ink` in `sleeper_core.py`:
- Background: `#163146`, text: `#BDE2FF`, grid: `#3D5E78`, font: Courier New
- Colorway: `coastal_colorway` (default)

### Caching

`data_loader.py` uses MD5-keyed pickle files in `.cache/`. Dashboard loads data in a background thread; `_data`, `_loading_years`, `_failed_years` track state.

### League configuration

Seasonal config lives in `config/*.json` (`roster_ids.json`, `league_ids.json`, `side_bet_seasons.json`), loaded by `sleeper_core.py` at import. `AVAILABLE_YEARS` is derived from the league IDs — adding a new season is a JSON-only edit.

## Key Data Files

| File | Purpose |
|------|---------|
| `Data/stats_player_week_2025.csv` | NFL weekly player stats (100+ cols incl. EPA) |
| `Data/stats_player_regpost_2025.csv` | Regular season + postseason stats |

`sleeper_core.py` is the authoritative source for all chart logic. `Sleeper_v3.ipynb` is a thin interactive wrapper around it — never copy logic into the notebook. The retired `Sleeper_v2.ipynb` lives in `archive/`; it is stale except for its PickEm cells, kept as the reference for the planned Pick 'Em webapp page.
