# Playoff Probability Calculator — Implementation Plan

## Goal

Add a **Playoff Probability** card to the **This Week** tab (immediately after the Power Rankings
card) that shows each team's probability of making the playoffs, how that probability has evolved
week-over-week, and which games to root for this week.

---

## Recommended Subagent Model

**claude-sonnet-4-6** for all implementation phases. The algorithm is well-specified (NumPy
bitmask enumeration), the codebase patterns are established, and the integration targets are
exact. Opus is not warranted.

---

## Architecture Context

Read these files before writing any code:

| File | Purpose |
|---|---|
| `sleeper_core.py` | All data classes; add `PlayoffCalculator` class here |
| `data_loader.py` | Disk-cache layer; add caching helpers here |
| `webapp/app.py` | Dash app; add card after `_power_rankings_native()` in `_tab_week()` |
| `webapp/assets/style.css` | CSS design system; add any new class selectors here |
| `tests/test_pipeline.py` | Data integrity tests; add `TestPlayoffCalculator` class here |
| `tests/test_charts.py` | Chart smoke tests; add chart smoke tests here |
| `tests/conftest.py` | Shared fixtures; add `playoff_calc_*` fixtures here |

**Key existing patterns to follow:**
- Chart methods live on domain classes in `sleeper_core.py` and return `fig` objects
- `data_loader.py` uses MD5-keyed pickle files in `.cache/`; use `_cache_key()` + `_load()` /
  `_save()` helpers (or the nearest equivalent — read the file to see the exact pattern)
- CSS uses `--ink-*` CSS variables from `gridiron_ink`; do not hardcode colors
- Tab cards use `_card(fig, title, subtitle)` helper in `app.py`
- Error boundaries: wrap each card in `try/except` and use `_card(_err(str(e)), title)`

---

## Data Model

### What we need per team (as of week W):

```python
@dataclass
class TeamPlayoffSnapshot:
    roster_id: int
    name: str          # from roster_ids dict
    wins: int          # wins through completed week W-1
    losses: int
    points_for: float  # cumulative regular-season PF through week W-1 (tiebreaker)
    prob_any: float    # P(makes playoffs) — tied-at-cutoff-or-better
    prob_guar: float   # P(guaranteed spot) — strictly above cutoff
    clinch_in: int | None   # min additional wins to clinch in ALL scenarios; None if already clinched or impossible
    elim_in: int | None     # max additional losses before eliminated in ALL scenarios; None if already eliminated
    key_matchups_swing: dict[tuple[int, int], float] = field(default_factory=dict)
    # Maps (roster_id_a, roster_id_b) → swing in P(this team makes playoffs) if roster_id_a wins.
    # Computed during the bitmask loop — only includes current-week matchups not involving this team.
    # Entries with 0.0 swing are excluded before attaching.
```

### Source of truth for past results:
- `Season.ConcatinatedWeeks` DataFrame has columns: `Team` (display name), `Total` (score),
  `Won` (0/1), `Week`, `Season`
- Derive wins and points_for from this DataFrame, filtered to `Week < as_of_week` and
  `Season == 'Regular'`
- Map display names back to `roster_id` using `roster_ids[year]` (inverted)

### Source of truth for future matchups:
- Call `data_loader.fetch_matchups_json(league_id, week)` for each remaining week
  (`as_of_week` through `playoff_week_start - 1`)
- Add `fetch_matchups_json(league_id, week)` to `data_loader.py` if it does not already exist;
  it should hit `https://api.sleeper.app/v1/league/{league_id}/matchups/{week}` with disk caching
- Each entry has `roster_id` and `matchup_id`; pair entries sharing a `matchup_id` to get
  (home_roster_id, away_roster_id) pairs
- Filter out any entries where `points > 0` — those games are already decided

### Tiebreaker:
- Tiebreaker for equal wins is **points_for** (higher PF wins the tiebreaker)
- Use *current accumulated* PF as the tiebreaker proxy; do not simulate future scores
- This is the standard approach: future score accumulation is unknown and not modeled

---

## Availability Window

| Year / Week | State | Behavior |
|---|---|---|
| Historical year (2019–2024) | Season complete | Compute snapshot at each week 9–14; show trajectory chart (read-only, no live data needed) |
| Current year, week < 9 | Too early | Card renders but is locked — show "Projections unlock Week 9" with grayed content |
| Current year, weeks 9–14 | Active | Full visualization |
| Current year, week ≥ 15 | Playoffs started | Show final Week 14 snapshot; label "Regular season final" |

---

## Phase 1 — Core Algorithm (`sleeper_core.py`)

Add a `PlayoffCalculator` class. No Numba dependency. NumPy only.

```python
class PlayoffCalculator:
    """
    Computes playoff probabilities for all teams using exact NumPy bitmask enumeration.
    Falls back to Monte Carlo (1M simulations) when remaining matchups exceed 29
    (2^29 ≈ 500M scenarios, the practical NumPy memory ceiling).
    """

    EARLY_WEEK_THRESHOLD = 9      # weeks below this show locked state
    NUMPY_EXACT_BIT_LIMIT = 29    # use MC above this matchup count
    MC_SIMULATIONS = 1_000_000

    def __init__(self, league: League, season: Season, as_of_week: int):
        ...

    def compute(self) -> list[TeamPlayoffSnapshot]:
        """Run enumeration and return one snapshot per team."""
        ...

    def _build_standings(self) -> dict[int, dict]:
        """
        Derive wins, losses, points_for per roster_id from Season.ConcatinatedWeeks,
        filtered to regular-season weeks < as_of_week.
        """
        ...

    def _fetch_remaining_matchups(self) -> list[tuple[int, int]]:
        """
        Return list of (roster_id_a, roster_id_b) for undecided games from
        as_of_week through playoff_week_start - 1.
        Use data_loader.fetch_matchups_json(); filter out games with points > 0.
        """
        ...

    def _determine_playoff_spots(self) -> int:
        """Read settings.playoff_teams from league.league_settings."""
        ...

    def _exact_numpy(self, matchup_pairs, current_week_pairs, initial_wins, pf_totals, num_playoffs, total_scenarios):
        """
        Vectorized bitmask enumeration. For each scenario, determine which teams
        make the playoffs using the points_for tiebreaker.

        Tiebreaker logic: for a given final_wins vector, rank teams by
        (wins DESC, pf DESC, roster_id ASC) — roster_id as tertiary key ensures
        deterministic results when wins and PF are identical.

        Batch in chunks of 1<<20 to bound memory usage.

        Also maintains a (num_teams, num_current_week_games, 2) accumulator array
        to tally, for each current-week game G and outcome O ∈ {0,1}, how many
        times team T makes the playoffs. After the loop, compute swings as
        abs(tally[:,g,0]/count_0 - tally[:,g,1]/count_1) for each game g, and
        attach to TeamPlayoffSnapshot.key_matchups_swing (excluding 0.0 entries).
        current_week_pairs is the subset of matchup_pairs in the current week only.

        Returns (in_count, guar_count, swing_tally) where swing_tally has shape
        (num_teams, num_current_week_games, 2).
        """
        ...

    def _monte_carlo(self, matchup_pairs, current_week_pairs, initial_wins, pf_totals, num_playoffs):
        """
        1M random simulations using numpy random. Same tiebreaker logic
        (wins DESC, pf DESC, roster_id ASC). Also computes the same
        (num_teams, num_current_week_games, 2) swing accumulator as _exact_numpy.
        Returns (in_count, guar_count, num_sims, swing_tally).
        """
        ...

    def _clinch_number(self, roster_id: int, matchup_pairs, initial_wins, pf_totals, num_playoffs) -> int | None:
        """
        Find minimum additional wins W such that team makes playoffs in ALL scenarios
        where they win exactly W more of their remaining games (regardless of opponent results).
        Linear scan over W in range(num_own_remaining_games + 1) — domain is at most 6
        values so binary search is not warranted.
        Returns None if already clinched or if impossible even winning all remaining games.
        """
        ...

    def _elim_number(self, roster_id: int, matchup_pairs, initial_wins, pf_totals, num_playoffs) -> int | None:
        """
        Find maximum additional losses L such that team still has any path to playoffs.
        Linear scan over L in range(num_own_remaining_games + 1) — same reasoning as
        _clinch_number; at most 6 values to check.
        Returns None if already eliminated.
        """
        ...
```

**Tests to write in `tests/test_pipeline.py` → class `TestPlayoffCalculator`:**
- `test_probs_sum_to_num_playoff_spots`: sum of all `prob_any` values ≈ `num_playoff_spots` (within floating point tolerance) — this is a mathematical invariant of the enumeration
- `test_probs_bounded`: all `prob_any` and `prob_guar` values are in [0, 1]
- `test_prob_any_gte_prob_guar`: `prob_any >= prob_guar` for every team
- `test_clinched_team_has_100_guar`: any team with `prob_guar == 1.0` should have `clinch_in == None` (already clinched, no count needed)
- `test_eliminated_team_has_zero`: any team with `prob_any == 0.0` should have `elim_in == None`
- `test_matchup_count_correct`: total remaining matchup pairs equals expected count for the week

Use `pytest.skip` if required cache files are missing (no API calls in tests).

---

## Phase 2 — Caching Layer (`data_loader.py`)

### 2a: Add `fetch_matchups_json(league_id, week)`

If this function does not already exist, add it:

```python
def fetch_matchups_json(league_id: int, week: int) -> list:
    """Fetch raw Sleeper matchup JSON for a given week (cached to disk)."""
    key = f"matchups_{league_id}_{week}"
    # follow the existing _cache_key / _load / _save pattern in this file
    ...
```

Only add this if it doesn't already exist. Check the file first.

### 2b: Add `load_playoff_probs(year)`

```python
def load_playoff_probs(year: int) -> dict[int, list[TeamPlayoffSnapshot]] | None:
    """
    Returns a dict mapping as_of_week → list[TeamPlayoffSnapshot] for all
    weeks in the availability window (9 through playoff_week_start).

    For a completed season: computes all weeks 9–(playoff_week_start) once and caches.
    For the current season: computes all completed weeks 9–current_week; caches each week
    individually so partial results are available while the season progresses.

    Returns None if the data is not available (year not loaded, season too early).
    Cache key: f"playoff_probs_{year}" — invalidated automatically when weekly data changes.
    """
    ...
```

Cache each `(year, as_of_week)` independently so a new week doesn't bust the entire history.

---

## Phase 3 — Current Week Visualization (`webapp/app.py` + `sleeper_core.py`)

### 3a: Chart method on `PlayoffCalculator`

Add `PlayoffOddsBar(snapshots: list[TeamPlayoffSnapshot]) -> go.Figure` as a static or class method:

- Horizontal bar chart
- Teams on Y axis, sorted by `prob_any` descending
- Two layers per bar: `prob_guar` (darker fill, labeled "Guaranteed") extending to `prob_any`
  (lighter fill extending beyond, labeled "Any path")
- Vertical dashed line at the playoff cutoff (the probability value where rank = num_playoff_spots)
- Color coding per team using `self.teamcolors` (match existing chart convention)
- Hover tooltip: "X-Y record · PF: ZZZ.Z · Prob: AA.A% (BB.B% guaranteed)"
- X axis: 0–100%, formatted as percentages
- Status badge annotations on the right side: CLINCHED (if `prob_guar == 1.0`),
  ELIMINATED (if `prob_any == 0.0`), WIN OUT (if winning all remaining games ≥ ~90%),
  LONGSHOT (if `prob_any < 0.15`)
- Use `gridiron_ink` template; follow visual conventions from existing chart methods

### 3b: "Key games this week" native card

Add `_playoff_key_games_card(snapshots, league, as_of_week)` in `app.py`:

The conditional probability swings are already pre-computed — they live in
`snapshot.key_matchups_swing` (a `dict[tuple[int,int], float]` populated by the
bitmask loop in Phase 1). **Do not re-run the enumeration here.**

For each team T:
- Read `snapshot.key_matchups_swing` — keys are `(roster_id_a, roster_id_b)`, values
  are swing magnitude (already excludes 0.0 swings and matchups involving T)
- Find the entry with the highest swing value
- Render as: *"Root for **Name A** over **Name B** — adds +X% to your odds"*
- If `key_matchups_swing` is empty (team clinched, eliminated, or no impactful games),
  show *"No games this week affect your odds"*

Layout: a two-column grid of small native HTML rows (no Plotly), one row per team, showing
their own record + top key game. Use `className='chart-card chart-col-full'`.

Only show for the current week (not on historical years).

### 3c: Wire into `_tab_week()`

In `_tab_week(year, week, teams)`, after the Power Rankings card:

```python
try:
    prob_data = data_loader.load_playoff_probs(year)
    cards.append(_playoff_odds_card(prob_data, year, week, season))
except Exception as e:
    cards.append(_card(_err(str(e)), 'Playoff Probability'))
```

Add `_playoff_odds_card(prob_data, year, week, season)` function that:
- If `week < 9` (early season): return locked state card with message "Projections unlock Week 9"
- If `week >= playoff_week_start`: return the Week-(playoff_week_start-1) snapshot labeled
  "Regular Season Final"
- Otherwise: return the bar chart for `as_of_week = week`, plus the key games card below it

Update the SECTION MAP in `app.py`'s docstring with the correct line number.

**Tests to write in `tests/test_charts.py`:**
- `test_playoff_odds_bar_smoke`: `PlayoffCalculator.PlayoffOddsBar(snapshots)` returns a
  `go.Figure` with at least one trace and no exception

---

## Phase 4 — Historical Trajectory (`sleeper_core.py` + `webapp/app.py`)

### 4a: Chart method

Add `PlayoffOddsTrajectory(probs_by_week: dict[int, list[TeamPlayoffSnapshot]]) -> go.Figure`
as a static or class method on `PlayoffCalculator`:

- Line chart: X axis = week number (9 through final week), Y axis = playoff probability %
- One line per team, using `teamcolors`
- Markers at each data point
- Hover: "Week W · X-Y record · ZZ.Z%"
- Dashed horizontal line at 50% for reference
- For completed seasons: all lines end at a final point styled differently (filled marker vs
  hollow) to indicate the regular season ended
- Title: "Playoff Race · {year}" or "Playoff Race · Week {W}" for current season
- Use `gridiron_ink` template

### 4b: Wire into `_playoff_odds_card()`

Below the bar chart, add the trajectory line chart:
- Toggle between bar view and trajectory view using a `dcc.RadioItems` toggle.
  Follow the **exact same pattern** as the `luck-toggle` in `_tab_week()`:
  1. Assign the `dcc.RadioItems` a stable component ID (e.g. `'playoff-view-toggle'`)
  2. Register a `@app.callback` in the global scope with `Input('playoff-view-toggle', 'value')`
     and `Output('playoff-odds-graph', 'figure')` — same structure as the luck callback
  3. The callback receives the toggle value and returns the appropriate `go.Figure`
  Do **not** use `dcc.Tabs` — it would be inconsistent with every other toggle in the app.
- For historical years (where bar chart shows "Final"), show only the trajectory chart
  (the bar chart is redundant when all values are final)

**Tests:**
- `test_playoff_trajectory_smoke`: returns a `go.Figure` with N traces = number of teams

---

## Phase 5 — Most Likely Path Tooltip (`sleeper_core.py` + `webapp/app.py`)

*Implement only after Phases 1–4 are passing all tests.*

For each team T, among all scenarios where T makes the playoffs:
- Find the most common combination of T's own remaining game outcomes (win/loss sequence)
- This is a mode over a binary vector — group scenarios by T's own outcome bitmask and find
  the most frequent

Surface as a hover tooltip or `dcc.Tooltip` on the bar chart:
> *"Most common path: Win Wk 11, 13 · Any result Wk 12 — appears in 61% of your playoff scenarios"*

Display the week numbers and W/L labels. Do not show if `prob_any == 0` or `prob_any == 1`.

**Note:** This requires storing the raw scenario matrix (or re-running the enumeration with
logging). Consider caching the scenario-level data only if the team count × scenario count
is small enough (< ~100MB). If memory is a concern, run a second targeted pass for just this
feature rather than storing the full matrix.

---

## Constraints

- **No Numba dependency.** The league has ≤10 teams and ≤14 regular-season weeks. At the
  start of Week 9, there are 6 remaining weeks × 5 games/week = **30 matchups**, which
  exceeds `NUMPY_EXACT_BIT_LIMIT = 29`. Weeks 9 and 10 will therefore always use Monte Carlo
  (1M simulations, accurate to <0.1%). Exact enumeration kicks in from Week 11 onward as
  remaining matchups drop to ≤25. This is expected and acceptable — do not raise the bit
  limit to 30, as 2^30 chunked enumeration is slow and unnecessary for this use case.
- **No new blocking API calls.** All Sleeper API calls must go through `data_loader.py` with
  disk caching. The `load_playoff_probs()` function should be called from the existing background
  loading thread in `app.py`, not at render time.
- **Follow existing CSS conventions.** Add selectors to `webapp/assets/style.css` using
  `--ink-*` CSS variables. Do not hardcode hex colors.
- **Locked state must be visually consistent** with how the Survivor tab handles off-season
  states (greyed card, icon, short message). Read `_tab_survivor()` for reference.
- **Run `pytest tests/ -m "not slow" -q` after each phase** before moving to the next.
  All tests must pass. Do not move forward with failing tests.
- **Update the SECTION MAP** in `app.py`'s docstring whenever a new function is added or
  an existing one moves more than ~20 lines.


---

## Revision History

**Rev 1 (2026-05-25):** Incorporated findings from Gemini senior-developer review:
- Added `key_matchups_swing` field to `TeamPlayoffSnapshot`; pushed swing computation into the bitmask loop (`_exact_numpy`/`_monte_carlo`) rather than re-running enumeration in `app.py`
- Corrected matchup count math: Week 9 = 30 matchups > 29-bit limit; Monte Carlo is expected at weeks 9–10, exact enumeration from week 11 onward
- Made Phase 4b callback wiring explicit; kept `dcc.RadioItems` pattern consistent with existing toggles
- Replaced binary search spec in `_clinch_number`/`_elim_number` with linear scan (domain ≤ 6 values)
- Added `roster_id` as tertiary tiebreaker for deterministic sorting
- Specified that 0.0-swing games are excluded before attaching to `key_matchups_swing`