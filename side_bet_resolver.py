"""
Automatic resolution of weekly side bet winners.

The league's side bet challenges are declared in ``config/side_bet_seasons.json``
as ``{name, desc, winner}`` per week.  Historically ``winner`` was typed in by
hand; this module derives it from the data instead.

Three things matter about the design:

1. **A manual ``winner`` in the JSON always wins.**  It is the override for the
   handful of challenges that are not derivable (Soothsayer, the tiebreakers)
   and the escape hatch for anything the rules get wrong.
2. **Nothing resolves before the Tuesday following the week's last game.**
   nfl_data_py applies stat corrections into Tuesday, so a winner computed on
   Monday night can move.  ``is_settled`` gates on the real last ``gameday``
   for that week rather than a hardcoded calendar.
3. **A challenge with no rule stays blank** rather than guessing.  Unknown
   names fall through to ``unsupported`` and the UI keeps showing "TBD".

Rules are keyed by a normalised challenge name, because the same bet is spelled
inconsistently across seasons ("I'm flying, Jack!" vs "I'm Flying, Jack!").
"""

from __future__ import annotations

from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import pandas as pd

LEAGUE_TZ = ZoneInfo("America/New_York")

# Stat corrections land Tuesday morning; hold results until midday to be safe.
SETTLE_HOUR = 12

# Resolution outcomes, in the order the UI cares about.
MANUAL      = "manual"       # hand-entered in the JSON; always wins
COMPUTED    = "computed"     # derived from the data
PENDING     = "pending"      # rule exists, but the week has not settled yet
NO_DATA     = "no_data"      # week not cached / no rows to work with
UNSUPPORTED = "unsupported"  # no rule for this challenge


def norm_name(name: str) -> str:
    """Normalise a challenge name for rule lookup (case, punctuation, spacing)."""
    return " ".join(str(name).lower().replace("!", "").replace("-", "").split())


# ── Settlement gate ──────────────────────────────────────────────────────────

def last_gameday(breakout: pd.DataFrame) -> date | None:
    """Date of the final NFL game counted in this fantasy week, or None."""
    if breakout is None or breakout.empty or "gameday" not in breakout.columns:
        return None
    days = pd.to_datetime(breakout["gameday"], errors="coerce").dropna()
    return days.max().date() if not days.empty else None


def settles_at(breakout: pd.DataFrame) -> datetime | None:
    """First Tuesday strictly after the week's last game, at ``SETTLE_HOUR`` ET."""
    day = last_gameday(breakout)
    if day is None:
        return None
    ahead = (1 - day.weekday()) % 7 or 7          # Monday=0, Tuesday=1
    tuesday = day + timedelta(days=ahead)
    return datetime(tuesday.year, tuesday.month, tuesday.day,
                    SETTLE_HOUR, tzinfo=LEAGUE_TZ)


def is_settled(breakout: pd.DataFrame, now: datetime | None = None) -> bool:
    """True once stat corrections for the week should be final."""
    when = settles_at(breakout)
    if when is None:
        return False
    now = now or datetime.now(LEAGUE_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=LEAGUE_TZ)
    return now >= when


# ── Rule helpers ─────────────────────────────────────────────────────────────

def _extreme(scores: dict, want_max: bool = True) -> list[str]:
    """Teams tied at the best value. Shared wins are real — 2020 W4 had three."""
    scores = {t: v for t, v in scores.items() if pd.notna(v)}
    if not scores:
        return []
    best = max(scores.values()) if want_max else min(scores.values())
    return sorted(t for t, v in scores.items() if v == best)


def _by_team(df: pd.DataFrame, col: str, how: str) -> dict:
    if df.empty:
        return {}
    return getattr(df.groupby("team")[col], how)().round(2).to_dict()


def _starters(ctx):  return ctx.breakout[ctx.breakout["starter"] == 1]
def _bench(ctx):     return ctx.breakout[ctx.breakout["starter"] == 0]


class Ctx:
    """Everything a rule is allowed to look at."""

    def __init__(self, year, week, breakout, matches, league_id=None):
        self.year = year
        self.week = week
        self.breakout = breakout
        self.matches = matches
        self.league_id = league_id


# ── Rules ────────────────────────────────────────────────────────────────────

def r_high_score(ctx):
    return _extreme(_by_team(_starters(ctx), "points", "sum"))


def r_bench_total(ctx):
    return _extreme(_by_team(_bench(ctx), "points", "sum"))


def r_blackjack(ctx):
    st = _starters(ctx)
    return _extreme(_by_team(st[st["points"] <= 21], "points", "max"))


def r_k_def(ctx):
    st = _starters(ctx)
    return _extreme(_by_team(st[st["position"].isin(["K", "DEF"])], "points", "sum"))


def r_smallest_win(ctx):
    won = ctx.matches[ctx.matches["Margin"] > 0]
    return _extreme(dict(zip(won["Team"], won["Margin"].round(2))), want_max=False)


def r_biggest_win(ctx):
    won = ctx.matches[ctx.matches["Margin"] > 0]
    return _extreme(dict(zip(won["Team"], won["Margin"].round(2))))


def r_boom_bust(ctx):
    g = _starters(ctx).groupby("team")["points"]
    return _extreme((g.max() - g.min()).round(2).to_dict())


def r_over_15(ctx):
    st = _starters(ctx)
    counts = st[st["points"] > 15].groupby("team").size().to_dict()
    # Teams with zero qualifying starters still need to appear.
    for team in st["team"].unique():
        counts.setdefault(team, 0)
    return _extreme(counts)


def r_biggest_loser(ctx):
    lost = ctx.matches[ctx.matches["Margin"] < 0]
    return _extreme(dict(zip(lost["Team"], lost["Total"].round(2))))


def r_dead_weight(ctx):
    winners = set(ctx.matches[ctx.matches["Margin"] > 0]["Team"])
    st = _starters(ctx)
    st = st[st["team"].isin(winners)]
    return _extreme(_by_team(st, "points", "min"), want_max=False)


def r_best_te(ctx):
    te = ctx.breakout[ctx.breakout["position"] == "TE"]
    return _extreme(_by_team(te, "points", "max"))


def r_worst_def(ctx):
    d = ctx.breakout[ctx.breakout["position"] == "DEF"]
    return _extreme(_by_team(d, "points", "min"), want_max=False)


def r_closest_to_30(ctx):
    st = _starters(ctx).copy()
    st["gap"] = (st["points"] - 30).abs()
    return _extreme(_by_team(st, "gap", "min"), want_max=False)


def r_flex(ctx):
    """Highest FLEX score. The flex slot lives in the matches frame, not breakout."""
    if "WRT" not in ctx.matches.columns:
        return []
    scores = {}
    for team, cell in zip(ctx.matches["Team"], ctx.matches["WRT"]):
        if isinstance(cell, dict) and cell:
            scores[team] = round(max(cell.values()), 2)
    return _extreme(scores)


def r_rush_yards(ctx):
    return _extreme(_by_team(ctx.breakout, "rushing_yards", "sum"))


def r_best_rb_rush(ctx):
    """Desc is silent on bench; history settles it at starters (2/2 vs 1/2)."""
    rb = _starters(ctx)
    return _extreme(_by_team(rb[rb["position"] == "RB"], "rushing_yards", "max"))


def r_best_wr_recs(ctx):
    """Desc is silent on bench; starters is the best-fitting reading."""
    wr = _starters(ctx)
    return _extreme(_by_team(wr[wr["position"] == "WR"], "receptions", "max"))


def r_offensive_tds(ctx):
    """Passing TDs count. The intuition that they would double-count a QB->WR
    score is wrong in practice, and the league has scored it this way: including
    them reproduces 6 of 7 historical weeks, excluding them only 4."""
    st = _starters(ctx).copy()
    st["tds"] = (st["passing_tds"].fillna(0) + st["rushing_tds"].fillna(0)
                 + st["receiving_tds"].fillna(0))
    return _extreme(_by_team(st, "tds", "sum"))


def r_qb_completion_pct(ctx):
    qb = _starters(ctx)
    qb = qb[(qb["position"] == "QB") & (qb["attempts"] > 10)].copy()
    if qb.empty:
        return []
    qb["pct"] = (qb["completions"] / qb["attempts"] * 100).round(2)
    return _extreme(_by_team(qb, "pct", "max"))


def r_nfl_franchise(ctx):
    df = ctx.breakout.dropna(subset=["recent_teams"])
    if df.empty:
        return []
    best = df.groupby(["team", "recent_teams"])["points"].sum().round(2)
    return _extreme(best.groupby("team").max().to_dict())


def r_most_trades(ctx):
    """Completed trades to date. Needs the transactions endpoint, not breakout."""
    import data_loader as dl
    import sleeper_core as sc

    if ctx.league_id is None:
        return []
    roster_map = {int(k): v for k, v in sc.roster_ids.get(ctx.year, {}).items()}
    counts = {name: 0 for name in roster_map.values()}
    for wk in range(1, ctx.week + 1):
        try:
            txns = dl.fetch_transactions_json(ctx.league_id, wk) or []
        except Exception:
            return []          # incomplete data must not crown a winner
        for t in txns:
            if t.get("type") == "trade" and t.get("status") == "complete":
                for rid in (t.get("roster_ids") or []):
                    name = roster_map.get(int(rid))
                    if name in counts:
                        counts[name] += 1
    return _extreme(counts) if any(counts.values()) else []


RULES = {
    "i'm flying, jack":       r_high_score,
    "hot start":              r_high_score,
    "the replacements":       r_bench_total,
    "blackjack":              r_blackjack,
    "big helpers, too":       r_k_def,
    "coffee's for closers":   r_smallest_win,
    "like a boss":            r_biggest_win,
    "the boom & bust":        r_boom_bust,
    "all hands on deck":      r_over_15,
    "biggest loser":          r_biggest_loser,
    "dead weight":            r_dead_weight,
    "keeping it tight":       r_best_te,
    "endzones that way >":    r_worst_def,
    "thirty flirty & thriving": r_closest_to_30,
    "flexual healing":        r_flex,
    "campus rush week":       r_rush_yards,
    "rushmore":               r_best_rb_rush,
    "immaculate":             r_best_wr_recs,
    "look at these tds":      r_offensive_tds,
    "go long":                r_qb_completion_pct,
    "nfl franchise week":     r_nfl_franchise,
    "please not the jets":    r_most_trades,
    "please not the jets (trade deadline week)": r_most_trades,
}

# Not derivable from anything we store. Listed explicitly so the distinction
# between "no rule yet" and "never going to have one" stays visible.
MANUAL_ONLY = {
    "soothsayer":                    "managers submit guesses off-platform",
    "stay on target":                "needs weekly projections, which are not stored",
    "the old man & young buck":      "needs player age; only rookie_year is available",
    "breaking of the tie":           "managers pick the players",
    "breaking of the tie (if needed)": "managers pick the players",
    "tiebreaker":                    "positions are drawn at random",
}


# ── Public API ───────────────────────────────────────────────────────────────

def resolve_week(year, week, cfg, breakout=None, matches=None,
                 league_id=None, now=None):
    """Resolve one week. Returns ``(winner_string, source)``."""
    manual = (cfg.get("winner") or "").strip()
    if manual:
        return manual, MANUAL

    key = norm_name(cfg.get("name", ""))
    rule = RULES.get(key)
    if rule is None:
        return "", UNSUPPORTED

    if breakout is None or breakout.empty or matches is None or matches.empty:
        return "", NO_DATA

    if not is_settled(breakout, now):
        return "", PENDING

    try:
        winners = rule(Ctx(year, week, breakout, matches, league_id))
    except Exception:
        return "", NO_DATA

    return " & ".join(winners), (COMPUTED if winners else NO_DATA)


def resolved_season_config(year, now=None):
    """``SIDE_BET_SEASONS[year]`` with every derivable winner filled in.

    Each week gains a ``source`` key so callers can tell a computed winner from
    a hand-entered one. Weeks whose data is not cached are returned untouched.
    """
    import sleeper_core as sc

    base = sc.SIDE_BET_SEASONS.get(year, {})
    league_id = sc.leagueNumbers_Dict.get(year)
    out = {}
    for week, cfg in base.items():
        breakout = sc.AllBreakoutDict.get(year, {}).get(week)
        matches = sc.AllMatchesDict.get(year, {}).get(week)
        winner, source = resolve_week(year, week, cfg, breakout, matches,
                                      league_id, now)
        if source == COMPUTED:
            winner = sc.canonical_names_str(winner)
        out[week] = {**cfg, "winner": winner, "source": source}
    return out
