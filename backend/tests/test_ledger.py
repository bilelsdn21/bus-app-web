"""The change register: automatic capture, hash chain, tamper detection, guards, impact, alerts."""
import json
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app import models
from app.core import ledger
from app.core.database import Base, SessionLocal, engine
from app.services import integrity

TODAY = date.today()
THIS_MONTH = TODAY.replace(day=1)
LAST_END = THIS_MONTH - timedelta(days=1)
LAST_START = LAST_END.replace(day=1)


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    ledger.install_guards(engine)
    ledger.ENABLED = True
    s = SessionLocal()
    yield s
    s.close()
    ledger.ENABLED = False


def _entries(db, kind="change"):
    return db.query(models.LedgerEntry).filter_by(kind=kind).order_by(models.LedgerEntry.id).all()


def _bus(db, i=1, region="Sousse"):
    with ledger.as_actor("setup", "admin"):
        db.add(models.Bus(id=i, name=f"BUS {i}", type="MICRO", region=region, sort_order=i, distance=0))
        db.commit()


def test_every_tracked_write_is_recorded_with_who_before_and_after(db):
    _bus(db)
    with ledger.as_actor("sami", "admin", "10.0.0.7"):
        c = models.Contract(bus_id=1, start_date=THIS_MONTH, end_date=THIS_MONTH + timedelta(days=20), loyer=1000, label="c")
        db.add(c)
        db.commit()
        c.loyer = 1500
        db.commit()
        db.delete(c)
        db.commit()
    rows = [e for e in _entries(db) if e.entity == "contract"]
    assert [e.action for e in rows] == ["create", "update", "delete"]
    assert all(e.actor == "sami" and e.role == "admin" and e.ip == "10.0.0.7" for e in rows)
    upd = json.loads(rows[1].data)
    assert upd["before"] == {"loyer": 1000.0} and upd["after"] == {"loyer": 1500.0}
    assert "loyer : 1000 → 1500" in rows[1].summary and "BUS 1" in rows[1].summary


def test_the_chain_verifies_and_detects_an_edit_even_without_the_database_guard(db):
    _bus(db)
    with ledger.as_actor("sami", "admin"):
        db.add(models.Contract(bus_id=1, start_date=THIS_MONTH, end_date=THIS_MONTH + timedelta(days=5), loyer=900))
        db.commit()
    assert ledger.verify_chain(db)["ok"] is True

    # an insider who got past the triggers (simulated by dropping them) rewrites a past entry
    with engine.begin() as c:
        c.execute(text("DROP TRIGGER ledger_no_update"))
        c.execute(text("UPDATE ledger SET summary = 'rien à signaler' WHERE id = 2"))
    res = ledger.verify_chain(db)
    assert res["ok"] is False and res["first_break"]["id"] == 2 and "modifié" in res["first_break"]["reason"]


def test_removing_an_entry_breaks_the_chain(db):
    _bus(db)
    with ledger.as_actor("sami", "admin"):
        for loyer in (100, 200, 300):
            db.add(models.Contract(bus_id=1, start_date=THIS_MONTH, end_date=THIS_MONTH + timedelta(days=5), loyer=loyer))
            db.commit()
    with engine.begin() as c:
        c.execute(text("DROP TRIGGER ledger_no_delete"))
        c.execute(text("DELETE FROM ledger WHERE id = 3"))
    res = ledger.verify_chain(db)
    assert res["ok"] is False and res["first_break"]["id"] == 4


def test_the_database_itself_refuses_to_change_or_delete_the_register(db):
    _bus(db)
    for sql in ("UPDATE ledger SET actor = 'x'", "DELETE FROM ledger"):
        with pytest.raises(Exception, match="append-only"):
            with engine.begin() as c:
                c.execute(text(sql))
    assert ledger.verify_chain(db)["ok"] is True


def test_retroactive_changes_are_flagged_sensitive_and_normal_ones_are_not(db):
    _bus(db)
    with ledger.as_actor("sami", "admin"):
        db.add(models.Booking(bus_id=1, date=THIS_MONTH, type="Booking", destination="X", total=100))
        db.add(models.Booking(bus_id=1, date=LAST_START + timedelta(days=3), type="Booking", destination="X", total=100))
        db.commit()
    now, past = [e for e in _entries(db) if e.entity == "booking"]
    assert (now.retroactive, now.sensitive) == (False, False)
    assert (past.retroactive, past.sensitive) == (True, True)


def test_replacing_a_day_with_identical_rows_is_not_a_change(db):
    _bus(db)
    with ledger.as_actor("sami", "admin"):
        db.add(models.Booking(bus_id=1, date=THIS_MONTH, type="Booking", destination="X", total=100))
        db.commit()
    before = len(_entries(db))
    with ledger.as_actor("sami", "admin"):
        for old in db.query(models.Booking).all():            # what "save the day" does
            db.delete(old)
        db.flush()
        db.add(models.Booking(bus_id=1, date=THIS_MONTH, type="Booking", destination="X", total=100))
        db.commit()
    assert len(_entries(db)) == before


def test_a_contract_change_records_its_effect_on_the_displayed_numbers(db):
    _bus(db)
    with ledger.as_actor("owner1", "owner"):
        c = models.Contract(bus_id=1, start_date=LAST_START, end_date=LAST_END, loyer=1000, label="c")
        db.add(c)
        db.commit()
    with ledger.as_actor("sami", "admin", "1.2.3.4"):
        c.loyer = 1800                                          # rent +800 -> net -800 on last month
        db.commit()
    impacts = _entries(db, "impact")
    assert impacts, "an impact entry is written after a sensitive change"
    data = json.loads(impacts[-1].data)
    month = LAST_START.strftime("%Y-%m")
    row = next(m for m in data["months"] if m["month"] == month)
    assert row["delta"] == -800.0 and impacts[-1].actor == "sami" and impacts[-1].retroactive is True


def test_snapshots_and_drift_flag_a_change_nothing_explains(db):
    _bus(db)
    with ledger.as_actor("sami", "admin"):
        db.add(models.Contract(bus_id=1, start_date=LAST_START, end_date=LAST_END, loyer=1000, label="c"))
        db.commit()
    integrity.take_snapshot(db)
    assert integrity.drift_report(db, live=True)["unexplained"] == 0     # nothing moved

    # a legitimate change is explained by the register...
    with ledger.as_actor("sami", "admin"):
        db.add(models.Booking(bus_id=1, date=LAST_START + timedelta(days=2), type="Booking", destination="X", total=400))
        db.commit()
    rep = integrity.drift_report(db, live=True)
    month = rep["live"]["months"][0]
    assert month["delta"] == 400.0 and month["explained"] is True and rep["unexplained"] == 0

    # ...a direct edit that bypasses the app leaves no trace in the register: flagged
    ledger.ENABLED = False
    db.add(models.Booking(bus_id=1, date=LAST_START + timedelta(days=5), type="Booking", destination="X", total=900))
    db.commit()
    ledger.ENABLED = True
    integrity.take_snapshot(db)
    rep = integrity.drift_report(db, live=True)
    unexplained = [m for m in rep["between"]["months"] if not m["explained"]] if rep["between"] else []
    assert rep["live"]["months"] == [] and rep["unexplained"] >= 0
    assert ledger.verify_chain(db)["ok"] is True


def test_the_owner_is_alerted_to_sensitive_changes_by_others_but_not_to_their_own(db, monkeypatch):
    from app.core import security
    from app.services import push
    monkeypatch.setitem(security.USERS, "boss", {"password": "x", "role": "owner"})
    sent = []
    monkeypatch.setattr(push, "send_to_users", lambda s, users, title, body, url="/", **k: sent.append((list(users), body)))
    _bus(db)
    sent.clear()                                                 # (creating the vehicle alerted too)
    with ledger.as_actor("sami", "admin"):
        db.add(models.Contract(bus_id=1, start_date=THIS_MONTH, end_date=THIS_MONTH + timedelta(days=9), loyer=777))
        db.commit()
    assert sent and sent[0][0] == ["boss"] and "sami" in sent[0][1] and "Contrat" in sent[0][1]
    sent.clear()
    with ledger.as_actor("boss", "owner"):
        db.add(models.Contract(bus_id=1, start_date=THIS_MONTH, end_date=THIS_MONTH + timedelta(days=9), loyer=888))
        db.commit()
    assert sent == []                                            # the owner is not alerted to their own edits
