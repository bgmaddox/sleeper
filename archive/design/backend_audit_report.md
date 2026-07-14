# Sleeper Project Codebase Audit Report

**Date:** May 20, 2026
**Scope:** `webapp/app.py`, `sleeper_core.py`, `data_loader.py`

This document details the findings of a comprehensive codebase audit of the Sleeper Project backend. The goal is to highlight runtime hazards, orphaned code, performance bottlenecks, and fragility to guide future maintenance and optimization efforts.

## 1. Bugs & Runtime Hazards

These issues pose an immediate risk of runtime errors or missing functionality and should be prioritized.

*   **Undefined Variable in `app.py`**
    *   **Location:** `webapp/app.py` (Line 2343 in `_populate_chord_data`)
    *   **Issue:** The variable `all_owners` is referenced but never defined in the file scope. This causes the "All-Time Points Flow" chord diagram to silently fail and not render.
    *   **Actionable Fix:** Replace `all_owners` with a dynamic derivation of all available owners, such as `list(core.get_alltime_teamcolors().keys())` or by extracting the unique set of owners from the data matrix.

*   **Unsafe Dictionary Lookups (KeyError Risk)**
    *   **Location:** `sleeper_core.py` (e.g., within `WeeklyDataframe`)
    *   **Issue:** Player names are frequently accessed using direct dictionary lookups (e.g., `self.league.player_names[player]`). If the Sleeper API returns a new or unknown player ID not present in the cached dictionary, a `KeyError` will crash the data loading process.
    *   **Actionable Fix:** Replace direct indexing with the `.get()` method, providing a safe fallback (e.g., `self.league.player_names.get(player, "Unknown Player")`).

*   **Broken Cache Invalidation**
    *   **Location:** `data_loader.py` (`invalidate_week` function)
    *   **Issue:** The function attempts to delete cache files with a `matchup_` prefix pattern, but these specific cache files are never actually generated or used by the system.
    *   **Actionable Fix:** Audit the cache file generation patterns in `data_loader.py` and update the `invalidate_week` pattern to match the actual files being written to the `.cache/` directory.

## 2. Orphaned & Unused Code

Removing this code will reduce the bundle size, simplify navigation, and clarify the system architecture.

*   **The `SideBet` Class**
    *   **Location:** `sleeper_core.py` (Lines ~3728 to ~4791)
    *   **Issue:** This massive class (~1,000 lines) is completely unreferenced by `app.py` or any executing logic in `sleeper_core.py`.
    *   **Actionable Fix:** Safely delete the entire `SideBet` class.

*   **Orphaned Graphing/Tracking Methods**
    *   **Location:** `sleeper_core.py` (Within the `Season` class)
    *   **Issue:** Several visualization and tracking methods are defined but never called by the frontend or backend.
    *   **Actionable Fix:** Remove the following unused methods: `WholeSeasonBarGraph`, `WeekYTDTotalsPercents`, `StarterPerformanceGraph`, `ViolinPosition`, `PositionStengthPolar` (note the typo in the original), and `StatusGraph`.

*   **Redundant `Week` Methods**
    *   **Location:** `sleeper_core.py` (Within the `Week` class)
    *   **Issue:** `ImportPlayerData` is an unoptimized duplicate of `data_loader.fetch_player_data`. `ImportFixes` is an empty, unused stub.
    *   **Actionable Fix:** Remove `ImportPlayerData` and ensure all player data loading routes through `data_loader.py`. Remove `ImportFixes`.

## 3. Performance & Optimization

These items impact application startup time and runtime responsiveness.

*   **Bypassed Caching Layer**
    *   **Location:** `sleeper_core.py` (`League.__init__` and `Week.ImportWeek`)
    *   **Issue:** These methods use `requests.get()` directly against the Sleeper API. This bypasses the caching logic defined in `data_loader.py`, resulting in dozens of redundant network requests every time a season is initialized.
    *   **Actionable Fix:** Refactor these methods to call the appropriate helper functions in `data_loader.py` so that previously fetched JSON payloads are served from the local disk cache.

*   **Inefficient Pandas Operations**
    *   **Location:** `sleeper_core.py` (`WeeklyDataframe`, `WeeklyWins`, `PlayerBreakout`)
    *   **Issue:** The codebase heavily relies on `.apply()` or standard Python `for` loops to iterate over rows (e.g., calculating `sum_points`). This is highly inefficient in Pandas. `PlayerBreakout` also performs repeated regex string replacements within loops.
    *   **Actionable Fix:** Vectorize these calculations using native Pandas operations (e.g., using `df.groupby().sum()`, boolean indexing, or built-in string accessor methods like `df['col'].str.replace`).

## 4. Fragility & Hardcoding

These items threaten the long-term maintainability of the project and will cause imminent failures in upcoming seasons.

*   **Hardcoded `SeasonMultiplier`**
    *   **Location:** `sleeper_core.py`
    *   **Issue:** The logic determining the multiplier/index for calculating season progression is hardcoded with conditional statements ending at the year 2025. This guarantees failure when the 2026 season begins.
    *   **Actionable Fix:** Replace the hardcoded `if/elif` year checks with an algorithmic approach or a dynamically updating dictionary that extrapolates the multiplier based on the delta from a base year.

*   **Scattered Year Checks**
    *   **Location:** `sleeper_core.py`
    *   **Issue:** The codebase contains numerous `if self.year != 2025` checks, making it brittle.
    *   **Actionable Fix:** Identify the root business requirement driving these checks (e.g., a rule change that occurred in a specific year) and refactor to use a configuration object or specific feature flags tied to the season context rather than the raw integer year.