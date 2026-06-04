"""Excursion (Booking) domain logic: validation, pricing, and labels."""
from datetime import date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.config import UNAVAIL_CATS
from .lookups import price_for


def excursion_out(b: models.Booking) -> dict:
    """Serialize one excursion for the editor (start/end + multi-day flag)."""
    return {
        "id": b.id, "bus_id": b.bus_id,
        "start_date": b.date.isoformat(),
        "end_date": (b.end_date or b.date).isoformat(),
        "type": b.type, "destination": b.destination, "client": b.client,
        "pax": b.pax, "unit_price": b.unit_price, "total": b.total,
        "heure_debut": b.heure_debut, "heure_fin": b.heure_fin, "notes": b.notes,
        "multi_day": (b.end_date is not None and b.end_date != b.date),
    }


def describe_exc(db: Session, b: models.Booking) -> str:
    """Short human label of an excursion for the Journal, e.g.
    'BUS ISKANDER 371 — 10/05, Zarzis, 3 pax, 450 TND'."""
    bus = db.get(models.Bus, b.bus_id)
    span = b.date.strftime("%d/%m")
    if b.end_date and b.end_date != b.date:
        span += "→" + b.end_date.strftime("%d/%m")
    what = b.destination or b.type
    parts = [bus.name if bus else f"#{b.bus_id}", span, what]
    if b.type == "Booking":
        if b.pax:
            parts.append(f"{b.pax} pax")
        parts.append(f"{(b.total or 0):.0f} TND")
    return " — ".join(parts[:2]) + ", " + ", ".join(parts[2:])


def require_contract(db: Session, bus_id: int, d: date):
    """Block writing an excursion on a date no contract covers for this bus."""
    cov = (db.query(models.Contract)
           .filter(models.Contract.bus_id == bus_id,
                   models.Contract.start_date <= d,
                   models.Contract.end_date >= d).first())
    if not cov:
        raise HTTPException(409,
            "Aucun contrat ne couvre cette date pour ce véhicule. "
            "Créez d'abord un contrat (onglet Contrats) couvrant cette période.")


def apply_excursion(db: Session, b: models.Booking, body: schemas.ExcursionIn):
    """Validate the payload and write it onto a (new or existing) Booking `b`."""
    bus = db.get(models.Bus, body.bus_id)
    if not bus:
        raise HTTPException(404, "Véhicule introuvable.")
    start = body.start_date
    end = body.end_date or start
    if end < start:
        raise HTTPException(400, "La date de fin doit être ≥ la date de début.")
    cat = (body.category or "").strip()
    dest = (body.destination or "").strip()
    is_unavail = cat in UNAVAIL_CATS
    if not is_unavail and not dest:
        raise HTTPException(400, "Choisissez une destination.")
    require_contract(db, bus.id, start)   # coverage on the start day
    b.bus_id = bus.id
    b.date = start
    b.end_date = end
    b.client = body.client
    b.pax = body.pax
    b.heure_debut = body.heure_debut
    b.heure_fin = body.heure_fin
    b.notes = body.notes
    if is_unavail:
        b.type = "Unavailable"; b.destination = cat
        b.unit_price = 0; b.total = 0
    else:
        price = price_for(db, dest, bus.type)
        b.type = "Booking"; b.destination = dest
        b.unit_price = price
        b.total = body.total if body.total is not None else price
