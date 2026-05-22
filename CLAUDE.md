# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Testing Convention

Write tests before or during implementation — not after. For any new class, method, or data pipeline change:
- Add tests to `tests/test_pipeline.py` (data shape/integrity) or `tests/test_charts.py` (chart smoke tests) or a new file if the feature is large enough to warrant it (e.g., `tests/test_playoffs.py`)
- Use `@pytest.mark.xfail(strict=True)` for tests targeting code that doesn't exist yet — they document the expected contract and flip to passing once implemented
- Run `pytest tests/ -m "not slow" -q` after every meaningful change to catch regressions early

All tests load from `.cache/` — no API calls during test runs. If a cache file is missing, fixtures use `pytest.skip` rather than failing.

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
# Open http://localhost:8050  (password: legacy)
```

Always kill before restarting. Confirm with `curl -s -o /dev/null -w "%{http_code}" http://localhost:8050/login` (expect 200).

Run the server in the background so the session stays interactive. After code changes, kill and restart — there is no hot reload.

Activate the venv if running other scripts: `source .venv/bin/activate` (Python 3.11, venv at `Sleeper Project/.venv/`).

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
Sleeper_v2.ipynb    — Authoritative notebook (source of sleeper_core.py methods)
archive/            — Old planning docs, prototypes, superseded files
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

Global dicts populated as objects are built:
- `AllMatchesDict[year][week]` — matchup dataframes
- `AllBreakoutDict[year][week]` — player-level stat dataframes
- `OptimalScoresByYear[year][week]` — best possible lineup score per team

### Dashboard tabs

1. **This Week** — weekly matchups, points timeline, power rankings, luck chart (YTD / This Week toggle)
2. **Season** — win progression (wins / points toggle), points for/against (avg line toggle), scoring frequency (all/wins/losses toggle), bench strength (season / by-week toggle)
3. **Players** — player points, violin distributions (starters / all rostered toggle), score trends, top players (QB/RB/WR/TE toggle)
4. **All-Time** — hall of fame/shame, highest-scoring losses, closest margins, cumulative stats
5. **Head-to-Head** — all-time matchup history between two selected teams

### Theming

Custom Plotly template `gridiron_ink` in `sleeper_core.py`:
- Background: `#163146`, text: `#BDE2FF`, grid: `#3D5E78`, font: Courier New
- Colorway: `coastal_colorway` (default)

### Caching

`data_loader.py` uses MD5-keyed pickle files in `.cache/`. Dashboard loads data in a background thread; `_data`, `_loading_years`, `_failed_years` track state.

### League configuration

`sleeper_core.py` contains:
- `leagueNumbers_Dict` — year → Sleeper league ID
- `roster_ids` — year → {roster_num: username} for 2019–2025
- `AVAILABLE_YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]`

## Key Data Files

| File | Purpose |
|------|---------|
| `Data/stats_player_week_2025.csv` | NFL weekly player stats (100+ cols incl. EPA) |
| `Data/stats_player_regpost_2025.csv` | Regular season + postseason stats |

`Sleeper_v2.ipynb` is the authoritative notebook for chart logic.
