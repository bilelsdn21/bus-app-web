"""The monthly calendar (viewer)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_user
from ..services.calendar import build_calendar

# Reads require a signed-in account; writes add require_admin on top.
router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/api/calendar/{year}/{month}")
def calendar(year: int, month: int, db: Session = Depends(get_db)):
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mois invalide.")
    return build_calendar(db, year, month)
