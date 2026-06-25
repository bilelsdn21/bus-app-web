"""Analytics endpoint: precise per-vehicle monthly rentability + time occupancy."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin
from ..services.analytics import build_analytics

router = APIRouter()


@router.get("/api/analytics/{year}/{month}")
def analytics(year: int, month: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    return build_analytics(db, year, month)
