# Phase 7 — Synthesis & Fix Roadmap

Date: 2026-07-14
Inputs: `phase-1-notebook-parity.md`, `phase-2-core-library.md`, `phase-3-webapp.md`, `phase-4-styling.md`, `phase-5-infra-hygiene.md`, `phase-6-analysis-soundness.md`, plus `design/review-plan.md` (goal + post-review Sleeper_v3 note).

---

## 1. Overall verdict

**The app is genuinely good where it's hardest to be good, and wrong where it's easiest not to notice.**

The parts most hobby projects get wrong — a coherent design system, a working cache layer, real error handling in the UI, an actual test suite, a functioning 8-tab dashboard with zero console errors — are all in solid shape here. The parts that are broken are quiet: **several numbers shown to the league are simply incorrect** (optimal lineups wrong for 11 of 12 teams in the verified week, player season totals inflated 4× for same-name players, lineup efficiencies over 100%, the luck-chart quadrant line drawn at the wrong median), and **the All-Time tab silently shows only the seasons you've happened to click on**. None of these throw an error, which is exactly why they survived — the smoke tests confirm charts render, not that they render the truth.

The good news buried in the reports: almost every serious finding traces back to a small number of root causes, and the two most feared problems turned out to be smaller than expected (see §3). A focused half-dozen work sessions fixes everything that actually matters. The big scary refactors (splitting the 6.5k-line core file, removing the module-global dicts) are explicitly **not** required to get the numbers right.

### Scorecard by area

| Area | Grade | One-line summary |
|---|---|---|
| **Analysis correctness** | ⚠️ Weakest area | Power rankings verified exact; but optimal lineups, efficiency, player YTD totals, and the luck-chart divider are all wrong in user-visible ways (Phase 6, with reproductions) |
| **Core library** (`sleeper_core.py`) | Fragile but functional | Works on the happy path; module-global dicts, name-based joins, and zero I/O error handling are the structural debt (Phase 2) |
| **Webapp** (`app.py`) | Good with two real bugs | Error handling unusually thorough; auth posture correct for the threat level; but All-Time under-reports and year-switch strands users on "Loading…" (Phase 3) |
| **Styling / front-end** | Strongest area | One palette across CSS/Plotly/D3, AAA contrast, zero console errors on all 8 tabs; a few undefined CSS vars and a broken mobile bottom nav (Phase 4) |
| **Infrastructure** | Solid, untidy | Cache layer correct; 170/171 tests pass; but a large uncommitted diff sits on `main`, secrets defaults are public, and untracked exhaust litters the tree (Phase 5) |
| **Notebook parity** | Resolved question | `Sleeper_v2.ipynb` is stale, not authoritative; core has outgrown it by 6 classes. Retire it (Phase 1) |

### What's genuinely good (say it out loud)

- **Power Rankings verified exactly correct** against independent recomputation — the flagship analytic is trustworthy.
- **The design system reads as one designed object** across three technologies (CSS, Plotly template, D3). Rare at any scale of hand-rolled front-end. Main text contrast is WCAG AAA.
- **Auth is right for the job**: all data endpoints gated, no unauthenticated leak found, and the token approach is proper (the one gap is the public default signing key — see §4, Cluster E).
- **Warm-cache performance is excellent**: every season loads in ~0.13s. The feared 30-second blocking does not exist.
- **The test suite is a real regression net for the data layer** (170 passing tests, cache-based, no API calls) — good enough that the fixes below can be verified.
- **Error handling in the webapp is unusually thorough** — every chart is wrapped, and the past "error fig not in dcc.Graph" bug class is confirmed fully fixed.
- **The port from notebook to core was done well**: every shared method is line-for-line identical or deliberately improved. The notebook is stale because core moved *forward*, not because the port was sloppy.

---

## 2. Deduplication & conflict resolutions

Where reports overlapped or disagreed, resolved as follows:

1. **`sleeper_core.py:902` stale-loop-variable** — Phase 2 flagged it as a correctness bug (finding #2); Phase 6 confirmed the bug (finding #8) but proved **zero user impact**: `DreamTeamDF` is never referenced by `webapp/app.py`. Resolution: downgrade from "fix this week" to "delete the dead loop while rewriting `Week.OptimalTeams`" (same method, same session).
2. **"41 dead CSS classes" (Phase 5's earlier framing)** — Phase 4 re-audited: ~22 of the 41 style Dash/react-select/rc-slider generated DOM and are live; **~19 are genuinely dead** (~100–120 lines). Resolution: use Phase 4's list.
3. **"`_year_changed` blocks up to 30s"** — Phase 3 disproved it with measurements: `_ensure` is non-blocking and warm loads are 0.12–0.15s/year. The real bug is that **nothing re-fires the render** when the background load finishes (Phase 3 #2). Phase 4's "All-Time is the slow one" (#14) is the same mechanism, not a perf problem. Resolution: fix is re-render wiring + eager load, not optimization.
4. **Playoff bracket "Efficiency" badges** — three findings are one symptom chain: values inherit the `Week.OptimalTeams` flex bug (Phase 6 #1), *and* the badges are usually `None` anyway because `OptimalScoresByYear` isn't snapshotted by the cache (Phase 6 #7, which is also an instance of Phase 2 #1 / Phase 3 #5's global-dict coupling). Resolution: grouped under Clusters B and C below.
5. **H2H tab empty on first open** — Phase 4 #9 spotted it in the browser; Phase 3 didn't list it but it's an `app.py` callback-wiring issue. Kept, assigned to the webapp session.
6. **Secrets** — Phases 3 and 5 found the same thing from two angles (forgeable cookie vs. public-repo exposure). Merged into Cluster E.
7. **Debug mode ships in the served app** — flagged by both Phase 4 (#11) and Phase 5 (deployability). Merged into Cluster E / deploy prep.
8. **Python version** — CLAUDE.md says 3.11; the venv is actually 3.12.7 (Phase 3 #12). Doc fix only.

---

## 3. Findings grouped by root cause

Most of the ~60 raw findings collapse into eight clusters. Fixing the cluster's root fixes every symptom listed under it.

### Cluster A — Name-based joins instead of player-ID joins ⟶ *wrong numbers*
**Root:** `Week.PlayerBreakout` merges on player *name* at `sleeper_core.py:732` and `:752`, propped up by name-mangling regexes and hardcoded row fixups (`:682–691`). The ID migration (commit `fd45842`) fixed the stats join but was left half-finished.
**Symptoms:** Josh Allen shown at ~1,791 season pts vs. true 447.6 (exactly 4× — Players tab); Lamar Jackson and Michael Thomas likewise; BrawnyBench +129 pts for one team; duplicate rows let optimal lineups "start" the same player twice; future name collisions silently drop players (position → NaN).
**Also in cluster:** the `week` column in `BreakoutSeason` is an NFL-stats artifact (15–22), not the fantasy week — the real week is `week_x` (Phase 6 #2 side effect); document or rename during the fix.

### Cluster B — `Week.OptimalTeams` is wrong ⟶ *wrong numbers*
**Root:** the FLEX pick groups by `recent_team` (NFL franchise) instead of fantasy team (`sleeper_core.py:920`). Lineups range 8–13 players instead of 10.
**Symptoms:** weekly optimal scores wrong for 11/12 teams in the verified week (−7.6 to +25.9 pts); the This Week Power Rankings **Efficiency column** off by up to ~17 percentage points; playoff bracket efficiency badges wrong when populated; `Season.LineupEfficiency` shows impossible >100% for 6/12 teams (its own second bug: filtering on `week_NFL` excludes all DEF — fix is `week_x` + dedupe by `player_id`).
**Free rider:** the confirmed-but-harmless DreamGroups stale-variable bug (`:901–908`) lives in the same method — delete it during the rewrite. `Season.OptimalTeams` already does pooled flex correctly; copy that pattern. Also delete/repair the dead `Week.LuckScore` (`:958`, `NameError`) and the `Season.Calc` team-path `NameError` (`:1558`) while in the file.

### Cluster C — Module-global dicts populated as construction side effects ⟶ *silent incompleteness & races*
**Root:** `AllMatchesDict` / `AllBreakoutDict` / `OptimalScoresByYear` (`sleeper_core.py:457–473`) are written as side effects of building `Week` objects and read by nearly everything, including `webapp/app.py` directly.
**Symptoms:** **All-Time tab silently shows only browsed seasons** (Phase 3 #1 — a fresh session's "all-time" charts are 2025-only); choropleth/chord stores have the same defect and don't re-fire on year change (Phase 3 #11); unlocked read/write race between the load thread and callbacks (Phase 3 #5); `OptimalScoresByYear` never snapshotted by the cache, so bracket efficiency is `None` on every cache load (Phase 6 #7); `data_loader` must hand-patch globals on every cache hit for anything to work at all.
**Pragmatic fix (cheap):** eager-load all 7 years at startup (~0.9s warm total per Phase 3's timings), have callbacks read only the `_data[year]` snapshot, add `OptimalScoresByYear` to the cache payload. **Full fix (expensive):** move the dicts to `Season`-owned instance state — deferred, see roadmap Tier 3.

### Cluster D — Loading/re-render wiring in `app.py` ⟶ *"Loading…" forever*
**Root:** the `boot` interval is the only re-render poller and is permanently disabled after first load; `_year_changed` starts a background load but never re-arms it.
**Symptoms:** switching to an unloaded year strands the user on a static "Loading season data…" until they poke something (this — not blocking — was the reported 10–50s "delay"); All-Time perceived slowness; H2H tab renders empty until a selection changes (Phase 4 #9); `_year_changed` redundantly double-starts the load thread (harmless).
**Note:** eager startup loading (Cluster C's cheap fix) makes most of this moot; re-arming `boot` on year change is the belt-and-suspenders line.

### Cluster E — Secrets & deploy posture (friends-league threat level)
**Root:** `SECRET_KEY` defaults to a literal and `LEAGUE_PASSWORD` to `legacy`, both committed to the **public** repo (`webapp/app.py:122–123`), the password also documented in the committed CLAUDE.md; no `.env` exists, so the app currently runs on the public defaults. Anyone can forge a valid auth cookie with the public signing key — the gate is effectively open.
**Also:** `debug=True` in `__main__` (Werkzeug debugger = RCE if ever exposed); unauthenticated `/debug-error` log-spam sink (low). The rest of the auth layer is verified sound — data endpoints are gated, nothing leaks without a token.
**Judgment:** the *password* being weak is fine at this threat level; the *signing key* being a known public constant is the one thing to actually fix. Fail loudly if `SECRET_KEY` is unset.

### Cluster F — Theme defined three times + copy-paste boilerplate ⟶ *drift, not danger*
**Root:** the palette lives in CSS `:root`, in `sleeper_core.py`'s template, and as raw hex sprinkled through `d3charts.js`; the 9 D3 renderers share ~80% copy-pasted scaffolding; `UpdateColors`/`SetTeamColors` duplicated across 3–5 classes; error-graph wrapping copy-pasted ~55× in `app.py`; 30+ chart methods repeat Plotly layout boilerplate.
**Symptoms already caused by drift:** four undefined CSS variables (`--grid`, `--text`, `--card-bg`) silently break Playoffs/Side Bets card styling; `#1C3C54` near-miss for `--bg-card`; `.tab-selected` duplicate. Plus the D3 listener/timer leaks in `renderScoreRace` and unbounded `_waitForEl` retry stacking (real leaks, modest impact).

### Cluster G — Config-as-code (`roster_ids`, `SIDE_BET_SEASONS`, `leagueNumbers_Dict`)
~250 lines of hand-edited seasonal data inside the module; a typo breaks import of everything; `roster_ids_2024` is literally the same dict object as 2023 (mutation landmine). Move to `data/*.json`; make the yearly "add a season" chore safe.

### Cluster H — Stale artifacts & repo hygiene
The notebook is no longer authoritative and CLAUDE.md's claim that it is should be removed (Phase 1); the `app.py` SECTION MAP is wrong on every line (Phase 3 #4); a ~1,900-line uncommitted diff sits on `main` with no backup; `sidebets_historical/` + `scripts/parse_sidebet_xlsx.py` are real source data at risk of loss (untracked); ~20 MB of Playwright/screenshot exhaust and logs need gitignoring; one test fails on a pandas `StringDtype` strictness issue (not a data bug); CLAUDE.md says Python 3.11, venv is 3.12.7.

### Standalone findings (no cluster)
- **Playoff Calculator semantics** (Phase 6 #4): enumeration math verified correct, but already-played games in week ≥ `as_of_week` are discarded, so every retroactively-computed checkpoint collapses to 0%/100% — the "odds trajectory" chart is a step function, not a probability history. Plus a latent out-of-bounds on rematch pairs, and two model caveats worth a UI footnote (50/50 games, frozen PF).
- **Tie handling** (Phase 6 #12): a tied matchup would award both teams a win. Never happened in league history; cheap insurance.
- **Hardcoded lineup slots** (Phase 6 #13): QB1/RB2/WR2/TE1/FLEX1/K1/DEF1 duplicated in three places instead of read from league settings — add a one-time assertion.
- **Mobile bottom nav** (Phase 4 #3): renders as a full-height vertical stack on phones, covering half the screen. One CSS rule.
- **Small-sample presentation** (Phase 6 #14): H2H win pie and HeatCheck are computed correctly but presented without sample-size context — add "n games" annotations.
- **Plotly template sized for notebooks, not cards** (Phase 4 #10): `height=1000`, title 45pt, `margin t=130` waste space in every card.
- **No error handling on network calls** (Phase 2 #4): any API blip crashes a whole year load; the week-loop's broad `except` then hides real bugs. Timeouts + `raise_for_status` + narrower catch.
- **`invalidate_week` gap** (Phase 5): doesn't bust per-week raw caches. Doc note or 3-line fix.
- **PickEm** (Phase 1): the one real notebook-only feature. Decide if Pick 'Em is still played before porting or discarding.

---

## 4. Prioritized fix roadmap

Sized in **work sessions** (one session ≈ a focused evening, 2–4 hours). Order matters within Tier 1: the join fix (Session 2) feeds correct inputs to everything after it.

### Tier 1 — Do this, it's load-bearing (wrong numbers & silent lies)

**Session 1 — Housekeeping & safety net** *(short session)*
Commit the pending ~1,900-line diff (it's the app that currently runs, with no backup); reconcile the three deleted `design/*.md` files; commit `scripts/parse_sidebet_xlsx.py` + `sidebets_historical/`; gitignore `.playwright-mcp/`, `playwrite_screenshots/`, `*.log`, `.antigravitycli/` and delete the exhaust; fix the `StringDtype` test (`tests/test_playoffs.py:62`) so the suite is green before any correctness work; correct the Python-version line in CLAUDE.md.
*Why first:* everything after this needs a clean baseline and a passing suite to diff against.

**Session 2 — Kill the name-join bug class (Cluster A)**
Replace both name merges in `PlayerBreakout` (`sleeper_core.py:732`, `:752`) with `player_id`/gsis-based joins (the crosswalk at `:743–748` is the pattern), or at minimum dedupe on (`team`, `week`, `player_id`) immediately after; delete the name-mangling fixups (`:682–691`) once unneeded; add regression tests asserting Josh Allen's 2023 total ≈ 447.6 and `BreakoutSeason` row count == unique (team, week, player_id).
*Fixes:* 4× player inflation (Players tab), BrawnyBench overcounts, duplicate-player optimal lineups, the whole future-name-collision bug class.

**Session 3 — Fix the optimal-lineup family (Cluster B)**
Rewrite `Week.OptimalTeams` to the per-team pooled-flex pattern already correct in `Season.OptimalTeams`; delete the dead DreamGroups loop (`:901–908`), `Week.LuckScore`, and the `Calc` NameError path; fix `LineupEfficiency` (`week_x` filter + `player_id` dedupe); one-line `LuckChart` median fix (`:1688`, `median_opp` → `median_score`); add value-asserting tests against Phase 6's reference numbers (2023 W5).
*Fixes:* wrong optimal scores for ~11/12 teams, the Efficiency column, >100% efficiencies, mis-classified luck quadrants.

**Session 4 — All-Time completeness & loading limbo (Clusters C-cheap + D)**
Eagerly `_ensure(y)` for all years at startup (~0.9s warm); re-enable the `boot` interval in `_year_changed` (or give `_loading_placeholder` its own interval); make callbacks read from the `_data[year]` snapshot instead of `core.*Dict` globals; add a year/data-ready input to the choropleth/chord store callbacks; snapshot `OptimalScoresByYear` in `data_loader`'s cache payload (fixes the always-`None` bracket efficiency); render H2H with its default pair on tab open; drop the redundant thread start in `_year_changed`.
*Fixes:* the silent 2025-only "All-Time" charts, the eternal "Loading…", empty H2H, dead efficiency badges, and defuses the practical race risk.

**Session 5 — Secrets & deploy posture (Cluster E)** *(short session)*
Remove the fallback defaults: `os.environ['SECRET_KEY']` (fail loudly), same for the password; generate real values into an untracked `.env` / future systemd `Environment=`; change the actual password since `legacy` is public forever in git history; remove the password from the committed CLAUDE.md; ensure `debug=True` can't reach any deployed path; gate or drop `/debug-error`.
*Note:* old defaults live in git history permanently — rotating the real values is the fix, not history rewriting.

### Tier 2 — Nice to have (real value, no wrong numbers at stake)

**Session 6 — Front-end quick wins (Cluster F symptoms + mobile)**
Fix the four undefined CSS variables (10-minute find/replace — restores Playoffs/Side Bets card styling); force `flex-direction: row` on the mobile bottom nav + let team chips wrap (the difference between usable-at-the-bar and not); add teardown to `renderScoreRace` and a cancellation guard to `_waitForEl`; delete the ~19 dead classes / Bootstrap shim (~120 lines); right-size the Plotly template for cards (height, title size, margins) — every tab gets denser for free.

**Session 7 — Config to data files + I/O hardening (Cluster G + network)**
Extract `roster_ids` / `SIDE_BET_SEASONS` / `leagueNumbers_Dict` / `SURVIVOR_LEAGUE_IDS` to `data/*.json` loaded at import; fix the `roster_ids_2024` shared-reference alias in passing; add timeouts + `raise_for_status()` to all raw `requests.get` calls and narrow the week-loop `except`. Makes the yearly "add a season" edit safe and load failures diagnosable.

**Session 8 — Retire the notebook (Cluster H + review-plan note)**
Archive `Sleeper_v2.ipynb`; create the planned **`Sleeper_v3.ipynb` as a thin wrapper** that imports `sleeper_core` + `data_loader` and calls chart methods — interactive chart generation without a 5,470-line logic copy; update both CLAUDE.md files ("authoritative notebook" claim); decide PickEm's fate (still played? port following the Survivor pattern; not? discard); regenerate or de-number the `app.py` SECTION MAP (grep-able marker names only).

**Session 9 — Playoff Calculator semantics + presentation honesty**
Fold played-game results into standings instead of discarding (`:6119`); label retroactive checkpoints or persist only mid-season snapshots; guard the rematch-pair indexing; add UI footnotes (50/50 model, frozen PF); add "n games" to the H2H win pie; fix tie handling (`:807`) and add the lineup-slots-vs-settings assertion. Cheap insurance for the analytics' credibility.

**Session 10 — Boilerplate consolidation (Cluster F root)**
One `_err_graph(e)` helper in `app.py` (replaces ~55 copies, prevents the wrapping-drift bug class recurring); shared `UpdateColors`/`SetTeamColors` mixin; `setupChart`/`makeTooltip` helpers in `d3charts.js` + read colors from CSS variables (`getComputedStyle`) — single-source theme, several hundred lines gone. Do only when touching those files anyway; it's leverage, not urgency.

### Tier 3 — Only if the pain justifies it

- **Pi deployment** (Phase 5's checklist): `sleeper.service` with gunicorn `--workers 1` (measured ~620 MB RSS holding all seasons — multiple workers would multiply it), env-var secrets, Caddy route, cache seeding via rsync. Well-scoped, no blockers — do it when you actually want it live, after Session 5.
- **Module-global dict removal + file split** (Phase 2 #1 and the decomposition sketch): the *real* structural debt, but Session 4's snapshot-reads defuse the user-visible harm. Phase 2's advice stands: land the quick fixes, grow tests around the year-boundary/cache-rehydration paths, *then* move the dicts to `Season`-owned state — and only split files after that. Do not start here.
- **Dash callback / auth pytest coverage**: nice in principle; the Playwright hierarchy in CLAUDE.md covers it adequately for one maintainer.

### Not worth it for a hobby project

- MD5 suffix removal in cache keys, cache TTL/pruning (363 MB on a Mac and a 4–8 GB Pi is fine).
- Replacing `iterrows` at 12-team scale; the nth-child animation stagger cap; the team-chip double-tooltip; a JS test harness for `d3charts.js`.
- Preserving anything from the notebook's ~110 scratch/instantiation cells, the buggy standalone `OptimalTeams`, or the hand-keyed winnings table.
- Rewriting git history over the leaked defaults — rotate the live values (Session 5) and move on.

---

## 5. Suggested sequencing summary

```
Tier 1 (do now):     S1 hygiene → S2 ID joins → S3 optimal/efficiency → S4 all-time/loading → S5 secrets
Tier 2 (this season): S6 front-end → S7 config+I/O → S8 notebook v3 → S9 playoff-calc/presentation → S10 boilerplate
Tier 3 (on demand):  Pi deploy · globals refactor (tests first) · callback tests
```

After Tier 1, every number the league sees is correct, the All-Time tab tells the truth, year-switching works, and the door isn't held open by a public signing key. Everything after that is polish and future-proofing — worth doing, but the league stops being lied to five sessions from now.
