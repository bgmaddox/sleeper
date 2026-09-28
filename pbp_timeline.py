"""Play-by-play fantasy scoring for the This Week points timeline.

Turns an nflverse play-by-play frame into per-play fantasy points under a
league's own ``scoring_settings``, then into a per-team running total.

Two rules hold it together:

- **Scoring is read from the league, never hardcoded.** ``play_stats`` emits
  counts keyed by Sleeper's stat names (``rec``, ``pass_yd``, ``fgm_yds``...);
  ``score`` multiplies by whatever that season's settings say. A stat the
  league doesn't score is simply worth zero.
- **The final value always equals Sleeper.** Per-play attribution is an
  approximation (laterals, special-teams oddities, stat corrections), so each
  starter's shortfall against their Sleeper total lands as one
  ``final_adjust`` step at their game's last play. For a team defense that
  step is the points/yards-allowed tier bonus — by design, since tiers are
  only known at the final whistle. ``tests/test_pbp_timeline.py`` backtests
  how small those residuals are for offensive players; that floor, not
  intuition, governs changes to the attribution rules.
"""

from __future__ import annotations

import re

import pandas as pd

LEAGUE_TZ = 'America/New_York'

# nflverse team abbreviations that differ from Sleeper's DEF player_id.
NFLVERSE_TO_SLEEPER_TEAM = {'LA': 'LAR'}

# Time from scheduled kickoff to a game's end, for players whose game has no
# play-by-play published yet.
GAME_LENGTH = pd.Timedelta(hours=3, minutes=15)


class PBPUnavailable(Exception):
    """nflverse has published no play-by-play for the requested week."""


# ── Per-play stat extraction ─────────────────────────────────────────────────

def _flag(pbp: pd.DataFrame, col: str) -> pd.Series:
    return pbp[col].fillna(0).astype(float).eq(1)


def _team(s: pd.Series) -> pd.Series:
    return s.replace(NFLVERSE_TO_SLEEPER_TEAM)


def _fg_tier_keys(scoring_settings: dict, prefix: str) -> list[tuple[str, float, float]]:
    """(key, lo, hi) for distance-tiered kicking keys like fgm_40_49 / fgmiss_50p."""
    tiers = []
    for key in scoring_settings:
        m = re.fullmatch(rf'{prefix}_(\d+)_(\d+)', key)
        if m:
            tiers.append((key, float(m[1]), float(m[2])))
            continue
        m = re.fullmatch(rf'{prefix}_(\d+)p', key)
        if m:
            tiers.append((key, float(m[1]), float('inf')))
    return tiers


def play_stats(pbp: pd.DataFrame, scoring_settings: dict | None = None) -> pd.DataFrame:
    """Long-format stat rows: (game_id, play_id, entity, stat_key, value).

    `entity` is a GSIS player id, or a Sleeper team abbreviation for team
    defense. `scoring_settings` is only consulted for distance-tiered kicking
    keys, so the tier boundaries follow the league rather than a fixed list.
    """
    scoring_settings = scoring_settings or {}
    pbp = pbp.copy()          # helper columns below must not leak to the caller
    parts = []

    def emit(mask, entity_col, stat_key, value=1.0):
        rows = pbp.loc[mask, ['game_id', 'play_id', entity_col]].copy()
        rows = rows[rows[entity_col].notna()]
        if rows.empty:
            return
        if isinstance(value, str):
            vals = pbp.loc[rows.index, value].fillna(0).astype(float)
        else:
            vals = value
        parts.append(pd.DataFrame({
            'game_id': rows['game_id'].values,
            'play_id': rows['play_id'].values,
            'entity': rows[entity_col].values,
            'stat_key': stat_key,
            'value': vals if not isinstance(vals, pd.Series) else vals.values,
        }))

    two_pt = pbp['two_point_conv_result'].eq('success')
    pass_td, rush_td = _flag(pbp, 'pass_touchdown'), _flag(pbp, 'rush_touchdown')
    intercepted = _flag(pbp, 'interception')
    ret_td = _flag(pbp, 'return_touchdown')

    # Passer
    emit(pbp['passing_yards'].notna(), 'passer_player_id', 'pass_yd', 'passing_yards')
    emit(pass_td, 'passer_player_id', 'pass_td')
    emit(intercepted, 'passer_player_id', 'pass_int')
    emit(intercepted & ret_td, 'passer_player_id', 'pass_int_td')
    emit(two_pt & _flag(pbp, 'pass_attempt'), 'passer_player_id', 'pass_2pt')

    # Rusher
    emit(pbp['rushing_yards'].notna(), 'rusher_player_id', 'rush_yd', 'rushing_yards')
    emit(rush_td & pbp['td_player_id'].eq(pbp['rusher_player_id']), 'rusher_player_id', 'rush_td')
    emit(two_pt & _flag(pbp, 'rush_attempt'), 'rusher_player_id', 'rush_2pt')

    # Receiver
    emit(_flag(pbp, 'complete_pass'), 'receiver_player_id', 'rec')
    emit(pbp['receiving_yards'].notna(), 'receiver_player_id', 'rec_yd', 'receiving_yards')
    emit(pass_td & pbp['td_player_id'].eq(pbp['receiver_player_id']), 'receiver_player_id', 'rec_td')
    emit(two_pt & _flag(pbp, 'pass_attempt'), 'receiver_player_id', 'rec_2pt')

    # Laterals: yards gained after a lateral belong to the lateral receiver.
    emit(pbp['lateral_receiving_yards'].notna(), 'lateral_receiver_player_id', 'rec_yd', 'lateral_receiving_yards')
    emit(pbp['lateral_rushing_yards'].notna(), 'lateral_rusher_player_id', 'rush_yd', 'lateral_rushing_yards')

    # Fumbles: every fumble costs `fum`; one the other team recovers costs
    # `fum_lost` on top and is a `fum_rec` for the recovering defense. Judged per
    # fumble, not by the play's `fumble_lost` flag — a play can hold two
    # fumbles (an interception fumbled back to the passer, who fumbles again).
    for k in (1, 2):
        fumbler, rec_team = f'fumbled_{k}_player_id', f'fumble_recovery_{k}_team'
        lost = pbp[rec_team].notna() & pbp[rec_team].ne(pbp[f'fumbled_{k}_team'])
        emit(pbp[fumbler].notna(), fumbler, 'fum')
        emit(lost, fumbler, 'fum_lost')
        pbp[f'_rec{k}'] = _team(pbp[rec_team])
        emit(lost, f'_rec{k}', 'fum_rec')

    # A teammate who recovers a fumble and scores (credited to nobody above).
    emit(_flag(pbp, 'touchdown') & _flag(pbp, 'fumble') & pbp['td_team'].eq(pbp['posteam'])
         & pbp['td_player_id'].ne(pbp['rusher_player_id'])
         & pbp['td_player_id'].ne(pbp['receiver_player_id']), 'td_player_id', 'fum_rec_td')

    # Returners
    kickoff, punt = pbp['play_type'].eq('kickoff'), pbp['play_type'].eq('punt')
    emit(kickoff & pbp['return_yards'].notna(), 'kickoff_returner_player_id', 'kr_yd', 'return_yards')
    emit(punt & pbp['return_yards'].notna(), 'punt_returner_player_id', 'pr_yd', 'return_yards')
    st_td = ret_td & (kickoff | punt)
    emit(st_td & pbp['td_player_id'].eq(pbp['kickoff_returner_player_id']), 'kickoff_returner_player_id', 'st_td')
    emit(st_td & pbp['td_player_id'].eq(pbp['punt_returner_player_id']), 'punt_returner_player_id', 'st_td')

    # Kicker
    fg = pbp['field_goal_result']
    dist = pbp['kick_distance'].astype(float)
    made, missed = fg.eq('made'), fg.isin(['missed', 'blocked'])
    emit(made, 'kicker_player_id', 'fgm')
    emit(made, 'kicker_player_id', 'fgm_yds', 'kick_distance')
    for key, lo, hi in _fg_tier_keys(scoring_settings, 'fgm'):
        emit(made & dist.between(lo, hi), 'kicker_player_id', key)
    emit(missed, 'kicker_player_id', 'fgmiss')
    for key, lo, hi in _fg_tier_keys(scoring_settings, 'fgmiss'):
        emit(missed & dist.between(lo, hi), 'kicker_player_id', key)
    xp = pbp['extra_point_result']
    emit(xp.eq('good'), 'kicker_player_id', 'xpm')
    emit(xp.isin(['failed', 'blocked']), 'kicker_player_id', 'xpmiss')

    # Team defense / special teams, keyed by Sleeper team abbreviation.
    pbp['_def'] = _team(pbp['defteam'])
    pbp['_td'] = _team(pbp['td_team'])
    emit(_flag(pbp, 'sack'), '_def', 'sack')
    emit(intercepted, '_def', 'int')
    emit(_flag(pbp, 'safety'), '_def', 'safe')
    emit(pbp['blocked_player_id'].notna(), '_def', 'blk_kick')
    # A return TD belongs to whoever scored it: the defense on turnovers, the
    # receiving team on kicks (nflverse's posteam on a kickoff is the returner).
    emit(ret_td & ~(kickoff | punt), '_td', 'def_td')
    emit(st_td, '_td', 'def_st_td')

    if not parts:
        return pd.DataFrame(columns=['game_id', 'play_id', 'entity', 'stat_key', 'value'])
    out = pd.concat(parts, ignore_index=True)
    out['value'] = out['value'].astype(float)
    return out


def score(stats: pd.DataFrame, scoring_settings: dict) -> pd.DataFrame:
    """Per-play fantasy points: (game_id, play_id, entity, points, stat_keys)."""
    s = stats.copy()
    s['points'] = s['value'] * s['stat_key'].map(lambda k: float(scoring_settings.get(k, 0) or 0))
    s = s[s['points'] != 0]
    return (s.groupby(['game_id', 'play_id', 'entity'], as_index=False)
             .agg(points=('points', 'sum'), stat_keys=('stat_key', list), values=('value', list)))


# ── Timing ───────────────────────────────────────────────────────────────────

def kickoffs(schedule: pd.DataFrame) -> pd.Series:
    """game_id → scheduled kickoff, naive Eastern time."""
    ts = pd.to_datetime(schedule['gameday'].astype(str) + ' ' + schedule['gametime'].astype(str),
                        errors='coerce')
    return pd.Series(ts.values, index=schedule['game_id'].values)


def play_times(pbp: pd.DataFrame, schedule: pd.DataFrame) -> pd.Series:
    """Naive Eastern wall-clock time of each play, indexed like `pbp`.

    nflverse leaves ~3% of `time_of_day` null (mostly each game's first row);
    those take the previous play's time, or the scheduled kickoff when a game
    starts with nulls.
    """
    ts = (pd.to_datetime(pbp['time_of_day'], utc=True, errors='coerce', format='ISO8601')
            .dt.tz_convert(LEAGUE_TZ).dt.tz_localize(None))
    order = pbp.sort_values(['game_id', 'play_id']).index
    ts = ts.loc[order].groupby(pbp.loc[order, 'game_id']).ffill()
    missing = ts.isna()
    if missing.any():
        ts[missing] = pbp.loc[ts[missing].index, 'game_id'].map(kickoffs(schedule))
    return ts.reindex(pbp.index)


# ── Descriptions ─────────────────────────────────────────────────────────────

def _describe(stat_keys: list, values: list) -> str:
    st = dict(zip(stat_keys, values))

    def yds(key):
        return f"{int(round(st[key]))}-yd "

    bits = []
    if 'pass_yd' in st or 'pass_td' in st:
        bits.append(f"{yds('pass_yd') if 'pass_yd' in st else ''}{'TD ' if 'pass_td' in st else ''}pass")
    if 'pass_int' in st:
        bits.append('INT thrown' + (', returned for TD' if 'pass_int_td' in st else ''))
    if 'rush_yd' in st or 'rush_td' in st:
        bits.append(f"{yds('rush_yd') if 'rush_yd' in st else ''}{'TD ' if 'rush_td' in st else ''}run")
    if 'rec_yd' in st or 'rec_td' in st or 'rec' in st:
        bits.append(f"{yds('rec_yd') if 'rec_yd' in st else ''}{'TD ' if 'rec_td' in st else ''}catch")
    if {'pass_2pt', 'rush_2pt', 'rec_2pt'} & st.keys():
        bits.append('2-pt conversion')
    if 'kr_yd' in st:
        bits.append(f"{yds('kr_yd')}kick return")
    if 'pr_yd' in st:
        bits.append(f"{yds('pr_yd')}punt return")
    if 'st_td' in st:
        bits.append('return TD')
    if 'fgm_yds' in st or 'fgm' in st:
        bits.append(f"{yds('fgm_yds') if 'fgm_yds' in st else ''}FG")
    if any(k.startswith('fgmiss') for k in st):
        bits.append('missed FG')
    if 'xpm' in st:
        bits.append('XP')
    if 'xpmiss' in st:
        bits.append('missed XP')
    if 'fum_rec_td' in st:
        bits.append('fumble recovery TD')
    if 'fum_lost' in st:
        bits.append('fumble lost')
    elif 'fum' in st:
        bits.append('fumble')
    for key, label in (('sack', 'sack'), ('int', 'interception'), ('fum_rec', 'fumble recovery'),
                       ('safe', 'safety'), ('blk_kick', 'blocked kick'),
                       ('def_td', 'defensive TD'), ('def_st_td', 'return TD')):
        if key in st:
            bits.append(label)
    return ', '.join(bits) if bits else 'scoring play'


_PLAYER_ID_COLUMNS = [
    'passer_player_id', 'rusher_player_id', 'receiver_player_id', 'kicker_player_id',
    'td_player_id', 'fumbled_1_player_id', 'fumbled_2_player_id',
    'kickoff_returner_player_id', 'punt_returner_player_id',
    'lateral_receiver_player_id', 'lateral_rusher_player_id',
]


def _entity_games(pbp: pd.DataFrame) -> dict:
    """entity → the game_id it appears in this week (players and team DEFs)."""
    ids = pbp[['game_id', *_PLAYER_ID_COLUMNS]].melt(id_vars='game_id', value_name='entity')
    teams = pd.concat([
        pbp[['game_id', 'home_team']].rename(columns={'home_team': 'entity'}),
        pbp[['game_id', 'away_team']].rename(columns={'away_team': 'entity'}),
    ])
    teams['entity'] = _team(teams['entity'])
    both = pd.concat([ids[['game_id', 'entity']], teams]).dropna().drop_duplicates('entity')
    return dict(zip(both['entity'], both['game_id']))


# ── Team timeline ────────────────────────────────────────────────────────────

TIMELINE_COLUMNS = ['ts', 'team', 'matchup', 'player', 'delta', 'cum', 'desc', 'kind']


def team_timeline(breakout: pd.DataFrame, pbp: pd.DataFrame, schedule: pd.DataFrame,
                  scoring_settings: dict) -> pd.DataFrame:
    """One row per scoring event per fantasy team, with a running total.

    Columns: ``ts`` (naive ET), ``team``, ``matchup``, ``player``, ``delta``,
    ``cum``, ``desc``, ``kind`` — where kind is ``anchor`` (0 at the week's
    first kickoff), ``play``, ``final_adjust`` (reconciliation to Sleeper at
    the game's last play) or ``no_pbp`` (the game has no play-by-play yet; the
    player's whole score lands at the scheduled end).

    `breakout` is ``Week.Breakout``; `schedule` is the NFL schedule (any
    superset of this week's games).
    """
    starters = breakout[breakout['starter'] == 1].copy()
    starters['entity'] = starters['gsis_id'].where(starters['position'] != 'DEF', starters['player_id'])
    week_games = set(starters['game_id'].dropna())
    sched = schedule[schedule['game_id'].isin(week_games | set(pbp['game_id']))]
    kick = kickoffs(sched)

    pbp = pbp.copy()
    pbp['ts'] = play_times(pbp, sched)
    game_end = pbp.groupby('game_id')['ts'].max()
    plays = score(play_stats(pbp, scoring_settings), scoring_settings)
    plays = plays.merge(pbp[['game_id', 'play_id', 'ts']], on=['game_id', 'play_id'], how='left')

    # Join on the player alone, not his Breakout game: a player appears in
    # exactly one game's plays per week, so the plays locate him even when
    # Breakout's game_id is wrong (it falls back to the end-of-season roster
    # team for a player with no weekly stats row).
    ev = starters[['team', 'matchup', 'player', 'entity', 'points']].merge(
        plays, on='entity', how='inner', suffixes=('', '_play'))
    ev = ev.assign(delta=ev['points_play'],
                   desc=ev['player'] + ': ' + [_describe(k, v) for k, v in zip(ev['stat_keys'], ev['values'])],
                   kind='play')
    rows = [ev[['ts', 'team', 'matchup', 'player', 'delta', 'desc', 'kind']]]

    # Reconciliation: whatever the plays don't explain lands at the final whistle.
    earned = ev.groupby(['team', 'entity'])['delta'].sum()
    played_in = _entity_games(pbp)
    adj = []
    for s in starters.itertuples(index=False):
        sleeper = float(s.points or 0)
        game = played_in.get(s.entity, s.game_id)
        if game in game_end.index:
            residual = sleeper - earned.get((s.team, s.entity), 0.0)
            if abs(residual) >= 0.01:
                label = 'Points/yards allowed bonus' if s.position == 'DEF' else 'Stat adjustment'
                adj.append((game_end[game], s.team, s.matchup, s.player, residual,
                            f'{s.player}: {label}', 'final_adjust'))
        elif abs(sleeper) >= 0.01:
            when = kick.get(s.game_id, pd.NaT)
            when = when + GAME_LENGTH if pd.notna(when) else game_end.max()
            adj.append((when, s.team, s.matchup, s.player, sleeper,
                        f'{s.player}: Final (no play data yet)', 'no_pbp'))
    rows.append(pd.DataFrame(adj, columns=['ts', 'team', 'matchup', 'player', 'delta', 'desc', 'kind']))

    first = min(kick.min(), pbp['ts'].min())
    teams = starters[['team', 'matchup']].drop_duplicates()
    rows.append(teams.assign(ts=first, player='', delta=0.0, desc='Kickoff', kind='anchor'))

    out = pd.concat([r for r in rows if not r.empty], ignore_index=True)
    out = out[(out['kind'] == 'anchor') | (out['delta'].abs() >= 1e-9)]
    out['_anchor'] = out['kind'].ne('anchor')           # anchor sorts first at a tie
    out = out.sort_values(['team', 'ts', '_anchor']).drop(columns='_anchor')
    out['cum'] = out.groupby('team')['delta'].cumsum()
    return out[TIMELINE_COLUMNS].reset_index(drop=True)


# ── Chart helpers ────────────────────────────────────────────────────────────

def axis_breaks(times, min_gap=pd.Timedelta(minutes=60), pad=pd.Timedelta(minutes=15)) -> list[dict]:
    """Plotly ``rangebreaks`` that cut the dead time between game windows.

    Any stretch longer than `min_gap` with no plays (Thursday night → Sunday
    morning, overnight Sunday → Monday) is hidden, keeping `pad` of empty axis
    on each side so a window's first and last plays don't touch the seam.
    """
    ts = pd.Series(pd.to_datetime(pd.Series(times)).dropna().unique()).sort_values()
    gaps = ts.diff()
    breaks = []
    for end, gap in zip(ts[gaps > min_gap], gaps[gaps > min_gap]):
        # Whole minutes: play times carry milliseconds, which only add noise
        # to the figure JSON.
        start = (end - gap + pad).ceil('min')
        stop = (end - pad).floor('min')
        breaks.append(dict(values=[start.isoformat()], dvalue=(stop - start) / pd.Timedelta(milliseconds=1)))
    return breaks


def coalesce(tl: pd.DataFrame) -> pd.DataFrame:
    """One point per (team, ts): simultaneous events share a marker and hover."""
    g = tl.groupby(['team', 'ts'], sort=False)
    out = g.agg(matchup=('matchup', 'first'), delta=('delta', 'sum'), cum=('cum', 'last'),
                desc=('desc', '<br>'.join), kind=('kind', 'first')).reset_index()
    return out.sort_values(['team', 'ts']).reset_index(drop=True)
