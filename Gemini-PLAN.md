# Legacy League — Premium Web App Plan (React + FastAPI)

## Objective
To build a highly engaging, visually stunning, password-protected web application for the Legacy League. By splitting the architecture into a modern React (Next.js) frontend and a Python (FastAPI) backend, we achieve a fluid, app-like experience (with animations and polished UI) while fully reusing the complex data processing and custom Plotly charts from the original Python project.

## AI Agent Implementation Guidelines
**Role:** You are a senior full-stack engineer implementing this plan.
**Context Limits:** Do not read massive CSVs or pickles into context. Assume the data loader works. Focus on scaffolding the FastAPI endpoints and Next.js UI.
**Style & Quality:** Strictly adhere to the `gridiron_ink` design system (see CSS variables in codebase). Ensure type safety in Python (Pydantic/FastAPI) and TypeScript (Next.js).
**Execution:** Proceed phase-by-phase. Validate the backend endpoints return valid JSON before building the React components that consume them.

## Key Files & Context
- **Backend (Python/FastAPI):** Will wrap `FirstPyProject/sleeper_core.py` and `data_loader.py`.
- **Frontend (Next.js/React):** A brand new directory (`webapp-frontend/`) containing UI components, routing, and styling.
- **Data Handoff:** The Python backend will generate Plotly figures and return them as JSON. The React frontend will render them natively using `react-plotly.js`.

## Proposed Solution: Architecture

### 1. Backend: FastAPI (Python)
- Acts as a lightweight API server.
- Exposes endpoints like `/api/matchups/{week}`, `/api/season/standings`, and `/api/players/trends`.
- Under the hood, these endpoints call the existing `sleeper_core.py` methods.
- Instead of calling `fig.show()`, the endpoints will use `fig.to_json()` to send the chart data to the frontend.

### 2. Frontend: Next.js (React)
- **Framework:** Next.js (App Router) for easy routing and fast page loads.
- **Styling:** Tailwind CSS mapped to the `gridiron_ink` design system (deep blues, cyan text, Courier New fonts) so the UI chrome perfectly matches the charts.
- **Animations:** Framer Motion for buttery-smooth page transitions, fading in charts, and animated layout changes (e.g., clicking a tab slides the new content in).
- **Charting:** `react-plotly.js` receives the JSON from FastAPI and renders the charts exactly as they looked in Jupyter.

### 3. Authentication
- Simple password protection implemented via Next.js Middleware. A user enters the shared password, gets an HTTP-only secure cookie, and can access the app for 30 days.

## Implementation Plan

### Phase 1: Backend Foundation (FastAPI)
1. Initialize a FastAPI project in `webapp-backend/`.
2. Refactor/Import necessary logic from `FirstPyProject/sleeper_core.py` to ensure methods can return JSON instead of rendering immediately.
3. Create core REST endpoints:
   - `GET /api/week/{week_number}` -> returns Weekly Matchups, Timeline, Luck Chart JSON.
   - `GET /api/season` -> returns Win Progression Snake Graph JSON.
4. Test endpoints locally with Swagger UI.

### Phase 2: Frontend Foundation (Next.js)
1. Bootstrap a Next.js project in `webapp-frontend/`.
2. Configure Tailwind CSS with the `gridiron_ink` color palette.
3. Build the core layout: responsive sidebar/top-nav, and the central display area.
4. Implement the Login page and Middleware for password protection.

### Phase 3: Integration & UI Polish
1. Build out the specific tabs (This Week, Season, Players, All-Time, Head-to-Head).
2. Wire up `react-plotly.js` to fetch data from the FastAPI backend and render the charts.
3. Add Framer Motion animations to make tab switching and data loading feel premium.
4. Implement interactive controls (e.g., a dropdown to select which Week to view) that seamlessly trigger re-fetches from the backend.

### Phase 4: Deployment
1. **Backend:** Deploy the FastAPI service to Render.com (Web Service).
2. **Frontend:** Deploy the Next.js app to Vercel (free, highly optimized for Next.js).
3. Connect the frontend to the backend URL via environment variables.

## Verification & Testing
- **Backend Validation:** Ensure all endpoints return valid Plotly JSON structures and handle missing data gracefully.
- **Frontend Validation:** Test across desktop and mobile. Verify that `react-plotly.js` accurately reproduces the custom `coastal_colorway` and styling.
- **Auth Validation:** Confirm unauthorized users are blocked at the middleware level and redirected to the login screen.