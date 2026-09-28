"""?week= deep links (webapp/app.py _url_week).

Links like legacy.bgmaddox.com/?tab=week&year=2025&week=3 — and the 301s from
the old /legacy URLs, which preserve the query string — used to open on the
season's default week because the parser read only tab and year.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "webapp"))
os.environ.setdefault("SLEEPER_SKIP_EAGER_LOAD", "1")

app = pytest.importorskip("app", reason="webapp/app.py not importable")


def test_week_applies_to_the_linked_year():
    assert app._url_week('?tab=week&year=2025&week=3', 2025, 17) == 3


def test_week_is_ignored_for_other_years():
    """Switching seasons must not drag the link's week along."""
    assert app._url_week('?tab=week&year=2025&week=3', 2024, 17) is None


def test_link_without_year_means_the_current_season():
    assert app._url_week('?week=2', app.CURRENT_YEAR, 4) == 2
    assert app._url_week('?week=2', app.CURRENT_YEAR - 1, 17) is None


@pytest.mark.parametrize('search', ['', None, '?tab=week', '?year=2025&week=x',
                                    '?year=2025&week=0', '?year=2025&week=18'])
def test_invalid_or_missing_week_is_ignored(search):
    assert app._url_week(search, 2025, 17) is None
