"""Externally rented (reinforcement) vehicle cost — prorated by day into whichever
calendar month(s) each rental's period overlaps, grouped by region."""
from sqlalchemy.orm import Session
from .. import models
from . import calc


def rented_vehicles_summary(db: Session, year: int, month: int) -> dict:
    start, end = calc.month_bounds(year, month)
    rows = (db.query(models.RentedVehicle)
            .filter(models.RentedVehicle.start_date <= end,
                    models.RentedVehicle.end_date >= start).all())

    by_region: dict[str, float] = {}
    items = []
    for r in rows:
        cost = calc.prorate_period_cost(r.start_date, r.end_date, r.cost, year, month)
        if cost <= 0:
            continue
        reg = r.region or "—"
        by_region[reg] = by_region.get(reg, 0.0) + cost
        items.append({"id": r.id, "name": r.name, "region": r.region, "cost": cost})

    return {
        "year": year, "month": month,
        "by_region": [{"region": k, "cost": round(v, 2)} for k, v in by_region.items()],
        "items": items,
        "total": round(sum(by_region.values()), 2),
    }
