# Overall Project Review Plan — Sleeper Project

**Goal:** A full assessment of the tool — from the original `Sleeper_v2.ipynb` analysis through the conversion to the Dash web app — covering codebase quality, styling, infrastructure, and the data analysis itself. Assessment first, fixes later: each phase produces a findings report, not code changes. Fix work gets planned separately after the synthesis phase.

**How to run a phase:** Each phase is written as a self-contained subagent brief. In a fresh session, say "run Phase N of design/review-plan.md" and dispatch the brief below to a subagent with the recommended model. Each phase writes its findings to `design/review/phase-N-<name>.md`. Phases 1–5 are independent and can run in any order; Phase 6 requires all others.

**Status tracker**

| Phase | Focus | Model | Status |
|-------|-------|-------|--------|
| 1 | Notebook → core parity | sonnet | ✅ complete — `design/review/phase-1-notebook-parity.md` |
| 2 | Core library (`sleeper_core.py`) | opus | ✅ complete — `design/review/phase-2-core-library.md` |
| 3 | Webapp (`app.py` + auth + callbacks) | opus | ✅ complete — `design/review/phase-3-webapp.md` |
| 4 | Styling & front-end (CSS + D3 + UX) | sonnet | ✅ complete — `design/review/phase-4-styling.md` |
| 5 | Infrastructure & repo hygiene | sonnet | ✅ complete — `design/review/phase-5-infra-hygiene.md` |
| 6 | Data-analysis soundness | fable | ✅ complete — `design/review/phase-6-analysis-soundness.md` |
| 7 | Synthesis & fix roadmap | fable | ✅ complete — `design/review/synthesis.md` |

---

## Phase 1 — Notebook → Core Parity Audit (model: sonnet)

**Question:** Is `sleeper_core.py` a faithful, complete port of `Sleeper_v2.ipynb`, and should the notebook still be called "authoritative"?

Subagent brief:
- Extract the notebook's code cells (`jupyter nbconvert --to script` into scratchpad — do NOT read the .ipynb raw, it's 2.4MB with embedded outputs).
- Map notebook chart/analysis logic to its counterpart in `sleeper_core.py`. Flag: logic that exists only in the notebook (unported), logic that diverged (port was later edited), and logic that exists only in core (notebook is stale).
- Deliverable: a parity table + a recommendation on which artifact should be the source of truth going forward, and what "retiring" the notebook would take.

## Phase 2 — Core Library Review (model: opus)

**Question:** How maintainable and correct is `sleeper_core.py` (6,490 lines, 14 classes, 152 functions)?

Subagent brief:
- Review class design: `League`, `Week`, `Season`, `Playoffs`, `AllTimePlayoffs`, `AllTime`, `SideBet`, `Survivor`, `PlayoffCalculator`. Assess coupling, especially the module-level mutable dicts (`AllMatchesDict`, `AllBreakoutDict`, `OptimalScoresByYear`) populated as side effects of construction.
- Assess config-as-code: `roster_ids`, `SIDE_BET_SEASONS`, `leagueNumbers_Dict` embedded in the module — should these be data files?
- Look for: duplicated chart-method boilerplate across the 30+ chart methods, pandas anti-patterns (chained indexing, iterrows in hot paths), error-handling gaps, name-vs-ID joins (past bug source — see git log).
- Do NOT report style nits; focus on structural risk and correctness. Rank findings by blast radius.
- Deliverable: findings report + a candidate decomposition sketch (what a split into modules would look like) with an honest cost/benefit for a hobbyist maintainer.

## Phase 3 — Webapp Review (model: opus)

**Question:** Is `webapp/app.py` (3,319 lines, ~77 functions) sound as a long-lived app — callbacks, auth, data loading, error handling?

Subagent brief:
- Verify the SECTION MAP docstring matches reality (line numbers drift — L1976 Survivor is already out of order in the map).
- Review the auth layer (itsdangerous token, login route, middleware) — it's a friends-league password gate, judge it at that threat level, but flag anything that leaks data without any auth.
- Review the data-store/threading pattern (`_load_bg`, `_ensure`, `_loading_years`, `_failed_years`): race conditions, the known issue where `_year_changed` blocks up to 30s on `_ensure` (see claude-mem obs 550–552 — 2020 Side Bets tab 10–50s delay).
- Review callback structure: per-tab render functions, toggle callbacks, D3 store population — duplication, error-figure handling consistency (past bugs: error figs not wrapped in dcc.Graph).
- Deliverable: findings report ranked by user-visible impact, with the perf/blocking issues quantified where possible (time a cold `_ensure` per year).

## Phase 4 — Styling & Front-End Review (model: sonnet)

**Question:** Is the visual layer (`style.css` 1,361 lines, `d3charts.js` 1,487 lines, `gridiron_ink` template) coherent, and does the app hold up in the browser?

Subagent brief:
- Audit `style.css` for dead selectors (grep class names against `app.py` and `d3charts.js`), inconsistent use of the CSS variables vs hardcoded colors, and responsive behavior (is there any mobile handling at all?).
- Review `d3charts.js`: renderer structure, memory/listener leaks on tab switches, duplication across chart renderers.
- Live check with Playwright per the CLAUDE.md hierarchy (snapshot/console/evaluate first; screenshots only for genuinely visual questions): load each of the 8 tabs, capture console errors, note layout breakage. Budget screenshots — a handful max.
- Assess the `gridiron_ink` theme itself: contrast/readability (light text on `#163146`, Courier New everywhere), chart legibility.
- Deliverable: findings report + a short list of highest-value visual improvements.

## Phase 5 — Infrastructure & Repo Hygiene Review (model: sonnet)

**Question:** Is the project's plumbing — caching, tests, git state, deployability — in good shape?

Subagent brief:
- Cache layer: review `data_loader.py`; assess the 363MB `.cache/` (what's in it, per-year size, invalidation story, is MD5 keying doing anything useful).
- Tests: 171 collected across 5 files. Assess coverage honestly — what's tested (data shapes, chart smoke) vs not (callbacks, auth, D3, data_loader itself). Run the suite and report the state, including the known StringDtype/object dtype failure (obs 530/542).
- Git/repo state: uncommitted modifications on main, untracked dirs (`.antigravitycli/`, `.playwright-mcp/`, `playwrite_screenshots/`, `stitch-bracket/`, `webapp/startup*.log`), `.gitignore` gaps, secrets check (SECRET_KEY handling, the hardcoded `legacy` password — it's in CLAUDE.md which is committed to a public repo).
- Deployability: the app runs on localhost only. Assess what deploying to the Pi (per global CLAUDE.md workflow) would require — gunicorn, service file, cache on Pi, memory footprint.
- Deliverable: findings + a concrete hygiene checklist (gitignore additions, files to archive/delete, dtype test fix).

## Phase 6 — Data-Analysis Soundness Review (model: fable)

**Question:** Is the analysis itself — the numbers the league sees — statistically sound and correctly computed?

Subagent brief:
- Review the analytical methods on their merits: luck chart methodology, power rankings formula, `PlayoffCalculator` bitmask enumeration (is the probability model right? does it handle tiebreakers per league settings?), optimal-lineup computation, bench-points-left, Pythagorean-style metrics if present.
- Spot-verify computations against raw cached data for one known season (e.g. 2023 or 2024): recompute a week's optimal score, a team's playoff odds at a checkpoint, a luck value — by hand in a scratchpad script — and compare.
- Assess join integrity: player-name vs player-ID joins, roster_id → username mapping across years (past bugs here), traded/multi-team players, missing-stat weeks.
- Flag analyses that are computed correctly but interpreted questionably (e.g. small-sample rankings presented without caveats) — this is a judgment call, which is why this phase gets the strongest model.
- Deliverable: soundness report — "trustworthy / correct-but-fragile / suspect" rating per analysis, with reproduction evidence for anything flagged.

## Phase 7 — Synthesis & Fix Roadmap (model: fable)

**Question:** Given phases 1–6, what's the overall verdict and what should actually be fixed, in what order?

Subagent brief (or run in main session):
- Read all `design/review/phase-*.md` reports. Deduplicate overlapping findings, resolve conflicts between reports.
- Produce the overall assessment the user asked for: strengths/weaknesses across codebase, styling, infrastructure, analysis — written for the project owner (hobbyist, self-taught), honest about what's genuinely good.
- Produce a prioritized fix roadmap sized in sessions, distinguishing "do this, it's load-bearing" from "nice to have" from "not worth it for a hobby project."
- Deliverable: `design/review/synthesis.md` — this becomes the input to future fix-phase planning.

---

## Post-review fix work (noted during review, plan after Phase 7)

- **Sleeper notebook v3:** Create a `Sleeper_v3.ipynb` that still lets the owner generate static charts interactively, but fixes the problems Phase 1 found in `Sleeper_v2.ipynb` — instead of duplicating logic, it should be a thin notebook that imports `sleeper_core` + `data_loader` (the source of truth) and calls chart methods, replacing the stale 5,470-line copy of the code. This pairs with retiring/archiving `Sleeper_v2.ipynb`.

## Model rationale

- **sonnet** (Phases 1, 4, 5): high-volume mechanical work — parity mapping, grep-driven audits, running tools. Judgment needed is moderate; throughput matters more.
- **opus** (Phases 2, 3): deep single-file code review where finding real structural/concurrency issues (not nits) is the whole game.
- **fable** (Phases 6, 7): the phases where being *right about judgment calls* matters most — statistical soundness and the final prioritization. Also the most expensive model, so it's reserved for the two phases where it earns it.

## Ground rules for every phase

- Read-only: no edits to project files; findings go to `design/review/phase-N-<name>.md`.
- Use `.cache/` data — no live Sleeper API calls.
- Rank findings by impact; cap reports at the ~15 findings that matter, not an exhaustive nit list.
- Cite `file:line` for every finding.
- If the dev server is needed (Phase 4), follow the kill-then-restart procedure in CLAUDE.md.
