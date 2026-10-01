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


# ── One color per person, site-wide ─────────────────────────────────────────
# config/team_colors.json is the single source. A manager's color must not
# change between a season tab and an all-time tab, or between seasons.

SURFACE = '#163146'   # card background the colors are drawn on


def _lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(hex_):
    return [int(hex_[i:i + 2], 16) for i in (1, 3, 5)]


def _contrast(a, b):
    def lum(h):
        r, g, bl = (_lin(c) for c in _rgb(h))
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _oklab_delta(a, b):
    """OKLab distance ×100 — the same measure the palette validator uses."""
    def ok(h):
        r, g, bl = (_lin(c) for c in _rgb(h))
        l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * bl) ** (1 / 3)
        m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * bl) ** (1 / 3)
        s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * bl) ** (1 / 3)
        return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)
    return 100 * sum((x - y) ** 2 for x, y in zip(ok(a), ok(b))) ** 0.5


def test_every_manager_has_a_color():
    everyone = {n for slots in sc.roster_ids.values() for n in slots.values()}
    missing = everyone - set(sc.TEAM_COLORS)
    assert not missing, f"add these managers to config/team_colors.json: {sorted(missing)}"


def test_color_follows_the_person_across_seasons_and_tabs():
    alltime = sc.get_alltime_teamcolors()
    for year in sc.roster_ids:
        for name, color in sc.get_slot_teamcolors(year).items():
            assert color == alltime[name] == sc.TEAM_COLORS[name], (year, name)


def test_colors_are_unique():
    assert len(set(sc.TEAM_COLORS.values())) == len(sc.TEAM_COLORS)


def test_every_color_is_readable_on_the_card_background():
    weak = {n: round(_contrast(c, SURFACE), 2) for n, c in sc.TEAM_COLORS.items()
            if _contrast(c, SURFACE) < 3.0}
    assert not weak, f"below 3:1 against {SURFACE}: {weak}"


def test_current_roster_is_distinguishable():
    """Normal-vision floor (ΔE ≥ 15) across every pair in the newest season —
    the managers who share every weekly chart."""
    year = max(sc.roster_ids)
    cols = sc.get_slot_teamcolors(year)
    names = list(cols)
    close = [(a, b, round(_oklab_delta(cols[a], cols[b]), 1))
             for i, a in enumerate(names) for b in names[i + 1:]
             if _oklab_delta(cols[a], cols[b]) < 15]
    assert not close, f"too similar to tell apart: {close}"
