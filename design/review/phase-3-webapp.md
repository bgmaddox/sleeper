# Phase 3 Review — `webapp/app.py`

**Scope:** Is `app.py` (3,319 lines, ~77 functions) sound as a long-lived app? Callbacks, auth, data loading, threading, error handling.
**Method:** Static read of `app.py` + `sleeper_core.py` aggregation paths; timed cache loads via the project venv (Python 3.12.7, `.cache/`, no live API calls).

**Overall:** The app is functional and error-handling is unusually thorough (per-chart try/except everywhere). But there are two genuine correctness bugs (all-time charts silently under-report; year-switch leaves the user on a "Loading…" placeholder forever), a stale navigation aid the project's own rules require kept current, and a real auth-bypass if env vars are unset in prod. None are catastrophic at a friends-league threat level, but the two correctness bugs are user-visible today.

Findings are ranked by user-visible impact.

---

## 1. All-Time / Choropleth / Chord charts silently show INCOMPLETE data (correctness) — HIGH
`_tab_alltime` builds history via `core.AllTime()` (`app.py:1756`), which concatenates the module-level globals `AllMatchesDict`/`AllBreakoutDict` (`sleeper_core.py:3796`, `:3805`). Those globals are populated only as a *side effect* of constructing each year's `League`/`Season`. But only `CURRENT_YEAR` is eagerly loaded at startup (`app.py:338`); every other year loads lazily the first time the user visits it (`_ensure`). Nothing eagerly loads all years.

Result: the All-Time tab concatenates **only the seasons the user has already browsed**. Open the app fresh, click All-Time, and you get 2025-only "all-time" charts. `_populate_choropleth_data` (`app.py:3186`, `for year, ydata in _data.items()`) and `_populate_chord_data` (`app.py:3250`) have the same defect — they iterate `_data`, which holds only loaded years. This is a silent wrong-answer bug, not an error.
**Fix direction:** eagerly kick off `_ensure(y)` for all `ALL_YEARS` at startup, and/or have the all-time callbacks block until all years are present (or show a "loading N of 7 seasons" state).

## 2. Switching year to an unloaded season strands the user on "Loading…" forever — HIGH
The `boot` `dcc.Interval` (`app.py:804`) is the *only* poller that re-fires callbacks while data loads. `_boot` disables it permanently after the first successful load (`app.py:930`, returns `disabled=True`). `_year_changed` (`app.py:943`) starts a background load but does **not** re-enable `boot`. `_render_tab` then runs once with `_season(year)` still `None` and returns `_loading_placeholder()` (`app.py:651`) — a **static div with no interval/refresh**. When the background thread finishes, nothing re-fires `_render_tab`, so the tab stays on "Loading season data…" until the user manually clicks a week/team.

This is the mechanism behind the reported 10–50s "delay" switching to 2020 Side Bets: it isn't `_ensure` blocking (see #3 — warm loads are 0.13s), it's the absence of any re-render trigger, so the perceived delay is however long until the user pokes something.
**Fix direction:** re-enable `boot` (`disabled=False`) inside `_year_changed`, or make `_loading_placeholder()` embed a short `dcc.Interval` that re-fires the tab render, or on year-change block briefly for the (fast) cache load.

## 3. `_ensure`/`_year_changed` do not actually block 30s — the perf cost is cold API, not cache — MEDIUM (quantified)
Measured warm-cache `load_data_for_year(year, max_week=18) + SideBet(...)` from `.cache/`, project venv:

| Year | Load time | Weeks |
|------|-----------|-------|
| 2019 | 0.15s | 16 |
| 2020 | 0.12s | 16 |
| 2021 | 0.13s | 17 |
| 2022 | 0.14s | 17 |
| 2023 | 0.14s | 17 |
| 2024 | 0.13s | 17 |
| 2025 | 0.12s | 17 |

`_ensure` (`app.py:313`) and `_weeks` (`app.py:323`) are **non-blocking** — they spawn a daemon thread and immediately return `_data.get(year, {})` (empty on first hit). So `_year_changed` never blocks 30s. The multi-second delays users saw are (a) *cold* loads (first-ever fetch: Sleeper API + `nfl_data_py`, not measurable here without live calls), and (b) the no-re-render bug in #2. With a warm `.cache/`, any year is ready in ~0.13s — so eager-loading all years at startup (fixes #1 and #2) costs well under 1s total and is the right call.

## 4. SECTION MAP docstring is stale across the board — every line number is wrong — MEDIUM
`CLAUDE.md` mandates keeping the SECTION MAP current after any function move >~20 lines. It has drifted on **every** entry (verified against `# ──` markers):

| Map claims | Actual | Section |
|-----------|--------|---------|
| L28 | 56 | NFL Stadium Coords |
| L66 | 94 | Config |
| L101 | 153 | Auth |
| L236 | 288 | Data store |
| L283 | 341 | Helpers |
| L465 | 682 | League Digest |
| L569 | 786 | Layout |
| L675 | 903 | Core callbacks |
| L1185 | 1226 | Tab: This Week |
| L1260 | 1494 | Tab: Season |
| L1470 | 1743 | Tab: All-Time |
| L1670 | 2360 | Toggle callbacks |
| L1741 | 2692 | D3 store population |
| L2254 | 3233 | D3 Chord |
| L2332 | 3316 | Run |

Drift ranges from ~28 to ~950 lines. Additionally the **Survivor** entry (map L1976) is listed *out of order* — after the D3 chord entry, though its marker (actual L2123) sits before them. The map's stated purpose ("grep the `# ──` markers to jump directly") means the line numbers are decorative and misleading; the `# ──` markers themselves are accurate. Either regenerate the numbers or drop them and keep only the grep-able marker names.

## 5. Read/write race on module-global dicts between load thread and render callbacks — MEDIUM
`sleeper_core` writes `AllMatchesDict[year]`, `AllBreakoutDict[year]`, `OptimalScoresByYear[year]` incrementally during construction (`sleeper_core.py:868`, `:761`, `:954`) with no lock. Callbacks read those same globals directly — `_digest` (`app.py:692`), `_h2h` (`app.py:2280`), `_populate_bubble_data` (`app.py:3001`, `:3040`) — rather than the `_data[year]` snapshot. Because the load runs on a daemon thread, a render callback can read a **partially-populated** `AllMatchesDict[year]` mid-construction. Keys are year-scoped so cross-year collisions are unlikely, but same-year `_refresh` (`app.py:1157`, deletes `_data[year]` and reloads on a new thread) re-runs construction that overwrites those global keys while a concurrent callback reads them → possible `KeyError`/partial data. Also `_refresh` clears `_data[year]` but never clears `core.AllMatchesDict[year]`, so a reload with fewer weeks leaves stale week keys behind.
**Fix direction:** read exclusively from the `_data[year]` snapshot (already captured atomically in `_load_bg`), and treat the `core.*Dict` globals as write-only internals.

## 6. Auth fully bypassable if `SECRET_KEY` unset in production — MEDIUM (security, threat-adjusted)
`SECRET_KEY` defaults to the literal `'dev-secret-change-in-production'` (`app.py:122`) and `LEAGUE_PASSWORD` to `'legacy'` (`app.py:123`), both committed to a **public** repo. The auth cookie is an `itsdangerous` token signed with `SECRET_KEY` (`app.py:155–158`). If the Pi deployment does not set `SECRET_KEY` in the systemd env, anyone can forge a valid `ll_auth` cookie using the public default key — no password needed — and the password gate is moot. At a friends-league threat level the password itself is fine, but the *signing key* being a known public constant is the one thing worth hardening.
**Action:** confirm `SECRET_KEY` (and `LEAGUE_PASSWORD`) are set as `Environment=`/`EnvironmentFile=` on the Pi service; if not, the gate is effectively open. Consider `raise` on startup if `SECRET_KEY` is still the default.

## 7. `/debug-error` is an unauthenticated POST sink — LOW (security)
`_debug_error` (`app.py:268`) is in the `_auth_gate` bypass list (`app.py:278`) and prints arbitrary client-supplied JSON to server logs (`app.py:272`). Unauthenticated log-injection / log-spam vector. No data leak, but a stranger can flood the server log. Low priority; gate it or rate-limit if the app is ever exposed beyond Tailscale.

## 8. Data endpoints ARE gated — no unauthenticated data leak found (positive) — INFO
`_auth_gate` (`app.py:276`) returns 401 for `/_dash*` when the token is invalid (`app.py:282`), so callback data (`_dash-update-component`) is protected. The bypass list (`app.py:278`) only exposes `/login`, `/assets` (static JS/CSS/logo — non-sensitive), Dash component suites, favicon, manifest, reload-hash, and `/debug-error`. No league data is served without auth. This is the correct posture for the threat level.

## 9. `_year_changed` double-starts the load thread — LOW
`app.py:945–946` starts a thread *and then* calls `_ensure(year)`, which starts another. `_load_bg`'s lock guard (`app.py:297–300`) makes the second a fast no-op, so it's harmless, but it's redundant and signals confusion about `_ensure` already being a thread-spawner. Drop the explicit `threading.Thread(...)` line and keep just `_ensure(year)`.

## 10. Massive error-handling boilerplate duplication — LOW (maintainability)
The pattern `dcc.Graph(figure=_err(str(e)), config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})` is repeated ~15× (e.g. `app.py:1257, 1385, 1444, 1459, 1519, 1544, 1561, 1605, 1663, 1704, 2099`) and the per-chart `try/except … _card(_err(...))` pattern ~40×. The good news: the past "error figure not wrapped in dcc.Graph" bug (obs 476/477) appears fully fixed — every `_err()` I traced is wrapped in either `dcc.Graph` or `_card` (which wraps internally, `app.py:384`). Consolidate into one helper, e.g. `_err_graph(e)`, so the wrapping can never drift out of sync again. This is the single most effective way to prevent that class of bug from recurring.

## 11. `_populate_choropleth_data` / `_populate_chord_data` don't re-fire on year change — LOW
Both depend only on `Input('tabs','value')` and `Input('boot','disabled')` (`app.py:3178–3179`, `:3237–3238`). Since `boot` is permanently disabled after startup and the tab value doesn't change when you switch year, loading a new year while sitting on the All-Time tab won't refresh these D3 stores. Compounds #1 — even after a year finishes loading in the background, these charts won't pick it up without a tab switch. Add `store-year` (or a data-ready trigger) to their inputs.

## 12. Python version mismatch vs docs — INFO
`CLAUDE.md` states the venv is Python 3.11; the actual `.venv` runs 3.12.7 (`source .venv/bin/activate; python --version`). Harmless but the doc is wrong; worth correcting so future setup assumptions hold.

---

## Summary
- **Ship-blockers for "long-lived" soundness:** #1 (all-time charts under-report) and #2 (year-switch loading limbo) are real, current, user-visible bugs. Both are fixed cheaply by eager-loading all 7 years at startup (~0.9s total per the timings) plus re-enabling the `boot` interval on year change.
- **Security at threat level:** the password gate and data-endpoint gating are appropriate; the only real risk is the **public default `SECRET_KEY`** (#6) — verify it's overridden in prod.
- **Maintainability:** the SECTION MAP is entirely stale (#4) and error-handling is copy-pasted ~55× (#10); both are latent-bug sources the project's own conventions are meant to prevent.
- **Threading:** the daemon-thread + module-global-dict design works but has an unlocked read/write seam (#5) that the codebase should sidestep by reading only the `_data` snapshot.
