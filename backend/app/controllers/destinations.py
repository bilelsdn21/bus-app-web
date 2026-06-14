"""Destination + pricing CRUD."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin
from .. import models, schemas
from ..services.audit import log_action

router = APIRouter()


# ---------- historical price periods ----------
@router.get("/api/price-periods", response_model=list[schemas.PricePeriodOut])
def list_price_periods(db: Session = Depends(get_db)):
    return (db.query(models.PricePeriod)
            .order_by(models.PricePeriod.dest_name, models.PricePeriod.effective_from.desc()).all())


@router.put("/api/price-periods", response_model=schemas.PricePeriodOut)
def upsert_price_period(body: schemas.PricePeriodIn, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Set the price of a destination effective from a date (creates or updates)."""
    pp = (db.query(models.PricePeriod)
          .filter(models.PricePeriod.dest_name == body.dest_name,
                  models.PricePeriod.effective_from == body.effective_from).first())
    if not pp:
        pp = models.PricePeriod(dest_name=body.dest_name, effective_from=body.effective_from)
        db.add(pp)
    pp.price_micro, pp.price_otokar, pp.price_bus = body.price_micro, body.price_otokar, body.price_bus
    log_action(db, _admin, "Tarif période",
               f"{body.dest_name} dès {body.effective_from}: MICRO {body.price_micro:.0f}/OTOKAR {body.price_otokar:.0f}/BUS {body.price_bus:.0f}")
    db.commit(); db.refresh(pp)
    return pp


@router.delete("/api/price-periods/{pid}", status_code=204)
def delete_price_period(pid: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    pp = db.get(models.PricePeriod, pid)
    if pp:
        log_action(db, _admin, "Tarif période", f"Suppression : {pp.dest_name} dès {pp.effective_from}")
        db.delete(pp); db.commit()


@router.get("/api/destinations", response_model=list[schemas.DestinationOut])
def list_destinations(db: Session = Depends(get_db)):
    return db.query(models.Destination).order_by(models.Destination.category, models.Destination.name).all()


@router.post("/api/destinations", response_model=schemas.DestinationOut)
def create_destination(body: schemas.DestinationCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    d = models.Destination(**body.model_dump())
    db.add(d); db.flush()
    log_action(db, _admin, "Destination", f"Ajout : {d.name} (MICRO {d.price_micro:.0f}/OTOKAR {d.price_otokar:.0f}/BUS {d.price_bus:.0f})")
    db.commit(); db.refresh(d)
    return d


@router.put("/api/destinations/{did}", response_model=schemas.DestinationOut)
def update_destination(did: int, body: schemas.DestinationCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    d = db.get(models.Destination, did)
    if not d:
        raise HTTPException(404, "Destination introuvable.")
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    log_action(db, _admin, "Destination", f"Modification : {d.name} (MICRO {d.price_micro:.0f}/OTOKAR {d.price_otokar:.0f}/BUS {d.price_bus:.0f})")
    db.commit(); db.refresh(d)
    return d


@router.delete("/api/destinations/{did}", status_code=204)
def delete_destination(did: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    d = db.get(models.Destination, did)
    if d:
        name = d.name
        db.delete(d)
        log_action(db, _admin, "Destination", f"Suppression : {name}")
        db.commit()
