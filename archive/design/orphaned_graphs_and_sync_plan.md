# Goal Description

1. Address the items in the backend audit report, specifically regarding the orphaned graphing methods in `sleeper_core.py`.
2. Establish a structured, low-context-overhead synchronization method between Gemini and Claude.
3. Ensure a new feature branch is created before any code is modified, adhering to the project's git workflow rules.
4. Leave the `SideBet` class untouched as it is slated for a future major feature.

## User Review Required

### 1. Orphaned Graphs Analysis
I have reviewed the 6 orphaned graphing methods in `sleeper_core.py`. Here is my assessment:

**Graphs to Keep and Integrate (High Insight):**
*   **`PositionStengthPolar`** *(Typo to be fixed to `PositionStrengthPolar`)*: A 4x3 grid of polar charts showing each team's positional strength as a z-score relative to the league average. **Proposal:** Add to the **Season** tab.
*   **`ViolinPosition`**: Faceted violin plots showing point distributions by position across different teams. Excellent for seeing team-building strategies. **Proposal:** Add to the **Players** tab.
*   **`StarterPerformanceGraph`**: A horizontal bar chart breaking down total points scored by starters, color-coded by position. **Proposal:** Add to the **Season** tab.
*   **`StatusGraph`**: Compares weekly team scores against the league average alongside Power Rankings. **Proposal:** Add to the **This Week** tab.

**Graphs to Delete (High Clutter / Redundant):**
*   **`WholeSeasonBarGraph`** & **`WeekYTDTotalsPercents`**: These are stacked bar charts showing weekly performance and percentage domination. While visually interesting, they largely duplicate the insights already provided by the Win Progression and Points For/Against tabs, and will crowd the dashboard. **Proposal:** Safely delete these methods.

### 2. Claude/Gemini Sync Strategy
To keep us perfectly aligned without consuming massive amounts of context window, I propose creating a `SYNC.md` file in the root directory. 

**Format of `SYNC.md`:**
*   **Active Focus:** 1-2 sentences on what is currently being built or debugged.
*   **Key Decisions:** A bulleted list of recent architectural choices or solved bugs (e.g., "Fixed `all_owners` undefined variable by dynamically deriving it").
*   **Handoff Notes:** Specific notes left by Claude for Gemini, or Gemini for Claude.

Both `CLAUDE.md` and `GEMINI.md` will be updated with a rule requiring us to read `SYNC.md` at the start of a session and update it at the end of a session.

> [!IMPORTANT]
> Please review the proposed locations for the new graphs and let me know if you agree with deleting the two redundant graphs. 

## Open Questions

1. For the `SYNC.md` strategy, does this sound like a good approach, or would you prefer we utilize the existing `.claude/structure.md` file for this purpose?
2. What should we name our new feature branch? I am defaulting to `feat-orphaned-graphs-and-sync`.

## Proposed Changes

### Git Operations
- Run `git checkout -b feat-orphaned-graphs-and-sync`

### Documentation
#### [NEW] [SYNC.md](file:///Users/brettmaddox/Documents/CODING/Sleeper%20Project/SYNC.md)
- Create the sync file with initial context.
#### [MODIFY] [CLAUDE.md](file:///Users/brettmaddox/Documents/CODING/Sleeper%20Project/CLAUDE.md)
- Add instruction to read and update `SYNC.md`.
#### [MODIFY] [GEMINI.md](file:///Users/brettmaddox/Documents/CODING/Sleeper%20Project/GEMINI.md)
- Add instruction to read and update `SYNC.md`.

---

### Backend Logic (`sleeper_core.py`)
#### [MODIFY] [sleeper_core.py](file:///Users/brettmaddox/Documents/CODING/Sleeper%20Project/sleeper_core.py)
- Rename `PositionStengthPolar` to `PositionStrengthPolar`.
- Delete `WholeSeasonBarGraph`.
- Delete `WeekYTDTotalsPercents`.
- (Leave `SideBet` untouched).

---

### Frontend Webapp (`webapp/app.py`)
#### [MODIFY] [app.py](file:///Users/brettmaddox/Documents/CODING/Sleeper%20Project/webapp/app.py)
- Update the SECTION MAP to account for new graphing callback integrations.
- **Season Tab:** Add `PositionStrengthPolar` and `StarterPerformanceGraph` UI elements and callbacks.
- **Players Tab:** Add `ViolinPosition` UI elements and callbacks.
- **This Week Tab:** Add `StatusGraph` UI elements and callbacks.

## Verification Plan

### Automated Tests
- Run `flake8` or equivalent linter to ensure no syntax errors were introduced during the deletion/renaming.

### Manual Verification
- Start the server using the standard procedure (`lsof -ti :8050 | xargs kill -9 2>/dev/null; sleep 1; cd webapp && source ../.venv/bin/activate && python app.py`).
- Manually click through the "This Week", "Season", and "Players" tabs to verify the 4 newly integrated graphs render correctly without throwing Dash callback exceptions.
- Verify `all_owners` variable fix is still holding up in the All-Time tab.
