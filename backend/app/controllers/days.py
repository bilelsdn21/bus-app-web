"""Single-day read, contract coverage check, and the legacy day-save (mobile entry)."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin
from ..core.config import UNAVAIL_CATS
from .. import models, schemas
from ..services.lookups import price_for
from ..services.audit import log_action

router = APIRouter()


@router.get("/api/day/{bus_id}/{day_iso}")
def get_day(bus_id: int, day_iso: str, db: Session = Depends(get_db)):
    try:
        d = date.fromisoformat(day_iso)
    except ValueError:
        raise HTTPException(400, "Date invalide.")
    rows = (db.query(models.Booking)
            .filter(models.Booking.bus_id == bus_id, models.Booking.date == d)
            .all())
    return [schemas.BookingOut.model_validate(r).model_dump() for r in rows]


@router.get("/api/coverage/{bus_id}/{day_iso}")
def coverage(bus_id: int, day_iso: str, db: Session = Depends(get_db)):
    """Does this bus have a contract covering this date? Used by the entry form."""
    try:
        d = date.fromisoformat(day_iso)
    except ValueError:
        raise HTTPException(400, "Date invalide.")
    c = (db.query(models.Contract)
         .filter(models.Contract.bus_id == bus_id,
                 models.Contract.start_date <= d,
                 models.Contract.end_date >= d).first())
    return {"covered": c is not None,
            "contract": ({"id": c.id, "label": c.label,
                          "start_date": c.start_date.isoformat(),
                          "end_date": c.end_date.isoformat()} if c else None)}


@router.post("/api/day")
def save_day(body: schemas.DaySave, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    bus = db.get(models.Bus, body.bus_id)
    if not bus:
        raise HTTPException(404, "Véhicule introuvable.")

    # Require a contract covering this date IF there is real content to add.
    # (Clearing a day — empty rows — is always allowed.)
    has_content = any((r.category or "").strip() for r in body.rows)
    if has_content:
        covering = (db.query(models.Contract)
                    .filter(models.Contract.bus_id == bus.id,
                            models.Contract.start_date <= body.date,
                            models.Contract.end_date >= body.date).first())
        if not covering:
            raise HTTPException(
                409,
                "Aucun contrat ne couvre cette date pour ce véhicule. "
                "Créez d'abord un contrat (onglet Contrats) couvrant cette période.")

    # replace all existing rows for this bus+date (same semantics as Excel SaveAndReturn)
    db.query(models.Booking).filter(
        models.Booking.bus_id == bus.id, models.Booking.date == body.date
    ).delete()

    saved = 0
    for row in body.rows:
        cat = (row.category or "").strip()
        dest = (row.destination or "").strip()
        if not cat:
            continue
        is_unavail = cat in UNAVAIL_CATS
        if not is_unavail and not dest:
            continue  # booking with no destination -> skip
        if is_unavail:
            db.add(models.Booking(
                date=body.date, bus_id=bus.id, type="Unavailable",
                destination=cat, total=0, unit_price=0, notes=body.notes,
                heure_debut=row.heure_debut, heure_fin=row.heure_fin,
            ))
        else:
            price = price_for(db, dest, bus.type)
            db.add(models.Booking(
                date=body.date, bus_id=bus.id, type="Booking",
                destination=dest, client=row.client, pax=row.pax,
                unit_price=price, total=price, notes=body.notes,
                heure_debut=row.heure_debut, heure_fin=row.heure_fin,
            ))
        saved += 1

    log_action(db, _admin, "Journée", f"{bus.name}, {body.date.strftime('%d/%m/%Y')} : {saved} ligne(s) enregistrée(s)")
    db.commit()
    return {"ok": True, "saved": saved}
