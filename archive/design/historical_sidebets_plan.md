# Historical Side Bets — Implementation Plan

## Overview

Add side bet data for seasons 2019–2024 to the webapp. Data lives in Excel files under
`sidebets_historical/`. The app's Side Bets tab already supports any year present in
`SIDE_BET_SEASONS` (`sleeper_core.py:335`) — no structural app changes are required.
This is purely a data migration.

---

## Source Files

| File | Year |
|---|---|
| `sidebets_historical/Side Bets - Legacy League '19.xlsx` | 2019 |
| `sidebets_historical/Side Bets - Legacy League '20.xlsx` | 2020 |
| `sidebets_historical/Legacy League '21.xlsx` | 2021 |
| `sidebets_historical/Legacy League '22.xlsx` | 2022 |
| `sidebets_historical/Legacy League '23.xlsx` | 2023 |
| `sidebets_historical/Legacy League '24.xlsx` | 2024 |

Each file has a `Challenges` sheet with two columns:
- `Side Bet` — formatted as `"WEEK N: Name - Description"`
- `Winner` — single name, slash-separated ties (e.g. `"JT/Brett/Chip"`), or `"n/a"`

---

## Blockers — Resolve Before Running the Agent

### 1. Confirm the name → username mapping

Excel files use informal display names. The app uses Sleeper usernames. The agent needs
this mapping hardcoded before it runs. Confirm or fill in the unknowns.

**Resolution approach:** Before mapping anything, the parser does a *discovery pass* —
scan all files and print the full set of unique raw winner tokens (post-split on `/`)
grouped by year. The user resolves all unknowns from that single list rather than
discovering them one `KeyError` at a time during the real run.

| Excel name(s) | Sleeper username | Status |
|---|---|---|
| Brett | `bgmaddox` | ✅ confirmed |
| JT | `JTizzzzle` | ✅ confirmed |
| Jack | `jlglover` | ✅ confirmed |
| Reclam / LB/Reclam | `RReclam` | ✅ confirmed |
| Chip | `RascalHazard` | ✅ confirmed |
| Erin | `eegrady` | ✅ confirmed |
| Hunter | `jhuntmadd` | ✅ confirmed |
| Liam | `YouthPastor` | ✅ confirmed |
| SG / Stuart | `sgmaddox` | ✅ confirmed |
| Aaron | `akbrown29` | ✅ confirmed (2019 only) |
| Ross | `RossLikeSauce` | ✅ confirmed |
| Billy | `BillyRayGonnaGetcha` | ✅ confirmed (2019–2021) |
| Rachel D. | ??? | ❓ needs confirmation |
| Rachael | ??? | ❓ needs confirmation (appears to be a different person) |
| Liz | ??? | ❓ needs confirmation (appears 2022+) |

### 2. Clarify 2023 vs 2024

The 2023 and 2024 Excel files currently contain **identical data**. Determine whether:
- The 2024 file is a stale placeholder that needs to be updated with real 2024 results, or
- The 2024 season genuinely had the same bets and same winners as 2023

**Detection:** the parser computes an MD5 of each `Challenges` sheet's cell contents and
prints a warning if any two years produce the same hash. The agent halts on a collision
unless the user has already acknowledged the duplicate is intentional.

---

## Phase 1 — Write a Parser Script

**File:** `scripts/parse_sidebet_xlsx.py`

This is a **standalone, one-shot script** — not imported by the app. Commit it to
`scripts/` once it works; it documents how `SIDE_BET_SEASONS` was populated if the data
ever needs to be re-derived. `openpyxl` is not pinned in project deps — the script is
deliberately ad-hoc and only expected to run on the dev machine that already has it.

### Logic

1. Define `DISPLAY_NAME_MAP` using the confirmed table above.
2. Define `FILE_YEAR_MAP` pointing each xlsx path to its year.
3. **Discovery pass** — for each file, collect all unique raw winner tokens (post-split
   on `/`, stripped, excluding `"n/a"`) and print them grouped by year. Halt if the
   union of tokens contains any name not in `DISPLAY_NAME_MAP`. This surfaces every
   unmapped name at once instead of one per re-run.
4. **Duplicate detection** — MD5-hash each `Challenges` sheet's cell contents. Print a
   warning and halt if two years collide (covers the known 2023/2024 case and any future
   slip-ups).
5. **Parse pass** — for each file:
   - Open with `openpyxl`
   - Read the `Challenges` sheet
   - For each row, attempt to extract the week number via `re.search(r'WEEK\s+(\d+)', cell)`
   - Skip rows with no match (non-week rows like `"Top Side Bet Winner (2x)"`)
   - Split the cell text after `"WEEK N: "` on `" - "` to get `name` and `desc`
   - Normalize the winner:
     - Split on `r'\s*/\s*'` (handles `"/"`, `" / "`, `"JT/Brett"`, etc.)
     - Strip each part
     - Skip empty parts
     - If value is `"n/a"`, set winner to `""`
     - Map each name through `DISPLAY_NAME_MAP`
     - Rejoin with `" & "` — this matches the separator used by both
       `sleeper_core.py:4324` and `webapp/app.py:2014` (`cfg['winner'].split(' & ')`),
       so the rendered scoreboard correctly attributes ties to each tied team.
6. Print each year as a Python dict literal formatted to match the existing 2025 style

### Expected output format (example)

```python
2019: {
    1:  {"name": "Hot Start",           "desc": "Team with the highest score (starters only)",           "winner": "???"},
    2:  {"name": "Look At These TDs",   "desc": "Team with the most offensive touchdowns scored",        "winner": "JTizzzzle"},
    ...
},
```

The agent reviews the printed output before touching `sleeper_core.py`. Any `KeyError`
on an unmapped name must be resolved (update `DISPLAY_NAME_MAP`) before continuing.

---

## Phase 2 — Populate `SIDE_BET_SEASONS` ✅ COMPLETE

**File:** `sleeper_core.py` — `SIDE_BET_SEASONS` dict at line ~335

Insert 6 new year entries above the existing `2025` entry using the verified parser output.
The 2025 entry must not be modified.

**Done:** 2019–2024 entries inserted. One post-paste fix applied: 2019 weeks 3 and 11 used
`RReclam` (parser output), but the 2019 Sleeper roster used `GurlyGirls` (that person's old
username). Corrected in `sleeper_core.py`; the parser `DISPLAY_NAME_MAP` is annotated with
a warning to catch this on any future re-run.

```python
SIDE_BET_SEASONS = {
    2019: { 1: {"name": "...", "desc": "...", "winner": "..."}, ... },
    2020: { ... },
    2021: { ... },
    2022: { ... },
    2023: { ... },
    2024: { ... },
    2025: { ... },   # existing — do not touch
}
```

---

### Expected money-split behavior

The scoreboard math at `webapp/app.py:2017` (`share = 20 / len(names)`) means historical
weeks with tied winners will display split prizes (e.g. a 3-way tie shows `$6.67` per
person). This is correct behavior, not a regression — call it out so post-migration QA
doesn't flag it.

---

## Phase 3 — Add a Permanent Sanity Test ✅ COMPLETE

**File:** `tests/test_pipeline.py`

Add a parametrized test that locks in the invariant "every side bet winner is a real
roster member for that year." This catches mapping errors permanently, not just at
agent-run time:

```python
@pytest.mark.parametrize("year", [2019, 2020, 2021, 2022, 2023, 2024, 2025])
def test_sidebet_winners_match_rosters(year):
    valid = set(core.roster_ids[year].values())
    for cfg in core.SIDE_BET_SEASONS[year].values():
        for name in cfg['winner'].split(' & '):
            name = name.strip()
            if name:
                assert name in valid, f"{year}: {name!r} not in roster_ids"
```

---

## Phase 4 — No App Changes Required

The `_tab_sidebets` function in `webapp/app.py` already handles any year present in
`SIDE_BET_SEASONS`:

- **Scoreboard** — reads `winner_counts`, `money_earned`, `weeks_won` directly from
  `year_config`; `roster_ids` for all historical years already exist in `sleeper_core.py`
- **Fallback banner** — disappears automatically for any year now in the dict (banner only
  shows when `config_year != year`)
- **Week cards** — show name, description, and winner badge from config; the chart area
  displays `"Chart not yet available for Week N."` when no chart method exists, which is
  the correct behavior for historical read-only data

No changes to `webapp/app.py` or `webapp/assets/style.css` are needed.

---

## Phase 5 — Verification

The Phase 3 pytest assertion catches the only thing that can actually go wrong (bad
name mapping), so browser checks are minimal:

1. Run `pytest tests/ -m "not slow" -q` — expect all existing tests to pass, including
   the new `test_sidebet_winners_match_rosters` parametrized cases for 2019–2024
2. Start the app: `lsof -ti :8050 | xargs kill -9 2>/dev/null; sleep 1 && cd webapp && source ../.venv/bin/activate && python app.py`
3. Spot-check two years via `browser_snapshot` (not screenshot):
   - **2019** — confirms the historical render path works at all
   - **One year known to contain a multi-way tie** (pick from the parser output) —
     confirms split-prize formatting renders cleanly
4. `browser_console_messages` on those two years to confirm no React/JS errors

Skip cycling through every year; the render code path is year-agnostic and the pytest
assertion covers data correctness for the other years.

---

## Revision History

| Date | Change |
|---|---|
| 2026-05-26 | Initial plan drafted |
| 2026-05-27 | Review pass: added discovery pass for unknown names, MD5 duplicate detection, ` & ` separator rationale, money-split note, permanent pytest invariant (new Phase 3), trimmed Phase 5 verification, committed parser script to `scripts/` |
| 2026-05-27 | Phase 2 complete: 2019–2024 inserted into SIDE_BET_SEASONS; fixed 2019 RReclam→GurlyGirls (old Sleeper username); Phase 3 complete: `test_sidebet_winners_match_rosters` parametrized test added to test_pipeline.py, all 7 years pass |
