"""The monthly calendar (viewer)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services.calendar import build_calendar

router = APIRouter()


@router.get("/api/calendar/{year}/{month}")
def calendar(year: int, month: int, db: Session = Depends(get_db)):
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mois invalide.")
    return build_calendar(db, year, month)
