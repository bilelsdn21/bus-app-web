"""Bus (vehicle) CRUD."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin
from .. import models, schemas
from ..services.audit import log_action

router = APIRouter()


@router.get("/api/buses", response_model=list[schemas.BusOut])
def list_buses(db: Session = Depends(get_db)):
    return db.query(models.Bus).order_by(models.Bus.sort_order).all()


@router.post("/api/buses", response_model=schemas.BusOut)
def create_bus(body: schemas.BusCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    if db.query(models.Bus).filter(models.Bus.name == body.name).first():
        raise HTTPException(409, "Un véhicule avec ce nom existe déjà.")
    bus = models.Bus(**body.model_dump())
    db.add(bus); db.flush()
    log_action(db, _admin, "Véhicule", f"Ajout : {bus.name}")
    db.commit(); db.refresh(bus)
    return bus


@router.put("/api/buses/{bus_id}", response_model=schemas.BusOut)
def update_bus(bus_id: int, body: schemas.BusCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    bus = db.get(models.Bus, bus_id)
    if not bus:
        raise HTTPException(404, "Véhicule introuvable.")
    for k, v in body.model_dump().items():
        setattr(bus, k, v)
    log_action(db, _admin, "Véhicule", f"Modification : {bus.name}")
    db.commit(); db.refresh(bus)
    return bus


@router.delete("/api/buses/{bus_id}", status_code=204)
def delete_bus(bus_id: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    bus = db.get(models.Bus, bus_id)
    if not bus:
        return
    if db.query(models.Booking).filter(models.Booking.bus_id == bus_id).count():
        raise HTTPException(409, "Ce véhicule a des activités enregistrées — suppression bloquée.")
    name = bus.name
    db.delete(bus)
    log_action(db, _admin, "Véhicule", f"Suppression : {name}")
    db.commit()
