"""Fuel entry works the same for EVERY year (2025 included), and counts in the results."""
from datetime import date

import pytest
from fastapi import HTTPException

from app import models, schemas
from app.controllers.fuel import list_fuel, upsert_fuel
from app.core.database import Base, SessionLocal, engine
from app.services.analytics import build_analytics
from app.services.calendar import build_calendar
from app.services.contracts import compute_contract_result

YEARS = (2025, 2026, 2027)


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    s.add(models.Bus(id=1, name="BUS 1", type="MICRO", region="Sousse", sort_order=1, distance=0))
    s.commit()
    yield s
    s.close()


def put(db, year, month, **fields):
    return upsert_fuel(schemas.FuelUpsert(bus_id=1, year=year, month=month, **fields), db, _admin="t")


@pytest.mark.parametrize("year", YEARS)
def test_every_month_of_every_year_can_be_entered(db, year):
    for month in range(1, 13):
        put(db, year, month, estimated=100 + month)
        put(db, year, month, actual=200 + month)
    rows = list_fuel(bus_id=1, db=db)
    assert [(r.year, r.month, r.estimated, r.actual) for r in rows] == [(year, m, 100 + m, 200 + m) for m in range(1, 13)]


@pytest.mark.parametrize("year", YEARS)
def test_fuel_counts_in_the_contract_calendar_and_analysis_the_same_way_every_year(db, year):
    contract = models.Contract(bus_id=1, start_date=date(year, 3, 1), end_date=date(year, 3, 31), loyer=1000, label="c")
    db.add(contract)
    db.add(models.Booking(bus_id=1, date=date(year, 3, 10), type="Booking", destination="X", total=5000))
    db.commit()
    put(db, year, 3, estimated=600)
    assert compute_contract_result(db, contract)["net"] == 5000 - 1000 - 600
    assert compute_contract_result(db, contract)["is_estimated"] is True
    put(db, year, 3, actual=750)                                # the real amount replaces the estimate
    res = compute_contract_result(db, contract)
    assert res["fuel"] == 750 and res["net"] == 3250 and res["is_estimated"] is False
    assert build_calendar(db, year, 3)["buses"][0]["net"] == 3250
    assert build_analytics(db, year, 3)["buses"][0]["net"] == 3250


def test_a_value_can_be_cleared_and_only_the_sent_field_changes(db):
    put(db, 2025, 1, estimated=300)
    put(db, 2025, 1, actual=350)
    put(db, 2025, 1, actual=None)                               # box emptied
    row = list_fuel(bus_id=1, db=db)[0]
    assert row.actual is None and row.estimated == 300
    put(db, 2025, 1, estimated=None)
    assert list_fuel(bus_id=1, db=db)[0].estimated == 0


@pytest.mark.parametrize("bad", [{"month": 13, "year": 2025}, {"month": 1, "year": 1900}])
def test_invalid_month_or_year_is_refused(db, bad):
    with pytest.raises(HTTPException) as e:
        put(db, bad["year"], bad["month"], estimated=1)
    assert e.value.status_code == 422


def test_negative_amount_and_unknown_vehicle_are_refused(db):
    with pytest.raises(HTTPException) as e:
        put(db, 2025, 1, estimated=-5)
    assert e.value.status_code == 422
    with pytest.raises(HTTPException) as e:
        upsert_fuel(schemas.FuelUpsert(bus_id=99, year=2025, month=1, estimated=1), db, _admin="t")
    assert e.value.status_code == 404
