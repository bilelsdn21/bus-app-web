"""Fuel per bus per calendar month (estimated → actual)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin
from .. import models, schemas
from ..services.audit import log_action

router = APIRouter()


@router.get("/api/fuel", response_model=list[schemas.FuelOut])
def list_fuel(bus_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(models.FuelMonth)
    if bus_id:
        q = q.filter(models.FuelMonth.bus_id == bus_id)
    return q.order_by(models.FuelMonth.year, models.FuelMonth.month).all()


@router.put("/api/fuel", response_model=schemas.FuelOut)
def upsert_fuel(body: schemas.FuelUpsert, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Set estimated and/or actual for a bus + calendar month (creates if missing)."""
    fm = (db.query(models.FuelMonth)
          .filter(models.FuelMonth.bus_id == body.bus_id,
                  models.FuelMonth.year == body.year,
                  models.FuelMonth.month == body.month).first())
    if not fm:
        fm = models.FuelMonth(bus_id=body.bus_id, year=body.year, month=body.month, estimated=0.0)
        db.add(fm)
    parts = []
    if body.estimated is not None:
        fm.estimated = body.estimated; parts.append(f"estimé {body.estimated:.0f}")
    if body.actual is not None:
        fm.actual = body.actual; parts.append(f"réel {body.actual:.0f}")
    bus = db.get(models.Bus, body.bus_id)
    log_action(db, _admin, "Carburant",
               f"{bus.name if bus else body.bus_id} {body.month:02d}/{body.year}: " + ", ".join(parts))
    db.commit(); db.refresh(fm)
    return fm
