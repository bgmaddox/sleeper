# Phase 2 Review — `sleeper_core.py` (Core Library)

**Scope:** 6,490 lines, 14 classes, ~152 functions. Read-only structural + correctness audit.
**Verdict:** **Fragile-but-functional.** The code works for the happy path (cached historical seasons, one year at a time in a single process), but it carries real correctness bugs, brittle name-matching, zero I/O error handling, and heavy shared mutable global state. It is maintainable *by its author today* and hard for anyone else (or the author in six months). The single biggest risk is not any one bug — it is the **module-level mutable dicts populated as a side effect of object construction**, which couples caching, threading, and every downstream class together invisibly.

Findings are ranked by blast radius (how much breaks / how silently if it goes wrong).

---

## Findings (ranked by blast radius)

### 1. Module-global mutable dicts populated as construction side effects — *architecture-wide*
`AllMatchesDict`, `AllBreakoutDict`, `OptimalScoresByYear` are module-level dicts (`sleeper_core.py:457-473`). They are **written** as a side effect of constructing a `Week` (`PlayerBreakout` at line 761-762, `WeeklyDataframe` at 868, `OptimalTeams` via 954) and **read** by nearly every other class: `Season` (1263, 1322, 1336, 1451), `Playoffs` (3244-3245, 3277, 3392, 3423), `AllTimePlayoffs` (3480, 3505), `AllTime` (3796, 3805), `PlayoffCalculator` (6066), and `webapp/app.py` (687-692, 2276-2280, 3001-3040).

Why this is the top risk:
- **Hidden coupling.** A `Season`/`Playoffs`/`AllTime` object is only correct if the matching `Week` objects for that year were constructed *first, in this same process*. There is no explicit dependency — it is implied by global state. Nothing in a constructor signature tells you this.
- **Cache layer must manually re-hydrate globals.** `data_loader.py:232-233` has to `core.AllMatchesDict[year].update(...)` on every cache hit, and snapshot them back out at `272-273`. The cache "works" only because it patches this global state by hand. Miss that and cached objects silently return empty frames.
- **Cross-year / cross-run contamination.** Because the dicts are keyed by year but never cleared, a long-lived process (the Dash server loads years in a background thread) accumulates every year's frames in shared module state. `invalidate_week` and re-loads mutate globals other in-flight requests may be reading — a data race with no lock around these dicts.
- **Blast radius:** every chart in the app depends on these being correctly populated for the right year at the right time.

Recommendation: make these instance state on a per-season container (e.g. `Season` owns `self.matches[week]`, `self.breakout[week]`) and pass the container down to `Playoffs`/`PlayoffCalculator` explicitly. This is the change with the highest correctness payoff and is a prerequisite for any safe decomposition.

### 2. `OptimalTeams` "dream team" loop uses a stale variable — *correctness bug*
`sleeper_core.py:901-908`:
```python
for position, group in DreamGroups:   # position IS the group key
    position = name[1]                # ...immediately overwritten by leftover `name`
```
`name` is left over from the previous loop (`for name, group in OptGroups` at 891); after that loop it holds the *last* `(team, position)` tuple. So every iteration of the dream-team loop looks up `position_counts` for the **same** stale position, not the group's actual position. The "dream team" / `DreamTeamDF` is therefore computed from garbage for all but coincidentally-matching positions. Bug is masked because `DreamTeamDF` is only built for non-current seasons (931-933) and may be lightly used, but it is wrong wherever it feeds a chart. Fix is one line: delete `position = name[1]`.

Related, same method: `flex_dream_pool_df.loc[flex_dream_pool_df['points'].idxmax()]` (921) takes a single **league-wide** max rather than per-team (contrast the per-team `groupby('recent_team')` on line 920). If the dream team is meant to be league-wide this is intentional; if per-team it is a second bug. Worth a comment either way.

### 3. Name-based join for player position/team still lives in the hot path — *silent per-player data loss*
The stats join was moved to ID-based (`git fd45842`, PlayerBreakout 743-748), **but** player→position/team enrichment is still a name merge: `dfBreakout.merge(player_team_DF, left_on='player', right_on='player_name', ...)` (`732`) and `.merge(self.league.Rosters, on='player_name', ...)` (752). To make names line up it string-mangles both sides with order-dependent `.replace(' Jr.','')/(' Sr.','')/(' III','')/(' II','')` chains (682, 730, 733) and hardcodes fixups: `player_team_DF.drop(1035)`, `.replace('Marquise Brown','Hollywood Brown')`, `player_team_DF.loc[-1] = ['LAR','LA']` (686-691). Every one of these is a positional/string magic constant that silently mis-joins (position becomes NaN → player dropped from position charts / optimal lineup) when nflverse reorders rows or a new name collision appears. This is the exact class of bug the ID migration was meant to kill; it was only half-finished. Since Sleeper already provides `player_id` and `player_pos` (used at 709-710), the position/team columns should come from those maps, not a name merge.

### 4. Zero error handling around every network / remote-CSV call — *whole-season load crashes on a blip*
`League.__init__` fetches with no try/except: `nfl.import_schedules([year])` (491), `pd.read_csv(<github release URL>)` (496-499), `nfl.import_rosters([year])` (501). Raw `requests.get(...).json()` with no status check or timeout at 563-564 (`ImportWeek`), 590-591 (`Draft`), 624-625 (`Week.ImportWeek`). Any 500, rate-limit, network hiccup, or GitHub outage raises straight out of the constructor. `data_loader.load_data_for_year` wraps the per-week loop in a broad `except Exception` (swallowing *all* errors as "week skipped", which can hide real bugs), but `League(...)` construction itself is unguarded — a transient failure there kills the entire year load with a stack trace. Add timeouts + `raise_for_status()` + a narrow retry, and stop swallowing every exception silently in the week loop.

### 5. Config-as-code: `SIDE_BET_SEASONS`, `roster_ids`, `leagueNumbers_Dict` embedded in the module — *maintainability + edit risk*
`SIDE_BET_SEASONS` is ~113 lines of hand-aligned dict literals (`335-448`); `roster_ids` per-year dicts (256-276); `leagueNumbers_Dict`, `SURVIVOR_LEAGUE_IDS`, `AVAILABLE_YEARS` (323-333). This is pure data, edited by hand every season, living inside a 6.5k-line source file. Consequences: (a) a comma/quote typo in the data breaks *import of the whole module*; (b) git history from `522` shows a real data-correctness bug ("anachronistic username in 2019 week 11") — data errors hide among code; (c) the whitespace-aligned literals are fragile to edit. Moving to `data/side_bets.json`, `data/rosters.json`, `data/leagues.json` (loaded once at import) isolates data edits from code, makes validation possible, and shrinks the module. Low effort, clear win. Keep `AVAILABLE_YEARS` derivable from the leagues file.

### 6. `roster_ids_2024 = roster_ids_2023` alias — *shared-reference footgun*
`sleeper_core.py:271`. 2024 is the **same dict object** as 2023, not a copy. Any code that mutates `roster_ids[2024]` in place also mutates 2023. Nothing mutates it today, but it is an invisible landmine. Use an explicit copy or a separate literal.

### 7. `UpdateColors` / `SetTeamColors` duplicated verbatim across classes — *drift risk*
Identical `UpdateColors` bodies at `633-661` (Week) and `1290-1318` (Season); near-identical `SetTeamColors` at 628, 1285, 3812, 4384, plus `UpdateColors2` (4354). Any fix to color styling must be applied in 3-5 places or they drift. Hoist to a shared mixin or module-level helper (`get_slot_teamcolors` already exists as the single source for the palette — the fig-styling helper should join it).

### 8. 30+ chart methods duplicate Plotly boilerplate — *volume, not danger*
Each chart method re-specifies `template='gridiron_ink'`, `update_layout(width=…, height=…)`, `color_discrete_map=self.teamcolors`, and multi-line `add_annotation(... font=dict(family="Courier New"…))` inline (e.g. `LuckChart` 1673-1719). ~4 near-identical annotation blocks in `LuckChart` alone. This is the bulk of the file's length. It is not a correctness risk but it is the main reason the file is 6.5k lines and why every visual tweak is a find-and-replace across dozens of methods. A small `_styled_annotation(...)` / `_base_fig(...)` helper set would cut hundreds of lines.

### 9. Optimal/efficiency silently skipped for the current season — *empty charts, no warning*
`Week.__init__` guards `OptimalTeams()` + `EfficincyScore()` behind `if self.year != CURRENT_SEASON` (610-613), and `OptimalTeams` itself branches on the same at 931. So `OptimalScoresByYear[current_year]` stays empty, and any downstream efficiency/optimal chart for the live season returns nothing (`_efficiency` returns `None` at 3277-3279, `LineupEfficiency`, `BrawnyBench`, etc.). This may be a deliberate perf/data-availability choice, but it fails silently — a user viewing the current year just sees blank cards. Should at least surface "not available for in-progress season" rather than empty output.

### 10. `AllTimePlayoffs._process_year` re-implements `Playoffs._process_bracket` — *logic duplication*
Bracket-walking (group by round `r`, resolve `t1/t2/w`, map roster_id→name, join scores) exists twice: `Playoffs._process_bracket` (3288+) and `AllTimePlayoffs._process_year` (3472-3581, esp. 3496-3520). Two copies of the same bracket-resolution rules means a Sleeper bracket-format change (or a scoring-join fix) must be made twice. Extract one bracket resolver used by both.

### 11. `iterrows` in figure builders — *acceptable scale, flag for growth*
`iterrows` at 4010 (`AllTimeGraphing`), 5556, 5737, 5841 (Survivor). At 8-12 teams × ~18 weeks these are tiny and fine today. Not urgent — noting only so they are not copied into a genuinely hot path later. No action required now.

### 12. Broad `except Exception` swallowing in the load loop — *hides real failures*
`data_loader.load_data_for_year` catches every exception per week and prints "skipped" (seen in the flow at 200-290). A genuine bug in `Week` construction (e.g. the name-join dropping data, or a KeyError) is indistinguishable from "season hasn't reached this week." Narrow the catch or log at a level that is visible in tests.

### 13. Chained/duplicate-column cleanup as a load-bearing step — *hidden fragility*
`PlayerBreakout` ends with `dfBreakout = dfBreakout.loc[:,~dfBreakout.columns.duplicated()].copy()` (757) after three merges that each add suffixed columns. The final schema depends on dedup order and merge suffixes lining up. It works, but the resulting frame's columns are effectively undocumented and any new merge upstream can silently change which duplicate "wins." A short assertion on expected columns after this step would catch regressions the tests currently can't see.

### 14. `League` constructor does everything (network + parsing + 8 sub-steps) — *no seam for testing*
`League.__init__` (483-506) runs 8 fetch/transform steps eagerly, including two remote calls and a GitHub CSV read. There is no way to construct a `League` from local fixtures without hitting the network, which is why the whole test suite depends on `.cache/` pickles. A classmethod like `League.from_cache(...)` / dependency-injected fetchers would make the core unit-testable and decouple it from `data_loader`'s import-time patching.

---

## Candidate decomposition sketch

The module already has clean class boundaries; the problem is they all live in one file and communicate through globals. A pragmatic split (roughly by the seams that already exist):

```
sleeper/
  config.py         # loads data/leagues.json, data/rosters.json, data/side_bets.json,
                    #   survivor_ids.json  → the dicts currently at lines 256-448
  theming.py        # gridiron_ink template, colorways, get_slot_teamcolors,
                    #   get_alltime_teamcolors, apply_logo_to_fig, shared UpdateColors/
                    #   SetTeamColors mixin, a _styled_annotation()/_base_fig() helper
  ingest.py         # League + Week (all API/CSV fetching + dataframe building)
                    #   → owns per-week matches/breakout/optimal as INSTANCE state
  season.py         # Season (aggregation + its ~25 chart methods)
  playoffs.py       # Playoffs, AllTimePlayoffs, one shared bracket resolver
  alltime.py        # AllTime
  sidebets.py       # SideBet (+ its 14 Week* methods)
  survivor.py       # Survivor
  playoff_calc.py   # TeamPlayoffSnapshot, PlayoffCalculator, PlayoffOdds* charts
data/
  leagues.json  rosters.json  side_bets.json  survivor_ids.json
```

The keystone change is **retiring the three module-global dicts** (Finding #1): `Season` becomes the container that owns `{week: matches_df}` / `{week: breakout_df}` / `{week: optimal}`, and `Playoffs`/`PlayoffCalculator` receive that `Season` (or the frames) explicitly instead of reaching into module state. Everything else in the split is mechanical once that dependency is explicit.

### Honest cost/benefit for a solo, self-taught maintainer

**Do now (high value, low risk, hours not days):**
- #2 dream-team stale-variable — one-line fix, real bug.
- #6 `roster_ids_2024` alias — one-line fix, removes a landmine.
- #4 network timeouts + `raise_for_status` on the raw `requests.get` calls — small, prevents silent hangs/crashes.
- #5 extract the three config dicts to JSON — mechanical, isolates seasonal data edits from code, shrinks the file ~250 lines. This alone makes the yearly "add a season" chore far safer.

**Do soon (medium effort, clear payoff):**
- #7 de-duplicate `UpdateColors`/`SetTeamColors` into one mixin.
- #3 finish the ID-based migration for position/team (use `player_pos`/`player_names` maps instead of the name merge + hardcoded fixups). This kills a whole bug class.
- #9 make current-season "not available" explicit rather than blank.

**Do only if the pain justifies it (days of work, real regression risk):**
- The full file split and #1 globals-removal. For a **single-maintainer hobby app that works**, splitting 6.5k lines is satisfying but risky: it touches every import in `webapp/app.py`, and the globals-removal (#1) is the kind of refactor that introduces subtle "empty chart" regressions unless the test suite is strong first. **Recommendation: don't do the big split yet.** Instead: (a) land the quick fixes above, (b) grow `tests/test_pipeline.py`/`test_charts.py` coverage on the year-boundary and cache-rehydration paths so a refactor is verifiable, then (c) tackle #1 in isolation (globals → `Season`-owned state) *before* any cosmetic file-splitting. The file being long is annoyance; the globals are the actual structural debt. Fix the debt, defer the annoyance.

**One-sentence bottom line:** correct the two one-line bugs and add I/O error handling this week; move config to data files this month; leave the module split until you have tests that would catch a regression — the global-dict coupling, not the line count, is what actually makes this file risky.
