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


# ---------- historical region periods (a bus changes region by season) ----------
@router.get("/api/region-periods", response_model=list[schemas.RegionPeriodOut])
def list_region_periods(db: Session = Depends(get_db)):
    return (db.query(models.BusRegionPeriod)
            .order_by(models.BusRegionPeriod.bus_id, models.BusRegionPeriod.effective_from.desc()).all())


@router.put("/api/region-periods", response_model=schemas.RegionPeriodOut)
def upsert_region_period(body: schemas.RegionPeriodIn, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Set a bus's region effective from a date (creates or updates)."""
    rp = (db.query(models.BusRegionPeriod)
          .filter(models.BusRegionPeriod.bus_id == body.bus_id,
                  models.BusRegionPeriod.effective_from == body.effective_from).first())
    if not rp:
        rp = models.BusRegionPeriod(bus_id=body.bus_id, effective_from=body.effective_from)
        db.add(rp)
    rp.effective_to = body.effective_to
    rp.region = body.region
    bus = db.get(models.Bus, body.bus_id)
    log_action(db, _admin, "Région période",
               f"{bus.name if bus else body.bus_id} {body.effective_from}→{body.effective_to}: {body.region}")
    db.commit(); db.refresh(rp)
    return rp


@router.delete("/api/region-periods/{rid}", status_code=204)
def delete_region_period(rid: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    rp = db.get(models.BusRegionPeriod, rid)
    if rp:
        bus = db.get(models.Bus, rp.bus_id)
        log_action(db, _admin, "Région période", f"Suppression : {bus.name if bus else rp.bus_id} dès {rp.effective_from}")
        db.delete(rp); db.commit()
