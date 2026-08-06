"""Was renting an external vehicle actually necessary? For a rented vehicle's type,
region and period, check — day by day — whether one of OUR OWN fleet buses of the
same type was under an active contract AND had no booking/unavailable mark that day
(i.e. sitting idle) in the same region. If so, the rental may have been avoidable —
this is what lets the manager audit the dispatcher's decisions."""
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from . import calc
from .lookups import region_periods_by_bus, region_for


def check_alternatives(db: Session, vehicle_type: str, region: str, start_date: date, end_date: date) -> dict:
    buses = db.query(models.Bus).filter(models.Bus.type == vehicle_type).order_by(models.Bus.sort_order).all()
    days_total = (end_date - start_date).days + 1

    if not buses:
        return {"days_total": days_total, "days_with_alternative": 0, "days": [], "fleet_count": 0}

    bus_ids = [b.id for b in buses]

    # every booking/unavailable row (either counts as "busy") overlapping the period,
    # for buses of this type only
    books = (db.query(models.Booking)
             .filter(models.Booking.bus_id.in_(bus_ids),
                     models.Booking.date <= end_date,
                     func.coalesce(models.Booking.end_date, models.Booking.date) >= start_date)
             .all())
    busy = set()  # {(bus_id, date)}
    for b in books:
        s, e = max(b.date, start_date), min(b.end_date or b.date, end_date)
        for off in range((e - s).days + 1):
            busy.add((b.bus_id, s + timedelta(days=off)))

    contracts_by_bus = defaultdict(list)
    for c in db.query(models.Contract).filter(models.Contract.bus_id.in_(bus_ids)).all():
        contracts_by_bus[c.bus_id].append(c)

    periods_by_bus = region_periods_by_bus(db)

    days = []
    for off in range(days_total):
        d = start_date + timedelta(days=off)
        m_start, m_end = calc.month_bounds(d.year, d.month)
        free_here = []
        for bus in buses:
            covered = any(c.start_date <= d <= c.end_date for c in contracts_by_bus.get(bus.id, []))
            if not covered or (bus.id, d) in busy:
                continue
            bus_region = region_for(bus, m_start, m_end, periods_by_bus)
            if region and bus_region != region:
                continue
            free_here.append({"id": bus.id, "name": bus.name, "region": bus_region})
        days.append({"date": d.isoformat(), "available": free_here})

    return {
        "days_total": days_total,
        "days_with_alternative": sum(1 for x in days if x["available"]),
        "days": days,
        "fleet_count": len(buses),
    }
