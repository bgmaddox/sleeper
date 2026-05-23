#!/usr/bin/env python3
"""
Legacy League — Fantasy Football Web App
Run locally: python app.py  → http://localhost:8050
Deploy:      gunicorn app:server

SECTION MAP (for targeted edits — grep the # ── markers to jump directly)
  L28   NFL Stadium Coordinates   — static lat/lon lookup dict
  L66   Config                    — SECRET_KEY, AVAILABLE_YEARS, theme map
  L78   Plotly template           — _register_template()
  L89   Dash / Flask setup        — app, server
  L101  Auth                      — login route, token helpers, auth gate middleware
  L236  Data store                — _load_bg, _ensure, _season, _weeks, _week
  L283  Helpers                   — _strip, _empty, _card, _power_rankings_native, etc.
  L465  League Digest card        — _digest() builds the weekly summary card
  L569  Layout                    — full app HTML/component tree (html.Div structure)
  L675  Core callbacks            — boot, year/week/team controls, tab router, URL deep-link
  L971  Tab: This Week            — _tab_week()
  L1045 Tab: Season               — _tab_season()
  L1171 Tab: Players              — _tab_players()
  L1261 Tab: All-Time             — _tab_alltime()
  L1331 Tab: Head-to-Head         — _tab_h2h_shell(), _h2h() callback
  L1450 Tab: Playoffs             — _tab_playoffs() (winners + losers bracket cards)
  L1456 Toggle callbacks          — luck/timeline/pfa/freq/bench/bump/violin/top-players
  L1741 D3 store population       — _populate_d3_stores() (snake draft, schedule, matchups)
  L2003 D3: Bubble Map            — _populate_bubble_data()
  L2097 D3: Draft Board           — _populate_draft_data()
  L2196 D3: State Choropleth      — _populate_choropleth_data()
  L2254 D3: Chord Diagram         — _populate_chord_data()
  L2332 Run                       — if __name__ == '__main__'
"""

import sys
import os
import time
import threading
import traceback

# Core library lives at project root (one level up from webapp/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import plotly.io as pio
import plotly.graph_objects as go
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State, callback_context, no_update, ClientsideFunction, ALL
from flask import request, redirect, make_response, render_template_string
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

import sleeper_core as core
import data_loader as dl


# ── NFL Stadium Coordinates ───────────────────────────────────────────────────

NFL_STADIUM_COORDS = {
    'ARI': {'lat': 33.5277, 'lon': -112.2626},
    'ATL': {'lat': 33.7553, 'lon': -84.4006},
    'BAL': {'lat': 39.2780, 'lon': -76.6227},
    'BUF': {'lat': 42.7738, 'lon': -78.7870},
    'CAR': {'lat': 35.2258, 'lon': -80.8528},
    'CHI': {'lat': 41.8623, 'lon': -87.6167},
    'CIN': {'lat': 39.0954, 'lon': -84.5160},
    'CLE': {'lat': 41.5061, 'lon': -81.6995},
    'DAL': {'lat': 32.7473, 'lon': -97.0945},
    'DEN': {'lat': 39.7439, 'lon': -105.0201},
    'DET': {'lat': 42.3400, 'lon': -83.0456},
    'GB':  {'lat': 44.5013, 'lon': -88.0622},
    'HOU': {'lat': 29.6847, 'lon': -95.4107},
    'IND': {'lat': 39.7601, 'lon': -86.1639},
    'JAX': {'lat': 30.3240, 'lon': -81.6373},
    'KC':  {'lat': 39.0489, 'lon': -94.4839},
    'LA':  {'lat': 33.9535, 'lon': -118.3392},
    'LAC': {'lat': 33.9535, 'lon': -118.3392},
    'LV':  {'lat': 36.0909, 'lon': -115.1833},
    'MIA': {'lat': 25.9580, 'lon': -80.2389},
    'MIN': {'lat': 44.9740, 'lon': -93.2577},
    'NE':  {'lat': 42.0909, 'lon': -71.2643},
    'NO':  {'lat': 29.9511, 'lon': -90.0812},
    'NYG': {'lat': 40.8135, 'lon': -74.0745},
    'NYJ': {'lat': 40.8135, 'lon': -74.0745},
    'PHI': {'lat': 39.9008, 'lon': -75.1675},
    'PIT': {'lat': 40.4468, 'lon': -80.0158},
    'SEA': {'lat': 47.5952, 'lon': -122.3316},
    'SF':  {'lat': 37.4032, 'lon': -121.9698},
    'TB':  {'lat': 27.9759, 'lon': -82.5033},
    'TEN': {'lat': 36.1665, 'lon': -86.7713},
    'WAS': {'lat': 38.9079, 'lon': -76.8645},
}


# ── Config ────────────────────────────────────────────────────────────────────

CURRENT_YEAR  = 2025
ALL_YEARS     = core.AVAILABLE_YEARS
REGULAR_SEASON_WEEKS = 14  # weeks 15-18 are playoffs; capped until playoff feature is built

try:
    _nfl_state = dl.fetch_state_json()
except Exception:
    _nfl_state = {}


def _default_week(year: int, weeks_dict: dict) -> tuple:
    """Return (slider_max, default_week) for a given season year.

    Active regular season: use the API leg as default, full max as slider max.
    Completed / pre-season: cap both at REGULAR_SEASON_WEEKS (14).
    """
    if not weeks_dict:
        return 1, 1
    available_max = max(weeks_dict.keys())
    state_season = str(_nfl_state.get('season', ''))
    state_type   = _nfl_state.get('season_type', '')
    if str(year) == state_season and state_type == 'regular':
        leg = int(_nfl_state.get('leg', 1) or 1)
        return available_max, min(leg, available_max)
    default = min(REGULAR_SEASON_WEEKS, available_max)
    return available_max, default
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


@server.route('/debug-error', methods=['POST'])
def _debug_error():
    from flask import jsonify
    data = request.get_json(force=True, silent=True) or {}
    print(f'[JS-ERROR] {data}', flush=True)
    return jsonify({'ok': True})


@server.before_request
def _auth_gate():
    bypass = (LOGIN_URL, URL_BASE + 'assets', '/_dash-component-suites', '/favicon.ico', '/manifest.json', '/_reload-hash', '/debug-error')
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

def _apply_theme(key: str = 'coastal'):
    _register_template(core.coastal_colorway)


def _chip_abbrev(name):
    """Two-letter uppercase abbreviation from a username (alpha chars only)."""
    clean = ''.join(c for c in name if c.isalpha())
    return (clean[:2] if len(clean) >= 2 else name[:2]).upper()


def _strip(fig, h=580):
    fig.update_layout(
        title=None, width=None, height=h,
        margin=dict(t=20, b=100, l=80, r=40),
        legend=dict(orientation='h', yanchor='top', y=-0.12, xanchor='center', x=0.5),
    )
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


def _card(fig, title='', half=False, subtitle=''):
    cls = 'chart-col-half' if half else 'chart-col-full'
    kids = []
    if title:
        kids.append(html.Div(title, className='chart-title'))
    if subtitle:
        kids.append(html.Div(subtitle, className='chart-subtitle'))
    kids.append(dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True},
                          style={'width': '100%'}))
    return html.Div(kids, className=f'chart-card {cls}')


def _power_rankings_native(sf, week_obj):
    """Native HTML power rankings table — replaces the buggy Plotly indicator chart."""
    sf.Calc(week_obj)
    status    = sf.StatusDict
    Scores    = status['Scores']
    Averages  = status['AverageScores']
    LeagueAvg = status['LeagueAverage']
    Ranks     = status['PowerRanks']
    PrevRanks = status['PreviousRanks']
    PowerPcts = status['PowerPercents']
    Optimal   = status['OptimalScores']

    week = week_obj.week

    # Compute season-long stats from Matches
    ytd = sf.Matches[sf.Matches['Week'] <= week]
    rec = ytd.groupby('Team').agg(wins=('Won', 'sum'), played=('Won', 'count'))
    rec['losses'] = rec['played'] - rec['wins'].astype(int)
    pf_map     = dict(ytd.groupby('Team')['Total'].sum().round(1))
    _wk_df = sf.Matches[sf.Matches['Week'] == week]
    margin_map = (dict(_wk_df.set_index('Team')['Margin'].fillna(0).round(1))
                  if 'Margin' in _wk_df.columns else {})

    streak_map = {}
    for team, grp in ytd.sort_values('Week').groupby('Team'):
        recent = grp.tail(3)['Won'].tolist()
        streak_map[team] = ''.join('W' if w else 'L' for w in recent)

    teams = sorted(Scores.keys(), key=lambda t: Ranks[t])

    RANK_COLORS = {1: '#FFC300', 2: '#A8BCC8', 3: '#CD8C52'}

    thead = html.Thead(html.Tr([
        html.Th('#',          className='pr-th pr-th-center'),
        html.Th('',           className='pr-th'),
        html.Th('Team',       className='pr-th'),
        html.Th('Score',      className='pr-th pr-th-right'),
        html.Th('Margin',     className='pr-th pr-th-right pr-th-margin'),
        html.Th('Efficiency', className='pr-th pr-th-bar'),
        html.Th('Record',     className='pr-th pr-th-center'),
        html.Th('Streak',     className='pr-th pr-th-center pr-th-streak'),
        html.Th('Ssn PF',     className='pr-th pr-th-right pr-th-pf'),
        html.Th('vs Avg',     className='pr-th pr-th-right pr-th-vsavg'),
        html.Th('vs League',  className='pr-th pr-th-right pr-th-vsleague'),
        html.Th('Pwr Win%',   className='pr-th pr-th-right'),
    ]))

    def _delta_el(val):
        s = f'+{val:.1f}' if val >= 0 else f'{val:.1f}'
        c = '#90BE6D' if val >= 0 else '#F94144'
        return html.Span(s, style={'color': c})

    data_rows = []
    for team in teams:
        rank  = Ranks[team]
        prev  = PrevRanks.get(team, rank)
        score = Scores[team]
        avg   = Averages.get(team, score)
        opt   = Optimal.get(team, score)
        pct   = PowerPcts[team]
        color = sf.teamcolors.get(team, '#BDE2FF')
        rank_color = RANK_COLORS.get(rank, '#BDE2FF')

        wins   = int(rec.loc[team, 'wins'])   if team in rec.index else 0
        losses = int(rec.loc[team, 'losses']) if team in rec.index else 0
        ssn_pf = pf_map.get(team, 0)
        margin = margin_map.get(team, 0)
        streak = streak_map.get(team, '')

        delta = prev - rank
        if delta > 0:
            chg_el = html.Span(f'↑{delta}', style={'color': '#90BE6D'})
        elif delta < 0:
            chg_el = html.Span(f'↓{abs(delta)}', style={'color': '#F94144'})
        else:
            chg_el = html.Span('—', style={'color': '#3D5E78'})

        eff = min(score / opt, 1.0) if opt and opt > 0 else 0
        eff_pct = eff * 100
        bar_color = ('#90BE6D' if eff >= 0.90 else
                     '#E6DB74' if eff >= 0.70 else '#F94144')

        data_rows.append(html.Tr([
            html.Td(str(rank), className='pr-td pr-td-rank',
                    style={'color': rank_color,
                           'fontSize': '1.35rem' if rank <= 3 else '1.1rem'}),
            html.Td(chg_el,  className='pr-td pr-td-chg'),
            html.Td(team,    className='pr-td pr-td-team', style={'color': color}),
            html.Td(f'{score:.1f}', className='pr-td pr-td-score'),
            html.Td(_delta_el(margin), className='pr-td pr-td-right pr-td-margin'),
            html.Td(html.Div([
                html.Div(className='pr-bar-fill',
                         style={'width': f'{eff_pct:.0f}%', 'background': bar_color}),
                html.Span(f'{eff_pct:.0f}%', className='pr-bar-label'),
            ], className='pr-bar-wrap'), className='pr-td pr-td-bar'),
            html.Td(f'{wins}-{losses}', className='pr-td pr-td-center'),
            html.Td([
                html.Span(ch, style={'color': '#90BE6D' if ch == 'W' else '#F94144'})
                for ch in streak
            ], className='pr-td pr-td-center pr-td-streak', style={'letterSpacing': '2px'}),
            html.Td(f'{ssn_pf:.1f}',          className='pr-td pr-td-right pr-td-pf'),
            html.Td(_delta_el(score - avg),    className='pr-td pr-td-right pr-td-vsavg'),
            html.Td(_delta_el(score - LeagueAvg), className='pr-td pr-td-right pr-td-vsleague'),
            html.Td(f'{pct:.0%}', className='pr-td pr-td-right pr-td-muted'),
        ], className='pr-data-row'))

    return html.Div([
        html.Div('Power Rankings', className='chart-title'),
        html.Div('Composite rank built from record, points for, and strength of schedule through this week', className='chart-subtitle'),
        html.Table([thead, html.Tbody(data_rows)], className='pr-table'),
    ], className='chart-card chart-col-full')


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
    # teamcolors is slot-based from SetTeamColors() — preserve it, don't reassign
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

        # Bottom scorer this week
        bot_idx   = df['Total'].idxmin()
        bot_team  = df.loc[bot_idx, 'Team']
        bot_score = df.loc[bot_idx, 'Total']

        # League average score this week
        avg_score = df['Total'].mean()

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

        # Most unlucky: highest scorer among losers
        unlucky = None
        if 'Won' in df.columns:
            losers = df[df['Won'] == False]
            if not losers.empty:
                ul_idx   = losers['Total'].idxmax()
                ul_team  = losers.loc[ul_idx, 'Team']
                ul_score = losers.loc[ul_idx, 'Total']
                unlucky  = {'team': ul_team, 'score': ul_score}

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

        if unlucky:
            stats.append(html.Div([
                html.Div('Most Unlucky', className='digest-label'),
                html.Div(f'{unlucky["team"]}  ·  {unlucky["score"]:.2f}', className='digest-value'),
                html.Div('Highest score among losers', className='digest-sub'),
            ], className='digest-stat'))

        stats.append(html.Div([
            html.Div('Lowest Score', className='digest-label'),
            html.Div(f'{bot_team}  ·  {bot_score:.2f}', className='digest-value'),
        ], className='digest-stat'))

        stats.append(html.Div([
            html.Div('League Avg', className='digest-label'),
            html.Div(f'{avg_score:.2f}', className='digest-value'),
        ], className='digest-stat'))

        return html.Div(stats, className='digest-card')
    except Exception:
        return html.Div()


# ── Layout ────────────────────────────────────────────────────────────────────

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='store-year', data=CURRENT_YEAR),
    dcc.Store(id='store-week', data=1),
    dcc.Store(id='store-snake-data'),
    dcc.Store(id='store-race-data'),
    dcc.Store(id='store-heatmap-data'),
    dcc.Store(id='store-bubble-data'),
    dcc.Store(id='store-draft-data'),
    dcc.Store(id='store-chord-data'),
    dcc.Store(id='store-choropleth-data'),
    dcc.Store(id='store-arc-mode', data='top'),
    dcc.Store(id='store-snake-mode', data='wins'),
    dcc.Store(id='store-max-week', data=1),
    dcc.Store(id='store-d3-trigger', data=0),
    dcc.Interval(id='boot', interval=1500, n_intervals=0, max_intervals=60),

    # Top bar
    html.Div([
        html.Img(src=LOGO_URL, className='topbar-logo'),
        html.Span('Legacy League', className='topbar-title'),
        html.Span('Fantasy Football · Since 2019', className='topbar-tagline'),
    ], className='topbar'),

    # Controls bar — floating glass pill
    html.Div([
        # ── Season (custom year picker popover) ─────────────────────────
        html.Div([
            html.Span('Season', className='ctrl-label'),
            html.Div([
                html.Div(id='year-display', className='ctrl-year-display', n_clicks=0),
                html.Div(id='year-picker', className='year-picker', style={'display': 'none'},
                    children=[
                        html.Button(str(y), id={'type': 'year-btn', 'index': y},
                                    className='year-pick-btn', n_clicks=0)
                        for y in sorted(ALL_YEARS, reverse=True)
                    ]
                ),
            ], className='ctrl-year-wrap'),
            # Hidden dropdown drives all existing callbacks
            dcc.Dropdown(
                id='year-dd',
                options=[{'label': str(y), 'value': y} for y in sorted(ALL_YEARS, reverse=True)],
                value=CURRENT_YEAR, clearable=False,
                style={'display': 'none'},
            ),
        ], className='ctrl-group ctrl-group--season'),

        html.Div(className='ctrl-divider'),

        # ── Week scrubber (numbered row, replaces slider) ─────────────────
        html.Div([
            html.Span('Week', className='ctrl-label'),
            html.Div(id='week-scrubber', className='week-scrubber-row'),
            dcc.Slider(id='week-slider', min=1, max=18, step=1, value=1,
                       marks={}, tooltip={'always_visible': False},
                       className='hidden-slider'),
        ], className='ctrl-group ctrl-group--week'),

        html.Div(className='ctrl-divider'),

        # ── Teams ─────────────────────────────────────────────────────────
        html.Div([
            html.Span('TEAMS', className='ctrl-label ctrl-label--inline'),
            html.Div(id='team-chips-container', className='team-chips-row'),
            html.Div([
                html.Button('All',  id='btn-all',  className='btn btn--xs'),
                html.Button('None', id='btn-none', className='btn btn--xs'),
            ], className='ctrl-team-btns'),
            dcc.Dropdown(id='team-list', options=[], value=[], multi=True,
                         style={'display': 'none'}),
        ], className='ctrl-group ctrl-group--teams'),

        html.Div(className='ctrl-divider'),

        # ── Refresh ───────────────────────────────────────────────────────
        html.Div([
            html.Button('↺', id='btn-refresh', className='btn-refresh-hud'),
            html.Div([
                html.Span('SYNC', className='hud-sync-label'),
                html.Div(id='refresh-status', className='hud-sync-status'),
            ], className='hud-sync-info'),
        ], className='ctrl-group ctrl-group--refresh'),
    ], className='controls-bar'),

    # Main content (full-width, no sidebar)
    html.Div([
        html.Div(id='digest', className='digest-card'),

        dcc.Tabs(id='tabs', value='tab-week', className='main-tabs', children=[
            dcc.Tab(label='This Week',   value='tab-week',    className='tab tab--week',    selected_className='tab--selected'),
            dcc.Tab(label='Season',      value='tab-season',  className='tab tab--season',  selected_className='tab--selected'),
            dcc.Tab(label='Players',     value='tab-players', className='tab tab--players', selected_className='tab--selected'),
            dcc.Tab(label='All-Time',    value='tab-alltime', className='tab tab--alltime', selected_className='tab--selected'),
            dcc.Tab(label='Head-to-Head', value='tab-h2h',      className='tab tab--h2h',      selected_className='tab--selected'),
            dcc.Tab(label='Playoffs',     value='tab-playoffs', className='tab tab--playoffs', selected_className='tab--selected'),
        ]),

        dcc.Loading(
            html.Div(id='tab-content', className='tab-content-area'),
            type='circle', color='#FFC300', className='loading-wrapper',
        ),
    ], className='main-content'),
], className='app-shell')


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output('week-slider', 'max'),
    Output('week-slider', 'value'),
    Output('store-week', 'data'),
    Output('store-max-week', 'data'),
    Output('boot', 'disabled'),
    Output('team-list', 'value', allow_duplicate=True),
    Input('boot', 'n_intervals'),
    State('year-dd', 'value'),
    prevent_initial_call='initial_duplicate',
)
def _boot(_, year):
    w = _weeks(year or CURRENT_YEAR)
    if not w:
        return no_update, no_update, no_update, no_update, False, no_update  # keep polling
    slider_max, default_week = _default_week(year or CURRENT_YEAR, w)
    return slider_max, default_week, default_week, slider_max, True, []  # data ready — disable interval


@app.callback(
    Output('week-slider', 'max',         allow_duplicate=True),
    Output('week-slider', 'value',       allow_duplicate=True),
    Output('store-max-week', 'data',     allow_duplicate=True),
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
    slider_max, default_week = _default_week(year, w) if w else (1, 1)
    teams = sorted(core.roster_ids.get(year, {}).values())
    opts = [{'label': t, 'value': t} for t in teams]
    return slider_max, default_week, slider_max, opts, []


@app.callback(
    Output('year-display', 'children'),
    Input('year-dd', 'value'),
)
def _render_year_display(year):
    year = year or CURRENT_YEAR
    return str(year)


@app.callback(
    Output('year-picker', 'style'),
    Input('year-display', 'n_clicks'),
    Input({'type': 'year-btn', 'index': ALL}, 'n_clicks'),
    State('year-picker', 'style'),
    prevent_initial_call=True,
)
def _toggle_year_picker(display_clicks, year_btn_clicks, current_style):
    trigger = callback_context.triggered_id
    # Close picker when a year is selected
    if isinstance(trigger, dict) and trigger.get('type') == 'year-btn':
        return {'display': 'none'}
    # Toggle on display click
    is_hidden = (current_style or {}).get('display') == 'none'
    return {'display': 'block'} if is_hidden else {'display': 'none'}


@app.callback(
    Output('year-dd', 'value'),
    Input({'type': 'year-btn', 'index': ALL}, 'n_clicks'),
    State({'type': 'year-btn', 'index': ALL}, 'id'),
    prevent_initial_call=True,
)
def _year_btn_click(n_clicks_list, id_list):
    import json as _json
    if not callback_context.triggered:
        return no_update
    trigger_prop = callback_context.triggered[0]['prop_id']
    id_part = trigger_prop.split('.')[0]
    try:
        clicked_id = _json.loads(id_part)
    except Exception:
        return no_update
    year = clicked_id.get('index')
    return year if year else no_update


@app.callback(
    Output('week-scrubber', 'children'),
    Input('store-max-week', 'data'),
    Input('store-week', 'data'),
)
def _render_week_scrubber(max_week, current_week):
    max_week = max_week or 18
    current_week = current_week or 1
    return [
        html.Button(
            str(w),
            id={'type': 'week-btn', 'index': w},
            className='week-btn' + (' week-btn--active' if w == current_week else ''),
            n_clicks=0,
        )
        for w in range(1, max_week + 1)
    ]


@app.callback(
    Output('store-week', 'data', allow_duplicate=True),
    Output('week-slider', 'value', allow_duplicate=True),
    Input({'type': 'week-btn', 'index': ALL}, 'n_clicks'),
    State({'type': 'week-btn', 'index': ALL}, 'id'),
    prevent_initial_call=True,
)
def _week_btn_click(n_clicks_list, id_list):
    import json as _json
    if not callback_context.triggered:
        return no_update, no_update
    triggered = callback_context.triggered[0]
    # Ignore fires caused by dynamically adding new buttons (n_clicks=0 = not a real click)
    if not triggered.get('value'):
        return no_update, no_update
    trigger_prop = triggered['prop_id']
    id_part = trigger_prop.split('.')[0]
    try:
        clicked_id = _json.loads(id_part)
    except Exception:
        return no_update, no_update
    week = clicked_id.get('index')
    if week is None:
        return no_update, no_update
    return week, week


@app.callback(
    Output('team-list', 'value', allow_duplicate=True),
    Input('btn-all',  'n_clicks'),
    Input('btn-none', 'n_clicks'),
    State('year-dd',  'value'),
    prevent_initial_call=True,
)
def _toggle_teams(_, __, year):
    if callback_context.triggered_id == 'btn-all':
        return []
    teams = sorted(core.roster_ids.get(year, {}).values())
    return teams


@app.callback(
    Output('team-chips-container', 'children'),
    Input('year-dd',    'value'),
    Input('team-list',  'value'),
)
def _render_team_chips(year, selected_teams):
    year = year or CURRENT_YEAR
    slot_colors = core.get_slot_teamcolors(year)
    selected_set = set(selected_teams or [])
    all_active = not selected_set

    chips = []
    for slot, team in sorted(core.roster_ids.get(year, {}).items()):
        color = slot_colors.get(team, '#BDE2FF')
        is_active = all_active or team in selected_set
        abbrev = _chip_abbrev(team)
        chips.append(html.Button(
            abbrev,
            id={'type': 'team-chip', 'index': team},
            className='team-chip' + (' team-chip--active' if is_active else ' team-chip--muted'),
            title=team,
            style={'--chip-color': color},
            n_clicks=0,
        ))
    return chips


@app.callback(
    Output('team-list', 'value', allow_duplicate=True),
    Input({'type': 'team-chip', 'index': ALL}, 'n_clicks'),
    State({'type': 'team-chip', 'index': ALL}, 'id'),
    State('team-list',  'value'),
    State('year-dd',    'value'),
    prevent_initial_call=True,
)
def _toggle_team_chip(n_clicks_list, id_list, current_teams, year):
    import json as _json
    if not callback_context.triggered:
        return no_update
    triggered = callback_context.triggered[0]
    # n_clicks=0 means a new component was just rendered — not a real user click
    if not triggered.get('value'):
        return no_update
    trigger_prop = triggered['prop_id']
    id_part = trigger_prop.split('.')[0]
    try:
        clicked_id = _json.loads(id_part)
    except Exception:
        return no_update
    team = clicked_id.get('index')
    if not team:
        return no_update

    year = year or CURRENT_YEAR
    all_teams = list(core.roster_ids.get(year, {}).values())
    current = list(current_teams or [])

    if not current:
        # All visible — deselect the clicked one (show everyone else)
        current = [t for t in all_teams if t != team]
    elif team in current:
        current.remove(team)
        if not current:
            current = []  # empty → show all
    else:
        current.append(team)
        if set(current) == set(all_teams):
            current = []  # full selection → collapse to "all"

    return current


@app.callback(
    Output('store-year', 'data'),
    Output('store-week', 'data', allow_duplicate=True),
    Input('year-dd',     'value'),
    Input('week-slider', 'value'),
    prevent_initial_call=True,
)
def _sync_stores(year, week):
    return year, week


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
    return 'loading…'


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
    Input('team-list',  'value'),
)
def _render_tab(tab, year, week, teams):
    year = year or CURRENT_YEAR
    week = week or 1

    if tab == 'tab-week':    return _tab_week(year, week, teams)
    if tab == 'tab-season':  return _tab_season(year, week, teams)
    if tab == 'tab-players': return _tab_players(year, week, teams)
    if tab == 'tab-alltime': return _tab_alltime(teams, year)
    if tab == 'tab-h2h':       return _tab_h2h_shell()
    if tab == 'tab-playoffs':  return _tab_playoffs(year)
    return html.Div('Unknown tab')


# ── URL deep-link: parse ?tab=&year=&week= on initial load ───────────────────

@app.callback(
    Output('tabs',      'value'),
    Output('year-dd',   'value', allow_duplicate=True),
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
               'players': 'tab-players', 'alltime': 'tab-alltime',
               'h2h': 'tab-h2h', 'playoffs': 'tab-playoffs'}
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
        cards.append(_power_rankings_native(sf, week_obj))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Power Rankings'))

    try:
        fig = week_obj.WeeklyGraph()
        _strip(fig, 720).update_layout(margin=dict(t=20, b=120, l=160, r=40),
                                        legend=dict(orientation='h', yanchor='top', y=-0.15, xanchor='center', x=0.5))
        cards.append(_card(fig, f'Week {week} · Matchups', subtitle='Head-to-head scores and win/loss result for each matchup'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Week Matchups'))

    try:
        fig = week_obj.PointsOverTheWeekend()
        _strip(fig, 950).update_layout(margin=dict(t=80, b=100, l=80, r=40))
        initial_timeline = dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        initial_timeline = _err(str(e))
    cards.append(html.Div([
        html.Div(f'Week {week} · Points Timeline', className='chart-title'),
        html.Div('How scores accumulated by day through the matchup window', className='chart-subtitle'),
        dcc.RadioItems(id='timeline-animate-toggle', options=[
            {'label': 'Static', 'value': 'static'},
            {'label': 'Animated', 'value': 'animated'},
        ], value='static', className='toggle-group', inline=True),
        html.Div(initial_timeline, id='timeline-chart'),
    ], className='chart-card chart-col-full'))

    try:
        fig = sf.LuckChart(week)
        initial_luck = dcc.Graph(figure=_strip(fig, 660), config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        initial_luck = _err(str(e))
    cards.append(html.Div([
        html.Div('Luck Chart', className='chart-title'),
        html.Div('Expected wins based on scoring — separates lucky records from genuinely dominant ones', className='chart-subtitle'),
        dcc.RadioItems(id='luck-toggle', options=[
            {'label': 'YTD Cumulative', 'value': 'ytd'},
            {'label': 'This Week Only', 'value': 'weekly'},
        ], value='ytd', className='toggle-group', inline=True),
        html.Div(initial_luck, id='luck-chart'),
    ], className='chart-card chart-col-full'))

    try:
        fig = sf.LineupEfficiencyChart(week)
        _strip(fig, 680).update_layout(
            margin=dict(t=80, b=180, l=140, r=40),
            legend=dict(orientation='h', x=0.5, xanchor='center', y=1.0, yanchor='bottom'),
        )
        cards.append(_card(fig, f'Week {week} · Lineup Efficiency', subtitle='Actual score vs best possible lineup — measures how well each team set their roster'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Lineup Efficiency'))

    cards.append(html.Div([
        html.Div('NFL Contribution Map · This Week', className='chart-title'),
        html.Div('Where your fantasy points came from this week — bubble size = points contributed', className='chart-subtitle'),
        html.Button('▶  Load Chart', id='load-bubble', n_clicks=0, className='btn', style={'margin': '12px 0'}),
        html.Div(id='d3-bubble-container', style={'width': '100%', 'height': '860px'}),
    ], className='chart-card chart-col-full'))

    return html.Div(cards, className='charts-row')


# ── Tab: Season ───────────────────────────────────────────────────────────────

def _tab_season(year, week, teams):
    season = _season(year)
    if season is None:
        return _loading_placeholder()

    sf    = _filter_season(season, teams)
    cards = []

    cards.append(html.Div([
        html.Div('Win Progression', className='chart-title'),
        html.Div('How each team\'s win total (or points) has stacked up week by week through the selected week', className='chart-subtitle'),
        dcc.RadioItems(id='snake-mode-toggle', options=[
            {'label': 'Cumulative Wins', 'value': 'wins'},
            {'label': 'Cumulative Points', 'value': 'points'},
        ], value='wins', className='toggle-group', inline=True),
        html.Div(id='d3-snake-container', style={'width': '100%', 'height': '560px'}),
    ], className='chart-card chart-col-full'))

    try:
        fig = sf.SeasonPointsForAgainst()
        _strip(fig, 680).update_layout(margin=dict(l=250, t=60, b=80))
        initial_pfa = dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        initial_pfa = _err(str(e))
    cards.append(html.Div([
        html.Div('Points For & Against', className='chart-title'),
        html.Div('Total points scored vs allowed — identifies dominant teams from lucky ones', className='chart-subtitle'),
        dcc.RadioItems(id='pfa-toggle', options=[
            {'label': 'Season Total', 'value': 'total'},
            {'label': '+ League Avg Line', 'value': 'avg'},
        ], value='total', className='toggle-group', inline=True),
        html.Div(initial_pfa, id='pfa-chart'),
    ], className='chart-card chart-col-full'))

    try:
        fig = sf.WeeklyWinsGraphBreakout(week)
        stripped = _strip(fig, 900)
        stripped.update_layout(margin=dict(t=80))
        cards.append(_card(stripped, 'Weekly Wins · Breakout', subtitle='Each team\'s cumulative win total by week, faceted for side-by-side comparison'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Weekly Wins · Breakout'))

    try:
        fig = sf.ScoreFrequencyGraph(week)
        fig.update_layout(title=None, width=None, height=680)
        initial_freq = dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        traceback.print_exc()
        initial_freq = _err(str(e))
    cards.append(html.Div([
        html.Div('Scoring Frequency', className='chart-title'),
        html.Div('Distribution of game scores — reveals scoring tiers and outliers', className='chart-subtitle'),
        dcc.RadioItems(id='freq-toggle', options=[
            {'label': 'All Games', 'value': 'all'},
            {'label': 'Wins Only', 'value': 'wins'},
            {'label': 'Losses Only', 'value': 'losses'},
        ], value='all', className='toggle-group', inline=True),
        html.Div(initial_freq, id='freq-chart'),
    ], className='chart-card chart-col-full'))

    try:
        fig = sf.BrawnyBench()
        fig.update_layout(title=None, width=None, height=580)
        initial_bench = dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        initial_bench = _err(str(e))
    cards.append(html.Div([
        html.Div('Brawny Benches', className='chart-title'),
        html.Div('Points left on the bench — wasted potential from sub-optimal lineup decisions', className='chart-subtitle'),
        dcc.RadioItems(id='bench-toggle', options=[
            {'label': 'Season Total', 'value': 'season'},
            {'label': 'By Week', 'value': 'weekly'},
        ], value='season', className='toggle-group', inline=True),
        html.Div(initial_bench, id='bench-chart'),
    ], className='chart-card chart-col-full'))

    try:
        fig = sf.PositionStrengthHeatmap()
        n = len(fig.data[0].y) if fig.data else 12
        h = max(500, n * 52 + 100)
        fig.update_layout(title=None, width=None, height=h,
                          margin=dict(t=20, b=80, l=200, r=20),
                          legend=dict(orientation='h', yanchor='top', y=-0.1, xanchor='center', x=0.5))
        cards.append(_card(fig, 'Position Strength', subtitle='Average points per position vs league average — green = above, red = below (σ = standard deviations from mean)'))
    except Exception as e:
        traceback.print_exc()
        cards.append(_card(_err(str(e)), 'Position Strength'))

    try:
        fig = sf.StarterPerformanceGraph()
        fig.update_layout(title=None, width=None, height=1200, margin=dict(t=20, b=80, l=160, r=40))
        cards.append(_card(fig, 'Starter Points by Position', subtitle='Total fantasy points scored by starters this season, broken down by position'))
    except Exception as e:
        traceback.print_exc()
        cards.append(_card(_err(str(e)), 'Starter Points by Position'))

    try:
        fig = sf.PositionStrengthPolar()
        fig.update_layout(title=None, width=None, height=1400)
        cards.append(_card(fig, 'Positional Strength · Radar', subtitle='Each team\'s scoring by position as z-scores vs league average — shows positional build strategy'))
    except Exception as e:
        traceback.print_exc()
        cards.append(_card(_err(str(e)), 'Positional Strength · Radar'))

    try:
        fig = sf.WaiverWireBump(mode='rank')
        initial_bump = dcc.Graph(figure=_strip(fig, 660), config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        traceback.print_exc()
        initial_bump = _err(str(e))
    cards.append(html.Div([
        html.Div('Top Scorers · Points Race', className='chart-title'),
        html.Div('Weekly rank (or points) progression of the top fantasy scorers this season', className='chart-subtitle'),
        dcc.RadioItems(id='bump-toggle', options=[
            {'label': 'Rank Progression', 'value': 'rank'},
            {'label': 'Cumulative Points', 'value': 'points'},
        ], value='rank', className='toggle-group', inline=True),
        html.Div(initial_bump, id='bump-chart'),
    ], className='chart-card chart-col-full'))

    cards.append(html.Div([
        html.Div('Season Score Race · Cumulative Points', className='chart-title'),
        html.Div('Animated race of total points accumulated — hover any week to see the full standings', className='chart-subtitle'),
        html.Button('▶  Load Chart', id='load-race', n_clicks=0, className='btn', style={'margin': '12px 0'}),
        html.Div(id='d3-race-container', style={'width': '100%', 'height': '580px'}),
    ], className='chart-card chart-col-full'))

    cards.append(html.Div([
        html.Div('Season Heatmap · Score vs Average', className='chart-title'),
        html.Div('Each team\'s score vs their season average each week — green above, red below', className='chart-subtitle'),
        html.Button('▶  Load Chart', id='load-heatmap', n_clicks=0, className='btn', style={'margin': '12px 0'}),
        html.Div(id='d3-heatmap-container', style={'width': '100%', 'height': '500px'}),
    ], className='chart-card chart-col-full'))

    cards.append(html.Div([
        html.Div(f'Draft Board Replay · {year}', className='chart-title'),
        html.Div('The full draft in pick order — hover any player to see their season stats', className='chart-subtitle'),
        html.Button('▶  Load Chart', id='load-draft', n_clicks=0, className='btn', style={'margin': '12px 0'}),
        html.Div(id='d3-draft-container', style={'width': '100%', 'height': '640px'}),
    ], className='chart-card chart-col-full'))

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
        _strip(fig, 660).update_layout(margin=dict(t=60))
        cards.append(_card(fig, 'Player Points', subtitle='Total fantasy points per player through the selected week, grouped by team'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'Player Points'))

    try:
        fig = sf.ViolinPlayer(week, Starters=True)
        fig.update_layout(title=None, width=None, height=1000)
        initial_violin = dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        traceback.print_exc()
        initial_violin = _err(str(e))
    cards.append(html.Div([
        html.Div('Scoring Distribution', className='chart-title'),
        html.Div('Score spread per player — the box shows the typical range, dots are weekly outings. Switch to By Position to compare positional depth across teams.', className='chart-subtitle'),
        dcc.RadioItems(id='violin-toggle', options=[
            {'label': 'Starters (By Team)',     'value': 'starters'},
            {'label': 'All Rostered (By Team)', 'value': 'all'},
            {'label': 'Starters (By Position)', 'value': 'pos_starters'},
            {'label': 'All (By Position)',       'value': 'pos_all'},
        ], value='starters', className='toggle-group', inline=True),
        html.Div(initial_violin, id='violin-chart'),
    ], className='chart-card chart-col-full'))

    try:
        fig = sf.ScoreTrends()
        graph = dcc.Graph(figure=_strip(fig, 600), config={'displayModeBar': False, 'responsive': False}, style={'width': '100%'})
        cards.append(html.Div([
            html.Div('Weekly Score Trends', className='chart-title'),
            html.Div('Each player\'s fantasy output week by week — spot hot streaks and fades', className='chart-subtitle'),
            graph,
        ], className='chart-card chart-col-full', style={'minHeight': '660px'}))
    except Exception as e:
        traceback.print_exc()
        cards.append(_card(_err(str(e)), 'Weekly Score Trends'))

    try:
        fig = sf.EPAScatter()
        cards.append(_card(_strip(fig, 600), 'EPA vs Fantasy Points', subtitle='Expected Points Added vs fantasy production — measures real-world efficiency'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'EPA vs Fantasy Points'))

    try:
        fig = sf.WOPRTreemap(week)
        cards.append(_card(_strip(fig, 600), 'WR/TE Opportunity · WOPR Treemap', subtitle='Weighted opportunity rate — share of team targets and air yards for pass catchers'))
    except Exception as e:
        cards.append(_card(_err(str(e)), 'WOPR Treemap'))

    try:
        fig = sf.TopPlayers('QB', 50)
        initial_top = dcc.Graph(figure=_strip(fig, 580), config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        initial_top = _err(str(e))
    cards.append(html.Div([
        html.Div('Top Players · Cumulative Points', className='chart-title'),
        html.Div('Highest-scoring rostered players by position — ranked by total fantasy points this season', className='chart-subtitle'),
        dcc.RadioItems(id='pos-toggle', options=[
            {'label': 'QB', 'value': 'QB'},
            {'label': 'RB', 'value': 'RB'},
            {'label': 'WR', 'value': 'WR'},
            {'label': 'TE', 'value': 'TE'},
        ], value='QB', className='toggle-group', inline=True),
        html.Div([
            html.Span('Min pts:', style={'color': '#BDE2FF', 'fontFamily': 'Courier New, monospace', 'fontSize': '13px', 'opacity': '0.7'}),
            dcc.Input(
                id='top-players-threshold',
                type='number',
                value=50,
                min=0,
                step=1,
                debounce=True,
                style={
                    'width': '72px',
                    'background': 'rgba(255,255,255,0.06)',
                    'border': '1px solid rgba(189,226,255,0.2)',
                    'borderRadius': '6px',
                    'color': '#BDE2FF',
                    'fontFamily': 'Courier New, monospace',
                    'fontSize': '14px',
                    'padding': '4px 8px',
                    'marginLeft': '8px',
                    'outline': 'none',
                }
            ),
        ], style={'display': 'flex', 'alignItems': 'center', 'margin': '6px 0 14px'}),
        html.Div(initial_top, id='top-players-chart'),
    ], className='chart-card chart-col-full'))

    return html.Div(cards, className='charts-row')


# ── Tab: All-Time ─────────────────────────────────────────────────────────────

def _tab_alltime(teams, year=None):
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

    _alltime_meta = [
        ('HallofFame_Team',     'Hall of Fame · Best Team Scores',    False, 'The highest single-week team scores across all seasons'),
        ('HallofFame_Player',   'Hall of Fame · Best Player Scores',  False, 'The highest individual player scores ever recorded in the league'),
        ('HallofShame_Team',    'Hall of Shame · Worst Scores',       False, 'The lowest team scores across all seasons'),
        ('HighestScoringLosers','Highest-Scoring Losses',             False, 'High scores that still resulted in a loss — the cruelest outcomes'),
        ('SmallestMargins',     'Smallest Margins of Victory',        False, 'Games decided by the narrowest possible margin'),
        ('ForAgainstwithTeams', 'All-Time Points For & Against',      False, 'Career points scored vs allowed — the all-time offensive and defensive record'),
    ]
    for fn, title, half, sub in _alltime_meta:
        try:
            fig = getattr(at, fn)()
            stripped = _strip(fig, 700)
            if fn in ('HallofFame_Team', 'HallofFame_Player', 'HallofShame_Team', 'HighestScoringLosers'):
                stripped.update_layout(margin=dict(l=280, t=60, b=80))
            cards.append(_card(stripped, title, half=half, subtitle=sub))
        except Exception as e:
            traceback.print_exc()
            cards.append(_card(_err(str(e)), title, half=half))

    cards.append(html.Div([
        html.Div('Fantasy Points by State · All-Time NFL Contribution', className='chart-title'),
        html.Div('US states colored by total all-time fantasy points sourced from their NFL teams', className='chart-subtitle'),
        html.Div(id='d3-choropleth-container', style={'width': '100%', 'height': '700px'}),
    ], className='chart-card chart-col-full'))

    cards.append(html.Div([
        html.Div('Owner Territory Map · Who Owns Each NFL City', className='chart-title'),
        html.Div('Which fantasy owner has the most all-time points from each NFL franchise — dashed border = contested', className='chart-subtitle'),
        html.Div(id='d3-territory-container', style={'width': '100%', 'height': '820px'}),
    ], className='chart-card chart-col-full'))

    cards.append(html.Div([
        html.Div('Arc Connections · NFL City → Fantasy Owner', className='chart-title'),
        html.Div('Fantasy points flowing west-to-east from NFL stadiums to their dominant fantasy owner', className='chart-subtitle'),
        dcc.RadioItems(id='arc-mode-toggle', options=[
            {'label': 'Top Connection per City', 'value': 'top'},
            {'label': 'Significant (≥ 100 pts)',  'value': 'significant'},
            {'label': 'All Connections',           'value': 'all'},
        ], value='top', className='toggle-group', inline=True),
        html.Div(id='d3-arc-container', style={'width': '100%', 'height': '680px'}),
    ], className='chart-card chart-col-full'))

    cards.append(html.Div([
        html.Div('NFL Franchise → Fantasy Owner · All-Time Points Flow', className='chart-title'),
        html.Div('Chord diagram showing the distribution of all-time points from each NFL team to each fantasy owner', className='chart-subtitle'),
        html.Div(id='d3-chord-container', style={'width': '100%', 'height': '700px'}),
    ], className='chart-card chart-col-full'))

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


# ── Tab: Playoffs ─────────────────────────────────────────────────────────────

def _tab_playoffs(year):
    if year not in _data:
        return html.Div('No data loaded for this year.', className='loading-msg')

    league  = _data[year]['league']
    season  = _data[year]['season']

    try:
        playoffs = core.Playoffs(league, season)
    except Exception as e:
        traceback.print_exc()
        return html.Div(f'Could not build playoff data: {e}', className='error-msg-card')

    ROUND_LABELS = {1: 'Wild Card', 2: 'Semifinals', 3: 'Championship Week'}
    _ico = lambda name: html.Span(className=f'playoff-icon playoff-icon--{name}')
    PLACE_LABELS = {
        1: [_ico('trophy'), ' Championship'],
        3: '3rd Place',
        5: '5th Place',
    }
    week_start   = playoffs.playoff_week_start

    def _matchup_card(m, stats=True):
        placement  = m.get('placement')
        t1_cls = 'playoff-team playoff-team--winner' if m['winner'] == m['team1'] else 'playoff-team playoff-team--loser'
        t2_cls = 'playoff-team playoff-team--winner' if m['winner'] == m['team2'] else 'playoff-team playoff-team--loser'

        eff1 = m.get('efficiency1')
        eff2 = m.get('efficiency2')
        s1, s2 = m['score1'], m['score2']
        total = s1 + s2 if s1 + s2 > 0 else 1

        kids = []
        if placement:
            kids.append(html.Div(PLACE_LABELS.get(placement, ''), className='playoff-placement-badge'))
        kids += [
            html.Div([
                html.Span(m['team1'], className='playoff-team-name'),
                html.Span(f"{s1:.2f}", className='playoff-team-score'),
                html.Span(f"{eff1:.0f}%" if eff1 is not None else '', className='playoff-team-eff'),
            ], className=t1_cls),
            html.Hr(className='playoff-divider'),
            html.Div([
                html.Span(m['team2'], className='playoff-team-name'),
                html.Span(f"{s2:.2f}", className='playoff-team-score'),
                html.Span(f"{eff2:.0f}%" if eff2 is not None else '', className='playoff-team-eff'),
            ], className=t2_cls),
            html.Div([
                html.Div(style={'flex': str(s1), 'background': 'var(--accent)' if m['winner'] == m['team1'] else 'rgba(189,226,255,0.2)'}),
                html.Div(style={'flex': str(s2), 'background': 'var(--accent)' if m['winner'] == m['team2'] else 'rgba(189,226,255,0.2)'}),
            ], className='playoff-score-bar'),
        ]
        if stats:
            kids.append(html.Div([
                html.Span([_ico('star'), m['best_player']]),
                html.Span(f"Bench left: {m['bench_left']:.1f} pts"),
            ], className='playoff-stats'))

        cls = 'playoff-matchup' + (' playoff-matchup--placement' if placement else '')
        return html.Div(kids, className=cls)

    def _bracket_col(bracket, title, stats, extra_cls=''):
        col_kids = [html.Div(title, className='playoff-column-header')]
        for rnd in sorted(bracket):
            week  = week_start + rnd - 1
            label = f"{ROUND_LABELS.get(rnd, f'Round {rnd}')} · Week {week}"
            games = html.Div(
                [_matchup_card(m, stats) for m in bracket[rnd]],
                className='playoff-round-games',
            )
            col_kids.append(html.Div([html.Div(label, className='playoff-round-label'), games], className='playoff-round'))
        return html.Div(col_kids, className=f'playoff-column {extra_cls}'.strip())

    winners_col = _bracket_col(playoffs.winners, 'Winners Bracket', stats=True)
    losers_col  = _bracket_col(playoffs.losers,  'Losers Bracket',  stats=False, extra_cls='playoff-column--losers')

    # Analytics charts
    analytics = []
    for fn, title, subtitle, h, margins in [
        ('ChampionRoad',    "Champion's Road",
         "Score vs opponent in each round on the path to the title", 320,
         dict(t=20, b=40, l=180, r=170)),
        ('PlayoffHeatCheck','Playoff Heat Check',
         "Did each team peak at the right time? Last 3 regular season weeks vs playoff average", 420,
         dict(t=40, b=80, l=60, r=40)),
        ('BenchPointsLeft', 'Bench Points Left',
         "How many points did each team leave on the bench per playoff game", 460,
         dict(t=20, b=40, l=200, r=100)),
    ]:
        try:
            fig = getattr(playoffs, fn)()
            _strip(fig, h=h).update_layout(margin=margins)
            analytics.append(_card(fig, title, subtitle=subtitle))
        except Exception as e:
            traceback.print_exc()
            analytics.append(_card(_err(str(e)), title))

    return html.Div([
        html.Div([winners_col, losers_col], className='playoff-wrapper'),
        *analytics,
    ], className='charts-row')


@app.callback(
    Output('h2h-stats',  'children'),
    Output('h2h-charts', 'children'),
    Input('h2h-team-a',  'value'),
    Input('h2h-team-b',  'value'),
    prevent_initial_call=True,
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
    _at_colors = core.get_alltime_teamcolors()
    color_a = _at_colors.get(team_a, '#FFC300')
    color_b = _at_colors.get(team_b, '#54A2E5')
    df_h2h['label'] = df_h2h.apply(lambda r: f"{r['year']} Wk{r['week']}", axis=1)
    fig_games = go.Figure()
    fig_games.add_bar(name=team_a, x=df_h2h['label'], y=df_h2h['score_a'],
                      marker_color=color_a)
    fig_games.add_bar(name=team_b, x=df_h2h['label'], y=df_h2h['score_b'],
                      marker_color=color_b)
    fig_games.update_layout(
        template='gridiron_ink', barmode='group', showlegend=True, height=500,
        title=None, width=None, margin=dict(t=20, b=80, l=60, r=20),
        legend=dict(orientation='h', x=0.5, xanchor='center', y=1.05, yanchor='bottom'),
    )

    # Chart 2: score distribution comparison (box)
    fig_dist = go.Figure()
    fig_dist.add_box(name=team_a, y=df_h2h['score_a'], marker_color=color_a,
                     boxpoints='all', jitter=0.3, pointpos=-1.5)
    fig_dist.add_box(name=team_b, y=df_h2h['score_b'], marker_color=color_b,
                     boxpoints='all', jitter=0.3, pointpos=-1.5)
    fig_dist.update_layout(
        template='gridiron_ink', showlegend=True, height=500,
        title=None, width=None, margin=dict(t=20, b=40, l=60, r=20),
    )

    charts = html.Div([
        _card(fig_games, f'{team_a} vs {team_b} · All Matchups'),
        _card(fig_dist,  f'{team_a} vs {team_b} · Score Distributions', half=False),
    ], className='charts-row')

    return stats, charts


# ── Toggle callbacks ─────────────────────────────────────────────────────────

@app.callback(
    Output('luck-chart', 'children'),
    Input('luck-toggle', 'value'),
    State('store-year', 'data'),
    State('store-week', 'data'),
    State('team-list', 'value'),
    prevent_initial_call=True,
)
def _update_luck_chart(mode, year, week, teams):
    year = year or CURRENT_YEAR
    week = week or 1
    season = _season(year)
    if season is None:
        return _loading_placeholder()
    sf = _filter_season(season, teams)
    try:
        if mode == 'ytd':
            fig = sf.LuckChart(week)
            return dcc.Graph(figure=_strip(fig, 660), config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})

        # This Week Only — scatter of single-week scores vs opponent scores
        sf.WeeklyWins(week)
        df_all = sf.ConcatinatedWeeks
        df_week = df_all[df_all['Week'] == week].copy()
        if df_week.empty:
            return html.Div('No data for this week.', style={'color': '#BDE2FF', 'padding': '20px'})

        median_score = df_week['Total'].median()
        median_opp   = df_week['Opp'].median()

        fig = go.Figure(layout_template='gridiron_ink')
        for _, row in df_week.iterrows():
            color = sf.teamcolors.get(row['Team'], '#BDE2FF')
            fig.add_scatter(
                x=[row['Opp']], y=[row['Total']],
                mode='markers+text', name=row['Team'],
                text=[row['Team']], textposition='top center',
                textfont=dict(color=color, size=15, weight='bold'),
                marker=dict(color=color, size=18),
                showlegend=False,
            )

        y_pad = (df_week['Total'].max() - df_week['Total'].min()) * 0.12 + 10
        x_pad = (df_week['Opp'].max() - df_week['Opp'].min()) * 0.12 + 10
        fig.add_shape(type='line', x0=median_opp, x1=median_opp,
                      y0=df_week['Total'].min() - y_pad, y1=df_week['Total'].max() + y_pad,
                      opacity=0.5, line=dict(color='gold', width=2, dash='dash'))
        fig.add_shape(type='line', x0=df_week['Opp'].min() - x_pad, x1=df_week['Opp'].max() + x_pad,
                      y0=median_score, y1=median_score,
                      opacity=0.5, line=dict(color='gold', width=2, dash='dash'))

        for txt, xp, yp in [('Bad but Lucky', 0, 0), ('Bad & Unlucky', 1, 0),
                              ('Good & Lucky', 0, 1), ('Good & Tested', 1, 1)]:
            fig.add_annotation(x=xp, y=yp, text=txt, showarrow=False,
                               xref='paper', yref='paper',
                               font=dict(family='Courier New', size=18, color='#FFC300'),
                               bgcolor='rgba(26,58,82,0.7)')

        fig.update_layout(
            height=660, width=None, showlegend=False,
            margin=dict(t=50, b=80, l=80, r=40),
            xaxis_title='Opponent Score This Week',
            yaxis_title='Score This Week',
            xaxis=dict(title_font=dict(color='#F94144', shadow='none'), tickfont=dict(size=16, family='Courier New')),
            yaxis=dict(title_font=dict(color='#90BE6D', shadow='none'), tickfont=dict(size=16, family='Courier New')),
        )
        return dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        return html.Div(f'Error: {e}', style={'color': '#F94144', 'padding': '20px'})


@app.callback(
    Output('timeline-chart', 'children'),
    Input('timeline-animate-toggle', 'value'),
    State('store-year', 'data'),
    State('store-week', 'data'),
    prevent_initial_call=True,
)
def _update_timeline_chart(mode, year, week):
    year = year or CURRENT_YEAR
    week = week or 1
    week_obj = _week(year, week)
    if week_obj is None:
        return _loading_placeholder()
    try:
        fig = week_obj.PointsOverTheWeekend(animate=(mode == 'animated'))
        _strip(fig, 950).update_layout(margin=dict(t=80, b=100, l=80, r=40))
        return dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        return html.Div(f'Error: {e}', style={'color': '#F94144', 'padding': '20px'})


@app.callback(
    Output('pfa-chart', 'children'),
    Input('pfa-toggle', 'value'),
    State('store-year', 'data'),
    State('team-list', 'value'),
    prevent_initial_call=True,
)
def _update_pfa_chart(mode, year, teams):
    year = year or CURRENT_YEAR
    season = _season(year)
    if season is None:
        return _loading_placeholder()
    sf = _filter_season(season, teams)
    try:
        fig = sf.SeasonPointsForAgainst()
        _strip(fig, 580)
        if mode == 'avg' and sf.Matches is not None and not sf.Matches.empty:
            avg_pts = sf.Matches.groupby('Team')['Total'].sum().mean()
            fig.add_vline(
                x=avg_pts, line_dash='dash', line_color='#FFC300', line_width=2,
                annotation_text=f'Avg: {avg_pts:.0f}',
                annotation_font_color='#FFC300',
                annotation_position='top',
            )
        return dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        return html.Div(f'Error: {e}', style={'color': '#F94144', 'padding': '20px'})


@app.callback(
    Output('freq-chart', 'children'),
    Input('freq-toggle', 'value'),
    State('store-year', 'data'),
    State('store-week', 'data'),
    State('team-list', 'value'),
    prevent_initial_call=True,
)
def _update_freq_chart(mode, year, week, teams):
    year = year or CURRENT_YEAR
    week = week or 1
    season = _season(year)
    if season is None:
        return _loading_placeholder()
    sf = _filter_season(season, teams)
    try:
        matches = sf.Matches[sf.Matches['Week'].isin(range(0, week + 1))].copy()
        if mode == 'wins':
            matches = matches[matches['Won'] == True]
        elif mode == 'losses':
            matches = matches[matches['Won'] == False]

        if matches.empty:
            return html.Div('No data for this filter.', style={'color': '#BDE2FF', 'padding': '20px'})

        fig = px.histogram(matches, x='Total', template='gridiron_ink', marginal='rug',
                           color='Team', color_discrete_map=sf.teamcolors)
        fig.update_layout(width=None, height=680, title=None,
                          margin=dict(t=20, b=120, l=75, r=75))
        fig.update_yaxes(tickfont=dict(size=15), title=None)
        fig.update_xaxes(tickfont=dict(size=15), title=None, dtick=10)
        fig.update_layout(legend=dict(orientation='h', yanchor='top', y=-0.12, xanchor='center', x=0.5))
        fig.update_traces(marker_line_width=2, marker_line_color='rgba(0,0,0,0.25)')
        fig.update_traces(
            hovertemplate='Score range: <b>%{x}</b><br>Count: <b>%{y}</b><extra></extra>'
        )
        return dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        return html.Div(f'Error: {e}', style={'color': '#F94144', 'padding': '20px'})


@app.callback(
    Output('bench-chart', 'children'),
    Input('bench-toggle', 'value'),
    State('store-year', 'data'),
    State('store-week', 'data'),
    State('team-list', 'value'),
    prevent_initial_call=True,
)
def _update_bench_chart(mode, year, week, teams):
    year = year or CURRENT_YEAR
    week = week or 1
    season = _season(year)
    if season is None:
        return _loading_placeholder()
    sf = _filter_season(season, teams)
    try:
        if mode == 'season':
            fig = sf.BrawnyBench()
            fig.update_traces(textfont_size=14)
            fig.update_layout(title=None, width=None, height=420, margin=dict(t=20, b=40, l=220, r=40))
        else:
            bench = sf.BreakoutSeason[sf.BreakoutSeason['starter'] == 0].copy()
            week_col = next((c for c in ['week_NFL', 'week'] if c in bench.columns), None)
            if week_col is None:
                return html.Div('Week column not found.', style={'color': '#F94144', 'padding': '20px'})
            bench = bench[bench[week_col] <= week]
            weekly = bench.groupby(['team', week_col])['points'].sum().reset_index()
            weekly.columns = ['team', 'week', 'bench_pts']
            weekly = weekly.sort_values('week')
            fig = px.line(
                weekly, x='week', y='bench_pts', color='team',
                color_discrete_map=sf.teamcolors,
                template='gridiron_ink', line_shape='spline',
                labels={'week': 'Week', 'bench_pts': 'Bench Points', 'team': 'Team'},
            )
            fig.update_traces(line=dict(width=2.5))
            fig.update_traces(
                hovertemplate='<b>%{fullData.name}</b><br>Week %{x}<br>Bench pts: <b>%{y:.1f}</b><extra></extra>'
            )
            fig.update_layout(
                title=None, width=None, height=580,
                margin=dict(t=20, b=100, l=80, r=40),
                legend=dict(orientation='h', yanchor='top', y=-0.12, xanchor='center', x=0.5),
                xaxis=dict(dtick=1, title=dict(text='Week', standoff=15)),
                yaxis=dict(title='Bench Points'),
            )
        return dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        return html.Div(f'Error: {e}', style={'color': '#F94144', 'padding': '20px'})


@app.callback(
    Output('bump-chart', 'children'),
    Input('bump-toggle', 'value'),
    State('store-year', 'data'),
    State('team-list', 'value'),
    prevent_initial_call=True,
)
def _update_bump_chart(mode, year, teams):
    year = year or CURRENT_YEAR
    season = _season(year)
    if season is None:
        return _loading_placeholder()
    sf = _filter_season(season, teams)
    try:
        fig = sf.WaiverWireBump(mode=mode)
        return dcc.Graph(figure=_strip(fig, 660), config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        return html.Div(f'Error: {e}', style={'color': '#F94144', 'padding': '20px'})


@app.callback(
    Output('violin-chart', 'children'),
    Input('violin-toggle', 'value'),
    State('store-year', 'data'),
    State('store-week', 'data'),
    State('team-list', 'value'),
    prevent_initial_call=True,
)
def _update_violin(mode, year, week, teams):
    year = year or CURRENT_YEAR
    week = week or 1
    season = _season(year)
    if season is None:
        return _loading_placeholder()
    sf = _filter_season(season, teams)
    try:
        if mode in ('starters', 'all'):
            fig = sf.ViolinPlayer(week, Starters=(mode == 'starters'))
            fig.update_layout(title=None, width=None, height=1000)
        else:
            fig = sf.ViolinPosition(Starters=(mode == 'pos_starters'))
            fig.update_layout(title=None, width=None, height=1200)
        return dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        return html.Div(f'Error: {e}', style={'color': '#F94144', 'padding': '20px'})


_POS_THRESHOLDS = {'QB': 50, 'RB': 75, 'WR': 75, 'TE': 40}


@app.callback(
    Output('top-players-chart', 'children'),
    Input('pos-toggle', 'value'),
    Input('top-players-threshold', 'value'),
    State('store-year', 'data'),
    State('store-week', 'data'),
    State('team-list', 'value'),
    prevent_initial_call=True,
)
def _update_top_players(position, thresh, year, week, teams):
    year = year or CURRENT_YEAR
    week = week or 1
    season = _season(year)
    if season is None:
        return _loading_placeholder()
    sf = _filter_season(season, teams)
    thresh = thresh if thresh is not None else _POS_THRESHOLDS.get(position, 50)
    try:
        fig = sf.TopPlayers(position, thresh)
        return dcc.Graph(figure=_strip(fig, 580), config={'displayModeBar': False, 'responsive': True}, style={'width': '100%'})
    except Exception as e:
        return html.Div(f'Error: {e}', style={'color': '#F94144', 'padding': '20px'})


# ── D3 store population ───────────────────────────────────────────────────────

@app.callback(
    Output('store-snake-data',   'data'),
    Output('store-race-data',    'data'),
    Output('store-heatmap-data', 'data'),
    Input('tabs',              'value'),
    Input('store-year',        'data'),
    Input('store-week',        'data'),
    Input('team-list',         'value'),
    Input('boot',              'disabled'),
    Input('store-d3-trigger',  'data'),
)
def _populate_d3_stores(tab, year, week, teams, _boot_done, _trigger):
    if tab != 'tab-season':
        return no_update, no_update, no_update
    year = year or CURRENT_YEAR
    week = week or 1
    season = _season(year)
    if season is None:
        return no_update, no_update, no_update

    sf = _filter_season(season, teams)
    all_teams = sorted(sf.Matches['Team'].unique().tolist()) if sf.Matches is not None else []
    colors = sf.teamcolors  # slot-based, set in Season.SetTeamColors()

    # --- Snake data ---
    snake_data = None
    try:
        matches = sf.Matches
        if matches is not None and not matches.empty:
            weeks_range = sorted(matches['Week'].unique().tolist())
            series = {}
            for team in all_teams:
                team_df = matches[matches['Team'] == team].sort_values('Week')
                wins_by_week = {}
                for _, row in team_df.iterrows():
                    w = int(row['Week'])
                    matchup_id = row.get('Matchup', None)
                    if matchup_id is not None:
                        opp = matches[
                            (matches['Week'] == row['Week']) &
                            (matches['Matchup'] == matchup_id) &
                            (matches['Team'] != team)
                        ]
                        if not opp.empty:
                            wins_by_week[w] = 1 if row['Total'] > opp.iloc[0]['Total'] else 0
                        else:
                            wins_by_week[w] = 0
                    else:
                        wins_by_week[w] = 0
                cumulative = [0]
                running = 0
                for wk in weeks_range:
                    running += wins_by_week.get(int(wk), 0)
                    cumulative.append(running)
                series[team] = cumulative

            # Cumulative points per team (for points toggle mode)
            cumulative_pts = {}
            for team in all_teams:
                team_df = matches[matches['Team'] == team].sort_values('Week')
                running = 0.0
                pts_series = [0.0]
                for wk in weeks_range:
                    row = team_df[team_df['Week'] == wk]
                    running += float(row['Total'].iloc[0]) if not row.empty else 0.0
                    pts_series.append(round(running, 1))
                cumulative_pts[team] = pts_series

            snake_data = {
                'teams': all_teams,
                'colors': [colors[t] for t in all_teams],
                'weeks': [0] + [int(w) for w in weeks_range],
                'series': series,
                'cumulative_pts': cumulative_pts,
                'current_week': int(week),
            }
    except Exception as e:
        print(f'[d3] snake_data error: {e}')

    # --- Score Race data (cumulative points) ---
    race_data = None
    try:
        matches = sf.Matches
        if matches is not None and not matches.empty:
            weeks_range = sorted(matches['Week'].unique().tolist())
            cumulative = {t: [] for t in all_teams}
            for team in all_teams:
                running = 0.0
                for wk in weeks_range:
                    row = matches[(matches['Team'] == team) & (matches['Week'] == wk)]
                    running += float(row['Total'].iloc[0]) if not row.empty else 0.0
                    cumulative[team].append(round(running, 2))
            race_data = {
                'weeks': [int(w) for w in weeks_range],
                'teams': all_teams,
                'colors': [colors[t] for t in all_teams],
                'cumulative': cumulative,
                'current_week': int(week),
            }
    except Exception as e:
        print(f'[d3] race_data error: {e}')

    # --- Heatmap data ---
    heatmap_data = None
    try:
        matches = sf.Matches
        if matches is not None and not matches.empty:
            weeks_range = sorted(matches['Week'].unique().tolist())
            win_counts = {}
            for team in all_teams:
                team_df = matches[matches['Team'] == team]
                wins = 0
                for _, row in team_df.iterrows():
                    w = row['Week']
                    matchup_id = row.get('Matchup', None)
                    if matchup_id is not None:
                        opp = matches[
                            (matches['Week'] == w) &
                            (matches['Matchup'] == matchup_id) &
                            (matches['Team'] != team)
                        ]
                        if not opp.empty and row['Total'] > opp.iloc[0]['Total']:
                            wins += 1
                win_counts[team] = wins
            ordered_teams = sorted(all_teams, key=lambda t: -win_counts.get(t, 0))
            avg_scores = {
                t: float(matches[matches['Team'] == t]['Total'].mean())
                for t in all_teams
            }
            scores = {}
            for team in ordered_teams:
                scores[team] = {}
                team_df = matches[matches['Team'] == team]
                for wk in weeks_range:
                    row = team_df[team_df['Week'] == wk]
                    if not row.empty:
                        score = float(row['Total'].iloc[0])
                        matchup_id = row.iloc[0].get('Matchup', None)
                        won = False
                        opp_name = ''
                        opp_score = 0.0
                        if matchup_id is not None:
                            opp = matches[
                                (matches['Week'] == wk) &
                                (matches['Matchup'] == matchup_id) &
                                (matches['Team'] != team)
                            ]
                            if not opp.empty:
                                opp_name = str(opp.iloc[0]['Team'])
                                opp_score = float(opp.iloc[0]['Total'])
                                won = score > opp_score
                        scores[team][int(wk)] = {
                            'score': score,
                            'avg': avg_scores[team],
                            'won': won,
                            'opp': opp_name,
                            'opp_score': opp_score,
                        }

            heatmap_data = {
                'teams': ordered_teams,
                'weeks': [int(w) for w in weeks_range],
                'scores': scores,
                'teamcolors': {t: colors.get(t, '#BDE2FF') for t in ordered_teams},
            }
    except Exception as e:
        print(f'[d3] heatmap_data error: {e}')

    return snake_data, race_data, heatmap_data


# ── Clientside callbacks (D3 rendering) ───────────────────────────────────────

app.clientside_callback(
    ClientsideFunction(namespace='d3charts', function_name='renderSnakeGraph'),
    Output('d3-snake-container', 'data-rendered'),
    Input('store-snake-data', 'data'),
    Input('tabs', 'value'),
    Input('store-snake-mode', 'data'),
    prevent_initial_call=True,
)

app.clientside_callback(
    'function(v) { return v || "wins"; }',
    Output('store-snake-mode', 'data'),
    Input('snake-mode-toggle', 'value'),
    prevent_initial_call=True,
)

app.clientside_callback(
    ClientsideFunction(namespace='d3charts', function_name='renderScoreRace'),
    Output('d3-race-container', 'data-rendered'),
    Input('store-race-data', 'data'),
    Input('tabs', 'value'),
    prevent_initial_call=True,
)

app.clientside_callback(
    ClientsideFunction(namespace='d3charts', function_name='renderHeatmap'),
    Output('d3-heatmap-container', 'data-rendered'),
    Input('store-heatmap-data', 'data'),
    Input('tabs', 'value'),
    prevent_initial_call=True,
)

app.clientside_callback(
    ClientsideFunction(namespace='d3charts', function_name='renderBubbleMap'),
    Output('d3-bubble-container', 'data-rendered'),
    Input('store-bubble-data', 'data'),
    Input('tabs', 'value'),
    prevent_initial_call=True,
)

app.clientside_callback(
    ClientsideFunction(namespace='d3charts', function_name='renderDraftBoard'),
    Output('d3-draft-container', 'data-rendered'),
    Input('store-draft-data', 'data'),
    Input('tabs', 'value'),
    prevent_initial_call=True,
)

app.clientside_callback(
    ClientsideFunction(namespace='d3charts', function_name='renderChoropleth'),
    Output('d3-choropleth-container', 'data-rendered'),
    Input('store-choropleth-data', 'data'),
    Input('tabs', 'value'),
)

app.clientside_callback(
    'function(v) { return v || "top"; }',
    Output('store-arc-mode', 'data'),
    Input('arc-mode-toggle', 'value'),
    prevent_initial_call=True,
)

app.clientside_callback(
    ClientsideFunction(namespace='d3charts', function_name='renderArcMap'),
    Output('d3-arc-container', 'data-rendered'),
    Input('store-chord-data', 'data'),
    Input('tabs', 'value'),
    Input('store-arc-mode', 'data'),
    prevent_initial_call=True,
)

app.clientside_callback(
    ClientsideFunction(namespace='d3charts', function_name='renderTerritoryMap'),
    Output('d3-territory-container', 'data-rendered'),
    Input('store-chord-data', 'data'),
    Input('tabs', 'value'),
)

app.clientside_callback(
    ClientsideFunction(namespace='d3charts', function_name='renderChordDiagram'),
    Output('d3-chord-container', 'data-rendered'),
    Input('store-chord-data', 'data'),
    Input('tabs', 'value'),
)

# Wire D3 load buttons via event delegation.
# Buttons live inside tab-content (dynamic IDs can't be Dash Inputs), so we
# attach a document-level click listener once and call set_props to increment
# store-d3-trigger, which feeds into the Python data-population callbacks.
app.clientside_callback(
    '''
    function(n) {
        if (!window._d3LoadBound) {
            window._d3LoadBound = true;
            window._d3TriggerCount = 0;
            document.addEventListener('click', function(e) {
                var btn = e.target.closest('button');
                if (btn && (btn.id === 'load-race' || btn.id === 'load-heatmap' || btn.id === 'load-draft' || btn.id === 'load-bubble')) {
                    window._d3TriggerCount = (window._d3TriggerCount || 0) + 1;
                    window.dash_clientside.set_props('store-d3-trigger', {data: window._d3TriggerCount});
                }
            });
        }
        return window.dash_clientside.no_update;
    }
    ''',
    Output('store-d3-trigger', 'data'),
    Input('boot', 'disabled'),
    prevent_initial_call=True,
)


# ── D3 store population — Bubble Map ─────────────────────────────────────────

@app.callback(
    Output('store-bubble-data', 'data'),
    Input('tabs',             'value'),
    Input('store-year',       'data'),
    Input('store-week',       'data'),
    Input('boot',             'disabled'),
    Input('store-d3-trigger', 'data'),
)
def _populate_bubble_data(tab, year, week, _boot_done, _trigger):
    if tab != 'tab-week':
        return no_update
    year = year or CURRENT_YEAR
    week = week or 1

    try:
        wk = _week(year, week)
        if wk is None:
            return no_update

        # Get breakout data for this week
        breakout = core.AllBreakoutDict.get(year, {}).get(week)
        if breakout is None:
            return no_update

        # Combine list of DataFrames if needed
        if isinstance(breakout, list):
            df = pd.concat(breakout, ignore_index=True)
        else:
            df = breakout

        # Filter to starters only
        starters = df[df['starter'] == 1].copy() if 'starter' in df.columns else df.copy()

        # Find team column (nfl team, not fantasy team)
        team_col = None
        for c in ['recent_team', 'team', 'nfl_team']:
            if c in starters.columns:
                team_col = c
                break
        if team_col is None:
            return no_update

        grp = starters.groupby(team_col).agg(
            fantasy_pts=('points', 'sum'),
            top_player_pts=('points', 'max'),
        ).reset_index()

        # Top player per team
        def top_player_for_team(t):
            sub = starters[starters[team_col] == t]
            if sub.empty:
                return ''
            idx = sub['points'].idxmax()
            return str(sub.loc[idx, 'player']) if 'player' in sub.columns else ''

        grp['top_player'] = grp[team_col].apply(top_player_for_team)

        # Season average per NFL team (use all weeks loaded so far)
        season_avgs = {}
        all_weeks_breakout = core.AllBreakoutDict.get(year, {})
        for w, wb in all_weeks_breakout.items():
            if wb is None:
                continue
            wdf = pd.concat(wb, ignore_index=True) if isinstance(wb, list) else wb
            if team_col not in wdf.columns:
                continue
            ws = wdf[wdf['starter'] == 1] if 'starter' in wdf.columns else wdf
            for t, pts in ws.groupby(team_col)['points'].sum().items():
                season_avgs.setdefault(t, []).append(pts)
        avg_map = {t: sum(v)/len(v) for t, v in season_avgs.items() if v}

        bubble_teams = []
        for _, row in grp.iterrows():
            nfl_team = row[team_col]
            coords = NFL_STADIUM_COORDS.get(nfl_team)
            if coords is None:
                continue
            bubble_teams.append({
                'nfl_team': nfl_team,
                'lat': coords['lat'],
                'lon': coords['lon'],
                'fantasy_pts': round(float(row['fantasy_pts']), 1),
                'season_avg': round(avg_map.get(nfl_team, float(row['fantasy_pts'])), 1),
                'top_player': row['top_player'],
                'top_player_pts': round(float(row['top_player_pts']), 1),
            })

        return {'week': week, 'teams': bubble_teams}

    except Exception as e:
        print(f'[bubble] error: {e}')
        return no_update


# ── D3 store population — Draft Board ────────────────────────────────────────

@app.callback(
    Output('store-draft-data', 'data'),
    Input('tabs',             'value'),
    Input('store-year',       'data'),
    Input('boot',             'disabled'),
    Input('store-d3-trigger', 'data'),
)
def _populate_draft_data(tab, year, _boot_done, _trigger):
    if tab != 'tab-season':
        return no_update
    year = year or CURRENT_YEAR
    try:
        league_data = _data.get(year, {}).get('league')
        if league_data is None:
            return no_update
        draft = league_data.Draft()
        if draft is None or draft.empty:
            return no_update

        # Get optimal player scores for value tiers
        season_data = _data.get(year, {}).get('season')
        player_totals = {}
        if season_data and hasattr(season_data, 'BreakoutSeason') and season_data.BreakoutSeason is not None:
            bs = season_data.BreakoutSeason
            player_totals = bs.groupby('player')['points'].sum().to_dict()

        colors = core.get_slot_teamcolors(year)

        picks = []
        for _, row in draft.iterrows():
            player_name = str(row.get('player_name', row.get('player', '')))
            # roster_id column is already mapped to display_name by Draft()
            team_name   = str(row.get('roster_id', row.get('display_name', row.get('team', ''))))
            total_pts   = player_totals.get(player_name, 0.0)

            # Value tier by season points
            if   total_pts >= 200: tier = 'elite'
            elif total_pts >= 120: tier = 'solid'
            elif total_pts >= 60:  tier = 'average'
            else:                  tier = 'bust'

            # Position from metadata if available
            pos = str(row.get('metadata.position', row.get('position', '')))

            picks.append({
                'round':     int(row.get('round', 1)),
                'pick':      int(row.get('pick_no', row.get('draft_slot', 1))),
                'team':      team_name,
                'player':    player_name,
                'position':  pos,
                'total_pts': round(float(total_pts), 1),
                'tier':      tier,
                'color':     colors.get(team_name, '#BDE2FF'),
            })

        return {'year': year, 'picks': picks}
    except Exception as e:
        print(f'[draft] error: {e}')
        return no_update


# ── D3 store population — State Choropleth ───────────────────────────────────

_NFL_TEAM_STATE = {
    'ARI': {'fips': '04', 'name': 'Arizona'},
    'ATL': {'fips': '13', 'name': 'Georgia'},
    'BAL': {'fips': '24', 'name': 'Maryland'},
    'BUF': {'fips': '36', 'name': 'New York'},
    'CAR': {'fips': '37', 'name': 'North Carolina'},
    'CHI': {'fips': '17', 'name': 'Illinois'},
    'CIN': {'fips': '39', 'name': 'Ohio'},
    'CLE': {'fips': '39', 'name': 'Ohio'},
    'DAL': {'fips': '48', 'name': 'Texas'},
    'DEN': {'fips': '08', 'name': 'Colorado'},
    'DET': {'fips': '26', 'name': 'Michigan'},
    'GB':  {'fips': '55', 'name': 'Wisconsin'},
    'HOU': {'fips': '48', 'name': 'Texas'},
    'IND': {'fips': '18', 'name': 'Indiana'},
    'JAX': {'fips': '12', 'name': 'Florida'},
    'KC':  {'fips': '29', 'name': 'Missouri'},
    'LA':  {'fips': '06', 'name': 'California'},
    'LAC': {'fips': '06', 'name': 'California'},
    'LV':  {'fips': '32', 'name': 'Nevada'},
    'MIA': {'fips': '12', 'name': 'Florida'},
    'MIN': {'fips': '27', 'name': 'Minnesota'},
    'NE':  {'fips': '25', 'name': 'Massachusetts'},
    'NO':  {'fips': '22', 'name': 'Louisiana'},
    'NYG': {'fips': '34', 'name': 'New Jersey'},
    'NYJ': {'fips': '34', 'name': 'New Jersey'},
    'PHI': {'fips': '42', 'name': 'Pennsylvania'},
    'PIT': {'fips': '42', 'name': 'Pennsylvania'},
    'SEA': {'fips': '53', 'name': 'Washington'},
    'SF':  {'fips': '06', 'name': 'California'},
    'TB':  {'fips': '12', 'name': 'Florida'},
    'TEN': {'fips': '47', 'name': 'Tennessee'},
    'WAS': {'fips': '24', 'name': 'Maryland'},
}


@app.callback(
    Output('store-choropleth-data', 'data'),
    Input('tabs',  'value'),
    Input('boot',  'disabled'),
)
def _populate_choropleth_data(tab, _boot_done):
    if tab != 'tab-alltime':
        return no_update
    try:
        team_pts: dict = {}
        for year, ydata in _data.items():
            season = ydata.get('season')
            if season is None or not hasattr(season, 'BreakoutSeason'):
                continue
            bs = season.BreakoutSeason
            if bs is None or bs.empty:
                continue
            team_col = next((c for c in ['recent_teams', 'recent_team', 'nfl_team', 'team_y']
                             if c in bs.columns), None)
            if team_col is None:
                continue
            starters = bs[bs['starter'] == 1] if 'starter' in bs.columns else bs
            for nfl_t, pts in starters.groupby(team_col)['points'].sum().items():
                team_pts[nfl_t] = team_pts.get(nfl_t, 0.0) + float(pts)

        # Aggregate by state
        state_agg: dict = {}
        for team, pts in team_pts.items():
            if team not in _NFL_TEAM_STATE:
                continue
            info  = _NFL_TEAM_STATE[team]
            fips  = info['fips']
            entry = state_agg.setdefault(fips, {'name': info['name'], 'total_pts': 0.0, 'teams': {}})
            entry['total_pts']    += pts
            entry['teams'][team]   = round(pts, 1)

        states_list = []
        for fips, entry in state_agg.items():
            top_team = max(entry['teams'], key=lambda t: entry['teams'][t])
            states_list.append({
                'fips':         fips,
                'name':         entry['name'],
                'total_pts':    round(entry['total_pts'], 1),
                'teams':        entry['teams'],
                'top_team':     top_team,
                'top_team_pts': entry['teams'][top_team],
            })

        max_pts = max((s['total_pts'] for s in states_list), default=1.0)
        return {'states': states_list, 'max_pts': round(max_pts, 1), '_ts': time.time()}

    except Exception as e:
        print(f'[choropleth] error: {e}')
        traceback.print_exc()
        return no_update


# ── D3 store population — Chord Diagram ──────────────────────────────────────

@app.callback(
    Output('store-chord-data', 'data'),
    Input('tabs',  'value'),
    Input('boot',  'disabled'),
)
def _populate_chord_data(tab, _boot_done):
    if tab != 'tab-alltime':
        return no_update
    try:
        import pandas as pd
        from collections import defaultdict

        colors = core.get_alltime_teamcolors()

        # Accumulate fantasy pts per (nfl_team, fantasy_owner) across all loaded years
        matrix_dict = defaultdict(lambda: defaultdict(float))
        nfl_teams_seen = set()

        for year, ydata in _data.items():
            season = ydata.get('season')
            if season is None or not hasattr(season, 'BreakoutSeason'):
                continue
            bs = season.BreakoutSeason
            if bs is None or bs.empty:
                continue

            # BreakoutSeason uses 'recent_teams' for NFL team and 'team' for fantasy owner
            # (already mapped to display names by the time it's stored)
            team_col = None
            for c in ['recent_teams', 'recent_team', 'nfl_team', 'team_y']:
                if c in bs.columns:
                    team_col = c
                    break
            if team_col is None:
                continue

            owner_col = 'team' if 'team' in bs.columns else None
            if owner_col is None:
                continue

            starters = bs[bs['starter'] == 1].copy() if 'starter' in bs.columns else bs.copy()

            for _, row in starters.iterrows():
                nfl_t = str(row.get(team_col, ''))
                owner = str(row.get(owner_col, ''))
                pts   = float(row.get('points', 0))
                if nfl_t and owner and pts > 0 and nfl_t != 'nan' and owner != 'nan':
                    matrix_dict[nfl_t][owner] += pts
                    nfl_teams_seen.add(nfl_t)

        if not matrix_dict:
            return no_update

        # Filter to NFL teams with meaningful contribution (at least 50 total pts)
        nfl_teams  = sorted([t for t in nfl_teams_seen if sum(matrix_dict[t].values()) >= 50])
        all_owners = sorted({o for owner_dict in matrix_dict.values() for o in owner_dict})
        owners     = [o for o in all_owners if any(matrix_dict[t].get(o, 0) > 0 for t in nfl_teams)]

        if not nfl_teams or not owners:
            return no_update

        # Build matrix: rows = nfl_teams, cols = owners
        matrix = []
        for nfl_t in nfl_teams:
            row = [round(matrix_dict[nfl_t].get(o, 0), 1) for o in owners]
            matrix.append(row)

        return {
            'nfl_teams': nfl_teams,
            'fantasy_owners': owners,
            'colors': {o: colors[o] for o in owners if o in colors},
            'matrix': matrix,
            'stadium_coords': {t: NFL_STADIUM_COORDS[t] for t in nfl_teams if t in NFL_STADIUM_COORDS},
            '_ts': time.time(),
        }
    except Exception as e:
        print(f'[chord] error: {e}')
        traceback.print_exc()
        return no_update


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True, dev_tools_hot_reload=False, host='0.0.0.0', port=8050)
