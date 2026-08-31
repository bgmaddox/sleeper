"""Drift check: config/roster_ids.json vs. the live Sleeper league.

Manager names are a deliberate frozen snapshot — Sleeper only exposes *current*
display names, so deriving them live would rewrite history on every rename. The
cost of freezing them is that a roster change goes unnoticed until someone spots
a departed manager on a chart mid-season. This test is that someone.

Marked slow because it is the one test that talks to the network; the default
`-m "not slow"` run skips it. Run it deliberately after a roster change:

    .venv/bin/pytest tests/test_roster_drift.py -m slow -q

A failure here is not a code bug — it means config/roster_ids.json needs the
new usernames for the current season (slot numbers stay put; a new manager
inherits the slot, and its color, from the one they replaced).
"""

import json
import os
import sys
import urllib.error
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import sleeper_core as core  # noqa: E402

pytestmark = pytest.mark.slow


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        pytest.skip(f"Sleeper API unreachable: {e}")


@pytest.fixture(scope="module")
def live_slots():
    """{roster_slot: display_name} straight from Sleeper for the current season."""
    year = core.CURRENT_SEASON
    league_id = core.leagueNumbers_Dict.get(year)
    if not league_id:
        pytest.skip(f"no league id configured for {year}")
    users = _get(f"https://api.sleeper.app/v1/league/{league_id}/users")
    rosters = _get(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    by_id = {u["user_id"]: core.canonical_name(u["display_name"]) for u in users}
    return {r["roster_id"]: by_id.get(r.get("owner_id")) for r in rosters}


def test_every_slot_has_an_owner(live_slots):
    """An ownerless slot means the league is mid-turnover — names can't be
    trusted yet, and the swap isn't ready to be written down."""
    orphaned = sorted(s for s, name in live_slots.items() if name is None)
    assert not orphaned, (
        f"roster slots {orphaned} have no owner on Sleeper yet — someone has "
        f"left and their replacement hasn't joined. Re-run once the league is full."
    )


def test_config_matches_the_live_league(live_slots):
    year = core.CURRENT_SEASON
    configured = core.roster_ids.get(year, {})

    drift = {
        slot: (configured.get(slot), live)
        for slot, live in sorted(live_slots.items())
        if live is not None and configured.get(slot) != live
    }
    assert not drift, (
        f"config/roster_ids.json is stale for {year}. Update these slots "
        f"(slot: configured -> live): "
        + ", ".join(f"{s}: {old!r} -> {now!r}" for s, (old, now) in drift.items())
    )


def test_slot_count_matches(live_slots):
    year = core.CURRENT_SEASON
    assert len(core.roster_ids.get(year, {})) == len(live_slots), (
        f"{year} has {len(live_slots)} rosters on Sleeper but "
        f"{len(core.roster_ids.get(year, {}))} in config/roster_ids.json"
    )
