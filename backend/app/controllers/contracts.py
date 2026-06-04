"""Contract CRUD + result. Rent (loyer) lives here, per arbitrary date period."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin
from .. import models, schemas
from ..services.contracts import compute_contract_result
from ..services.audit import log_action

router = APIRouter()


@router.get("/api/contracts")
def list_contracts(bus_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Contract)
    if bus_id:
        q = q.filter(models.Contract.bus_id == bus_id)
    contracts = q.order_by(models.Contract.start_date.desc()).all()
    return [compute_contract_result(db, c) for c in contracts]


@router.post("/api/contracts")
def create_contract(body: schemas.ContractCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    if body.end_date < body.start_date:
        raise HTTPException(400, "La date de fin doit être après la date de début.")
    if not db.get(models.Bus, body.bus_id):
        raise HTTPException(404, "Véhicule introuvable.")
    c = models.Contract(**body.model_dump())
    db.add(c); db.flush()
    bus = db.get(models.Bus, c.bus_id)
    log_action(db, _admin, "Contrat", f"Ajout : {bus.name if bus else c.bus_id}, {c.start_date}→{c.end_date}, loyer {c.loyer:.0f} TND")
    db.commit(); db.refresh(c)
    return compute_contract_result(db, c)


@router.put("/api/contracts/{cid}")
def update_contract(cid: int, body: schemas.ContractCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    c = db.get(models.Contract, cid)
    if not c:
        raise HTTPException(404, "Contrat introuvable.")
    if body.end_date < body.start_date:
        raise HTTPException(400, "La date de fin doit être après la date de début.")
    old_loyer = c.loyer
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    bus = db.get(models.Bus, c.bus_id)
    loyer_part = f"loyer {old_loyer:.0f} → {c.loyer:.0f} TND" if abs((old_loyer or 0) - (c.loyer or 0)) > 0.5 else f"loyer {c.loyer:.0f} TND"
    log_action(db, _admin, "Contrat", f"Modification : {bus.name if bus else c.bus_id}, {c.start_date}→{c.end_date}, {loyer_part}")
    db.commit(); db.refresh(c)
    return compute_contract_result(db, c)


@router.delete("/api/contracts/{cid}", status_code=204)
def delete_contract(cid: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    c = db.get(models.Contract, cid)
    if c:
        bus = db.get(models.Bus, c.bus_id)
        log_action(db, _admin, "Contrat", f"Suppression : {bus.name if bus else c.bus_id}, {c.start_date}→{c.end_date}, loyer {c.loyer:.0f} TND")
        db.delete(c); db.commit()


@router.get("/api/contracts/{cid}/result")
def contract_result_endpoint(cid: int, db: Session = Depends(get_db)):
    c = db.get(models.Contract, cid)
    if not c:
        raise HTTPException(404, "Contrat introuvable.")
    return compute_contract_result(db, c)
