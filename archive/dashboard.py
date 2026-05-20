#!/usr/bin/env python3
# dashboard.py  –  Liquid League Fantasy Football Dashboard
# Run with:  python dashboard.py
# Then open  http://localhost:8050  in your browser.

import threading
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

import sleeper_core as core
import data_loader as dl

# ── App bootstrap ─────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG, dbc.icons.BOOTSTRAP],
    title="Liquid League Dashboard",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server

# ── Global data store ─────────────────────────────────────────────────────────
_data: dict = {}
_loading_years: set = set()
_failed_years: set = set()
_load_lock = threading.Lock()

CURRENT_YEAR = 2025
ALL_YEARS = core.AVAILABLE_YEARS


def _load_year_bg(year: int):
    with _load_lock:
        if year in _data or year in _loading_years or year in _failed_years:
            return
        _loading_years.add(year)
    try:
        league, season, weeks = dl.load_data_for_year(year, max_week=18, verbose=True)
        _data[year] = {"league": league, "season": season, "weeks": weeks}
        _failed_years.discard(year)
    except Exception as e:
        print(f"Error loading {year}: {e}")
        _failed_years.add(year)
    finally:
        _loading_years.discard(year)


def _ensure_year(year: int):
    if year not in _data and year not in _failed_years:
        _load_year_bg(year)


def _get_season(year: int):
    _ensure_year(year)
    return _data.get(year, {}).get("season")


def _get_weeks(year: int):
    _ensure_year(year)
    return _data.get(year, {}).get("weeks", {})


def _get_week(year: int, week: int):
    return _get_weeks(year).get(week)


threading.Thread(target=_load_year_bg, args=(CURRENT_YEAR,), daemon=True).start()


# ── Figure helpers ─────────────────────────────────────────────────────────────

def _strip_title(fig, height: int):
    """Remove the figure's built-in title, fix width for responsiveness,
    and shrink the top margin (no longer needed for a title)."""
    fig.update_layout(
        title=None,
        width=None,
        height=height,
        margin=dict(t=30, b=70, l=80, r=40),
    )
    return fig


def _empty_fig(msg="Loading…", height=400):
    fig = go.Figure()
    fig.update_layout(
        template="gridiron_ink",
        annotations=[dict(text=msg, x=0.5, y=0.5, showarrow=False,
                          font=dict(size=20, color="#BDE2FF"), xref="paper", yref="paper")],
        xaxis_visible=False, yaxis_visible=False,
        title=None, width=None, height=height,
        margin=dict(t=20, b=20, l=20, r=20),
    )
    return fig


def _error_fig(msg="No data available"):
    return _empty_fig(msg)


# ── Layout helpers ────────────────────────────────────────────────────────────

def _chart_card(fig, title: str = "", half: bool = False):
    """Wrap a figure in a card with a dashboard-level title header."""
    col_cls = "col-12 col-xl-6" if half else "col-12"
    children = []
    if title:
        children.append(html.Div(title, className="chart-title"))
    children.append(
        dcc.Graph(
            figure=fig,
            config={"displayModeBar": False, "responsive": True},
            style={"width": "100%"},
        )
    )
    return html.Div(children, className=col_cls + " chart-card")


def _loading_card():
    return html.Div(
        dbc.Spinner(color="warning", size="lg"),
        className="col-12 text-center py-5",
    )


# ── Sidebar controls ──────────────────────────────────────────────────────────

def _sidebar():
    return html.Div(
        id="sidebar",
        children=[
            html.Div([
                html.Img(
                    src="https://raw.githubusercontent.com/bgmaddox/sleeper/master/LL%20logo.png",
                    style={"width": "70px", "display": "block", "margin": "0 auto 8px"},
                ),
                html.H4("Liquid League", className="text-center sidebar-title"),
            ], className="sidebar-header"),

            html.Hr(style={"borderColor": "#3D5E78"}),

            html.Label("Season", className="sidebar-label"),
            dcc.Dropdown(
                id="year-dropdown",
                options=[{"label": str(y), "value": y} for y in sorted(ALL_YEARS, reverse=True)],
                value=CURRENT_YEAR,
                clearable=False,
                className="dash-dropdown",
            ),

            html.Br(),

            html.Label("Week", className="sidebar-label"),
            dcc.Slider(
                id="week-slider",
                min=1, max=18, step=1, value=1,
                marks={w: str(w) for w in [1, 4, 7, 10, 13, 16, 18]},
                tooltip={"placement": "bottom", "always_visible": True},
                className="week-slider",
            ),

            html.Br(),

            html.Label("Teams", className="sidebar-label"),
            html.Div([
                dbc.Button("All",  id="btn-all-teams", size="sm", color="secondary",
                           outline=True, className="me-1 mb-1"),
                dbc.Button("None", id="btn-no-teams",  size="sm", color="secondary",
                           outline=True, className="mb-1"),
            ]),
            dcc.Checklist(
                id="team-checklist",
                options=[], value=[],
                labelStyle={"display": "block", "padding": "2px 0"},
                className="team-checklist",
                inputStyle={"marginRight": "6px"},
            ),

            html.Br(),

            html.Label("Color Theme", className="sidebar-label"),
            dcc.Dropdown(
                id="theme-dropdown",
                options=[
                    {"label": "Coastal (default)", "value": "coastal"},
                    {"label": "Neon Future",        "value": "neon"},
                    {"label": "Autumn Forest",      "value": "autumn"},
                ],
                value="coastal",
                clearable=False,
                className="dash-dropdown",
            ),

            html.Br(),

            dbc.Button(
                [html.I(className="bi bi-arrow-clockwise me-1"), "Refresh Data"],
                id="btn-refresh",
                color="warning", outline=True, size="sm", className="w-100",
            ),
            html.Div(id="refresh-status", className="mt-2 text-center small"),
        ],
        className="sidebar",
    )


# ── App layout ────────────────────────────────────────────────────────────────

app.layout = html.Div([
    dcc.Store(id="store-year",  data=CURRENT_YEAR),
    dcc.Store(id="store-week",  data=1),
    dcc.Store(id="store-theme", data="coastal"),
    dcc.Interval(id="boot-interval", interval=1000, n_intervals=0, max_intervals=1),

    html.Div([
        html.Span("🏈", style={"fontSize": "28px", "marginRight": "10px"}),
        html.Span("LIQUID LEAGUE DASHBOARD", className="topbar-title"),
    ], className="topbar"),

    html.Div([
        _sidebar(),
        html.Div([
            dcc.Tabs(
                id="main-tabs", value="tab-week",
                className="main-tabs",
                children=[
                    dcc.Tab(label="⚡ This Week",  value="tab-week",    className="tab", selected_className="tab-selected"),
                    dcc.Tab(label="📈 Season",      value="tab-season",  className="tab", selected_className="tab-selected"),
                    dcc.Tab(label="🏅 Players",     value="tab-players", className="tab", selected_className="tab-selected"),
                    dcc.Tab(label="🏆 All-Time",    value="tab-alltime", className="tab", selected_className="tab-selected"),
                ],
            ),
            html.Div(id="tab-content", className="tab-content-area"),
        ], className="main-content"),
    ], className="body-row"),
], className="app-shell")


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("week-slider", "max"),
    Output("week-slider", "value"),
    Output("store-week", "data"),
    Input("boot-interval", "n_intervals"),
    State("year-dropdown", "value"),
)
def _boot(_, year):
    weeks = _get_weeks(year or CURRENT_YEAR)
    mw = max(weeks.keys()) if weeks else 1
    return mw, mw, mw


@app.callback(
    Output("week-slider", "max",        allow_duplicate=True),
    Output("week-slider", "value",      allow_duplicate=True),
    Output("team-checklist", "options"),
    Output("team-checklist", "value"),
    Input("year-dropdown", "value"),
    prevent_initial_call=True,
)
def _year_changed(year):
    if year not in _data:
        threading.Thread(target=_load_year_bg, args=(year,), daemon=True).start()
        _ensure_year(year)
    weeks = _get_weeks(year)
    mw = max(weeks.keys()) if weeks else 1
    roster = core.roster_ids.get(year, {})
    teams = sorted(roster.values())
    return mw, mw, [{"label": t, "value": t} for t in teams], teams


@app.callback(
    Output("team-checklist", "value", allow_duplicate=True),
    Input("btn-all-teams", "n_clicks"),
    Input("btn-no-teams",  "n_clicks"),
    State("year-dropdown", "value"),
    prevent_initial_call=True,
)
def _toggle_teams(n_all, n_none, year):
    ctx = callback_context.triggered_id
    teams = sorted(core.roster_ids.get(year, {}).values())
    return teams if ctx == "btn-all-teams" else []


@app.callback(
    Output("refresh-status", "children"),
    Input("btn-refresh", "n_clicks"),
    State("year-dropdown", "value"),
    prevent_initial_call=True,
)
def _refresh(n, year):
    if year in _data:
        del _data[year]
    _failed_years.discard(year)
    dl.invalidate_week(year, 0)
    threading.Thread(target=_load_year_bg, args=(year,), daemon=True).start()
    return "Refreshing…"


@app.callback(
    Output("store-year",  "data"),
    Output("store-week",  "data", allow_duplicate=True),
    Output("store-theme", "data"),
    Input("year-dropdown",  "value"),
    Input("week-slider",    "value"),
    Input("theme-dropdown", "value"),
    prevent_initial_call=True,
)
def _sync_stores(year, week, theme):
    return year, week, theme


@app.callback(
    Output("tab-content", "children"),
    Input("main-tabs",      "value"),
    Input("store-year",     "data"),
    Input("store-week",     "data"),
    Input("store-theme",    "data"),
    Input("team-checklist", "value"),
)
def _render_tab(tab, year, week, theme, selected_teams):
    year  = year  or CURRENT_YEAR
    week  = week  or 1
    theme = theme or "coastal"
    _apply_theme(theme)

    if tab == "tab-week":
        return _tab_this_week(year, week, selected_teams)
    elif tab == "tab-season":
        return _tab_season(year, week, selected_teams)
    elif tab == "tab-players":
        return _tab_players(year, week, selected_teams)
    elif tab == "tab-alltime":
        return _tab_alltime(selected_teams)
    return html.Div("Unknown tab")


# ── Theme ─────────────────────────────────────────────────────────────────────

_COLORWAYS = {
    "coastal": core.coastal_colorway,
    "neon":    core.neon_future_colorway,
    "autumn":  core.autumn_forest_colorway,
}

def _apply_theme(theme_key: str):
    import plotly.io as pio
    cw = _COLORWAYS.get(theme_key, core.coastal_colorway)
    core.gridiron_ink_template.layout.colorway = cw
    pio.templates["gridiron_ink"] = core.gridiron_ink_template


def _filter_season(season, selected_teams):
    if season is None or not selected_teams:
        return season
    import copy
    s = copy.copy(season)
    if hasattr(s, "Matches") and s.Matches is not None:
        s.Matches = s.Matches[s.Matches["Team"].isin(selected_teams)].copy()
    if hasattr(s, "BreakoutSeason") and s.BreakoutSeason is not None:
        s.BreakoutSeason = s.BreakoutSeason[s.BreakoutSeason["team"].isin(selected_teams)].copy()
        s.Starters = s.BreakoutSeason[s.BreakoutSeason["starter"] == 1].copy()
    cw = core.gridiron_ink_template.layout.colorway
    all_teams = sorted(s.Matches["Team"].unique()) if hasattr(s, "Matches") and s.Matches is not None else []
    s.teamcolors = dict(zip(all_teams, cw))
    return s


# ── Tab: This Week ────────────────────────────────────────────────────────────

def _tab_this_week(year, week, selected_teams):
    season = _get_season(year)
    week_obj = _get_week(year, week)

    if season is None or week_obj is None:
        return html.Div([_loading_card()], className="row g-3")

    season_f = _filter_season(season, selected_teams)
    cards = []

    try:
        fig = week_obj.WeeklyGraph()
        _strip_title(fig, height=560)
        # One bar per position per team — give more room per team row
        fig.update_layout(margin=dict(t=20, b=50, l=160, r=40))
        cards.append(_chart_card(fig, title=f"Week {week} · Matchups"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Matchups: {e}"), title="Week Matchups"))

    try:
        fig = week_obj.PointsOverTheWeekend()
        _strip_title(fig, height=480)
        cards.append(_chart_card(fig, title=f"Week {week} · Points Timeline"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Timeline: {e}"), title="Points Timeline"))

    try:
        fig = season_f.StatusGraph(week_obj)
        _strip_title(fig, height=620)
        fig.update_layout(showlegend=True)
        cards.append(_chart_card(fig, title="Power Rankings"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Power Rankings: {e}"), title="Power Rankings"))

    try:
        fig = season_f.LuckChart(week)
        _strip_title(fig, height=520)
        cards.append(_chart_card(fig, title="Luck Chart"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Luck Chart: {e}"), title="Luck Chart"))

    return html.Div(cards, className="row g-3")


# ── Tab: Season ───────────────────────────────────────────────────────────────

def _tab_season(year, week, selected_teams):
    season = _get_season(year)

    if season is None:
        return html.Div([_loading_card()], className="row g-3")

    season_f = _filter_season(season, selected_teams)
    cards = []

    try:
        fig = season_f.SnakeGraph(week)
        _strip_title(fig, height=500)
        fig.update_layout(showlegend=True)
        cards.append(_chart_card(fig, title="Win Progression"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Win Progression: {e}"), title="Win Progression"))

    try:
        fig = season_f.SeasonPointsForAgainst()
        _strip_title(fig, height=500)
        cards.append(_chart_card(fig, title="Points For & Against"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Points For/Against: {e}"), title="Points For & Against"))

    try:
        fig = season_f.WeeklyWinsGraphBreakout(week)
        _strip_title(fig, height=720)
        cards.append(_chart_card(fig, title="Weekly Wins · Breakout"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Weekly Wins Breakout: {e}"), title="Weekly Wins · Breakout"))

    try:
        fig = season_f.ScoreFrequencyGraph(week)
        _strip_title(fig, height=460)
        cards.append(_chart_card(fig, title="Scoring Frequency", half=True))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Scoring Frequency: {e}"), title="Scoring Frequency", half=True))

    try:
        fig = season_f.BrawnyBench()
        _strip_title(fig, height=460)
        fig.update_layout(margin=dict(t=20, b=50, l=160, r=40))
        cards.append(_chart_card(fig, title="Brawny Benches", half=True))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Brawny Bench: {e}"), title="Brawny Benches", half=True))

    try:
        fig = season_f.PositionStengthPolar()
        _strip_title(fig, height=580)
        cards.append(_chart_card(fig, title="Position Strength"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Position Strength: {e}"), title="Position Strength"))

    return html.Div(cards, className="row g-3")


# ── Tab: Players ──────────────────────────────────────────────────────────────

def _tab_players(year, week, selected_teams):
    season = _get_season(year)

    if season is None:
        return html.Div([_loading_card()], className="row g-3")

    season_f = _filter_season(season, selected_teams)
    cards = []

    try:
        fig = season_f.PlayerPoints(week)
        _strip_title(fig, height=580)
        cards.append(_chart_card(fig, title="Player Points"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Player Points: {e}"), title="Player Points"))

    try:
        fig = season_f.ViolinPlayer(week, Starters=True)
        _strip_title(fig, height=500)
        cards.append(_chart_card(fig, title="Starter Scoring Distribution", half=True))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Violin (Starters): {e}"), title="Starter Scoring Distribution", half=True))

    try:
        fig = season_f.ViolinPlayer(week, Starters=False)
        _strip_title(fig, height=500)
        cards.append(_chart_card(fig, title="Bench Scoring Distribution", half=True))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Violin (Bench): {e}"), title="Bench Scoring Distribution", half=True))

    try:
        fig = season_f.ScoreTrends()
        _strip_title(fig, height=460)
        cards.append(_chart_card(fig, title="Weekly Score Trends"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Score Trends: {e}"), title="Weekly Score Trends"))

    try:
        fig = season_f.TopPlayers()
        _strip_title(fig, height=580)
        cards.append(_chart_card(fig, title="Top Players"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Top Players: {e}"), title="Top Players"))

    return html.Div(cards, className="row g-3")


# ── Tab: All-Time ─────────────────────────────────────────────────────────────

def _tab_alltime(selected_teams):
    missing = [y for y in ALL_YEARS if y not in _data]
    if missing:
        for y in missing:
            threading.Thread(target=_load_year_bg, args=(y,), daemon=True).start()
        return html.Div([
            html.Div(
                f"Loading historical seasons ({', '.join(str(y) for y in missing)})… "
                "Please wait a moment and switch back to this tab.",
                className="col-12 text-center py-5 text-warning fs-5",
            )
        ], className="row g-3")

    try:
        all_time = dl.load_all_time(ALL_YEARS)
    except Exception as e:
        return html.Div([_chart_card(_error_fig(f"All-Time load failed: {e}"))], className="row g-3")

    cards = []

    try:
        fig = all_time.HallofFame_Team()
        _strip_title(fig, height=580)
        cards.append(_chart_card(fig, title="Hall of Fame · Best Team Scores"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"HoF Teams: {e}"), title="Hall of Fame · Teams"))

    try:
        fig = all_time.HallofFame_Player()
        _strip_title(fig, height=580)
        cards.append(_chart_card(fig, title="Hall of Fame · Best Player Scores"))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"HoF Players: {e}"), title="Hall of Fame · Players"))

    try:
        fig = all_time.HallofShame_Team()
        _strip_title(fig, height=500)
        cards.append(_chart_card(fig, title="Hall of Shame · Worst Scores", half=True))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"HoS: {e}"), title="Hall of Shame", half=True))

    try:
        fig = all_time.HighestScoringLosers()
        _strip_title(fig, height=500)
        cards.append(_chart_card(fig, title="Highest Scoring Losses", half=True))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Scoring Losers: {e}"), title="Highest Scoring Losses", half=True))

    try:
        fig = all_time.SmallestMargins()
        _strip_title(fig, height=500)
        cards.append(_chart_card(fig, title="Smallest Margins of Victory", half=True))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"Margins: {e}"), title="Smallest Margins", half=True))

    try:
        fig = all_time.ForAgainstwithTeams()
        _strip_title(fig, height=500)
        cards.append(_chart_card(fig, title="All-Time Points For & Against", half=True))
    except Exception as e:
        cards.append(_chart_card(_error_fig(f"For/Against All-Time: {e}"), title="All-Time For & Against", half=True))

    return html.Div(cards, className="row g-3")


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
