"""Vehicle create / edit through the controller functions (regression: the new optional end date)."""
from datetime import date, timedelta

import pytest

from app import models, schemas
from app.controllers.buses import create_bus, update_bus
from app.core.database import Base, SessionLocal, engine


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    yield s
    s.close()


def test_a_new_vehicle_can_be_created_with_the_region_window_fields_present(db):
    body = schemas.BusCreate(name="BUS NEW 1 TU 1", plate="1 TU 1", type="MICRO", region="Sousse", distance=0,
                             region_effective_from=None, region_effective_to=None)
    bus = create_bus(body, db, _admin="t")
    assert bus.id and bus.region == "Sousse"


def test_editing_a_vehicle_region_over_an_exact_window_adds_one_period(db):
    bus = create_bus(schemas.BusCreate(name="B", plate="1", type="MICRO", region="Sousse", distance=0), db, _admin="t")
    f, t = date.today() - timedelta(days=60), date.today() - timedelta(days=30)
    db.add(models.Contract(bus_id=bus.id, start_date=f, end_date=t, loyer=1)); db.commit()
    update_bus(bus.id, schemas.BusCreate(name="B", plate="1", type="MICRO", region="Djerba", distance=0,
                                         region_effective_from=f, region_effective_to=t), db, _admin="t")
    per = db.query(models.BusRegionPeriod).all()
    assert [(p.region, p.effective_from, p.effective_to) for p in per] == [("Djerba", f, t)]
    assert db.get(models.Bus, bus.id).region == "Sousse"        # a past window never changes "now"
