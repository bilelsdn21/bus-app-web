"""Period cutoffs (morning/evening/night boundaries)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin
from .. import schemas
from ..services.lookups import get_config
from ..services.audit import log_action

router = APIRouter()


@router.get("/api/config", response_model=schemas.ConfigOut)
def read_config(db: Session = Depends(get_db)):
    return get_config(db)


@router.put("/api/config", response_model=schemas.ConfigOut)
def update_config(body: schemas.ConfigUpdate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    cfg = get_config(db)
    cfg.cut_morn, cfg.cut_night = body.cut_morn, body.cut_night
    cfg.current_prices_since = body.current_prices_since
    since = body.current_prices_since.isoformat() if body.current_prices_since else "—"
    log_action(db, _admin, "Périodes", f"matin < {body.cut_morn}h, nuit ≥ {body.cut_night}h · prix actuels depuis {since}")
    db.commit(); db.refresh(cfg)
    return cfg
