"""Small DB lookups shared across controllers/services."""
from sqlalchemy.orm import Session
from .. import models


def get_config(db: Session) -> models.Config:
    """The single Config row (period cutoffs). Created with defaults if missing."""
    cfg = db.query(models.Config).first()
    if not cfg:
        cfg = models.Config(cut_morn=13, cut_night=22)
        db.add(cfg); db.commit(); db.refresh(cfg)
    return cfg


def price_for(db: Session, destination: str, bus_type: str) -> float:
    """Unit price for a destination given the bus type (MICRO/OTOKAR/BUS)."""
    d = db.query(models.Destination).filter(models.Destination.name == destination).first()
    if not d:
        return 0.0
    return {"MICRO": d.price_micro, "OTOKAR": d.price_otokar, "BUS": d.price_bus}.get(
        (bus_type or "").upper(), 0.0)
