"""Analytics endpoint: precise per-vehicle monthly rentability + time occupancy."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.cache import cached
from ..core.security import require_admin, require_user
from ..services.analytics import build_analytics

# Reads require a signed-in account; writes add require_admin on top.
router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/api/analytics/{year}/{month}")
def analytics(year: int, month: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    return cached(("analytics", year, month), lambda: build_analytics(db, year, month))
