"""Destination + pricing CRUD."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin
from .. import models, schemas
from ..services.audit import log_action

router = APIRouter()


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
