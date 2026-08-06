"""Externally rented (reinforcement) vehicle CRUD + monthly cost summary."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin
from .. import models, schemas
from ..services.audit import log_action
from ..services.rentals import rented_vehicles_summary

router = APIRouter()


@router.get("/api/rented-vehicles", response_model=list[schemas.RentedVehicleOut])
def list_rented_vehicles(db: Session = Depends(get_db)):
    return db.query(models.RentedVehicle).order_by(models.RentedVehicle.start_date.desc()).all()


@router.post("/api/rented-vehicles", response_model=schemas.RentedVehicleOut)
def create_rented_vehicle(body: schemas.RentedVehicleCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    if body.end_date < body.start_date:
        raise HTTPException(400, "La date de fin doit être après la date de début.")
    r = models.RentedVehicle(**body.model_dump())
    db.add(r); db.flush()
    log_action(db, _admin, "Véhicule loué", f"Ajout : {r.name}, {r.start_date}→{r.end_date}, {r.cost:.0f} TND")
    db.commit(); db.refresh(r)
    return r


@router.put("/api/rented-vehicles/{rid}", response_model=schemas.RentedVehicleOut)
def update_rented_vehicle(rid: int, body: schemas.RentedVehicleCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    r = db.get(models.RentedVehicle, rid)
    if not r:
        raise HTTPException(404, "Véhicule loué introuvable.")
    if body.end_date < body.start_date:
        raise HTTPException(400, "La date de fin doit être après la date de début.")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    log_action(db, _admin, "Véhicule loué", f"Modification : {r.name}, {r.start_date}→{r.end_date}, {r.cost:.0f} TND")
    db.commit(); db.refresh(r)
    return r


@router.delete("/api/rented-vehicles/{rid}", status_code=204)
def delete_rented_vehicle(rid: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    r = db.get(models.RentedVehicle, rid)
    if r:
        log_action(db, _admin, "Véhicule loué", f"Suppression : {r.name}, {r.start_date}→{r.end_date}")
        db.delete(r); db.commit()


@router.get("/api/rented-vehicles/summary/{year}/{month}")
def rented_vehicles_summary_endpoint(year: int, month: int, db: Session = Depends(get_db)):
    return rented_vehicles_summary(db, year, month)
