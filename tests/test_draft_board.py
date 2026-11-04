"""Draft Board Replay payload (webapp/app.py _draft_board_payload).

The board used to derive each pick's column from a plain snake (odd rounds
left-to-right), which put every pick from round 3 on in the wrong column: the
league has used a 3rd-round reversal every season since 2020. Columns now come
from Sleeper's own draft_slot.
"""
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "webapp"))
os.environ.setdefault("SLEEPER_SKIP_EAGER_LOAD", "1")

app = pytest.importorskip("app", reason="webapp/app.py not importable")

TEAMS = ['ann', 'bob', 'cat']


def _reversal_draft(rounds=4, reversal=3):
    """Picks as Sleeper returns them for a 3-team snake with a reversal round."""
    rows, pick_no = [], 1
    for rnd in range(1, rounds + 1):
        # Snake flips every round, except the reversal round repeats the previous direction
        forward = (rnd % 2 == 1) != (rnd >= reversal)
        order = [1, 2, 3] if forward else [3, 2, 1]
        for slot in order:
            rows.append({'round': rnd, 'pick_no': pick_no, 'draft_slot': slot,
                         'roster_id': TEAMS[slot - 1], 'player_name': f'P{pick_no}',
                         'metadata.position': 'WR'})
            pick_no += 1
    return pd.DataFrame(rows)


def test_round_three_reversal_keeps_each_team_in_its_column():
    payload = app._draft_board_payload(_reversal_draft(), {}, {}, 2025)
    for p in payload['picks']:
        assert TEAMS[p['slot'] - 1] == p['team'], p
    r3 = sorted((p for p in payload['picks'] if p['round'] == 3), key=lambda p: p['pick'])
    assert [p['slot'] for p in r3] == [3, 2, 1]   # same direction as round 2


def test_columns_are_headed_by_their_team():
    colors = {'ann': '#111111', 'bob': '#222222', 'cat': '#333333'}
    payload = app._draft_board_payload(_reversal_draft(), {}, colors, 2025)
    assert payload['slots'] == [
        {'slot': 1, 'team': 'ann', 'color': '#111111'},
        {'slot': 2, 'team': 'bob', 'color': '#222222'},
        {'slot': 3, 'team': 'cat', 'color': '#333333'},
    ]
