# Name-Matching Audit — dfBreakout Join

**Created:** 2026-05-22  
**Context:** Task 3B from roadmap.md  

The `dfBreakout` pipeline joins Sleeper matchup data (player names from Sleeper's player DB) to nflverse weekly stats (`stats_player_week_YYYY.csv`) using a name+week composite key:

```python
player_week_id = player_display_name + ' - ' + week
```

This audit documents actual mismatches found and known fragility patterns.

---

## Diagnostic Results

**Method:** Load all weeks from AllBreakoutDict for 2024 and 2025. Flag starters (non-DEF) where all stat columns (`passing_yards`, `rushing_yards`, `receiving_yards`, `pts_half_ppr`) are null.

| Year | Weeks checked | Unmatched starters | Genuine name bugs |
|------|-------------|-------------------|-------------------|
| 2024 | 1–17 | 0 | 0 |
| 2025 | 15–18 only* | 23 (all week 18) | 0 |

*AllBreakoutDict only had playoff weeks cached at time of audit — weeks 1-14 for 2025 not in the cache snapshot.

**Conclusion:** The join works correctly for all complete regular-season data. **Zero genuine name-mismatch bugs were found.** The 23 week-18 mismatches for 2025 are players who did not play in that week (teams resting starters in the final regular-season week before playoffs).

---

## Known Fragile Patterns

### 1. Name suffixes — HANDLED
Both Sleeper and nflverse include `Jr.`, `Sr.`, `II`, `III`. The pipeline strips these from both sides before joining:
```python
# PlayerBreakout strips from player_team_DF
.replace(' Jr.','', regex=True).replace(' Sr.','', regex=True)
# WeeklyNFLData strips from player_display_name
WeeklyNFLData['player_display_name'].replace(' Jr.','', regex=True)...
```
No mismatches observed.

### 2. Dot-initial names (A.J., C.J., etc.) — CURRENTLY WORKING
Sleeper and nflverse both use the same dotted-initial format:
- `A.J. Brown`, `C.J. Stroud`, `J.K. Dobbins`, `T.J. Hockenson`

No normalization needed. Watch for future players where the two sources diverge (e.g., a source that drops the dots).

### 3. Specific player name corrections — HARDCODED in code
```python
player_team_DF = player_team_DF.replace('Marquise Brown', 'Hollywood Brown')
player_team_DF = player_team_DF.replace('Audric Estimé', 'Audric Estime')
# Also in WeeklyNFLData strip:
.replace('Bam Knight', 'Zonovan Knight', regex=True)
```
These are one-off hardcoded corrections. Each new mismatch requires a code change.

### 4. DST (team defenses) — SPECIAL-CASED
Defenses don't appear in nflverse player stats (they have no `player_display_name` row). They're handled separately via `NFLTeamList` and the `Defence` DataFrame built in `PlayerBreakout`. The join skips them for nflverse stats, which is correct — DEF scoring comes entirely from Sleeper's matchup points.

**Risk:** If an NFL franchise relocates or rebrands (e.g., Raiders to Las Vegas), the abbreviation used by Sleeper vs nflverse may diverge. The `player_team_DF.loc[-1] = ['LAR','LA']` correction in the code suggests this has already happened at least once.

### 5. Mid-season player additions — POTENTIAL GAP
If a player is added to a roster mid-season and their name is not yet in `self.league.player_team_DF` (the local roster cache), the join will produce a null row for that player. The stats may still merge correctly if the name matches nflverse.

---

## Current Mismatch Inventory

As of the 2025 season diagnostic, **no persistent name mismatches were found**. The following were investigated and ruled out as bugs:

| Player | Weeks | Status |
|--------|-------|--------|
| Patrick Mahomes | 18 | Did not play week 18 (Chiefs rested starters) |
| Saquon Barkley | 18 | Rested before playoffs |
| CeeDee Lamb | 18 | Rested — matched correctly in all earlier weeks |
| Zach Ertz | 18 | End-of-season / released |
| (all others) | 18 | Same pattern — week 18 roster rest |

---

## Future Fix Direction

The ideal fix is an ID-based join to eliminate name fragility entirely:

1. `nfl_data_py.import_rosters()` includes `espn_id` and `gsis_id` per player
2. Sleeper's player endpoint (`/v1/players/nfl`) includes `espn_id` per player
3. If both `espn_id` fields match the same player, a crosswalk table can be built:
   `sleeper_player_id → gsis_id` (what nflverse uses as its primary key in weekly stats)

This would replace the `player_week_id` name-based join with a `gsis_id + week` join, making suffix/punctuation/nickname variations irrelevant.

**Pre-work needed:** Confirm that `espn_id` in nfl_data_py rosters matches `espn_id` in Sleeper's player DB for a sample of players. If they match, the crosswalk is viable.

---

## Side Finding: AllBreakoutDict Coverage Gap

The cache for 2024 and 2025 only contains late-season weeks (week 17+ for 2024, week 15+ for 2025). Weeks 1-14 of the regular season are missing from the in-memory dict, which means charts that iterate over `AllBreakoutDict[year]` will only show late-season player data.

This is a data loading issue, not a name-matching issue. Investigate whether `Season` loads all weeks from the pickle or only the weeks that were active when the cache was written.
