"""Re-assigning a vehicle's region for ANY date window (past or future)."""
from datetime import date, timedelta

import pytest

from app import models
from app.core.database import Base, SessionLocal, engine
from app.services.calendar import build_calendar
from app.services.lookups import region_periods_by_bus, region_on
from app.services.regions import assign_region_range, preview_assign

DAY = timedelta(days=1)
TODAY = date.today()
THIS_MONTH = TODAY.replace(day=1)
LAST_END = THIS_MONTH - DAY                      # last day of the previous month
LAST_START = LAST_END.replace(day=1)
PREV2_END = LAST_START - DAY                     # last day of the month before that
PREV2_START = PREV2_END.replace(day=1)


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    yield s
    s.close()


def _bus(db, region="Sousse", i=1, name="BUS A"):
    b = models.Bus(id=i, name=name, type="MICRO", region=region, sort_order=i, distance=0)
    db.add(b)
    db.flush()
    return b


def _contract(db, bus_id, s, e, loyer=1000):
    db.add(models.Contract(bus_id=bus_id, start_date=s, end_date=e, loyer=loyer, label="c"))


def _trip(db, bus_id, day, total=500):
    db.add(models.Booking(bus_id=bus_id, date=day, type="Booking", destination="X", total=total,
                          heure_debut="08:00", heure_fin="12:00"))


def _region(db, bus, day):
    return region_on(bus, day, region_periods_by_bus(db))


def _periods(db, bus_id=1):
    rows = (db.query(models.BusRegionPeriod).filter_by(bus_id=bus_id)
            .order_by(models.BusRegionPeriod.effective_from).all())
    return [(p.region, p.effective_from, p.effective_to) for p in rows]


def test_past_two_months_move_to_another_region_and_nothing_else_changes(db):
    bus = _bus(db, "Sousse")
    db.commit()
    assign_region_range(db, bus, "Djerba", PREV2_START, LAST_END, "t")
    db.commit()
    assert _region(db, bus, PREV2_START) == "Djerba" and _region(db, bus, LAST_END) == "Djerba"
    assert _region(db, bus, PREV2_START - DAY) == "Sousse"        # before: untouched (default region)
    assert _region(db, bus, THIS_MONTH) == "Sousse"               # after: untouched
    assert bus.region == "Sousse"                                 # a past window never changes "now"


def test_trips_and_totals_follow_the_region(db):
    bus = _bus(db, "Sousse")
    _contract(db, 1, PREV2_START, LAST_END, 1000)
    _trip(db, 1, LAST_START + timedelta(days=4), 500)
    _trip(db, 1, LAST_START + timedelta(days=9), 700)
    db.commit()

    before = build_calendar(db, LAST_START.year, LAST_START.month)
    assert [r["region"] for r in before["buses"]] == ["Sousse"]
    assert {g["region"] for g in before["summary"]["regions"]} == {"Sousse"}

    assign_region_range(db, bus, "Djerba", PREV2_START, LAST_END, "t")
    db.commit()
    after = build_calendar(db, LAST_START.year, LAST_START.month)
    assert [r["region"] for r in after["buses"]] == ["Djerba"]
    regs = {g["region"]: g for g in after["summary"]["regions"]}
    assert set(regs) == {"Djerba"} and regs["Djerba"]["loyer"] == 1000
    # the totals did not change, they only moved: same money, other region
    assert after["summary"]["total"]["net"] == before["summary"]["total"]["net"]
    assert after["buses"][0]["revenue"] == 1200


def test_window_inside_an_existing_period_splits_it_in_three(db):
    bus = _bus(db, "Sousse")
    db.add(models.BusRegionPeriod(bus_id=1, region="Sousse", effective_from=date(2024, 1, 1), effective_to=None))
    db.commit()
    f, t = date(2025, 3, 10), date(2025, 4, 20)
    assign_region_range(db, bus, "Djerba", f, t, "t")
    db.commit()
    assert _periods(db) == [("Sousse", date(2024, 1, 1), f - DAY), ("Djerba", f, t), ("Sousse", t + DAY, None)]


def test_window_spanning_two_periods_trims_both(db):
    bus = _bus(db, "Sousse")
    db.add_all([
        models.BusRegionPeriod(bus_id=1, region="Sousse", effective_from=date(2025, 1, 1), effective_to=date(2025, 3, 31)),
        models.BusRegionPeriod(bus_id=1, region="Tunis", effective_from=date(2025, 4, 1), effective_to=date(2025, 6, 30)),
    ])
    db.commit()
    assign_region_range(db, bus, "Djerba", date(2025, 3, 15), date(2025, 4, 15), "t")
    db.commit()
    assert _periods(db) == [
        ("Sousse", date(2025, 1, 1), date(2025, 3, 14)),
        ("Djerba", date(2025, 3, 15), date(2025, 4, 15)),
        ("Tunis", date(2025, 4, 16), date(2025, 6, 30)),
    ]


def test_window_swallowing_whole_periods_removes_them(db):
    bus = _bus(db, "Sousse")
    db.add_all([
        models.BusRegionPeriod(bus_id=1, region="Sousse", effective_from=date(2025, 2, 1), effective_to=date(2025, 2, 28)),
        models.BusRegionPeriod(bus_id=1, region="Tunis", effective_from=date(2025, 3, 1), effective_to=date(2025, 3, 31)),
    ])
    db.commit()
    assign_region_range(db, bus, "Djerba", date(2025, 1, 1), date(2025, 6, 30), "t")
    db.commit()
    assert _periods(db) == [("Djerba", date(2025, 1, 1), date(2025, 6, 30))]


def test_same_region_neighbours_are_merged(db):
    bus = _bus(db, "Sousse")
    db.add_all([
        models.BusRegionPeriod(bus_id=1, region="Djerba", effective_from=date(2025, 1, 1), effective_to=date(2025, 3, 31)),
        models.BusRegionPeriod(bus_id=1, region="Djerba", effective_from=date(2025, 6, 1), effective_to=date(2025, 8, 31)),
    ])
    db.commit()
    assign_region_range(db, bus, "djerba ", date(2025, 4, 1), date(2025, 5, 31), "t")   # spelling noise too
    db.commit()
    assert _periods(db) == [("Djerba", date(2025, 1, 1), date(2025, 8, 31))]


def test_a_window_containing_today_updates_the_current_region_without_rewriting_the_past(db):
    bus = _bus(db, "Sousse")
    _contract(db, 1, PREV2_START, TODAY + timedelta(days=30))
    db.commit()
    assign_region_range(db, bus, "Djerba", TODAY - timedelta(days=10), TODAY + timedelta(days=10), "t")
    db.commit()
    assert bus.region == "Djerba"                                        # where it is now
    assert _region(db, bus, TODAY - timedelta(days=11)) == "Sousse"     # history before the window is pinned
    assert _region(db, bus, PREV2_START) == "Sousse"
    assert _region(db, bus, TODAY) == "Djerba"


def test_open_ended_window_is_a_move(db):
    bus = _bus(db, "Sousse")
    _contract(db, 1, PREV2_START, TODAY)
    db.commit()
    assign_region_range(db, bus, "Djerba", LAST_START, None, "t")
    db.commit()
    assert bus.region == "Djerba"
    assert _region(db, bus, LAST_START - DAY) == "Sousse" and _region(db, bus, LAST_START) == "Djerba"


def test_preview_reports_exactly_what_will_move_and_writes_nothing(db):
    bus = _bus(db, "Sousse")
    _contract(db, 1, PREV2_START, LAST_END)
    _trip(db, 1, LAST_START + timedelta(days=2), 500)
    _trip(db, 1, LAST_START + timedelta(days=6), 300)
    db.add(models.Booking(bus_id=1, date=LAST_START + timedelta(days=3), type="Unavailable", destination="Entretien"))
    db.commit()

    p = preview_assign(db, bus, "Djerba", LAST_START, LAST_END)
    days = (LAST_END - LAST_START).days + 1
    assert p["days"] == days and p["changed_days"] == days and p["unchanged_days"] == 0
    assert p["trips"] == 2 and p["revenue"] == 800                      # unavailable marks are not revenue
    assert p["from"] == [{"region": "Sousse", "days": days, "trips": 2, "revenue": 800.0}]
    assert _periods(db) == []                                           # a preview never writes

    # a window that is already in the target region changes nothing
    assert preview_assign(db, bus, "Sousse", LAST_START, LAST_END)["changed_days"] == 0
