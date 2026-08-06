"""Excel export endpoints. Each mirrors the auth level of its equivalent list
endpoint: most GETs in this app are public reads (/api/calendar, /api/buses,
/api/contracts, …), analytics is admin-only, and the audit log is admin/owner-only
— the exports below match that exactly rather than inventing a new policy."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin, require_owner
from .. import models
from ..services import calc
from ..services.export import (
    build_calendar_workbook, build_rentals_workbook,
    build_price_periods_workbook, build_region_periods_workbook,
    build_buses_workbook, build_destinations_workbook, build_contracts_workbook,
    build_analytics_workbook, build_journal_workbook,
)

router = APIRouter()

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_CONNECTION_ACTIONS = ("Connexion", "Déconnexion", "Connexion échouée")


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


@router.get("/api/export/buses")
def export_buses(db: Session = Depends(get_db)):
    buf = build_buses_workbook(db)
    return StreamingResponse(buf, media_type=XLSX_MEDIA,
                              headers={"Content-Disposition": 'attachment; filename="Vehicules.xlsx"'})


@router.get("/api/export/destinations")
def export_destinations(db: Session = Depends(get_db)):
    buf = build_destinations_workbook(db)
    return StreamingResponse(buf, media_type=XLSX_MEDIA,
                              headers={"Content-Disposition": 'attachment; filename="Destinations.xlsx"'})


@router.get("/api/export/contracts")
def export_contracts(db: Session = Depends(get_db)):
    buf = build_contracts_workbook(db)
    return StreamingResponse(buf, media_type=XLSX_MEDIA,
                              headers={"Content-Disposition": 'attachment; filename="Contrats.xlsx"'})


@router.get("/api/export/analytics/{year}/{month}")
def export_analytics(year: int, month: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mois invalide.")
    buf = build_analytics_workbook(db, year, month)
    filename = f"Analyse_{calc.MONTH_FR[month]}_{year}.xlsx"
    return StreamingResponse(buf, media_type=XLSX_MEDIA,
                              headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/api/export/journal")
def export_journal(db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Changes-only log (matches /api/audit/changes — what admins see)."""
    rows = (db.query(models.AuditLog)
            .filter(~models.AuditLog.method.in_(_CONNECTION_ACTIONS))
            .order_by(models.AuditLog.created_at.desc()).limit(1000).all())
    buf = build_journal_workbook(rows, "Journal (modifications)")
    return StreamingResponse(buf, media_type=XLSX_MEDIA,
                              headers={"Content-Disposition": 'attachment; filename="Journal.xlsx"'})


@router.get("/api/export/journal/full")
def export_journal_full(db: Session = Depends(get_db), _owner: str = Depends(require_owner)):
    """Full log including logins/logouts (matches /api/audit — owner only)."""
    rows = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(1000).all()
    buf = build_journal_workbook(rows, "Journal complet")
    return StreamingResponse(buf, media_type=XLSX_MEDIA,
                              headers={"Content-Disposition": 'attachment; filename="Journal_complet.xlsx"'})
