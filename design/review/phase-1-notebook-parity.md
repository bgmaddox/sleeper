# Phase 1 — Notebook/Core Parity Review

**Question:** Is `sleeper_core.py` a faithful, complete port of `Sleeper_v2.ipynb`, and should the notebook still be called "authoritative"?

**Method:** Extracted all 127 code cells from `Sleeper_v2.ipynb` (180 cells total, 2.56MB) via direct JSON parse (nbconvert/nbformat unavailable in the venv) into the scratchpad as `notebook_extracted.py` (5,470 lines). Compared class/method inventories against `sleeper_core.py` (6,490 lines), then line-diffed the bodies of matching methods to check for divergence.

## Verdict

**No — the notebook is stale and should no longer be called "authoritative."** `sleeper_core.py` has outgrown it substantially: it contains 6 classes/feature areas (`Playoffs`, `AllTimePlayoffs`, `PlayoffCalculator`, `TeamPlayoffSnapshot`, a rewritten `Survivor`, plus ~8 new chart methods) that don't exist in the notebook at all, and at least 4 shared methods have diverged since the port (theming, caching, new params) without those changes ever being backported to the notebook. Conversely, the notebook has exactly one class (`PickEm`) that was never ported to core or wired into the webapp — everything else notebook-only is scratch/exploratory code, not durable logic.

The notebook's structure (127 code cells) breaks down as: ~16 cells define classes/functions, ~50 cells are object instantiation boilerplate (`League_2019 = League(2019, ...)`, `Week1_2019 = Week(1, League_2019)` × 7 years), and the remaining ~60 are one-off exploratory/scratch analysis (ad-hoc dataframes, a Sankey diagram experiment, a manually-entered "Winnings Breakdown" table) that were never intended to be reusable logic.

## Parity Table

| Notebook (cell / class.method) | Core counterpart (file:line) | Status |
|---|---|---|
| `ImportPlayerData()` (cell 4, notebook line 56) | `init_player_data()` `sleeper_core.py:32` | **ported-diverged** — rewritten to route through `data_loader.fetch_player_data()` with a global-cache guard instead of a raw synchronous `requests.get` every call. Intentional architecture upgrade (matches `data_loader.py` caching design), never was/needs to be backported. |
| `League.__init__` / `SettingsJSONtoDF` / `UsersJSONtoDF` / `StructureWeekIDs` / `StructureNFLData` / `PlayerTeamImport` / `Player_Pos_Dict` / `UserSetup` / `ImportWeek` (notebook 378–464) | `League` class `sleeper_core.py:482–567` | **ported-identical** (line-for-line, cosmetic only) |
| `League.ScheduleFormater` / `Draft` (notebook 464–497) | `sleeper_core.py:567–599` | **ported-identical** (9-line diff, all whitespace/renumbering) |
| `Week.PlayerBreakout` (notebook 578–677) | `Week.PlayerBreakout` `sleeper_core.py:663–765` | **ported-identical** (32-line diff, comment/formatting only) |
| `Week.PointsOverTheWeekend` (notebook 1006–1094) | `Week.PointsOverTheWeekend` `sleeper_core.py:1106–1244` | **ported-diverged** — core added a `hovertemplate` and a full `animate=False` Plotly-frames play/pause feature (progressive game-time reveal) that has no notebook equivalent at all. |
| `Season.StatusGraph` / Power Rankings (notebook 2487–2647) | `sleeper_core.py:2637–2797` | **ported-diverged (minor)** — hardcoded `"gold"` annotation color replaced with a `LABEL_COLOR` theme constant; logic otherwise identical. |
| `Season.LuckChart` (notebook 1548–1653) | `sleeper_core.py:1661–1768` | **ported-diverged** — core adds `color_discrete_map=self.teamcolors` (per-team scatter coloring) and `bgcolor='rgba(26,58,82,0.7)'` annotation backgrounds; matches the CLAUDE.md-documented "Luck chart (YTD / This Week toggle)" feature that postdates the notebook. |
| `Season.PositionStengthPolar` (notebook 2253–2413, note the typo'd name) | `Season.PositionStrengthPolar` `sleeper_core.py:2392–2570` | **ported-identical** (logic unchanged, name corrected) |
| — (no notebook counterpart) | `Season.PositionStrengthHeatmap` `sleeper_core.py:2294–2392` | **core-only** — new positional-z-score heatmap view added alongside the ported polar chart. |
| `SideBet.Week1`–`Week10`, `Week12`, `Week13` (notebook 3718–4617) | `sleeper_core.py:4504–5450` | **ported-identical to ported-diverged** (spot-checked Week1/Week13 structurally match; per-week bodies not individually diffed) |
| — (no notebook counterpart) | `SideBet.Week11`, `SideBet.Week14`, `SideBet.get_week_config()` `sleeper_core.py:5279, 5342, 4389` | **core-only** — confirmed by git log ("Phase 7 complete: Week11/Week14 side bets"); notebook was never updated after this phase shipped. |
| `Survivor` class (notebook 2719–2816): `__init__(self, League)`, `SettingsJSONtoDF`, `find_unpicked`, `ProcessData`, `DisplayLogos` | `Survivor` class `sleeper_core.py:5450–5942` | **ported-diverged (major rewrite)** — constructor signature changed to `__init__(self, year: int)`, pulls from `data_loader.fetch_survivor_rosters/users` (cached) instead of live `requests.get` inside the class, and adds a `NFL_TEAMS` constant plus 2025 "revive mechanic" (`lost_leg_ids`) support the notebook's single-elimination-only model can't express. Six new chart methods (`pick_matrix_fig`, `elimination_timeline_fig`, `weekly_carnage_fig`, `team_graveyard_fig`, `win_margin_fig`, `longevity_leaderboard_fig`) replace the notebook's single `DisplayLogos`. The notebook version would need the caller graph rewritten to run at all against current data. |
| `PickEm` class (notebook 2817–2957): `__init__`, `SettingsJSONtoDF`, `Graph` | *(none)* | **notebook-only** — confirmed absent from `sleeper_core.py` (`grep -n "class PickEm"` returns nothing) and absent from `webapp/app.py`. This is the one real feature gap: a full class with a working `Graph()` method, exercised in the notebook (`PickEm_2025 = PickEm(League_PickEm_2025)`, cell 33-34) but never surfaced in the dashboard. |
| `AllTime` class core methods (`HallofFame_Team`, `HighestScoringLosers`, `SmallestMargins`, `TopScores`, etc., notebook 2962–3547) | `sleeper_core.py:3779–4342` | **ported-identical** (structurally matched; not exhaustively diffed) |
| — (no notebook counterpart) | `Playoffs` class `sleeper_core.py:3210–3450` | **core-only** — bracket resolution, best-player-per-matchup, bench-points-left; entire Playoffs tab backend. |
| — (no notebook counterpart) | `AllTimePlayoffs` class `sleeper_core.py:3450–3779` | **core-only** — cross-season playoff aggregation (Playoff Pedigree, Win Rate, Seeding vs Finish, Path to Glory charts). |
| — (no notebook counterpart) | `PlayoffCalculator` / `TeamPlayoffSnapshot` `sleeper_core.py:5942–6490` | **core-only** — full playoff-odds bitmask/Monte-Carlo simulation engine driving the This Week tab's Playoff Calculator card. Notably complex (500+ lines) and has zero notebook precedent to fall back on. |
| — (no notebook counterpart) | `Season.EPAScatter`, `WOPRTreemap`, `WaiverWireBump`, `LineupEfficiency`, `LineupEfficiencyChart` `sleeper_core.py:2866–3210` | **core-only** — five chart methods added directly to core with no notebook prototyping step. |
| Standalone scratch `def OptimalTeams(week):` (notebook cell 115, line 5307) | `Week.OptimalTeams` / `Season.OptimalTeams` (proper class methods, `sleeper_core.py:872, 1354`) | **notebook-only, and buggy** — this free function has a live bug: the `for position, group in DreamGroups:` loop immediately overwrites `position` with the stale `name[1]` from the *previous* loop (`OptGroups`), so `dream_lineup_df` construction is broken. Dead scratch code, not worth porting. |
| "Winnings Breakdown" money table (notebook cells 88–90, hand-entered `MoneyDF`) | *(none)* | **notebook-only** — manually keyed side-bet payout ledger for 2025, exploratory/personal bookkeeping, not chart logic. Not appropriate for `sleeper_core.py`. |
| Sankey "Points Flow" diagram (notebook cell 126) | *(none)* | **notebook-only** — one-off experiment, never reused, no cell output referenced elsewhere. |

*(15 findings above, ranked roughly by impact — architecture-level divergences first, scratch-code trivia last.)*

## Recommendation: source of truth going forward

**`sleeper_core.py` should be the sole source of truth immediately; the notebook should be formally retired (or renamed to "historical/exploratory"), not maintained as parallel authoritative source.**

Reasoning:
- Every actively-used piece of chart logic in the webapp already lives in and is driven from `sleeper_core.py` — the notebook's class definitions have not tracked featureset growth for at least 3 shipped phases (Playoffs tab, Playoff Calculator, Survivor 2025 revive mechanic, Side Bet Weeks 11/14).
- The notebook's own `CLAUDE.md` claim ("authoritative source for all chart logic") is already false for any method touched after the port — divergences above show core received bug fixes and feature work the notebook never got back.
- The only genuine unported feature (`PickEm`) is small (140 lines) and can be evaluated on its own merits (is Pick 'Em still an active league mechanic worth a dashboard tab?) rather than treated as evidence the notebook needs to stay authoritative.

## What retiring the notebook would take

1. **Triage `PickEm`** — decide whether Pick 'Em is still played. If yes, port the class (constructor + `SettingsJSONtoDF` + `Graph`) into `sleeper_core.py` following the `Survivor` pattern (route data access through a new `data_loader.fetch_pickem_*` cache function rather than raw `requests.get`), add a webapp tab or card, and write `tests/test_pipeline.py` coverage per this repo's testing convention. If no, discard.
2. **Update `CLAUDE.md`** (project root) — the line `Sleeper_v2.ipynb is the authoritative notebook for chart logic` (and the matching claim in `/CODING/CLAUDE.md`'s `Sleeper_v2.ipynb (180 cells) — authoritative source for all chart logic`) needs to be replaced with "`sleeper_core.py` is authoritative; the notebook is a historical exploration log, not maintained."
3. **Move or relabel the notebook** — either move `Sleeper_v2.ipynb` into `archive/` (consistent with this repo's existing convention of archiving superseded files) or add a banner cell at the top stating it is no longer maintained, so a future session doesn't reach for it when debugging chart behavior.
4. **No code migration needed for the bulk of the notebook** — the ~50 cells of per-year object instantiation (`League_2019 = League(2019, ...)`, `Week1_2019 = Week(1, League_2019)`, etc.) and the ~60 cells of scratch analysis have no durable value; they were exploratory scaffolding, not logic that needs preserving elsewhere.
5. **Optional cleanup** — the dead/buggy standalone `OptimalTeams(week)` function (notebook cell 115) and the manually-keyed `MoneyDF` winnings table should not be preserved anywhere; they're not referenced by core or the webapp.

No code changes were made to any project file other than this one; the extracted notebook script (`notebook_extracted.py`) and intermediate diff files remain in the scratchpad only.
