# Play-by-Play Points Timeline — Implementation Plan

**Goal.** Add a **By play** mode to the This Week → Points Timeline card. It rebuilds each
fantasy team's score play by play from nflverse play-by-play data, so the chart shows every
touchdown, catch and field goal landing at the moment it happened. The existing mode only
adds a step when each NFL game window finishes.

> **Status: complete. Shipped 2026-09-28 (`a9dd609`, `7fc5982`), live on
> legacy.bgmaddox.com.** Each phase's DONE note records what was actually built, and those
> notes win over the step lists beneath them, which are the original plan kept for the
> record. The code is authoritative over both.

## Current state (verified 2026-09-27)

- **Chart:** `Week.PointsOverTheWeekend(Alternate=None, animate=False)` in `sleeper_core.py`
  (~line 1034). Starters only (`Breakout['starter'] == 1`), grouped by
  `gametime_gameday_format` (one point per kickoff slot), `px.area` faceted by matchup
  (`facet_col='MatchupTitle', facet_col_wrap=2`), facet titles coloured with `self.teamcolors`.
- **Card and toggle:** `webapp/app.py` `_tab_week()` (~line 1980) builds the card with
  `dcc.RadioItems(id='timeline-animate-toggle')` offering `static`/`animated`. The callback
  `_update_timeline_chart(mode, year, week)` (~line 3113) re-renders into `timeline-chart`.
- **Data:** `nfl_data_py` 0.2.11 is already a dependency (`sleeper_core.py:20`). The
  Sleeper→GSIS ID crosswalk already exists: `data_loader.fetch_sleeper_gsis_crosswalk(year)`,
  and `Breakout` carries a `gsis_id` column. DEF rows use the team abbreviation as
  `player_id`, and the Rams are `LAR` in Sleeper but `LA` in nflverse (handled at
  `sleeper_core.py:698`).
- **Scoring:** the league's rules live in `dl.fetch_league_json(league.id)['scoring_settings']`
  (half-PPR: `rec` 0.5, `pass_yd` 0.04, `fgm_yds` 0.1 per yard with no flat FG value, `fum` -1
  **and** `fum_lost` -1, DEF `pts_allow_*`/`yds_allow_*` tiers, and more). They can differ
  between seasons, so they must be read per year and never hardcoded.
- **Settle gate:** `side_bet_resolver.is_settled(breakout)` returns True after the Tuesday
  following the week's last game.

**PBP facts, verified by running it:**
- `nfl.import_pbp_data([year], columns=[...], downcast=False, cache=False)` works for
  2019 through 2026. On 2026-09-27, 2026 had weeks 1–3.
- The full-season frame is about 49k rows × 372 columns, **~370 MB in memory**. Always pass
  `columns=` and keep only one week. The Pi has about 2 GB of RAM available.
- `time_of_day` is a UTC ISO string per play, and 3–4% of values are null (mostly the first
  row of each game).
- Every column this plan names exists in the 2025 data: `passer_player_id`,
  `rusher_player_id`, `receiver_player_id`, `kicker_player_id`, `td_player_id`,
  `fumbled_1_player_id`, `kickoff_returner_player_id`, `punt_returner_player_id`,
  `lateral_receiver_player_id`, `passing_yards`, `rushing_yards`, `receiving_yards`,
  `return_yards`, `complete_pass`, `touchdown`, `interception`, `fumble_lost`, `sack`,
  `safety`, `two_point_conv_result`, `field_goal_result`, `kick_distance`,
  `extra_point_result`, `posteam`, `defteam`, `qtr`, `game_seconds_remaining`.
- nflverse publishes PBP hours after a game ends, so this mode is **not live**.

**Decisions already made (with the user, 2026-09-27):**
1. After-the-fact data is fine. There is no live in-game source.
2. The x-axis is real Eastern clock time, with the dead stretches between game windows cut
   out using Plotly `rangebreaks`.
3. DEF event points (sacks, INTs, fumble recoveries, TDs, safeties, blocks) land on their play.
   The points-allowed and yards-allowed tier bonus lands at the final whistle.

## Success criteria

1. The Points Timeline toggle offers **Static / Animated / By play**.
2. For any week where PBP is published, each team's final value in By-play mode equals its
   Sleeper starter total to within 0.01. Reconciliation (Phase 1) guarantees this.
3. Scoring backtest: for **2025 offensive starters (QB/RB/WR/TE/K)**, play-derived points
   are within 0.5 of Sleeper's value for at least 90% of player-weeks. Phase 1 measures the
   real rate and pins the floor just below it. This is the same approach
   `test_side_bet_resolver.py` uses.
4. A week with no PBP published falls back to the per-game chart with a one-line note.
   A week with some games missing shows those players' points as a single step at their
   game's scheduled end.
5. It is deployed to `legacy.bgmaddox.com` and works there. The Pi process's memory stays
   under +300 MB on a cold PBP fetch.

---

## Phase 1: PBP data and per-play scoring engine

> **DONE 2026-09-28 (`a9dd609`).** 14 new tests; full suite 445 passed.
> - **Backtest:** 99.9% of 2025 offensive starter-weeks are within 0.5 pts (2019: 99.7%,
>   2022: 100%). The floor is pinned at 98% (`BACKTEST_FLOOR`). Every team's final total
>   equalled Sleeper in every week tested.
>
> **Where the build differs from the steps below** (the code is authoritative):
> - **Cache keys:** they come from `dl.pbp_cache_key(year, week, final)`. Frozen weeks are
>   stored under a separate `_final` key, rather than expiring on one key. `_PBP_VERSION`
>   is part of the key; bump it whenever `PBP_COLUMNS` changes.
>   `dl.fetch_pbp_weeks(year, weeks)` warms many weeks with one download.
> - **Extra columns:** `PBP_COLUMNS` also includes `fumbled_{1,2}_team`,
>   `fumbled_2_player_id`, `fumble_recovery_2_team`, `lateral_rusher_player_id` and
>   `lateral_{receiving,rushing}_yards`.
> - **Extra attribution rules:** lateral yards; up to two fumbles per play, with "lost"
>   judged by comparing the recovering team with the fumbler's team; `fum_rec_td` for a
>   teammate who recovers a fumble and scores; `st_td` and `def_st_td` on return TDs.
> - **Timeline contract:** it has a fourth `kind`, `'anchor'`: a 0-point row per team at
>   the week's first kickoff. Phase 2 should draw no marker on it.
> - **Finding game times:** a starter's game comes from where they actually appear in the
>   PBP, not from `Breakout.game_id`. `Breakout.game_id` is derived from the player's
>   **end-of-season** team, so it is wrong for players traded mid-season in the weeks
>   before the trade. See Deferred.

**Model:** Opus 5. Attributing plays to fantasy stats is subtle: fumble double-penalties,
2-pt conversions, DEF vs. offense, FG distance tiers. It also has to be calibrated against
real data.

**Files:**
- `data_loader.py`: add `fetch_pbp_week`
- `pbp_timeline.py`: **new**, at the project root beside `side_bet_resolver.py`
- `tests/test_pbp_timeline.py`: **new**

**Steps:**
1. **`data_loader.fetch_pbp_week(year, week) -> pd.DataFrame | None`**
   - Call `nfl.import_pbp_data([year], columns=PBP_COLUMNS, downcast=False, cache=False)`,
     filter to `week`, and return `None` if there are no rows. `PBP_COLUMNS` is a module
     constant: every column listed under "PBP facts" above plus `game_id`, `play_id`,
     `week`, `time_of_day`, `home_team`, `away_team`, `pass_touchdown`, `rush_touchdown`,
     `return_touchdown`, `pass_attempt`, `rush_attempt`, `fumble`, `blocked_player_id`,
     `play_type`, `desc`.
   - Cache key `pbp_{year}_w{week}`. Save the cache permanently only when both of these
     hold: every `game_id` in that week's schedule (`fetch_nfl_schedule(year)`) is present,
     and the week is past the Tuesday settle. Otherwise read it with `max_age=6*3600`.
     Follow the expiry pattern in `_load_cache`'s docstring.
   - Import `nfl_data_py` inside the function, as `fetch_sleeper_gsis_crosswalk` does.
2. **`pbp_timeline.play_stats(pbp) -> DataFrame`** returns long-format rows
   `(game_id, play_id, entity, stat_key, value)`. `entity` is a GSIS player ID, or a
   **Sleeper DEF abbreviation** (map nflverse `LA` → `LAR`). `stat_key` uses Sleeper's
   `scoring_settings` names. Attribution rules:
   - Passer: `pass_yd` = `passing_yards`; `pass_td` when `pass_touchdown`; `pass_int` when
     `interception`; `pass_int_td` when `interception` and `return_touchdown`.
   - Rusher: `rush_yd`, and `rush_td` when `rush_touchdown`.
   - Receiver: `rec` when `complete_pass`, `rec_yd`, and `rec_td` when `pass_touchdown`.
   - 2-pt conversion with `two_point_conv_result == 'success'`: `pass_2pt` to the passer and
     `rec_2pt` to the receiver, or `rush_2pt` to the rusher.
   - Fumbles: `fum` to `fumbled_1_player_id` when `fumble`, **plus** `fum_lost` when
     `fumble_lost`.
   - Returners: `kr_yd` / `pr_yd` = `return_yards`, chosen by play type.
   - Kicker: when `field_goal_result == 'made'`, emit `fgm_yds` = `kick_distance`, plus any
     `fgm_<lo>_<hi>` tier key present. When it is `missed` or `blocked`, emit the matching
     `fgmiss_<lo>_<hi>` tier. `xpm` for `extra_point_result == 'good'`, `xpmiss` for
     `failed`/`blocked`.
   - DEF (`defteam`): `sack`, `int`, `fum_rec` (when `fumble_lost`), `safe`, `def_td`
     (return TD by the defense), `blk_kick`.
   - Anything not covered here (laterals, ST TDs, forced fumbles) is **left to
     reconciliation**. Do not chase it past the backtest floor.
3. **`pbp_timeline.score(stats, scoring_settings) -> DataFrame`** computes
   `points = value * scoring_settings.get(stat_key, 0)` and sums per `(game_id, play_id, entity)`.
   **No constants from the current league are baked in.**
4. **`pbp_timeline.play_times(pbp, schedule) -> Series`** gives the Eastern-time naive
   datetime of each play:
   - Parse `time_of_day` as UTC, convert with `tz_convert('America/New_York')`, then drop
     the timezone.
   - Sort by `(game_id, play_id)` and forward-fill nulls within each game. If a game's
     first rows are still null, fill them with that game's scheduled kickoff.
5. **`pbp_timeline.team_timeline(breakout, pbp, schedule, scoring_settings) -> DataFrame`**
   builds the chart's input contract. One row per scoring event per fantasy team, with
   columns `ts` (naive ET), `team` (manager), `matchup`, `player` (display name), `delta`,
   `cum`, `desc`, and `kind`, where `kind` is `'play'`, `'final_adjust'` or `'no_pbp'`.
   - Use starters only.
   - Join `score()` output to starters on `gsis_id`, or on `player_id` for DEF.
   - **Reconcile:** for each starter, compute `residual = Sleeper points − Σ play points`.
     If `|residual| ≥ 0.01`, append a `final_adjust` row at the timestamp of their game's
     last play. For DEF this row carries the tier bonus by design, and its `desc` is
     "Points/yards allowed bonus". For others, `desc` is "Stat adjustment".
   - A starter whose game is missing from the PBP gets one `no_pbp` row. It is worth their
     full points, timed at scheduled kickoff + 3h15m, with `desc` "Final (no play data yet)".
   - Drop rows where `delta == 0`.
   - Add a `ts` = first kickoff of the week, `cum` = 0 anchor row per team.
   - Compute `cum` as a per-team cumulative sum sorted by `ts`.
   - Find the week's schedule rows with `breakout` or `league.ScheduleGroup`. First confirm
     `Breakout` has `game_id` after its schedule merge; if not, join on `recent_teams`.
   - `desc` is short: `"{player} {N}-yd TD rec"`, `"{player} 47-yd FG"`, or else a stat
     summary built from the play's stat keys. Don't parse the nflverse `desc` field.
6. **Tests** (`tests/test_pbp_timeline.py`). The fixture calls `dl.fetch_pbp_week` and
   **skips if the `pbp_*` cache pickle is absent**, following the conftest rule of no
   network in tests. Build the 2025 caches once with a scratch loop over weeks 1–17 before
   running the tests.
   - Unit tests on hand-built mini PBP frames: a lost fumble costs -2; a 47-yard FG scores
     4.7; a successful 2-pt pass credits both players; a DEF sack goes to the defteam
     abbreviation, and `LA` becomes `LAR`.
   - Invariant: for every 2025 week, each team's last `cum` equals the Sleeper starter
     total to within 0.01.
   - Backtest: across 2025 weeks 1–17, the share of offensive starter-weeks with
     `|residual| < 0.5`. Print the measured rate, then set the asserted floor to
     `floor(rate*100)-1`%. If the rate is **below 90%**, stop and fix attribution before
     pinning. Look at the largest residuals first.
   - Every play timestamp in a week falls between Thursday 00:00 and Tuesday 06:00 ET of
     that week.

**Verification:**
```bash
.venv/bin/pytest tests/test_pbp_timeline.py -q -s    # -s shows the measured backtest rate
.venv/bin/pytest tests/ -m "not slow" -q               # no regressions
```
**Depends on:** nothing.

---

## Phase 2: By-play chart method

> **DONE 2026-09-28 (`a9dd609`).** `Week.PointsTimelinePBP()` sits directly after
> `PointsOverTheWeekend`. There are 4 chart tests in `TestPointsTimelinePBP` and 2 helper
> tests. The full suite passes: 451 passed. Every 2025 week (1–17) and 2019 week 10 build,
> taking ~0.1 s per week once cached. It was checked visually against 2025 week 3.
>
> **Where the build differs from the steps below:**
> - **Helpers:** the gap and merge logic lives in `pbp_timeline.axis_breaks()` and
>   `pbp_timeline.coalesce()`, so it can be tested without drawing a chart.
>   `values` + `dvalue` rangebreaks worked on the subplots, so the `bounds` fallback wasn't
>   needed.
> - **Ticks:** one per kickoff slot in the schedule (`ScheduleGroup` `Tick`, first per
>   label), forced to `side='bottom'`. With the template default they sat on top and
>   collided with the panel titles.
> - **`'end'` rows:** each line carries flat to the week's last play. Otherwise a team
>   whose starters finished early stops mid-panel.
> - **Playoff weeks:** starters with no matchup (eliminated teams, weeks 15 and 17) are
>   dropped, matching `PointsOverTheWeekend`.

**Model:** Sonnet 5. It is a single, well-specified chart method with a fixed input
contract from Phase 1. The styling copies the existing timeline.

**Files:** `sleeper_core.py` (a new method on `Week`, placed directly after
`PointsOverTheWeekend`), `tests/test_charts.py`.

**Steps:**
1. Add `Week.PointsTimelinePBP(self) -> go.Figure`.
   - It calls `dl.fetch_pbp_week(self.year, self.week)`. If that returns `None`, raise
     `PBPUnavailable`, a small exception class defined in `pbp_timeline.py`.
   - Otherwise it builds `pbp_timeline.team_timeline(self.Breakout, ...)` using
     `dl.fetch_league_json(self.league.id)['scoring_settings']`.
2. Layout must match `PointsOverTheWeekend`:
   - `make_subplots(rows=ceil(n_matchups/2), cols=2, subplot_titles=...)`, with the same
     coloured "A vs B" facet titles, `template='gridiron_ink'`, height 1200, no legend, and
     `apply_logo_to_fig` at the same spot.
   - Use `make_subplots` directly instead of `px.area` so each trace can carry its own
     hover `customdata`.
3. Traces: one `go.Scatter` per team per facet, with
   `x=ts, y=cum, line_shape='hv', fill='tozeroy'`, colour `self.teamcolors[team]`, and
   markers only on `kind != anchor` rows, size 4.
   - Hover shows the play and the running total:
     `"<b>%{customdata[0]}</b><br>%{customdata[1]} (%{customdata[2]:+.2f})<br>Total: <b>%{y:.2f}</b><extra></extra>"`,
     where customdata is `[team, desc, delta]`.
   - Coalesce rows that share `(team, ts)` into one point, joining their `desc` values with
     `<br>`.
4. Compressed x-axis:
   - Collect every `ts` across all teams, sorted. For each gap of more than 60 minutes
     between consecutive timestamps, hide `[gap_start + 15min, gap_end - 15min]` with
     `rangebreaks=[dict(values=[start_iso], dvalue=ms), ...]`. Apply it to **every** facet
     with `fig.update_xaxes(...)`.
   - Plotly's documented arbitrary-gap mechanism is `values` + `dvalue`. First confirm it
     renders with a two-gap toy figure. If it misbehaves on subplots, fall back to `bounds`.
   - Put one tick per window start, reusing the existing tick style
     `"<b>Sun</b><br><sup>1 PM</sup>"` (see `Tick` in `League`, `sleeper_core.py:551`).
5. Add smoke tests to `tests/test_charts.py`:
   - 2025 week 3 returns a Figure with 2 × n_matchups traces.
   - Every trace's last y equals that team's Sleeper total to within 0.01.
   - `layout.xaxis.rangebreaks` is non-empty.
   - With `fetch_pbp_week` monkeypatched to return `None`, it raises `PBPUnavailable`.

**Verification:**
```bash
.venv/bin/pytest tests/test_charts.py tests/test_pbp_timeline.py -q
.venv/bin/python -c "import data_loader as dl; _,_,w=dl.load_data_for_year(2025,verbose=False); f=w[3].PointsTimelinePBP(); f.write_html('pbp_w3.html'); print(len(f.data))"
```
Then open the HTML. This is the one place a visual check is warranted: confirm the gaps are
compressed, the steps land at plausible times, and the hover text reads well.

**Depends on:** Phase 1. It can run **in parallel** with Phase 1's backtest tuning once
`team_timeline()` returns the contract in Phase 1 step 5.

---

## Phase 3: Dash wiring, docs, deploy

> **DONE 2026-09-28 — deployed (`7fc5982`).** 2 callback tests; full suite 453 passed.
> - **Live check:** 2025 week 14 renders at legacy.bgmaddox.com. A cold PBP fetch took
>   2.0 s and grew the worker's RSS by +124 MB (940 → 1,066 MB), under the 300 MB budget.
> - **SECTION MAP:** unchanged. It points at `# ──` markers, not line numbers.
> - **The fallback almost never shows.** The app only offers completed weeks, so the
>   "isn't published yet" note can only appear between Monday night's final whistle and
>   nflverse publishing, usually a few hours. The `no_pbp` partial-week path is likewise
>   reachable only in that window. Both are covered by unit tests, not the live site.
> - **Also found:** the `?week=` deep-link parameter was ignored. Fixed afterwards; see
>   Deferred.

**Model:** Sonnet 5. It is routine callback wiring plus the project's deploy runbook.

**Files:** `webapp/app.py`, `CLAUDE.md`, `.claude/structure.md`, `PROJECTS.md` (workspace root).

**Steps:**
1. In `_tab_week()`, add `{'label': 'By play', 'value': 'pbp'}` to `timeline-animate-toggle`.
   No emojis. Keep the initial render `static`, because a cold PBP fetch shouldn't slow down
   tab load.
2. In `_update_timeline_chart`, when `mode == 'pbp'`:
   - Call `week_obj.PointsTimelinePBP()`, then
     `_strip(fig, 950).update_layout(margin=dict(t=80, b=100, l=80, r=40))`, then `_graph(fig)`.
   - On `PBPUnavailable`, return the static chart preceded by a
     `html.Div('Play-by-play for this week isn\'t published yet — showing per-game view.', className='chart-subtitle')`.
   - Any other exception is handled by the existing error div.
3. Update the card subtitle so it covers both modes, for example "How scores accumulated
   through the matchup window — By play shows every scoring play".
4. Update the app.py docstring **SECTION MAP** if any line numbers shift by more than 20.
   Add `pbp_timeline.py` to the `core:` line of `.claude/structure.md`.
   Add a short **Play-by-play timeline** section to `CLAUDE.md` covering three things:
   the reconciliation invariant (final value always equals Sleeper), PBP being
   after-the-fact, and that the backtest floor governs attribution changes.
5. Test locally:
   - Kill port 8050 and start the app (CLAUDE.md "Running the App").
   - Use `browser_snapshot` to confirm the three toggle options.
   - Click By play for 2025 week 3 and check `browser_console_messages` for errors.
   - For a 2026 week whose PBP isn't published yet, confirm the fallback note appears.
6. Deploy using the `pi-server` skill (`ssh rachett 'bash ~/deploy.sh sleeper'` after
   pushing).
   - The Pi fetches PBP on demand, so there's no need to rsync the `pbp_*` pickles.
     Rsyncing them is optional and only warms the cache.
   - Record the gunicorn worker's RSS before and after the first By-play click:
     `ssh rachett 'ps -C gunicorn -o pid,rss,args --sort=-rss | head -2'`. (`systemctl`
     reports no memory figure for this unit, so don't use it.)
7. Update the `PROJECTS.md` Next Step column.

**Verification:**
```bash
.venv/bin/pytest tests/ -m "not slow" -q
curl -s -o /dev/null -w '%{http_code}\n' https://legacy.bgmaddox.com/login   # 200
```
Then run a `browser_snapshot` on the live site and click By play for a settled week. The
chart must render, and the memory delta must be under 300 MB.

**Depends on:** Phase 2.

---

## Phase 4: Plan self-review

**Model:** Sonnet 5. It is a read-through for gaps and has no code to design.

> **DONE 2026-09-28**, run after Phases 1–3 rather than before them (the user went
> straight to Phase 1). Changes made:
> - Added a status block at the top saying which layer is authoritative. The DONE notes
>   diverge from the original steps, and without it a cold reader can't tell which to
>   follow.
> - Changed "uncommitted" to commit hashes.
> - Phase 2's verification wrote to a machine-specific temp path; it now uses a relative
>   one.
> - Phase 3's `systemctl` memory command returns nothing on the Pi; replaced it with the
>   `ps` RSS command that was actually used.
> - Marked the rangebreak risk as resolved, and both Deferred bugs as fixed.
> - **Length.** The original step lists for Phases 1–3 are now mostly history, and each
>   is longer than its DONE note. They're kept because they record the reasoning. For a
>   future change, read the DONE notes and the code, not the steps.

**Steps:** Re-read this plan cold, as the executing agent would.
- Check each line number cited against current code, since `app.py` shifts often.
- Check each column name against `PBP_COLUMNS`.
- Confirm the Phase 1 output contract matches what Phase 2 consumes.
- Fix anything ambiguous or contradictory in place. Note any section that is longer than it
  needs to be.

**Verification:** a list of the changes made, or the words "no changes needed", recorded at
the bottom of this file.

**Depends on:** nothing. It was meant to run first and ran last. See the DONE note.

---

## Risks

| Risk | Mitigation / rollback |
|---|---|
| `nfl_data_py` is archived upstream (nflverse moved to `nflreadpy`). The URLs could break. | All PBP access goes through `data_loader.fetch_pbp_week`, so a swap is one function. Existing caches keep working. |
| The per-season PBP download spikes memory on the Pi (4 GB total, ~2 GB free). | `columns=` subset and a one-week filter before caching. Phase 3 measures the delta. If it's too high, prebuild the pickles locally and rsync them. |
| Attribution is wrong in ways that make the intra-game shape misleading, even though totals are right. | The backtest floor in Phase 1 plus the visible `final_adjust` rows, whose hover says "Stat adjustment". |
| Stat corrections move a player's Sleeper total after the PBP cache is frozen. | The PBP cache only freezes after the settle Tuesday. Reconciliation always uses the current Sleeper total, so the final value is still correct. |
| Rangebreaks misrender on subplots. | Resolved: `values` + `dvalue` render correctly on all six panels (Phase 2). |
| Rollback | The mode is purely additive. Remove the toggle option and nothing else changes. |

## Deferred

- **Live in-game updates.** This would need an unofficial source such as ESPN's game feed.
  Declined 2026-09-27.
- **Animated By-play mode.** Frames per play would be heavy. Revisit after the static mode ships.
- **Exact lateral, special-teams TD and forced-fumble attribution.** Reconciliation absorbs
  these for now. Tighten only if the backtest shows they matter.
- **~~Existing bug: traded players in the wrong game~~ — FIXED 2026-09-28.**
  `Breakout.recent_teams`, and therefore `game_id`, `gameday` and `gametime`, came from the
  end-of-season roster team. As a result, the per-game timeline drew traded players' points
  in the wrong slot before the trade: 269 rostered player-weeks in 2025 alone, including
  Rashid Shaheed and Jakobi Meyers. It now uses the team from `WeeklyNFLData` for that
  week, and falls back to the roster team when there's no stats row. Guarded by
  `test_traded_players_sit_in_the_game_they_played`. The fix introduced
  `data_loader.SEASON_SCHEMA` so stale season pickles rebuild (see CLAUDE.md).
- **~~`?week=` deep links ignored~~ — FIXED 2026-09-28.** `webapp/app.py` `_url_week()`,
  used by `_boot` and `_year_changed`, applies the link's week to the season the link
  names. Guarded by `tests/test_deep_link.py`.
- **Migrating to `nflreadpy`.** Do this when `nfl_data_py` actually breaks, not preemptively.
- **Timing.** It's currently mid-season (2026 weeks 1–3 are published), which is the ideal
  time to build and check it against fresh weeks. There's no calendar dependency otherwise;
  2019–2025 all work any time.
