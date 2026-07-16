"""Tests for the shared TeamColorsMixin (Session 10 boilerplate consolidation)."""
import plotly.graph_objects as go
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import sleeper_core as sc


class _Dummy(sc.TeamColorsMixin):
    def __init__(self, year=2025):
        self.year = year


def test_subclasses_use_mixin():
    for cls in (sc.Week, sc.Season, sc.AllTime, sc.SideBet):
        assert issubclass(cls, sc.TeamColorsMixin)


def test_set_team_colors_default_and_override():
    d = _Dummy()
    d.SetTeamColors()
    assert d.teamcolors == sc.get_slot_teamcolors(2025)
    d.SetTeamColors({'TeamA': '#fff'})
    assert d.teamcolors == {'TeamA': '#fff'}


def test_update_colors_styles_yaxis_labels():
    d = _Dummy()
    d.SetTeamColors({'TeamA': '#123456'})
    fig = go.Figure(go.Bar(x=[1, 2], y=['TeamA', 'TeamB'], orientation='h'))
    out = d.UpdateColors(fig)
    assert out.layout.yaxis.ticktext == (
        "<span style='color:#123456'>TeamA</span>",
        "<span style='color:white'>TeamB</span>",  # unknown team falls back to white
    )


def test_update_colors_empty_fig_passthrough():
    d = _Dummy()
    d.SetTeamColors({})
    fig = go.Figure()
    assert d.UpdateColors(fig) is fig


def test_update_colors2_uses_other_objects_colors():
    d = _Dummy()
    d.SetTeamColors({'TeamA': '#111111'})
    other = _Dummy()
    other.SetTeamColors({'TeamA': '#abcdef'})
    fig = go.Figure(go.Bar(x=[1], y=['TeamA'], orientation='h'))
    out = d.UpdateColors2(other, fig)
    assert '#abcdef' in out.layout.yaxis.ticktext[0]
