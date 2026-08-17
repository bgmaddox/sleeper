# Decisions & Do-Not-Repeat Ledger

Settled decisions and dead ends for this project. **Read before proposing an approach.**
If something here is wrong, correct the entry rather than silently working around it.

Format: decision, then the reason, then the date it was settled.

---

## Settled

**`sleeper_core.py` is the single source of truth for chart logic.**
Chart behavior is also *described* in the notebook and in `webapp/app.py`; those are
consumers, not authorities. When they disagree, `sleeper_core.py` wins.

**`Sleeper_v2.ipynb` is retired. `Sleeper_v3.ipynb` is a thin wrapper holding no logic.**
Settled Session 8 (`f21246f`). Do not add logic to the notebook and do not consult v2 —
it is archived and stale.

**League config lives in `config/*.json`, not in code.**
Settled Session 7 (`92f22e3`), same commit that hardened network I/O.

**The app is served under a subpath; `/` redirects to `URL_BASE`.**
Settled in `ac5ed10`. Do not assume the app is at domain root when writing links or
testing routes.

**Deployment is Pi + Tailscale Funnel**, documented in `CLAUDE.md` (`300c876`).
Public URL is <https://rachett.tail504ae5.ts.net/legacy/>.

**Data loading is disk-cached in `.cache/`.**
First load hits the Sleeper API + nfl_data_py; afterwards it's pickles. Use
`invalidate_week(year, week)` to bust stale data — do not delete `.cache/` wholesale
and do not add a second caching layer.

**Manager display names are resolved through `config/aliases.json`; the *current*
Sleeper display name is canonical.**
Two managers renamed themselves ahead of 2026 (`jhuntmadd` → `jhmad`,
`InfiniteJesse` → `InfiniteJess`). Without a resolver they split into separate
identities across All-Time, Head-to-Head, and Hall of Fame. The cheaper option —
writing the *old* names into `roster_ids.json` for 2026 — was considered and rejected;
it keeps history intact but leaves Survivor and Pick 'Em (which read `display_name`
live from the API) showing different names than the rest of the app. Settled 2026-08-16,
planned as roadmap Task 11B.

**Survivor and Pick 'Em are main-league-independent and were not renewed for 2026.**
Only the main league exists on Sleeper as of 2026-08-16. Both tabs already fall back to
`max(...)` of their config, so they correctly keep showing 2025. Add the IDs to
`config/league_ids.json` if and when those pools are created.

**Cache writes go through `_save_cache`, which is atomic (temp file + `os.replace`).
Reads treat a corrupt pickle as a miss.**
Pickling straight to the destination corrupted 43 of ~170 cache files in a single
session once the dev server, a test run and a couple of scripts warmed the same keys
concurrently. The Pi runs gunicorn with 4 threads and eagerly loads every season on
boot, so it has the same exposure. Do not "simplify" this back to a plain
`open(path, "wb")`. Settled 2026-08-16, roadmap Task 11G, guarded by
`TestCacheDurability`.

**Sleeper is the source of truth for the draft date; `config/season_dates.json` is only
a fallback.**
`data_loader.draft_start_ms()` prefers the draft's `start_time` from Sleeper, so
scheduling the draft there is all that is required and no config edit is needed. The
override exists purely to show a date before it has been scheduled. An unscheduled draft
is **never cached** — with no TTL, caching a null `start_time` would pin the hero to TBD
permanently. Settled 2026-08-16, roadmap Task 11E.

**Season-spanning labels name the year explicitly.**
"DEFENDING CHAMPION" with no year misled a reader into thinking the wrong season was
shown, because a season starting in 2025 finishes in 2026. The banner reads
`2025 CHAMPION`. Apply the same rule to any other label that refers to "last"/"this"
season. (For the record: DirtyCommie won 2024, cosmodromedary won 2025.)

**An empty (preseason) season is never cached.**
There is no TTL on season pickles, so caching a zero-week season freezes the year as
permanently empty until someone hits ↺. The cost is that a renewed-but-unplayed season
refetches on every app start (~5s) — that is the point, it is how the app notices Week 1.

---

## Do not repeat

*(Add entries here when an approach is tried and rejected — that's the whole point of
this file. An empty section is fine; a wrong one is not.)*

- Nothing recorded yet. The Session 9 playoff-calculator rebuild (`47a0cd5`, "checkpoint
  semantics; presentation honesty") looks like it replaced an earlier approach — if you
  remember what was wrong with the original, record it here.

- **Do not react to bare `addedNodes` in a `MutationObserver` that also writes to the
  DOM.** `webapp/assets/kickoff.js` updated `textContent` — itself a childList mutation
  — so an observer watching all `addedNodes` re-entered its own render loop. Observer
  callbacks are microtasks, so it never yielded and the browser tab hung outright.
  Filter to `nodeType === 1` and to the specific element you care about (this is why
  `counter.js` checks `node.nodeType === 1`). Found 2026-08-16.

- **Do not use percentage `translate` on a small element to move it across a container.**
  Percentages resolve against the element's own border box, not the parent. On a ~24px
  football, `translateX(46%)` is ~11px. Put the horizontal travel on a track that spans
  the container instead. Found 2026-08-16 on the preseason hero.

- **Do not position an animated element with inline layout inside a centred container.**
  The preseason football was an `inline-block`, so it inherited `text-align: center`
  from `.ps-hero` and began its travel at the container's midpoint — the bounce sat
  entirely in the right half. A zero-height track compounded it by hanging the element
  below its own baseline. Anchor moving pieces with `position: absolute` and explicit
  offsets. Found 2026-08-16; verify changes by measuring `getBoundingClientRect()`
  against the container at several widths, not by eye.

- **Do not run the dev server and the test suite at the same time** until you have
  confirmed the atomic-write fix above is in place. That overlap is what corrupted the
  cache; symptoms were a hanging test suite and a hero with no countdown, neither of
  which pointed at the cache.
