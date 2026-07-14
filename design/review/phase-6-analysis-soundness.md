# Phase 6 — Analysis Soundness Review

**Question:** Are the numbers the league sees in the Dash app statistically sound and correctly computed?

**Method:** All analytical methods in `sleeper_core.py` were reviewed on their merits, then spot-verified against cached 2023 (and 2024) data via `data_loader.load_data_for_year()` — no API calls. Reference computations were done independently in scratchpad scripts (proper per-team optimal lineups, manual all-play records, deduplicated bench sums) and compared with what the app's methods produce.

## Ratings at a Glance

| Analysis | Rating | Verdict |
|---|---|---|
| Power Rankings (all-play) — `Season.PowerRankings` | **trustworthy** | Verified exact vs. manual recomputation |
| Luck chart ("Lucky Squares") — `Season.LuckChart` | **suspect** (visual) | Data correct; horizontal quadrant divider drawn at the wrong value |
| Weekly optimal lineup — `Week.OptimalTeams` | **suspect** | Wrong for 11/12 teams in test week (−7.6 to +25.9 pts) |
| This Week "Efficiency" column (uses the above) | **suspect** | Off by up to ~17 pts of percentage |
| Lineup Efficiency chart — `Season.LineupEfficiency` | **suspect** | Efficiency > 100% for 6/12 teams (impossible) |
| Player YTD / Top Players — `Season.BreakoutConcat` + `TopPlayers` | **suspect** | Same-name players inflated 4× (Josh Allen shown ~1,791 pts vs. true 447.6) |
| Bench strength — `Season.BrawnyBench` | **correct-but-fragile** | Correct except teams rostering duplicate-name players (+129 pts for one team in 2023) |
| Playoff Calculator — `PlayoffCalculator` | **correct-but-fragile** | Enumeration math is right; semantics collapse to 0%/100% for any already-played week |
| Playoff bracket efficiency — `Playoffs._efficiency` | **suspect** | Silently unavailable on cache loads; wrong values when populated |
| Playoff charts (ChampionRoad, HeatCheck, BenchPointsLeft) | **trustworthy** / fragile on dup-name teams | Simple lookups, logic sound |
| Season-long optimal — `Season.OptimalTeams` / `EfficincyScore` | **correct-but-fragile** | Algorithm right, inputs inflated by dup rows; metric definition wrong but unused by webapp |
| Week luck score — `Week.LuckScore` | **broken (dead code)** | Raises `NameError`; also a range bug. Not reachable from the app |
| Matchup preview win pie — `MatchupPreview_WinPercentage` | correct-but-questionable | Raw all-time H2H % on tiny samples presented as win probability |
| Pythagorean-style metrics | n/a | None exist in this project (only in the NCAA project) |

---

## Findings (ranked by impact)

### 1. `Week.OptimalTeams` picks FLEX players per **NFL team**, not per fantasy team — weekly optimal scores are wrong for nearly every team — SUSPECT

`sleeper_core.py:920`:

```python
flex_players_df = flex_pool_df.loc[flex_pool_df.groupby('recent_team')['points'].idxmax()]
```

`recent_team` is the NFL franchise (BUF, KC, …) from the nflverse stats merge. This selects one "FLEX" player per *NFL team represented in the pool*, then concatenates them all into the optimal lineups. Fantasy teams whose benches span many NFL teams get several FLEX players; others get none. Lineup sizes should be 10; they range 8–13.

**Reproduction (2023, Week 5)** — app `OptimalScoresDict` vs. independent reference optimal (QB1/RB2/WR2/TE1/FLEX1/K1/DEF1, deduped by player_id):

| team | ref | app | diff | FLEX count in app lineup |
|---|---|---|---|---|
| RascalHazard | 107.44 | 133.34 | **+25.9** | 5 |
| bgmaddox | 116.10 | 133.90 | +17.8 | 3 |
| JTizzzzle | 104.16 | 117.56 | +13.4 | 3 |
| jhuntmadd | 175.78 | 187.78 | +12.0 | 2 |
| eegrady | 91.02 | 83.42 | **−7.6** | 0 (8-man lineup) |
| RossLikeSauce | 87.28 | 87.28 | 0.0 | 1 |

11 of 12 teams wrong; errors −7.6 to +25.9 points. The negative cases also produce impossible "efficiency > 100%".

**Where the league sees it:** the This Week Power Rankings table's **Efficiency** column (`webapp/app.py:391–399` → `Season.Calc` at `sleeper_core.py:1552–1553` → `WeekObj.OptimalTeams()`), and playoff bracket efficiency badges (finding 7). Example: RascalHazard W5 true efficiency 87.2% (93.64/107.44) but app computes 70.2% (93.64/133.34).

Note: `Season.OptimalTeams` (`sleeper_core.py:1379–1404`) does this correctly (per-team pooled RB/WR/TE+FLEX). The weekly version should use the same approach.

### 2. Name-based join fan-out: same-name NFL players quadruple rows in `Breakout` — inflates player YTD charts 4× and bench totals — SUSPECT

`sleeper_core.py:732` (`merge(player_team_DF, left_on='player', right_on='player_name')`) and `:752` (`merge(self.league.Rosters, on='player_name')`) join on **name**. Distinct players sharing a name (Josh Allen QB/LB, Lamar Jackson QB/CB, Michael Thomas WR×2) fan out to 4 rows each per week.

**Reproduction (2023):** `BreakoutSeason` has 3,256 rows but only 3,094 unique (team, week, player_id) — 162 duplicate rows across 54 player-weeks. In 2024: 54 dup rows (Lamar Jackson).

Downstream damage, measured:

- **Top Players / Score YTD** (`sleeper_core.py:1273–1274` cumsum/sum by `player` name; charted by `TopPlayers` at `:2250`): Josh Allen's 2023 season total computes to **1,790.56 vs. true 447.64 (exactly 4×)**; same for Lamar Jackson (1,484.88 vs. 371.22) and Michael Thomas. The Players-tab QB line chart plots these inflated trajectories.
- **BrawnyBench** (`sleeper_core.py:2848`, sums `starter==0` points): 2023 DirtyCommie shown 598 vs. true 469 (**+129**), InfiniteJesse 396 vs. 360 (+36). Other teams unaffected.
- The duplicate rows also let `OptimalTeams`/`LineupEfficiency` "start" the same player in two slots.
- Side effect discovered: after the merges, the plain `week` column in `BreakoutSeason` is **not** the fantasy week — it's an NFL-stats artifact holding values 15–22; the fantasy week lives in `week_x`. Any future code that filters `BreakoutSeason['week']` will silently select nothing/garbage.

Also note `sleeper_core.py:682–691`: regex name-mangling fixups (`' III'→''`, hardcoded `.drop(1035)`, `'Marquise Brown'→'Hollywood Brown'`) — the Phase 2 finding stands; these are year-specific patches on a join that should be ID-based (the gsis_id crosswalk at `:743–748` already exists for the stats join and is the right pattern).

### 3. `Season.LineupEfficiency` excludes all DEF (and any unmatched player) from the optimal — shows impossible >100% efficiency — SUSPECT

`sleeper_core.py:3051–3053` filters the week's players with `BreakoutSeason['week_NFL'] == float(week)`. `week_NFL` comes from the NFL-stats merge; **100% of DEF rows have `week_NFL = NaN`** (verified), as do unmatched players (707 of 3,256 rows in 2023). So the "optimal" lineup has no DEF slot filled while the *actual* score includes DEF.

**Reproduction (2023, Week 5)** — `LineupEfficiency(5)` output:

| Team | Actual | app Optimal | ref Optimal | Efficiency shown |
|---|---|---|---|---|
| JTizzzzle | 99.36 | 86.16 | 104.16 | **115.3%** |
| RossLikeSauce | 87.28 | 83.28 | 87.28 | 104.8% |
| sgmaddox | 106.18 | 101.98 | 109.98 | 104.1% |
| RReclam | 111.12 | 125.22 | 137.22 | 88.7% (opt −12.0) |

6 of 12 teams show efficiency > 100%, which is definitionally impossible. Rendered by `LineupEfficiencyChart` on the This Week tab (`webapp/app.py:1471`). Fix: filter on `week_x` (the actual fantasy week) and dedupe by `player_id`.

### 4. Playoff Calculator: already-played games are silently discarded, so historical odds are always 0%/100% — CORRECT-BUT-FRAGILE

`sleeper_core.py:6119–6120` skips any remaining matchup where either side has `points > 0`, but `_build_standings` (`:6069`) only counts weeks `< as_of_week`. Games that have been played in week ≥ as_of_week are therefore **neither simulated nor counted in standings** — their results vanish.

Consequences:
- For any completed season (which is all of them, once the season ends and the cache is rebuilt), every "checkpoint" reduces to `M=0` → deterministic ranking. **Verified:** every cached snapshot set is binary — 2020 wk9/wk12 and 2025 wk9/wk12 all show `prob_any ∈ {0.0, 1.0}` (`.cache/playoff_probs_*.pkl`). The "Playoff Odds Trajectory" chart is thus a step function of *"in the playoff seats if the season ended today"*, not a probability history. Since `load_playoff_probs` caches these permanently (`data_loader.py:316–326`), genuinely probabilistic snapshots computed mid-season get frozen, but any snapshot computed after the fact is binary.
- Mid-week (Sunday-night) computation during a live season drops completed current-week results, biasing odds.

The enumeration itself is sound: I verified the ranking logic (`_rank_teams`, `:6151–6173`) implements wins DESC → PF DESC → roster_id ASC, matching Sleeper's default PF tiebreaker, and the bitmask/chunking math is correct by construction. Two model caveats worth a UI footnote: every game is a 50/50 coin flip (team strength ignored), and the PF tiebreaker uses PF frozen at the checkpoint (future PF not simulated).

One latent crash: `:6206–6207` maps current-week pairs into `matchup_pairs` by tuple identity. If the same `(a, b)` pair appears again in a later remaining week (rematch), `cw_indices` gets more entries than `G = len(current_week_pairs)` and `swing_tally[:, local_g, :]` indexes out of bounds; a reversed `(b, a)` ordering is silently missed instead.

### 5. Luck chart's horizontal quadrant divider is drawn at the wrong value — SUSPECT (visual)

`sleeper_core.py:1687–1689`:

```python
figScat.add_shape(type="line", x0=..., x1=...,
            y0=median_opp, y1=median_opp, ...)
```

The horizontal line (which should split teams by median **Points For**, `median_score` computed at `:1678`) is drawn at `median_opp` (median Points *Against*). Whenever the two medians differ — typically by tens of points cumulatively — teams are visually classified into the wrong "Lucky/Unlucky/Good/Bad" quadrant. The underlying data (cumulative `Score YTD` vs `Opp YTD` from `WeeklyWins`, `:1343–1347`) is correct, and the median-split methodology is a reasonable descriptive luck measure. One-line fix.

### 6. `Week.LuckScore` is dead code that crashes, with a second bug inside — BROKEN (not user-visible)

`sleeper_core.py:958` references `Season_Dict`, which is defined nowhere in the codebase → `NameError` on every call (reproduced). Even if it ran, `:959–961` does `Season['Week'].isin(WeekRange)` where `WeekRange = [1, self.week+1]` — `isin` matches only weeks {1, week+1} literally, not the range (verified: selects weeks [1, 6] for week 5). The app's luck chart uses `Season.LuckChart` instead, so no user impact — but this method should be deleted or fixed. (Contrast `Season.CalculateAverages` at `:1326`, which correctly uses `range(0, WeekNum+1)`.)

### 7. Playoff bracket efficiency: dead on cache loads, wrong when alive — SUSPECT

`Playoffs._efficiency` (`sleeper_core.py:3277`) reads `OptimalScoresByYear[year][week]`, which is populated only during live `Week.__init__` (`:611–613`). `data_loader` snapshots `AllMatchesDict`/`AllBreakoutDict` but **not** `OptimalScoresByYear` (`data_loader.py:270–274`), so after a cache load it's empty (**verified: `OptimalScoresByYear[2023] == {}`**) and every bracket efficiency badge is `None`. When it *is* populated (first live build), the values inherit finding 1's bug. Reproduction for 2023 Week 15 (championship round 1): jhuntmadd true 79.7% vs app 71.7%; bgmaddox true 82.0% vs app 75.7%.

### 8. Phase 2's suspected stale-loop-variable bug at `sleeper_core.py:902` — CONFIRMED, but low impact

```python
for position, group in DreamGroups:
    position = name[1]          # ← 'name' is left over from the previous loop
```

Every iteration reuses the last `(team, position)` tuple from the `OptGroups` loop, so `num_players` is constant across all positions and the "dream team" head-count logic is meaningless. **Verified:** 2023 W5 `DreamTeamDF` contains 235 rows (should be ~10). Quantified effect on the app: **zero** — `DreamTeamDF` is never referenced in `webapp/app.py`. It's broken dead weight; the season-level dream team (`:1410–1435`) is computed correctly.

### 9. `Season.EfficincyScore` divides optimal by optimal — wrong metric, currently unused

`sleeper_core.py:1451–1456`: the numerator (`self.Scores`) is the sum of *weekly optimal* lineup points (from `OptimalScoresByYear`), not actual points; the denominator is the season-aggregate optimal. The result is not a lineup-efficiency measure of anything. Not called from `webapp/app.py`, so no current user impact — flag it before anyone wires it to a chart.

### 10. `Season.Calc` has a latent `NameError` on its `team` parameter path

`sleeper_core.py:1558`: `Power = PowerPercents[team]` — `PowerPercents` is undefined in that scope (the dict is `PowerPercentDict`). The app always calls `sf.Calc(week_obj)` with `team=None`, so it never triggers today.

### 11. Power Rankings — verified correct — TRUSTWORTHY

`Season.PowerRankings` (`sleeper_core.py:1506–1519`) implements an all-play record: each week's score is ranked against all 11 opponents, cumulated, and converted to an all-play win %. **Verified exactly** against a manual all-play recomputation for 2023 week 5 (all 12 teams match, e.g. RReclam 43/55 = .7818, bgmaddox 14/55 = .2545). This is a statistically sensible strength measure. Two nits: `rank().astype(int)` at `:1510` truncates tied ranks (average rank 5.5 → 5 for both, slightly compressing the all-play totals in tie weeks — no ties in league history so far), and the method mutates `self.Matches` in place.

### 12. Tie handling: a tied matchup awards both teams a win

`sleeper_core.py:807`: `Won = Total == max(group)` — in an exact tie both rows get `Won=1`, and the `Opp`/`Margin` logic at `:813–815` (winner's opp = group min) returns each team's own score. Sleeper leagues can tie. No tie has occurred in this league's cached history, so nothing is currently wrong — but standings, power rankings, and the playoff calculator would all double-count a tie week.

### 13. Lineup slot structure is hardcoded, not read from league settings

`position_counts`/flex definitions are duplicated in three places (`sleeper_core.py:875–884`, `:1358–1367`, `:3064–3065`) as QB1/RB2/WR2/TE1/FLEX1/K1/DEF1 rather than derived from the league's `roster_positions`. If any historical season used a different lineup (or settings change next year), every optimal/efficiency number silently shifts. Worth a one-time assertion against the Sleeper settings.

### 14. Interpretation caveats (computed correctly, presented without context)

- **Matchup preview "Win History" pie** (`sleeper_core.py:1846`, from `AllTime.OppWinPercentageTable` `:3823`): a raw all-time head-to-head win % on ~5–10 games rendered as a win-probability-style pie. With samples that small, a 70/30 pie is mostly noise; a "n games" annotation would keep it honest.
- **PlayoffHeatCheck** (`:3380`): "last-3-weeks vs playoff average" compares 3-game samples against ≤3-game samples — fine as a fun chart, not evidence of being "hot."
- **Playoff odds** (finding 4's model caveats): 50/50 coin-flip games and frozen-PF tiebreaks should be footnoted in the UI card.

---

## What was checked and found sound

- **Power rankings**: exact match to manual all-play (above).
- **`Season.WeeklyWins` cumulative wins/PF/PA** (`:1343–1347`): consistent with per-week matchup frames; drives SnakeGraph and LuckChart correctly.
- **Actual weekly totals & win flags** (`Week.WeeklyDataframe`): actual ≤ optimal held for all teams (no team's real score exceeded even the buggy optimal); opponent assignment by matchup pair is correct.
- **`Season.OptimalTeams`** per-team pooled flex algorithm (`:1379–1404`): structurally correct (contrast finding 1); only its inputs are tainted by finding 2.
- **Playoffs bracket resolution** (`_process_bracket`, `:3288`): roster_id → name mapping via `roster_ids[year]` is sound; `roster_ids` covers 2019–2025 with per-year owner changes.
- **`PlayoffCalculator._rank_teams`** tiebreaker order matches Sleeper defaults (wins → PF).
- **Bench-points-left** (`Playoffs._bench_left`, `:3265`): simple `starter==0` sum — correct except on duplicate-name rosters (finding 2).

## Recommended fix order

1. Replace both name-joins in `PlayerBreakout` (`:732`, `:752`) with `player_id`/gsis-based joins, or dedupe on (`team`,`week`,`player_id`) immediately after — clears findings 2 and most of 3's residue and the Player-tab 4× inflation.
2. Rewrite `Week.OptimalTeams` to use the `Season.OptimalTeams` pooled-flex pattern per fantasy team; delete the dead DreamGroups loop (`:901–908`) — clears findings 1, 7 (values), 8.
3. `LineupEfficiency`: filter on `week_x`, dedupe by `player_id` — clears finding 3.
4. One-line median fix in `LuckChart` (`:1688`).
5. Playoff calculator: fold played-game results into standings instead of discarding (`:6119`), and mark historical checkpoints as "computed retroactively" or persist mid-season snapshots only.
6. Snapshot `OptimalScoresByYear` in the data_loader cache payload.
7. Delete or repair `Week.LuckScore` and the `Calc` team-path NameError.
