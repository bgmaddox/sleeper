#!/usr/bin/env python3
"""
Legacy League — Fantasy Football Web App
Run locally: python app.py  → http://localhost:8050
Deploy:      gunicorn app:server
"""

import sys
import os
import threading

# Resolve imports from FirstPyProject without any code duplication
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'FirstPyProject'))

import pandas as pd
import plotly.io as pio
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State, callback_context, no_update
from flask import request, redirect, make_response, render_template_string
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

import sleeper_core as core
import data_loader as dl


# ── Config ────────────────────────────────────────────────────────────────────

CURRENT_YEAR  = 2025
ALL_YEARS     = core.AVAILABLE_YEARS
SECRET_KEY    = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
LEAGUE_PASS   = os.environ.get('LEAGUE_PASSWORD', 'legacy')
COOKIE_NAME   = 'll_auth'
COOKIE_TTL    = 30 * 24 * 3600   # 30 days
LOGO_URL      = 'https://raw.githubusercontent.com/bgmaddox/sleeper/master/LL%20logo.png'
URL_BASE      = os.environ.get('URL_BASE_PATHNAME', '/')


# ── Plotly template ───────────────────────────────────────────────────────────

def _register_template(colorway=None):
    t = core.gridiron_ink_template
    if colorway:
        t.layout.colorway = colorway
    pio.templates['gridiron_ink'] = t

_register_template(core.coastal_colorway)


# ── Dash / Flask setup ────────────────────────────────────────────────────────

app = Dash(
    __name__,
    title='Legacy League',
    suppress_callback_exceptions=True,
    url_base_pathname=URL_BASE,
    meta_tags=[{'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}],
)
server = app.server


# ── Auth ──────────────────────────────────────────────────────────────────────

_sz = URLSafeTimedSerializer(SECRET_KEY)

def _make_token():
    return _sz.dumps('ok')

def _valid_token(tok):
    if not tok:
        return False
    try:
        _sz.loads(tok, max_age=COOKIE_TTL)
        return True
    except (BadSignature, SignatureExpired):
        return False

_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Legacy League · Login</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0d1e2e;
      color: #BDE2FF;
      font-family: 'Courier New', monospace;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }
    .box {
      background: #163146;
      border: 1px solid #2e526e;
      border-radius: 16px;
      padding: 52px 44px;
      width: 100%;
      max-width: 390px;
      box-shadow: 0 12px 60px rgba(0,0,0,0.7);
      text-align: center;
    }
    .box img { width: 80px; margin-bottom: 14px; }
    .box h1 {
      font-family: Rockwell, Georgia, serif;
      color: #FFC300;
      font-size: 1.5rem;
      letter-spacing: 3px;
      text-transform: uppercase;
      text-shadow: 0 0 20px rgba(255,195,0,0.3);
      margin-bottom: 6px;
    }
    .box p { color: #6a9abf; font-size: 0.78rem; letter-spacing: 1px; margin-bottom: 36px; }
    input[type=password] {
      width: 100%;
      background: #0f2437;
      border: 1px solid #2e526e;
      border-radius: 8px;
      color: #BDE2FF;
      font-family: 'Courier New', monospace;
      font-size: 1rem;
      padding: 13px 16px;
      outline: none;
      margin-bottom: 12px;
      transition: border-color 0.2s;
    }
    input[type=password]:focus { border-color: #FFC300; }
    button {
      width: 100%;
      background: #FFC300;
      border: none;
      border-radius: 8px;
      color: #0d1e2e;
      font-family: Rockwell, Georgia, serif;
      font-size: 1rem;
      font-weight: bold;
      letter-spacing: 1.5px;
      padding: 13px;
      cursor: pointer;
      transition: background 0.2s, box-shadow 0.2s;
    }
    button:hover { background: #ffd133; box-shadow: 0 0 20px rgba(255,195,0,0.4); }
    .err { color: #F94144; font-size: 0.78rem; margin-top: 10px; }
  </style>
</head>
<body>
  <div class="box">
    <img src="{{ logo }}" alt="Legacy League">
    <h1>Legacy League</h1>
    <p>Fantasy Football &middot; Members Only</p>
    <form method="POST" action="{{ login_url }}">
      <input type="password" name="password" placeholder="Enter league password" autofocus>
      <button type="submit">Enter the League &rarr;</button>
      {% if error %}<div class="err">Wrong password. Try again.</div>{% endif %}
    </form>
  </div>
</body>
</html>"""


LOGIN_URL = URL_BASE.rstrip('/') + '/login'

@server.route(LOGIN_URL, methods=['GET', 'POST'])
def _login_route():
    if request.method == 'POST':
        if request.form.get('password') == LEAGUE_PASS:
            resp = make_response(redirect(URL_BASE))
            resp.set_cookie(COOKIE_NAME, _make_token(), max_age=COOKIE_TTL, httponly=True, samesite='Lax')
            return resp
        return render_template_string(_LOGIN_HTML, error=True, logo=LOGO_URL, login_url=LOGIN_URL)
    return render_template_string(_LOGIN_HTML, error=False, logo=LOGO_URL, login_url=LOGIN_URL)


@server.before_request
def _auth_gate():
    bypass = (LOGIN_URL, URL_BASE + 'assets', '/_dash-component-suites', '/favicon.ico', '/manifest.json', '/_reload-hash')
    if any(request.path.startswith(p) for p in bypass):
        return
    if not _valid_token(request.cookies.get(COOKIE_NAME)):
        if request.path.startswith('/_dash'):
            from flask import jsonify
            return jsonify({'error': 'unauthorized'}), 401
        return redirect(LOGIN_URL)


# ── Data store ────────────────────────────────────────────────────────────────

_data:          dict = {}
_loading_years: set  = set()
_failed_years:  set  = set()
_lock = threading.Lock()


def _load_bg(year: int):
    with _lock:
        if year in _data or year in _loading_years or year in _failed_years:
            return
        _loading_years.add(year)
    try:
        league, season, weeks = dl.load_data_for_year(year, max_week=18, verbose=True)
        _data[year] = {'league': league, 'season': season, 'weeks': weeks}
        _failed_years.discard(year)
    except Exception as e:
        print(f'[data] Error loading {year}: {e}')
        _failed_years.add(year)
    finally:
        _loading_years.discard(year)


def _ensure(year):
    if year not in _data and year not in _failed_years and year not in _loading_years:
        threading.Thread(target=_load_bg, args=(year,), daemon=True).start()


def _season(year):
    _ensure(year)
    return _data.get(year, {}).get('season')


def _weeks(year):
    _ensure(year)
    return _data.get(year, {}).get('weeks', {})


def _week(year, w):
    return _weeks(year).get(w)


# Pre-load current year in background at startup
threading.Thread(target=_load_bg, args=(CURRENT_YEAR,), daemon=True).start()


# ── Helpers ───────────────────────────────────────────────────────────────────

_COLORWAYS = {
    'coastal': core.coastal_colorway,
    'neon':    core.neon_future_colorway,
    'autumn':  core.autumn_forest_colorway,
}


def _apply_theme(key: str):
    _register_template(_COLORWAYS.get(key, core.coastal_colorway))


def _strip(fig, h=500):
    fig.update_layout(title=None, width=None, height=h, margin=dict(t=20, b=70, l=80, r=40))
    return fig


def _empty(msg='Loading…', h=400):
    fig = go.Figure()
    fig.update_layout(
        template='gridiron_ink',
        annotations=[dict(text=msg, x=0.5, y=0.5, showarrow=False,
                          font=dict(size=18, color='#BDE2FF'), xref='paper', yref='paper')],
        xaxis_visible=False, yaxis_visible=False,
        title=None, width=None, height=h, margin=dict(t=10, b=10, l=10, r=10),
    )
    return fig


def _err(msg): return _empty(f'⚠ {msg}')


def _card(fig, title='', half=False):
    cls = 'chart-col-half' if half else 'chart-col-full'
    kids = []
    if title:
        kids.append(html.Div(title, className='chart-title'))
    kids.append(dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True},
                          style={'width': '100%'}))
    return html.Div(kids, className=f'chart-card {cls}')


def _loading_placeholder():
    return html.Div([
        html.Div(className='loading-spinner'),
        'Loading season data…'
    ], className='loading-msg')


def _filter_season(season, teams):
    if season is None or not teams:
        return season
    import copy
    s = copy.copy(season)
    if hasattr(s, 'Matches') and s.Matches is not None:
        s.Matches = s.Matches[s.Matches['Team'].isin(teams)].copy()
    if hasattr(s, 'BreakoutSeason') and s.BreakoutSeason is not None:
        s.BreakoutSeason = s.BreakoutSeason[s.BreakoutSeason['team'].isin(teams)].copy()
        s.Starters = s.BreakoutSeason[s.BreakoutSeason['starter'] == 1].copy()
    cw = pio.templates['gridiron_ink'].layout.colorway
    all_teams = sorted(s.Matches['Team'].unique()) if hasattr(s, 'Matches') and s.Matches is not None else []
    s.teamcolors = dict(zip(all_teams, cw))
    return s


# ── League Digest card ────────────────────────────────────────────────────────

def _digest(year, week):
    """Hero stats bar above tabs: top scorer, tightest game, biggest beatdown.

    AllMatchesDict[year][week] is a single DataFrame where each row is one team.
    Teams in the same matchup share the same 'Matchup' value.
    Score column is 'Total'; team name column is 'Team'.
    """
    try:
        df = core.AllMatchesDict.get(year, {}).get(week)
        if df is None or df.empty:
            return html.Div()
        if 'Team' not in df.columns or 'Total' not in df.columns:
            return html.Div()

        # Top scorer this week
        top_idx = df['Total'].idxmax()
        top_team  = df.loc[top_idx, 'Team']
        top_score = df.loc[top_idx, 'Total']

        # Per-matchup margins — group rows by Matchup ID
        margins = []
        for _, grp in df.groupby('Matchup'):
            if len(grp) != 2:
                continue
            teams  = grp['Team'].tolist()
            scores = grp['Total'].tolist()
            winner_idx = 0 if scores[0] > scores[1] else 1
            margins.append({
                'diff':       abs(scores[0] - scores[1]),
                'winner':     teams[winner_idx],
                'loser':      teams[1 - winner_idx],
                'win_score':  max(scores),
                'loss_score': min(scores),
            })

        stats = [html.Span(f'WEEK {week}', className='digest-week-badge')]

        stats.append(html.Div([
            html.Div('Top Score', className='digest-label'),
            html.Div(f'{top_team}  ·  {top_score:.2f}', className='digest-value'),
        ], className='digest-stat'))

        if margins:
            tightest = min(margins, key=lambda x: x['diff'])
            stats.append(html.Div([
                html.Div('Closest Game', className='digest-label'),
                html.Div(f'{tightest["winner"]} def. {tightest["loser"]}', className='digest-value'),
                html.Div(
                    f'{tightest["win_score"]:.2f} – {tightest["loss_score"]:.2f}  '
                    f'(margin: {tightest["diff"]:.2f})',
                    className='digest-sub',
                ),
            ], className='digest-stat'))

            blowout = max(margins, key=lambda x: x['diff'])
            if blowout['diff'] > tightest['diff']:
                stats.append(html.Div([
                    html.Div('Biggest Beatdown', className='digest-label'),
                    html.Div(f'{blowout["winner"]} def. {blowout["loser"]}', className='digest-value'),
                    html.Div(f'By {blowout["diff"]:.2f} pts', className='digest-sub'),
                ], className='digest-stat'))

        return html.Div(stats, className='digest-card')
    except Exception:
        return html.Div()


# ── Layout ────────────────────────────────────────────────────────────────────

def _sidebar():
    return html.Div([
        html.Div([
            html.Img(src=LOGO_URL, className='sidebar-logo'),
            html.H4('Legacy League', className='sidebar-title'),
        ], className='sidebar-header'),

        html.Span('Season', className='sidebar-label'),
        dcc.Dropdown(
            id='year-dd',
            options=[{'label': str(y), 'value': y} for y in sorted(ALL_YEARS, reverse=True)],
            value=CURRENT_YEAR, clearable=False, className='dash-dropdown',
        ),

        html.Span('Week', className='sidebar-label'),
        dcc.Slider(id='week-slider', min=1, max=18, step=1, value=1,
                   marks={w: str(w) for w in [1, 4, 7, 10, 13, 16, 18]},
                   tooltip={'placement': 'bottom', 'always_visible': True}),

        html.Span('Teams', className='sidebar-label'),
        html.Div([
            html.Button('All',  id='btn-all',  className='btn'),
            html.Button('None', id='btn-none', className='btn'),
        ], className='btn-group'),
        dcc.Checklist(id='team-list', options=[], value=[],
                      labelStyle={'display': 'block', 'padding': '2px 0'},
                      className='team-checklist', inputStyle={'marginRight': '6px'}),

        html.Span('Color Theme', className='sidebar-label'),
        dcc.Dropdown(
            id='theme-dd',
            options=[
                {'label': 'Coastal (default)', 'value': 'coastal'},
                {'label': 'Neon Future',       'value': 'neon'},
                {'label': 'Autumn Forest',     'value': 'autumn'},
            ],
            value='coastal', clearable=False, className='dash-dropdown',
        ),

        html.Button('↺  Refresh Data', id='btn-refresh', className='btn-refresh'),
        html.Div(id='refresh-status', className='refresh-status'),
    ], className='sidebar', id='sidebar')


app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='store-year',  data=CURRENT_YEAR),
    dcc.Store(id='store-week',  data=1),
    dcc.Store(id='store-theme', data='coastal'),
    dcc.Interval(id='boot', interval=600, n_intervals=0, max_intervals=1),

    # Top bar
    html.Div([
        html.Img(src=LOGO_URL, className='topbar-logo'),
        html.Span('Legacy League', className='topbar-title'),
        html.Span('Fantasy Football · Since 2019', className='topbar-tagline'),
    ], className='topbar'),

    # Body
    html.Div([
        _sidebar(),

        html.Div([
            # Digest hero
            html.Div(id='digest', className='digest-card'),

            # Tab nav
            dcc.Tabs(id='tabs', value='tab-week', className='main-tabs', children=[
                dcc.Tab(label='⚡ This Week',  value='tab-week',    className='tab', selected_className='tab--selected'),
                dcc.Tab(label='📈 Season',     value='tab-season',  className='tab', selected_className='tab--selected'),
                dcc.Tab(label='🏅 Players',    value='tab-players', className='tab', selected_className='tab--selected'),
                dcc.Tab(label='🏆 All-Time',   value='tab-alltime', className='tab', selected_className='tab--selected'),
                dcc.Tab(label='⚔ Head-to-Head',value='tab-h2h',     className='tab', selected_className='tab--selected'),
            ]),

            # Tab content with loading indicator
            dcc.Loading(
                html.Div(id='tab-content', className='tab-content-area'),
                type='circle', color='#FFC300', className='loading-wrapper',
            ),
        ], className='main-content'),
    ], className='body-row'),
], className='app-shell')


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output('week-slider', 'max'),
    Output('week-slider', 'value'),
    Output('store-week', 'data'),
    Input('boot', 'n_intervals'),
    State('year-dd', 'value'),
)
def _boot(_, year):
    w = _weeks(year or CURRENT_YEAR)
    mw = max(w.keys()) if w else 1
    return mw, mw, mw


@app.callback(
    Output('week-slider', 'max',         allow_duplicate=True),
    Output('week-slider', 'value',       allow_duplicate=True),
    Output('team-list', 'options'),
    Output('team-list', 'value'),
    Input('year-dd', 'value'),
    prevent_initial_call=True,
)
def _year_changed(year):
    if year not in _data:
        threading.Thread(target=_load_bg, args=(year,), daemon=True).start()
        _ensure(year)
    w = _weeks(year)
    mw = max(w.keys()) if w else 1
    teams = sorted(core.roster_ids.get(year, {}).values())
    opts = [{'label': t, 'value': t} for t in teams]
    return mw, mw, opts, teams


@app.callback(
    Output('team-list', 'value', allow_duplicate=True),
    Input('btn-all',  'n_clicks'),
    Input('btn-none', 'n_clicks'),
    State('year-dd',  'value'),
    prevent_initial_call=True,
)
def _toggle_teams(_, __, year):
    teams = sorted(core.roster_ids.get(year, {}).values())
    return teams if callback_context.triggered_id == 'btn-all' else []


@app.callback(
    Output('store-year',  'data'),
    Output('store-week',  'data', allow_duplicate=True),
    Output('store-theme', 'data'),
    Input('year-dd',     'value'),
    Input('week-slider', 'value'),
    Input('theme-dd',    'value'),
    prevent_initial_call=True,
)
def _sync_stores(year, week, theme):
    return year, week, theme


@app.callback(
    Output('refresh-status', 'children'),
    Input('btn-refresh', 'n_clicks'),
    State('year-dd', 'value'),
    prevent_initial_call=True,
)
def _refresh(_, year):
    if year in _data:
        del _data[year]
    _failed_years.discard(year)
    dl.invalidate_week(year, 0)
    threading.Thread(target=_load_bg, args=(year,), daemon=True).start()
    return 'Refreshing…'


@app.callback(
    Output('digest', 'children'),
    Input('store-year', 'data'),
    Input('store-week', 'data'),
)
def _update_digest(year, week):
    return _digest(year or CURRENT_YEAR, week or 1)


@app.callback(
    Output('tab-content', 'children'),
    Input('tabs',       'value'),
    Input('store-year', 'data'),
    Input('store-week', 'data'),
    Input('store-theme','data'),
    Input('team-list',  'value'),
)
def _render_tab(tab, year, week, theme, teams):
    year  = year  or CURRENT_YEAR
    week  = week  or 1
    theme = theme or 'coastal'
    _apply_theme(theme)

    if tab == 'tab-week':    return _tab_week(year, week, teams)
    if tab == 'tab-season':  return _tab_season(year, week, teams)
    if tab == 'tab-players': return _tab_players(year, week, teams)
    if tab == 'tab-alltime': return _tab_alltime(teams)
    if tab == 'tab-h2h':     return _tab_h2h_shell()
    return html.Div('Unknown tab')


# ── URL deep-link: parse ?tab=&year=&week= on initial load ───────────────────

@app.callback(
    Output('tabs',      'value'),
    Output('year-dd',   'value'),
    Input('url', 'search'),
    prevent_initial_call=True,
)
def _parse_url(search):
    if not search:
        return no_update, no_update
    from urllib.parse import parse_qs
    params = parse_qs(search.lstrip('?'))
    tab  = params.get('tab',  [no_update])[0]
    year = params.get('year', [no_update])[0]
    if year is not no_update:
        try:
            year = int(year)
        except ValueError:
            year = no_update
    tab_map = {'week': 'tab-week', 'season': 'tab-season',
               'players': 'tab-players', 'alltime': 'tab-alltime', 'h2h': 'tab-h2h'}
    if tab is not no_update:
        tab = tab_map.get(tab, no_update)
    return tab, year


# ── Tab: This Week ────────────────────────────────────────────────────────────

def _tab_week(year, week, teams):
    season   = _season(year)
    week_obj = _week(year, week)
    if season is None or week_obj is None:
        return _loading_placeholder()

    sf    = _filter_season(season, teams)
    cards = []

    try:
        fig = week_obj.WeeklyGraph()
        _strip(fig, 560).update_layout(margin=dict(t=20, b=50, l=160, r=40))
        cards.append(_card(fig, f'Week {week} · Matchups'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Week Matchups'))

    try:
        fig = week_obj.PointsOverTheWeekend()
        cards.append(_card(_strip(fig, 480), f'Week {week} · Points Timeline'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Points Timeline'))

    try:
        fig = sf.StatusGraph(week_obj)
        _strip(fig, 620).update_layout(showlegend=True)
        cards.append(_card(fig, 'Power Rankings'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Power Rankings'))

    try:
        fig = sf.LuckChart(week)
        cards.append(_card(_strip(fig, 520), 'Luck Chart'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Luck Chart'))

    return html.Div(cards, className='charts-row')


# ── Tab: Season ───────────────────────────────────────────────────────────────

def _tab_season(year, week, teams):
    season = _season(year)
    if season is None:
        return _loading_placeholder()

    sf    = _filter_season(season, teams)
    cards = []

    try:
        fig = sf.SnakeGraph(week)
        _strip(fig, 500).update_layout(showlegend=True)
        cards.append(_card(fig, 'Win Progression'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Win Progression'))

    try:
        fig = sf.SeasonPointsForAgainst()
        cards.append(_card(_strip(fig, 500), 'Points For & Against'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Points For & Against'))

    try:
        fig = sf.WeeklyWinsGraphBreakout(week)
        cards.append(_card(_strip(fig, 720), 'Weekly Wins · Breakout'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Weekly Wins · Breakout'))

    try:
        fig = sf.ScoreFrequencyGraph(week)
        cards.append(_card(_strip(fig, 460), 'Scoring Frequency', half=True))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Scoring Frequency', half=True))

    try:
        fig = sf.BrawnyBench()
        _strip(fig, 460).update_layout(margin=dict(t=20, b=50, l=160, r=40))
        cards.append(_card(fig, 'Brawny Benches', half=True))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Brawny Benches', half=True))

    try:
        fig = sf.PositionStengthPolar()
        cards.append(_card(_strip(fig, 580), 'Position Strength'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Position Strength'))

    return html.Div(cards, className='charts-row')


# ── Tab: Players ──────────────────────────────────────────────────────────────

def _tab_players(year, week, teams):
    season = _season(year)
    if season is None:
        return _loading_placeholder()

    sf    = _filter_season(season, teams)
    cards = []

    try:
        fig = sf.PlayerPoints(week)
        cards.append(_card(_strip(fig, 580), 'Player Points'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Player Points'))

    try:
        fig = sf.ViolinPlayer(week, Starters=True)
        cards.append(_card(_strip(fig, 500), 'Starter Scoring Distribution', half=True))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Starter Distribution', half=True))

    try:
        fig = sf.ViolinPlayer(week, Starters=False)
        cards.append(_card(_strip(fig, 500), 'Bench Scoring Distribution', half=True))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Bench Distribution', half=True))

    try:
        fig = sf.ScoreTrends()
        cards.append(_card(_strip(fig, 460), 'Weekly Score Trends'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Score Trends'))

    try:
        fig = sf.TopPlayers()
        cards.append(_card(_strip(fig, 580), 'Top Players'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Top Players'))

    return html.Div(cards, className='charts-row')


# ── Tab: All-Time ─────────────────────────────────────────────────────────────

def _tab_alltime(teams):
    missing = [y for y in ALL_YEARS if y not in _data]
    if missing:
        for y in missing:
            threading.Thread(target=_load_bg, args=(y,), daemon=True).start()
        return html.Div([
            html.Div(className='loading-spinner'),
            f'Loading {len(missing)} historical season(s)… switch back in a moment.',
        ], className='loading-msg')

    try:
        at = core.AllTime()
    except Exception as e:
        return html.Div(f'Could not build All-Time data: {e}', className='error-msg-card')

    cards = []

    for fn, title, half in [
        ('HallofFame_Team',     'Hall of Fame · Best Team Scores',    False),
        ('HallofFame_Player',   'Hall of Fame · Best Player Scores',  False),
        ('HallofShame_Team',    'Hall of Shame · Worst Scores',       True),
        ('HighestScoringLosers','Highest-Scoring Losses',             True),
        ('SmallestMargins',     'Smallest Margins of Victory',        True),
        ('ForAgainstwithTeams', 'All-Time Points For & Against',      True),
    ]:
        try:
            fig = getattr(at, fn)()
            cards.append(_card(_strip(fig, 540), title, half=half))
        except Exception as e:
            cards.append(_card(_err(str(e)), title, half=half))

    return html.Div(cards, className='charts-row')


# ── Tab: Head-to-Head (shell + inner callback) ────────────────────────────────

def _tab_h2h_shell():
    all_teams = sorted({t for y in ALL_YEARS for t in core.roster_ids.get(y, {}).values()})
    opts = [{'label': t, 'value': t} for t in all_teams]
    default_a = all_teams[0]  if len(all_teams) > 0 else None
    default_b = all_teams[1]  if len(all_teams) > 1 else None

    return html.Div([
        # Controls bar
        html.Div([
            dcc.Dropdown(id='h2h-team-a', options=opts, value=default_a,
                         clearable=False, className='dash-dropdown', placeholder='Team A'),
            html.Span('vs', className='h2h-vs'),
            dcc.Dropdown(id='h2h-team-b', options=opts, value=default_b,
                         clearable=False, className='dash-dropdown', placeholder='Team B'),
        ], className='h2h-controls'),

        # Stats row
        html.Div(id='h2h-stats'),

        # Charts
        dcc.Loading(
            html.Div(id='h2h-charts', className='charts-row'),
            type='circle', color='#FFC300',
        ),
    ])


@app.callback(
    Output('h2h-stats',  'children'),
    Output('h2h-charts', 'children'),
    Input('h2h-team-a',  'value'),
    Input('h2h-team-b',  'value'),
    prevent_initial_call=False,
)
def _h2h(team_a, team_b):
    if not team_a or not team_b or team_a == team_b:
        return html.Div('Select two different teams above.', className='loading-msg'), html.Div()

    # Scan all matchup data across all loaded years.
    # AllMatchesDict[year][week] is a single DataFrame — one row per team,
    # grouped by 'Matchup' value. Score column is 'Total'.
    h2h_games = []
    for year, _ydata in _data.items():
        for week, df in core.AllMatchesDict.get(year, {}).items():
            if df is None or df.empty or 'Team' not in df.columns or 'Total' not in df.columns:
                continue
            teams_in_week = set(df['Team'].tolist())
            if team_a not in teams_in_week or team_b not in teams_in_week:
                continue
            # Find the specific matchup where both teams played each other
            for _, grp in df.groupby('Matchup'):
                grp_teams = set(grp['Team'].tolist())
                if team_a in grp_teams and team_b in grp_teams:
                    score_a = float(grp.loc[grp['Team'] == team_a, 'Total'].iloc[0])
                    score_b = float(grp.loc[grp['Team'] == team_b, 'Total'].iloc[0])
                    h2h_games.append({
                        'year': year, 'week': week,
                        'score_a': score_a, 'score_b': score_b,
                        'winner': team_a if score_a > score_b else team_b,
                    })

    if not h2h_games:
        msg = f'No head-to-head matchups found between {team_a} and {team_b} in loaded seasons.'
        return html.Div(msg, className='loading-msg'), html.Div()

    df_h2h = pd.DataFrame(h2h_games)
    wins_a = (df_h2h['winner'] == team_a).sum()
    wins_b = (df_h2h['winner'] == team_b).sum()
    avg_a  = df_h2h['score_a'].mean()
    avg_b  = df_h2h['score_b'].mean()
    total  = len(df_h2h)

    # Stat cards
    stats = html.Div([
        html.Div([html.Div(f'{wins_a}–{wins_b}', className='h2h-stat-number'),
                  html.Div(f'{team_a} record vs {team_b}', className='h2h-stat-label')],
                 className='h2h-stat-card'),
        html.Div([html.Div(f'{avg_a:.1f}', className='h2h-stat-number'),
                  html.Div(f'Avg score · {team_a}', className='h2h-stat-label')],
                 className='h2h-stat-card'),
        html.Div([html.Div(f'{avg_b:.1f}', className='h2h-stat-number'),
                  html.Div(f'Avg score · {team_b}', className='h2h-stat-label')],
                 className='h2h-stat-card'),
        html.Div([html.Div(str(total), className='h2h-stat-number'),
                  html.Div('All-time matchups', className='h2h-stat-label')],
                 className='h2h-stat-card'),
    ], className='h2h-stats-row')

    # Chart 1: every matchup, both scores as grouped bars
    df_h2h['label'] = df_h2h.apply(lambda r: f"{r['year']} Wk{r['week']}", axis=1)
    fig_games = go.Figure()
    fig_games.add_bar(name=team_a, x=df_h2h['label'], y=df_h2h['score_a'],
                      marker_color='#FFC300')
    fig_games.add_bar(name=team_b, x=df_h2h['label'], y=df_h2h['score_b'],
                      marker_color='#54A2E5')
    fig_games.update_layout(
        template='gridiron_ink', barmode='group', showlegend=True, height=420,
        title=None, width=None, margin=dict(t=20, b=80, l=60, r=20),
        legend=dict(orientation='h', x=0.5, xanchor='center', y=1.05, yanchor='bottom'),
    )

    # Chart 2: score distribution comparison (box)
    fig_dist = go.Figure()
    fig_dist.add_box(name=team_a, y=df_h2h['score_a'], marker_color='#FFC300',
                     boxpoints='all', jitter=0.3, pointpos=-1.5)
    fig_dist.add_box(name=team_b, y=df_h2h['score_b'], marker_color='#54A2E5',
                     boxpoints='all', jitter=0.3, pointpos=-1.5)
    fig_dist.update_layout(
        template='gridiron_ink', showlegend=True, height=420,
        title=None, width=None, margin=dict(t=20, b=40, l=60, r=20),
    )

    charts = html.Div([
        _card(fig_games, f'{team_a} vs {team_b} · All Matchups'),
        _card(fig_dist,  f'{team_a} vs {team_b} · Score Distributions', half=False),
    ], className='charts-row')

    return stats, charts


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8050)
