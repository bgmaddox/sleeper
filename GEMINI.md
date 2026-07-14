# GEMINI.md

This document serves as the project context and guidelines for Gemini when working on the Sleeper Project alongside Claude Code.

## Project Overview
- **Name:** Legacy League Webapp
- **Goal:** Provide rich visualizations and analytics for a fantasy football league using data from the Sleeper API and `nfl_data_py`. It originated from `Sleeper_v2.ipynb`.
- **Primary Stack:** Python 3.13, Dash/Flask, Plotly, D3.js.
- **Environment:** `../.venv` (Python 3.13)

## Architecture & Data Flow
1. **Core Logic (`sleeper_core.py`):** Handles API requests, processes data into Pandas DataFrames, and contains the logic for 30+ Plotly charts. Includes classes like `League`, `Week`, `Season`, and `AllTime`.
2. **Caching (`data_loader.py`):** Wraps the core logic with a disk-cache layer (`.cache/`) using MD5-keyed pickles to improve loading times. Data is loaded in a background thread in the webapp.
3. **Web Frontend (`webapp/app.py`):** The primary Dash application containing all layout and callback logic. Custom styling is located in `webapp/assets/style.css` using the `gridiron_ink` theme.

## Collaboration Rules
1. **Agent Synchronization:** Always read `SYNC.md` at the start of your session to understand the active context and previous decisions. Before concluding a major task or handing off, update `SYNC.md` with the new active focus and key decisions.
2. **Sync with Claude:** When modifying directory structures or large file maps, ensure `CLAUDE.md` and `.claude/structure.md` are updated to keep Claude in the loop.
3. **App.py Section Map:** `webapp/app.py` has a **SECTION MAP** at the top. If I add/remove/move functions by more than ~20 lines, I must update this map.
4. **Running the App:**
  - Kill existing processes first: `lsof -ti :8050 | xargs kill -9 2>/dev/null; sleep 1`
  - Activate environment and run: `cd webapp && source ../.venv/bin/activate && python app.py`
  - No hot reloading is configured; manual restart is required after code changes.
- **Git Workflow:** Always create a feature branch (`feat-...` or `fix-...`) from `main` before making code changes. Do not commit directly to `main`.

## Current Status
- Transitioned from Notebook to Webapp.
- Currently iterating on bug fixes and optimizing load times.
