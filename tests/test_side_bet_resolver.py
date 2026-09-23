"""
Automatic side bet winner resolution.

Covers the settlement gate (nothing resolves before the Tuesday after the
week's last game), the manual-override precedence, and a backtest of every
rule against the winners that were hand-entered across 2019–2025.

The backtest is the load-bearing test: it is the only thing standing between a
refactor and the app confidently announcing the wrong winner.

Run: pytest tests/test_side_bet_resolver.py -q
"""
import os
import sys
from datetime import datetime, date

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import data_loader as dl
import sleeper_core as core
import side_bet_resolver as R


# ── Settlement gate (pure — no season data required) ─────────────────────────

def _breakout_with_gamedays(days):
    return pd.DataFrame({"gameday": days, "points": [0.0] * len(days)})


@pytest.mark.parametrize("last_game,expected_tuesday", [
    ("2026-09-14", date(2026, 9, 15)),   # Monday night  -> next day
    ("2026-09-13", date(2026, 9, 15)),   # Sunday        -> two days later
    ("2026-09-10", date(2026, 9, 15)),   # Thursday-only -> following Tuesday
    ("2026-09-15", date(2026, 9, 22)),   # Tuesday game  -> a week later
])
def test_settles_on_the_tuesday_after_the_last_game(last_game, expected_tuesday):
    b = _breakout_with_gamedays(["2026-09-10", last_game])
    assert R.settles_at(b).date() == expected_tuesday


def test_last_gameday_ignores_missing_dates():
    b = _breakout_with_gamedays(["2026-09-13", None, "2026-09-14"])
    assert R.last_gameday(b) == date(2026, 9, 14)


def test_not_settled_before_cutoff_and_settled_after():
    b = _breakout_with_gamedays(["2026-09-14"])          # Monday
    monday_night = datetime(2026, 9, 14, 23, 0, tzinfo=R.LEAGUE_TZ)
    tuesday_early = datetime(2026, 9, 15, 8, 0, tzinfo=R.LEAGUE_TZ)
    tuesday_noon = datetime(2026, 9, 15, R.SETTLE_HOUR, 0, tzinfo=R.LEAGUE_TZ)

    assert not R.is_settled(b, monday_night)
    assert not R.is_settled(b, tuesday_early)
    assert R.is_settled(b, tuesday_noon)


def test_no_gameday_data_never_settles():
    assert R.settles_at(pd.DataFrame({"points": [1.0]})) is None
    assert not R.is_settled(pd.DataFrame({"points": [1.0]}))


# ── Name normalisation and coverage ──────────────────────────────────────────

def test_norm_name_collapses_spelling_drift():
    assert R.norm_name("I'm flying, Jack!") == R.norm_name("I'm Flying, Jack!")
    assert R.norm_name("  Go   Long ") == "go long"


def test_every_configured_challenge_is_classified():
    """A new season must not introduce a challenge nobody has triaged.

    Every name is either automatable (RULES) or explicitly declared manual.
    Failing this means a challenge would silently sit at TBD forever.
    """
    unclassified = set()
    for weeks in core.SIDE_BET_SEASONS.values():
        for cfg in weeks.values():
            key = R.norm_name(cfg["name"])
            if key not in R.RULES and key not in R.MANUAL_ONLY:
                unclassified.add(cfg["name"])
    assert not unclassified, f"unclassified challenges: {sorted(unclassified)}"


# ── Resolution precedence ────────────────────────────────────────────────────

def test_manual_winner_always_wins():
    """A hand-entered winner is never second-guessed, even by a live rule."""
    cfg = {"name": "I'm Flying, Jack!", "desc": "", "winner": "someone"}
    winner, source = R.resolve_week(2026, 1, cfg, None, None)
    assert (winner, source) == ("someone", R.MANUAL)


def test_unknown_challenge_stays_blank():
    cfg = {"name": "Soothsayer", "desc": "", "winner": ""}
    winner, source = R.resolve_week(2026, 1, cfg, None, None)
    assert winner == "" and source == R.UNSUPPORTED


def test_missing_data_stays_blank():
    cfg = {"name": "Blackjack", "desc": "", "winner": ""}
    winner, source = R.resolve_week(2026, 99, cfg, None, None)
    assert winner == "" and source == R.NO_DATA


# ── Season-data tests ────────────────────────────────────────────────────────

CONFIG_YEARS = sorted(core.SIDE_BET_SEASONS)


@pytest.fixture(scope="module")
def loaded_years():
    """Load every season that has a cache. Skips if fewer than two are present."""
    years = []
    for y in CONFIG_YEARS:
        if os.path.exists(dl.season_cache_path(y)):
            dl.load_data_for_year(y, verbose=False)
            years.append(y)
    if len(years) < 2:
        pytest.skip("need at least two cached seasons to backtest")
    return years


def _historical_cases(years):
    for y in years:
        lid = core.leagueNumbers_Dict.get(y)
        for wk, cfg in core.SIDE_BET_SEASONS.get(y, {}).items():
            hand = (cfg.get("winner") or "").strip()
            rule = R.RULES.get(R.norm_name(cfg["name"]))
            breakout = core.AllBreakoutDict.get(y, {}).get(wk)
            matches = core.AllMatchesDict.get(y, {}).get(wk)
            if not hand or rule is None or breakout is None or matches is None \
                    or breakout.empty or matches.empty:
                continue
            yield y, wk, cfg, hand, rule, breakout, matches, lid


def _names(s):
    return {p.strip() for p in s.split("&") if p.strip()}


def test_backtest_against_hand_entered_winners(loaded_years):
    """Rules must keep reproducing the winners the league recorded by hand.

    Seven weeks are known not to match. Three were verified as bookkeeping
    errors in the hand entry (the data unambiguously says otherwise); the rest
    are challenges with only one or two historical data points. The threshold
    guards the other ~90% against regression.
    """
    hits = misses = 0
    failed = []
    for y, wk, cfg, hand, rule, b, m, lid in _historical_cases(loaded_years):
        got = rule(R.Ctx(y, wk, b, m, lid))
        pred = core.canonical_names_str(" & ".join(got)) if got else ""
        if _names(pred) == _names(core.canonical_names_str(hand)):
            hits += 1
        else:
            misses += 1
            failed.append(f"{y}W{wk} {cfg['name']}: hand={hand} computed={pred or '-'}")

    total = hits + misses
    assert total >= 40, f"only {total} testable weeks — cache may be incomplete"
    assert hits / total >= 0.90, (
        f"backtest accuracy {hits}/{total} = {hits/total:.1%} (want >= 90%)\n  "
        + "\n  ".join(failed)
    )


def test_starter_flags_match_reported_totals(loaded_years):
    """Several rules sum starter points; that must equal the league's own total.

    This is what proved the disagreeing 2019 and 2024 weeks were hand-entry
    errors rather than a data problem, so it is worth pinning down.
    """
    for y in loaded_years:
        for wk, b in core.AllBreakoutDict.get(y, {}).items():
            m = core.AllMatchesDict.get(y, {}).get(wk)
            if m is None or b is None or b.empty:
                continue
            summed = b[b.starter == 1].groupby("team")["points"].sum().round(2)
            for team, total in zip(m["Team"], m["Total"].round(2)):
                assert abs(summed.get(team, float("nan")) - total) < 0.05, \
                    f"{y} W{wk} {team}: starters sum to {summed.get(team)} but total is {total}"


def test_resolved_config_preserves_every_week(loaded_years):
    for y in loaded_years:
        resolved = core.resolved_side_bets(y)
        assert set(resolved) == set(core.SIDE_BET_SEASONS[y])
        for wk, cfg in resolved.items():
            assert cfg["source"] in {R.MANUAL, R.COMPUTED, R.PENDING,
                                     R.NO_DATA, R.UNSUPPORTED}
            assert cfg["name"] == core.SIDE_BET_SEASONS[y][wk]["name"]


def test_resolver_never_overrides_a_hand_entered_winner(loaded_years):
    for y in loaded_years:
        resolved = core.resolved_side_bets(y)
        for wk, cfg in core.SIDE_BET_SEASONS[y].items():
            hand = (cfg.get("winner") or "").strip()
            if hand:
                assert resolved[wk]["winner"] == hand
                assert resolved[wk]["source"] == R.MANUAL


def test_unsettled_week_reports_pending(loaded_years):
    """A week resolves as pending when asked before its Tuesday."""
    for y in loaded_years:
        for wk, cfg in core.SIDE_BET_SEASONS.get(y, {}).items():
            if (cfg.get("winner") or "").strip():
                continue
            b = core.AllBreakoutDict.get(y, {}).get(wk)
            m = core.AllMatchesDict.get(y, {}).get(wk)
            if b is None or m is None or b.empty or R.settles_at(b) is None:
                continue
            if R.norm_name(cfg["name"]) not in R.RULES:
                continue
            just_before = R.settles_at(b).replace(hour=R.SETTLE_HOUR - 1)
            _, source = R.resolve_week(y, wk, cfg, b, m, None, just_before)
            assert source == R.PENDING
            return
    pytest.skip("no unsettled, rule-backed, blank week available")
