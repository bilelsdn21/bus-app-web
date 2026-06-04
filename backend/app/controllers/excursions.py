"""Excursion (Booking) CRUD — multi-day, overlapping, contract-gated."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin
from .. import models, schemas
from ..services.excursions import excursion_out, describe_exc, apply_excursion
from ..services.audit import log_action

router = APIRouter()


@router.get("/api/excursions/day/{bus_id}/{day_iso}")
def excursions_for_day(bus_id: int, day_iso: str, db: Session = Depends(get_db)):
    """All excursions ACTIVE on this day for the bus (covers multi-day spans)."""
    try:
        d = date.fromisoformat(day_iso)
    except ValueError:
        raise HTTPException(400, "Date invalide.")
    rows = (db.query(models.Booking)
            .filter(models.Booking.bus_id == bus_id,
                    models.Booking.date <= d,
                    func.coalesce(models.Booking.end_date, models.Booking.date) >= d)
            .order_by(models.Booking.heure_debut).all())
    return [excursion_out(r) for r in rows]


@router.post("/api/excursions")
def create_excursion(body: schemas.ExcursionIn, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    b = models.Booking()
    apply_excursion(db, b, body)
    db.add(b); db.flush()
    log_action(db, _admin, "Excursion", "Ajout : " + describe_exc(db, b))
    db.commit(); db.refresh(b)
    return excursion_out(b)


@router.put("/api/excursions/{exc_id}")
def update_excursion(exc_id: int, body: schemas.ExcursionIn, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    b = db.get(models.Booking, exc_id)
    if not b:
        raise HTTPException(404, "Excursion introuvable.")
    before = describe_exc(db, b)
    apply_excursion(db, b, body)
    db.flush()
    after = describe_exc(db, b)
    detail = after if after == before else f"{before}  ➜  {after}"
    log_action(db, _admin, "Excursion", "Modification : " + detail)
    db.commit(); db.refresh(b)
    return excursion_out(b)


@router.delete("/api/excursions/{exc_id}", status_code=204)
def delete_excursion(exc_id: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    b = db.get(models.Booking, exc_id)
    if b:
        detail = describe_exc(db, b)
        db.delete(b)
        log_action(db, _admin, "Excursion", "Suppression : " + detail)
        db.commit()
