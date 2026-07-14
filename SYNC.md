# Agent Synchronization Log (SYNC.md)

This file acts as a low-overhead communication channel between Claude Code and Gemini, ensuring seamless handoffs and shared context without consuming large amounts of context window.

## Active Focus
- **Current Task:** Verification and merge of `feat-orphaned-graphs-and-sync`. The 3 high-insight orphaned graphs (`PositionStrengthPolar`, `ViolinPosition`, `StarterPerformanceGraph`) have now been fully integrated.

## Key Decisions & Updates
- **Orphaned Graphs Integration Complete:** 
  - Deleted `WholeSeasonBarGraph` and `WeekYTDTotalsPercents` to reduce clutter. 
  - Intentionally deleted `StatusGraph` because the `Power Rankings` native Dash card recreates the graph's insights.
  - Renamed `PositionStengthPolar` typo. 
  - Integrated `StarterPerformanceGraph` and toggles for `pos-strength` and `violin` into the `app.py` UI.
- **Data Bug Fix Confirmed:** Verified that the `all_owners` undefined variable in `app.py` was fixed dynamically in a previous session.
- **Cache Corruption Bug Resolved:** Found that `KeyError: 'Team'` and duplicate index errors on the charts were caused by a corrupt `.cache/` state on disk (the cache incorrectly contained lowercase `team` and `week` schema from a temporary experimental code run). **Resolution:** Deleted `.cache/` and let the system rebuild it natively. **No code changes were needed in `sleeper_core.py`.**
- **SideBet Feature Deferred:** The orphaned `SideBet` class has been intentionally left alone per user request; it will be developed as a major feature in the future.

## Handoff Notes
- **To Claude Code:** If you experiment with changing core dataframe schemas (e.g. renaming columns in `sleeper_core.py`), please ensure you **clear the `.cache/` directory** before reverting the code, to avoid leaving corrupted caches on disk that crash subsequent runs.
- **To bgmaddox / User:** Code integration for orphaned graphs is complete. The server is running and the graphs are working perfectly using your code from last night. Please start the server and verify the UI for the "This Week", "Season", and "Players" tabs to ensure no Dash exceptions are thrown before merging `feat-orphaned-graphs-and-sync` to main.
