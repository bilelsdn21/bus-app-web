"""Excel export endpoints — Calendrier (colored grid + excursion detail + summary)
and the rented-vehicles list. Read-only, no auth dependency (same as the other
GET endpoints in this app — /api/calendar, /api/buses, /api/rented-vehicles, …)."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..services import calc
from ..services.export import (
    build_calendar_workbook, build_rentals_workbook,
    build_price_periods_workbook, build_region_periods_workbook,
)

router = APIRouter()

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/api/export/calendar/{year}/{month}")
def export_calendar(year: int, month: int, db: Session = Depends(get_db)):
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mois invalide.")
    buf = build_calendar_workbook(db, year, month)
    filename = f"Calendrier_{calc.MONTH_FR[month]}_{year}.xlsx"
    return StreamingResponse(buf, media_type=XLSX_MEDIA,
                              headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/api/export/rented-vehicles")
def export_rented_vehicles(db: Session = Depends(get_db)):
    buf = build_rentals_workbook(db)
    return StreamingResponse(buf, media_type=XLSX_MEDIA,
                              headers={"Content-Disposition": 'attachment; filename="Vehicules_loues.xlsx"'})


@router.get("/api/export/price-periods")
def export_price_periods(db: Session = Depends(get_db)):
    buf = build_price_periods_workbook(db)
    return StreamingResponse(buf, media_type=XLSX_MEDIA,
                              headers={"Content-Disposition": 'attachment; filename="Tarifs_anterieurs.xlsx"'})


@router.get("/api/export/region-periods")
def export_region_periods(db: Session = Depends(get_db)):
    buf = build_region_periods_workbook(db)
    return StreamingResponse(buf, media_type=XLSX_MEDIA,
                              headers={"Content-Disposition": 'attachment; filename="Regions_par_saison.xlsx"'})
