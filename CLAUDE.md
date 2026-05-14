# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
cd FirstPyProject
../.venv/bin/python3 dashboard.py
# Open http://localhost:8050
```

Activate the venv first if running other scripts: `source .venv/bin/activate` (Python 3.11, venv at `Sleeper Project/.venv/`).

To bust stale cache for a week: call `data_loader.invalidate_week(year, week)` or delete `.cache/` files manually. To clear all cache: `data_loader.clear_cache()`.

## Architecture

All core code lives in `FirstPyProject/`:

| File | Role |
|------|------|
| `dashboard.py` | Plotly Dash app — UI, callbacks, theming |
| `sleeper_core.py` | All data classes, API logic, 30+ chart methods |
| `data_loader.py` | Disk-cache layer (`.cache/*.pkl`) around sleeper_core |
| `assets/style.css` | CSS variables and dark-theme component styles |

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
- **`Season(league, weeks_dict)`** — aggregates all weeks; 30+ chart methods (see below)
- **`AllTime()`** — concatenates seasons 2019–2025 for historical charts

Global dicts populated as objects are built:
- `AllMatchesDict[year][week]` — list of matchup dataframes
- `AllBreakoutDict[year][week]` — list of player-level stat dataframes
- `OptimalScoresByYear[year][week]` — best possible score per team (used for luck)

**Chart methods** (all return `fig`, never call `fig.show()`):

| Class | Key methods |
|-------|------------|
| `Week` | `WeeklyGraph()`, `PointsOverTheWeekend()`, `StatusGraph()`, `LuckChart()` |
| `Season` | `SnakeGraph()`, `SeasonPointsForAgainst()`, `WeeklyWinsGraphBreakout()`, `ScoreFrequencyGraph()`, `BrawnyBench()`, `PositionStengthPolar()`, `PlayerPoints()`, `ViolinPlayer()`, `ScoreTrends()`, `TopPlayers()` |
| `AllTime` | `HallofFame_Team/Player()`, `HallofShame_Team()`, `HighestScoringLosers()`, `SmallestMargins()`, `ForAgainstwithTeams()` |

### Dashboard tabs

1. **This Week** — weekly matchups, points timeline, power rankings, luck chart
2. **Season** — win progression, points for/against, weekly wins, scoring frequency, bench strength, position radar
3. **Players** — player points, violin distributions, score trends, top players
4. **All-Time** — hall of fame/shame, highest-scoring losses, closest margins, cumulative stats

Sidebar controls: year dropdown, week slider (1–18), team checklist (with All/None buttons), theme selector (coastal/neon/autumn), refresh button.

### Theming

Custom Plotly template `gridiron_ink` defined in `sleeper_core.py`:
- Background: `#163146`, text: `#BDE2FF`, grid: `#3D5E78`, font: Courier New
- Three colorways: `coastal_colorway`, `neon_future_colorway`, `autumn_forest_colorway`
- Theme applied in dashboard via `_apply_theme(colorway)` callback

### Caching

`data_loader.py` uses MD5-keyed pickle files in `.cache/`. Full season payload cached as `season_data_{year}_{max_week}`. Dashboard loads data in a background thread with a threading lock; `_data`, `_loading_years`, `_failed_years` track state.

### League configuration

`sleeper_core.py` contains hardcoded metadata:
- `leagueNumbers_Dict` — maps year → Sleeper league ID
- `roster_ids` — maps year → {roster_num: username} for 2019–2025
- `AVAILABLE_YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025]`

Sleeper API is public (no auth). Logo fetched from GitHub raw URL.

## Key Data Files

| File | Purpose |
|------|---------|
| `Data/stats_player_week_2025.csv` | NFL weekly player stats (100+ cols incl. EPA) |
| `Data/stats_player_regpost_2025.csv` | Regular season + postseason stats |

`Sleeper_v2.ipynb` is the authoritative notebook for chart logic — the source from which `sleeper_core.py` chart methods were extracted. `Sleeper.ipynb` is the older version.

`DraftVideoProject/Drafter.py` and `Drafter2.py` are standalone video-stitching utilities for draft announcement videos — unrelated to the dashboard.

## Active Project: Legacy League Web App

**Status:** In planning. See `PLAN.md` for the full plan.

The next major initiative is building `webapp/` — a new hosted Dash app to replace the local `FirstPyProject/` dashboard. Key decisions already made:

- **Framework:** Plotly Dash with 100% custom CSS (no Bootstrap). FirstPyProject used Bootstrap CYBORG with no custom CSS — that's why it didn't look right.
- **Design:** All CSS variables derived from `gridiron_ink` (#163146 bg, #BDE2FF text, Courier New). UI chrome must feel like it belongs inside the charts.
- **Hosting:** Render.com (new account needed). Free tier to start, $7/mo for always-on.
- **Auth:** Single shared password via `LEAGUE_PASSWORD` env var + signed session cookie (`itsdangerous`). No database.
- **Data updates:** Manual — owner runs `refresh.py` after each week.
- **New features:** Head-to-Head tab, animated SnakeGraph (`animation_frame='week'`), WeeklyScoreRace bar chart race, mobile-responsive CSS.
- **Reuse:** `sleeper_core.py` chart methods and `data_loader.py` are the core assets — `webapp/` imports from `FirstPyProject/`.
- **Site name:** Legacy League

**Do not modify** `FirstPyProject/dashboard.py` — it's the old attempt, left as reference only. Build everything new in `webapp/`.
