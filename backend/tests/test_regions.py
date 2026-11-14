"""Region names are compared as text everywhere: they must have ONE canonical spelling."""
from datetime import date
from types import SimpleNamespace as NS

import pytest

from app.services.lookups import norm_region, region_segments


@pytest.mark.parametrize("raw,expected", [
    ("Djerba", "Djerba"), ("Djerba ", "Djerba"), (" djerba", "Djerba"), ("DJERBA", "Djerba"),
    ("djerba   nord", "Djerba Nord"), ("Nord-Ouest", "Nord-Ouest"), ("", ""), (None, ""),
])
def test_norm_region(raw, expected):
    assert norm_region(raw) == expected


def _periods(*rows):
    return {1: [NS(effective_from=f, effective_to=t, region=r) for f, t, r in rows]}


def test_bus_that_never_moved_is_one_segment():
    segs = region_segments(NS(id=1, region="Sousse"), date(2026, 5, 1), date(2026, 5, 31), {})
    assert len(segs) == 1 and segs[0]["days"] == 31


def test_move_splits_the_window_exactly_and_ignores_spelling_noise():
    bus = NS(id=1, region="Djerba")
    per = _periods((date(2026, 1, 1), date(2026, 5, 12), "SOUSSE "), (date(2026, 5, 13), None, " djerba"))
    segs = region_segments(bus, date(2026, 5, 1), date(2026, 5, 31), per)
    assert [(s["region"], s["days"]) for s in segs] == [("Sousse", 12), ("Djerba", 19)]
    assert segs[0]["to"] == date(2026, 5, 12) and segs[1]["from"] == date(2026, 5, 13)


def test_spelling_difference_alone_never_creates_a_fake_move():
    bus = NS(id=1, region="Djerba")
    per = _periods((date(2026, 5, 1), date(2026, 5, 15), "Djerba"), (date(2026, 5, 16), None, "Djerba "))
    assert len(region_segments(bus, date(2026, 5, 1), date(2026, 5, 31), per)) == 1
