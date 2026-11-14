"""The calendar grid, end to end on a throw-away database."""
from datetime import date

import pytest

from app import models
from app.core.database import Base, SessionLocal, engine
from app.services.calendar import build_calendar

D = date


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    yield s
    s.close()


def _bus(db, i, name, region):
    db.add(models.Bus(id=i, name=name, type="MICRO", region=region, sort_order=i, distance=0))


def _contract(db, bus, s, e, loyer, label="c"):
    db.add(models.Contract(bus_id=bus, start_date=s, end_date=e, loyer=loyer, label=label))


def _trip(db, bus, day, total=500):
    db.add(models.Booking(bus_id=bus, date=day, type="Booking", destination="X", total=total,
                          heure_debut="08:00", heure_fin="12:00"))


def test_a_region_is_one_block_whatever_its_spelling(db):
    for i, region in enumerate(["Djerba", "Sousse", "Djerba ", "djerba"], start=1):
        _bus(db, i, f"B{i}", region)
        _contract(db, i, D(2026, 5, 1), D(2026, 5, 31), 100)
    db.commit()
    regions = [b["region"] for b in build_calendar(db, 2026, 5)["buses"]]
    assert regions == ["Djerba", "Djerba", "Djerba", "Sousse"]          # contiguous, one Djerba block


def test_contract_change_between_regions_gives_one_row_per_contract(db):
    _bus(db, 1, "MOVER", "Djerba")
    _contract(db, 1, D(2026, 5, 1), D(2026, 5, 12), 600, "A")
    _contract(db, 1, D(2026, 5, 13), D(2026, 5, 31), 900, "B")
    db.add(models.BusRegionPeriod(bus_id=1, region="Sousse", effective_from=D(2026, 1, 1), effective_to=D(2026, 5, 12)))
    db.add(models.BusRegionPeriod(bus_id=1, region="Djerba", effective_from=D(2026, 5, 13), effective_to=None))
    for day in (3, 10, 15, 25):
        _trip(db, 1, D(2026, 5, day))
    db.commit()

    rows = build_calendar(db, 2026, 5)["buses"]
    by_region = {r["region"]: r for r in rows}
    assert set(by_region) == {"Sousse", "Djerba"}
    assert sorted(by_region["Sousse"]["days"]) == [3, 10] and sorted(by_region["Djerba"]["days"]) == [15, 25]
    assert by_region["Sousse"]["loyer"] == 600 and by_region["Djerba"]["loyer"] == 900
    assert by_region["Sousse"]["revenue"] == 1000 and by_region["Djerba"]["revenue"] == 1000
    # every day of the month is covered exactly once across the two rows
    assert sum(len(r["covered_days"]) for r in rows) == 31


def test_region_totals_add_up_to_all_contracts(db):
    _bus(db, 1, "A", "Djerba")
    _bus(db, 2, "B", "Sousse")
    _bus(db, 3, "C", "Djerba")
    _contract(db, 1, D(2026, 5, 1), D(2026, 5, 31), 1000)
    _contract(db, 2, D(2026, 5, 1), D(2026, 5, 31), 900)
    _contract(db, 3, D(2026, 5, 1), D(2026, 5, 12), 300, "A")
    _contract(db, 3, D(2026, 5, 13), D(2026, 5, 31), 400, "B")
    db.add(models.BusRegionPeriod(bus_id=3, region="Sousse", effective_from=D(2026, 1, 1), effective_to=D(2026, 5, 12)))
    db.add(models.BusRegionPeriod(bus_id=3, region="Djerba", effective_from=D(2026, 5, 13), effective_to=None))
    db.commit()
    summary = build_calendar(db, 2026, 5)["summary"]
    assert summary["total"]["loyer"] == 1000 + 900 + 300 + 400
    assert sum(r["loyer"] for r in summary["regions"]) == summary["total"]["loyer"]
    assert summary["total"]["count"] == 3                # a vehicle that moved is still ONE vehicle


def test_vehicle_without_contract_is_not_on_the_calendar(db):
    _bus(db, 1, "NOCONTRACT", "Djerba")
    db.commit()
    assert build_calendar(db, 2026, 5)["buses"] == []
