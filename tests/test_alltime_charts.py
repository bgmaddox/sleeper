"""All-Time record charts: values shown must be the real scores, rounded —
never truncated, never a raw float, never one game counted twice."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import sleeper_core as core  # noqa: E402

pytestmark = pytest.mark.usefixtures("alltime")


def _shown(trace):
    """The label text Plotly will draw for each bar."""
    if trace.texttemplate:
        assert trace.texttemplate in ('%{x:.2f}', '%{x:.1f}'), trace.texttemplate
        return [f'{v:.2f}' for v in trace.x]
    return [str(t) for t in trace.text]


@pytest.mark.parametrize('method', ['HallofFame_Team', 'HallofShame_Team'])
def test_hall_scores_are_rounded_not_truncated(alltime, method):
    fig = getattr(alltime, method)()
    totals = sorted(round(v, 2) for v in fig.data[0].x) if len(fig.data) == 1 else \
        sorted(round(v, 2) for tr in fig.data for v in tr.x)
    table = alltime.Matches.sort_values('Total', ascending=(method == 'HallofShame_Team'))['Total'][:10]
    assert totals == sorted(round(v, 2) for v in table)


def test_highest_scoring_losses_labels_have_two_decimals(alltime):
    fig = alltime.HighestScoringLosers()
    for label in _shown(fig.data[0]):
        whole, _, frac = label.partition('.')
        assert len(frac) <= 2, f'unrounded bar label {label!r}'


def test_smallest_margins_lists_each_game_once(alltime):
    fig = alltime.SmallestMargins()
    xs = [v for tr in fig.data for v in tr.x]
    assert len(xs) == 10, 'top 10 games, one bar each'
    assert all(v >= 0 for v in xs), 'a margin of victory is never negative'
    m = alltime.Matches
    expected = sorted(m.loc[m['Margin'] >= 0, 'Margin'].nsmallest(10).round(2))
    assert sorted(round(v, 2) for v in xs) == expected


# ── Selected-season marker ────────────────────────────────────────────────────
# The All-Time tab passes the season picked in the header; every entry from that
# season gets a star in front of its label.

LISTS = ['HallofFame_Team', 'HallofFame_Player', 'HallofShame_Team',
         'HighestScoringLosers', 'SmallestMargins']


def _labels(fig):
    return {y for tr in fig.data for y in tr.y}


@pytest.mark.parametrize('method', LISTS)
def test_no_star_without_a_selected_year(alltime, method):
    assert not any('\u2605' in l for l in _labels(getattr(alltime, method)()))


@pytest.mark.parametrize('method', LISTS)
def test_star_marks_exactly_the_selected_seasons_entries(alltime, method):
    plain = _labels(getattr(alltime, method)())
    year = int(sorted(plain)[0].replace('</sup>', '').rstrip()[-4:])
    marked = _labels(getattr(alltime, method)(highlight_year=year))
    assert len(marked) == len(plain), 'starring must not merge or drop entries'
    for label in marked:
        from_year = label.replace('</sup>', '').rstrip().endswith(str(year))
        assert label.startswith(core._YEAR_MARK_LABEL) == from_year, label
