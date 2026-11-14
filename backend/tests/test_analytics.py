"""Analyse must cut a month exactly like the Calendrier (same rows, same money)."""
from datetime import date

import pytest

from app import models
from app.core.database import Base, SessionLocal, engine
from app.services.analytics import build_analytics
from app.services.calendar import build_calendar

D = date


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    yield s
    s.close()


def _scenario(db):
    """A vehicle on contract A (Sousse, 1-12 May) then contract B (Djerba, 13-31 May)."""
    db.add(models.Bus(id=1, name="MOVER", type="MICRO", region="Djerba", sort_order=1, distance=0))
    db.add(models.Contract(bus_id=1, start_date=D(2026, 5, 1), end_date=D(2026, 5, 12), loyer=600, label="A"))
    db.add(models.Contract(bus_id=1, start_date=D(2026, 5, 13), end_date=D(2026, 5, 31), loyer=900, label="B"))
    db.add(models.BusRegionPeriod(bus_id=1, region="Sousse", effective_from=D(2026, 1, 1), effective_to=D(2026, 5, 12)))
    db.add(models.BusRegionPeriod(bus_id=1, region="Djerba", effective_from=D(2026, 5, 13), effective_to=None))
    for day in (3, 10, 15, 25):
        db.add(models.Booking(bus_id=1, date=D(2026, 5, day), type="Booking", destination="X", total=500,
                              heure_debut="08:00", heure_fin="12:00"))
    db.commit()


def test_contract_change_gives_one_analysed_row_per_contract(db):
    _scenario(db)
    rows = {r["region"]: r for r in build_analytics(db, 2026, 5)["buses"]}
    assert set(rows) == {"Sousse", "Djerba"}
    assert rows["Sousse"]["loyer"] == 600 and rows["Djerba"]["loyer"] == 900
    assert rows["Sousse"]["revenue"] == 1000 and rows["Djerba"]["revenue"] == 1000
    # each contract is analysed on its own days only
    assert rows["Sousse"]["covered_days"] == 12 and rows["Djerba"]["covered_days"] == 19
    assert rows["Sousse"]["worked_days"] == 2 and rows["Djerba"]["worked_days"] == 2
    assert rows["Sousse"]["trips"] == 2 and rows["Djerba"]["trips"] == 2


def test_analyse_and_calendrier_agree(db):
    _scenario(db)
    cal = {r["region"]: r for r in build_calendar(db, 2026, 5)["buses"]}
    ana = {r["region"]: r for r in build_analytics(db, 2026, 5)["buses"]}
    assert cal.keys() == ana.keys()
    for region in cal:
        for field in ("revenue", "loyer", "fuel", "net"):
            assert cal[region][field] == ana[region][field], (region, field)
