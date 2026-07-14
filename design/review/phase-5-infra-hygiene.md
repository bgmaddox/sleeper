# Phase 5 — Infra Hygiene Review (Cache / Tests / Git / Deployability)

Date: 2026-07-14

## 1. Cache layer (`data_loader.py`)

- `data_loader.py:17-19` — cache key is `f"{key}_{md5(key)}.pkl"`. The human-readable `key` prefix is
  already unique per (data-type, year, week, league_id) tuple, so the MD5 suffix is pure noise — it
  adds zero collision protection (the prefix alone is already the true key) and makes the `.cache/`
  directory harder to eyeball/grep. Purely cosmetic overhead, not a bug.
- `data_loader.py:202-279` (`load_data_for_year`) is the only *expensive* cache entry — one pickle
  per `(year, max_week=18)` holding the full `League` + `Week` dict + `Season` object graph.
  These are 43–54 MB each (`.cache/season_data_<year>_18_*.pkl`), accounting for ~350 MB of the
  363 MB total. This is a full object-graph pickle (not just the underlying DataFrames), so it's
  bulkier than necessary — Season/League objects likely carry duplicated references to the same
  player/week DataFrames across pickles.
- `data_loader.py:333-340` (`invalidate_week`) only busts the season-level cache; it does **not**
  invalidate the per-week `matchups_*`, `transactions_*`, or `playoff_probs_*` caches for that
  year, meaning a forced re-fetch of `load_data_for_year` will still read stale week-level raw
  JSON from disk if those fine-grained keys already exist. In practice this only matters if a
  week's transactions/matchups changed *after* being cached but the caller invalidates only the
  season — worth a doc note or a real fix (delete `transactions_<league>_<week>*` and
  `matchups_<league>_<week>*` too).
- `fetch_state_json()` (`data_loader.py:89-93`) is correctly *not* cached — confirmed by the May 24
  observation log ("remove caching from fetch_state_json to always reflect current week"), so this
  is intentional and correct, not an oversight.
- No TTL/expiry or cache size cap anywhere — `.cache/` only grows. For a repo that's meant to run
  indefinitely on a Pi, nothing currently prunes stale `playoff_probs_*` or per-week transaction
  files from prior seasons once games are final and data won't change.
- `.cache/` is correctly gitignored (`.gitignore:9`: `.cache/` and `*.pkl`) — no risk of ~363 MB of
  pickles landing in the public repo.

**Verdict:** functionally solid, no correctness bugs found. The MD5 keying is cosmetic-only, and
`invalidate_week` has a latent gap around raw per-week caches. Not urgent.

## 2. Tests

Ran: `source .venv/bin/activate && pytest tests/ -m "not slow" -q`

**Result: 170 passed, 1 failed, 3 deselected** (of ~174 collected, matching the "~171 collected"
description once `-m "not slow"` deselects 3).

Failure:
```
tests/test_playoffs.py:62 TestBreakoutPlayerID::test_player_id_is_string_for_known_players
AssertionError: player_id column should be string/object dtype
assert <StringDtype(storage='python', na_value=nan)> == object
```
The test asserts `non_null.dtype == object`, but the `player_id` column is now backed by pandas'
newer `StringDtype` (`storage='python'`), which is functionally a string column but is **not**
`==` to `object` dtype in current pandas. This is very likely a pandas version bump side effect
(pandas 2.x infers `string[python]` more aggressively in some construction paths) rather than a
real data bug — the underlying values are correct strings. The test's dtype check is just too
strict/outdated. Fix: compare against `pd.api.types.is_string_dtype(non_null)` or explicitly
`assert non_null.dtype in (object, "string")` instead of `== object`.

Coverage assessment (what's actually tested vs not), by file:
- `tests/test_pipeline.py` (332 lines) — data shape/integrity: DataFrame columns, dtypes, row
  counts, `League`/`Week`/`Season` construction from cached data. Good breadth here.
- `tests/test_charts.py` (229 lines) — chart *smoke* tests: calls chart methods, asserts a Plotly
  `Figure` comes back and doesn't raise. Does not assert on chart content/values, colors, or trace
  correctness — a chart that silently plots the wrong column would still pass.
- `tests/test_playoffs.py`, `test_alltime_playoffs.py`, `test_sidebet.py` — same shape/smoke
  pattern applied to Playoffs/AllTimePlayoffs/SideBet classes.
- **Not tested at all:**
  - `webapp/app.py` — zero test coverage of any Dash callback, the auth/login flow
    (`webapp/app.py:101-` per SECTION MAP), URL deep-linking, or tab routing. All ~3300+ lines of
    the actual web app are untested by pytest; only exercised via the parallel Playwright/manual
    verification workflow described in this project's `CLAUDE.md`.
  - `data_loader.py` itself — no unit tests for `_cache_path`, `_load_cache`/`_save_cache`,
    `invalidate_week`, or `load_playoff_probs`'s week-range logic. Since everything loads from
    `.cache/` in tests (per the project's own testing convention), the caching *mechanism* has no
    direct test, only its downstream consumers.
  - `d3charts.js` / D3 clientside rendering — no JS test coverage at all (expected, no JS test
    harness in this repo).
  - Auth/session — `SECRET_KEY`/token flow in `webapp/app.py:155` (`URLSafeTimedSerializer`) has no
    test for expiry, tampering, or invalid-token handling.

**Verdict:** the suite is a reasonable regression net for the data layer (Season/League/Week/
Playoffs), but "chart renders without throwing" is the ceiling of chart coverage, and the entire
Dash/Flask app layer (callbacks, auth, routing) has 0% pytest coverage — it's covered only by the
manual Playwright verification hierarchy in `CLAUDE.md`, which isn't run automatically.

## 3. Git / repo state

Current branch `main`, remote `https://github.com/bgmaddox/sleeper.git` — **this is a public repo**
per the user's global CLAUDE.md repo table.

**Tracked-file modifications** (uncommitted, on disk, `git diff --stat`):
```
CLAUDE.md               |  25 +-
data_loader.py          |  95 ++
sleeper_core.py         | 1146 ++++++++...
webapp/app.py           | 379 ++++...
webapp/assets/style.css |  54 ++
tests/*.py              | ~200 lines added across 3 files
design/roadmap.md       | 213 ++
```
Also **deleted-but-uncommitted**: `design/Issues.md`, `design/fix-plan.md`,
`design/name_matching_audit.md` — these show as `D` in git status, meaning they were removed from
disk without a corresponding commit. If intentional, this needs a commit; if accidental, they can
still be recovered with `git checkout -- <path>` since nothing has been committed yet.

**Untracked files/dirs** — assessed by nature:
- `.antigravitycli/a710faf2-....json` — appears to be local tool state from a different agent
  (Antigravity CLI), not project content. Should be gitignored, never committed.
- `.playwright-mcp/` — 245 files, 7.0 MB of console logs/snapshots/screenshots from Playwright MCP
  sessions (`console-*.log`, `page-*.yml`, `element-*.png`). Pure debugging exhaust — should be
  gitignored, and the directory can be deleted locally to reclaim ~7 MB.
- `playwrite_screenshots/` (note: misspelled "playwrite") — 56 files, 13 MB. Same story — ad hoc
  screenshot dumps, not referenced by any app code or test. Gitignore + safe to delete.
- `stitch-bracket/` — 80 KB, contains `bracket.html` + `bracket-screenshot.png`. Looks like a
  one-off Stitch design prototype for a bracket UI, not wired into the app. Worth confirming with
  the user before deleting — if it's dead exploration, move to `archive/` or delete.
- `sidebets_historical/` — 600 KB of `.xlsx` source files (2019–2024 side bet spreadsheets). This
  is legitimate **source data** consumed by `scripts/parse_sidebet_xlsx.py` — should probably be
  tracked in git (small, binary but not secret), not left untracked indefinitely. Currently at risk
  of accidental loss since it's neither committed nor gitignored.
- `scripts/parse_sidebet_xlsx.py` — legitimate one-shot utility script per the project layout doc
  in `CLAUDE.md` ("scripts/ — One-shot utility scripts"). Should be committed, not left untracked.
- `archive/FirstPyProject/` — 75 MB, includes a `__pycache__/` and `scratch_test_graphs.py`. This is
  by far the single largest untracked item. If this is meant to be kept for reference, at minimum
  the `__pycache__` inside it should be gitignored; if it's not needed, 75 MB is a lot to keep
  sitting untracked in a working tree that also isn't committed anywhere (i.e., it's not even
  backed up).
- `webapp/startup.log`, `webapp/startup_error.log` — runtime logs from local `python app.py` runs
  (contents confirm this: "Dash is running on http://0.0.0.0:8050/", "Address already in use").
  Pure local runtime exhaust — gitignore `*.log`, delete now.
- `GEMINI.md`, `SYNC.md` — legitimate multi-agent coordination docs (Claude Code ↔ Gemini handoff
  notes), actively referenced content (SYNC.md has real entries about orphaned-graph integration
  work). These read as genuine project artifacts, not scratch — should be committed if the user
  wants that workflow preserved in repo history, or explicitly gitignored if it's meant to stay
  local-only (recommend asking the user which).

**`.gitignore` gaps** (current `.gitignore` only covers `__pycache__/`, `.venv/`, `.cache/`/`*.pkl`,
`.ipynb_checkpoints/`, `.DS_Store`, `Data/`, `Photos&Videos/`, `sleeper/`, `.env`/`*.env`,
`.render/`):
- No entry for `.playwright-mcp/`, `playwrite_screenshots/`, `*.log` (would catch
  `webapp/startup*.log`), or `.antigravitycli/`. All four are pure local/debug exhaust and should
  be ignored.
- No entry for `archive/**/__pycache__/` specifically (the top-level `__pycache__/` rule should
  already catch this recursively since it has no leading `/`, so this one is actually fine as-is).

**Secrets check** — this is the most consequential finding:
- `webapp/app.py:122` — `SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')`
  and `webapp/app.py:123` — `LEAGUE_PASS = os.environ.get('LEAGUE_PASSWORD', 'legacy')`. Both fall
  back to hardcoded defaults when the env var isn't set. **This file is committed and pushed to the
  public repo** `github.com/bgmaddox/sleeper`, so both default values (`'dev-secret-change-in-
  production'` and `'legacy'`) are public right now, in git history, forever (rewriting history
  later won't erase old clones/forks).
- Compounding this: `/Users/brettmaddox/Documents/CODING/Sleeper Project/CLAUDE.md`
  ("Running the App" section) documents `password: legacy` in plain text, and that CLAUDE.md file
  is itself tracked and committed (`git ls-files | grep CLAUDE.md` confirms it's in the repo) —
  i.e., the login password is stated twice in the same public repo, once as code default and once
  as documentation.
- No `.env` file exists in the working tree (`ls .env` found nothing), so in practice the app is
  currently *only* ever run with the hardcoded fallback values — meaning the "real" password
  guarding the deployed/local app today literally is `legacy`, publicly known. This is a low-stakes
  app (a fantasy-football stat site for friends) but is worth a conscious decision, not an
  accident: either accept `legacy` as a deliberately low-security speedbump, or move the real
  values to an untracked `.env`/systemd `Environment=` and change the checked-in defaults to
  something clearly non-functional (e.g. `None`, forcing a startup error if unset in production).

## 4. Deployability (Raspberry Pi target)

- `webapp/app.py:1-5` already documents intent: `Run locally: python app.py` vs.
  `Deploy: gunicorn app:server` — and `gunicorn` is already listed in
  `webapp/requirements.txt`. So the Dash `server` (Flask) object is already gunicorn-ready in
  principle; nothing in the code needs to change to run it under gunicorn.
- `webapp/app.py:3319` — the `__main__` block runs `app.run(debug=True, ...)`. `debug=True` must
  never be used for the Pi deployment (enables the Werkzeug debugger, which is a known RCE vector
  if ever exposed beyond localhost) — but this only fires under `python app.py`, not under
  `gunicorn app:server`, so it's not wired into the actual deploy path already documented. Still
  worth flagging so nobody flips to `python app.py` in production out of habit.
- **No systemd unit file exists yet** for this app (unlike Diet/DnD, which the user's global
  CLAUDE.md documents as already having `.service` files on the Pi). Following the existing
  pattern (`diet.service` as template per global CLAUDE.md), a new `sleeper.service` would need:
  `ExecStart=.../gunicorn --workers 2 --bind 127.0.0.1:<port> app:server`, `WorkingDirectory=
  .../webapp`, and `Environment=SECRET_KEY=...` / `Environment=LEAGUE_PASSWORD=...` to override the
  insecure defaults above.
- **Cache must ship or rebuild on the Pi.** `.cache/` (363 MB) is gitignored, so a fresh `git
  clone` on the Pi would have an empty cache and the first load would hit the live Sleeper API +
  `nfl_data_py` for all 7 years — slow, and `nfl_data_py` pulls fairly large CSVs from nflverse's
  GitHub releases. Two options: (a) `rsync`/`scp` the `.cache/` directory to the Pi once, then let
  it self-maintain, or (b) let the Pi build its own cache on first boot (simpler, but the very
  first page load after deploy would be slow — this matters more if it's gunicorn with multiple
  workers all racing to build the same season cache simultaneously the first time, since there's no
  lock around `_save_cache`).
- **Memory footprint — measured directly** (via a scratchpad script using `resource.getrusage`,
  loading all 7 seasons 2019–2025 from the existing local `.cache/` sequentially in one process):
  baseline ~12.5 MB → after all 7 years loaded, peak RSS **~619 MB**. That's the in-memory cost of
  holding every season's `League`/`Week`/`Season` object graph simultaneously (which is what the
  dashboard's data store does across tab/year switches during a session). Common Pi models (4/8 GB
  RAM, e.g. Pi 4/5) can absorb this fine as a single gunicorn worker, but **multiple gunicorn
  workers each independently loading all years would multiply this** (2 workers ≈ 1.2 GB+) unless
  workers share the season cache via something like a preload/shared-memory strategy or the app is
  run with `--workers 1` (acceptable for a small-league, low-traffic app) or a `--preload` flag with
  a single shared cache reference. Given the traffic profile (a handful of league members), 1
  gunicorn worker with `--threads` for concurrency is the pragmatic choice, not multiple workers.
- No `Procfile`/`render.yaml` found beyond the `.render/` gitignore entry — suggests Render was
  considered previously but no live deploy config remains; Pi + Caddy (per global CLAUDE.md
  pattern) is the actual current deploy target and needs the systemd unit + Caddy route described
  in the global CLAUDE.md's "Adding a new app to the Pi" section.

**Verdict:** deployable with modest, well-scoped work — no architectural blockers. The main gaps
are (1) no systemd service file yet, (2) hardcoded secret defaults need real env values on the Pi,
(3) a decision on whether to seed `.cache/` via rsync or let the Pi cold-build it, and (4) run
gunicorn with `--workers 1` (or a preload strategy) given the ~620 MB per-process memory cost of
holding all seasons.

## Concrete hygiene checklist

**`.gitignore` additions:**
- [ ] `.playwright-mcp/`
- [ ] `playwrite_screenshots/`
- [ ] `*.log` (covers `webapp/startup.log`, `webapp/startup_error.log`)
- [ ] `.antigravitycli/`

**Files/dirs to archive or delete (confirm with user first where noted):**
- [ ] Delete `.playwright-mcp/` contents (7 MB, pure debug exhaust, already superseded by newer runs)
- [ ] Delete `playwrite_screenshots/` (13 MB, same — ad hoc, unreferenced)
- [ ] Delete `webapp/startup.log`, `webapp/startup_error.log` (local runtime logs)
- [ ] Confirm with user, then either delete or move to `archive/`: `stitch-bracket/` (80 KB, appears
      to be an unwired design prototype)
- [ ] Confirm with user whether `archive/FirstPyProject/` (75 MB, largest untracked item) should be
      committed for reference, trimmed, or deleted outright — currently it's neither backed up by
      git nor cleaned up
- [ ] Commit (don't delete) `scripts/parse_sidebet_xlsx.py` and `sidebets_historical/*.xlsx` — these
      are real source data/tooling currently at risk of being lost (untracked, not backed up)
- [ ] Decide on `GEMINI.md`/`SYNC.md`: commit if the multi-agent workflow should persist in repo
      history, or add to `.gitignore` if intentionally local-only

**Git housekeeping:**
- [ ] Reconcile the three deleted-but-uncommitted `design/*.md` files (`Issues.md`, `fix-plan.md`,
      `name_matching_audit.md`) — commit the deletion if intentional, or `git checkout --` to
      restore if accidental (safe right now since nothing is committed)
- [ ] Commit the large pending diff (`sleeper_core.py` +1146, `webapp/app.py` +379, etc.) — this is
      a lot of uncommitted work sitting on `main` with no safety net if something is lost locally

**Test fix:**
- [ ] `tests/test_playoffs.py:62` — replace `assert non_null.dtype == object` with a dtype check
      tolerant of pandas' `StringDtype`, e.g.:
      `assert non_null.dtype == object or pd.api.types.is_string_dtype(non_null)`

**Security (needs a decision, not just a fix):**
- [ ] `webapp/app.py:122-123` — hardcoded fallback `SECRET_KEY`/`LEAGUE_PASSWORD` defaults are live
      in a public repo. Either accept this deliberately for a low-stakes friends app, or set real
      values via `Environment=` in the future `sleeper.service` file and change the code defaults to
      fail loudly (`os.environ['SECRET_KEY']`, no fallback) so production can never silently run on
      the public default.

**Deployability prep (for when the user is ready to move to the Pi):**
- [ ] Write `sleeper.service` (model on `diet.service` per global CLAUDE.md), `ExecStart` using
      `gunicorn --workers 1 --bind 127.0.0.1:<port> app:server` from `webapp/`
- [ ] Decide on cache seeding strategy: `rsync .cache/` to the Pi vs. cold-build on first boot
- [ ] Add a Caddy route per the global CLAUDE.md Pi pattern
- [ ] Add a `deploy_sleeper()` function to `~/deploy.sh` on the Pi
