"""Builds the monthly calendar grid (day colors + contract-aware net + summary)."""
from datetime import date, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from . import calc
from .lookups import get_config
from .contracts import compute_contract_result


def _overlap_days(a0, a1, b0, b1) -> int:
    s, e = max(a0, b0), min(a1, b1)
    return (e - s).days + 1 if s <= e else 0


def build_calendar(db: Session, year: int, month: int) -> dict:
    cfg = get_config(db)
    start, end = calc.month_bounds(year, month)
    buses = db.query(models.Bus).order_by(models.Bus.sort_order).all()

    # bookings whose [date .. end_date] span OVERLAPS this month (covers multi-day)
    books = (db.query(models.Booking)
             .filter(models.Booking.date <= end,
                     func.coalesce(models.Booking.end_date, models.Booking.date) >= start)
             .all())

    # mark each excursion active on every day of its span that falls in this month
    by_cell = {}
    for b in books:
        s = max(b.date, start)
        e = min(b.end_date or b.date, end)
        cell = {"id": b.id, "type": b.type, "heure_debut": b.heure_debut, "heure_fin": b.heure_fin,
                "multi": (b.end_date is not None and b.end_date != b.date)}
        for off in range((e - s).days + 1):
            d = s + timedelta(days=off)
            by_cell.setdefault((b.bus_id, d.isoformat()), []).append(cell)

    # contracts grouped by bus, to pick the one overlapping the viewed month
    contracts = db.query(models.Contract).all()
    contracts_by_bus = {}
    for c in contracts:
        contracts_by_bus.setdefault(c.bus_id, []).append(c)

    bus_list = []
    sum_rows = []   # for region summary (contract-aware)
    for bus in buses:
        # a vehicle is on the calendar this month ONLY if a contract overlaps it
        overlapping = [c for c in contracts_by_bus.get(bus.id, [])
                       if _overlap_days(c.start_date, c.end_date, start, end) > 0]
        if not overlapping:
            continue  # no contract this month -> the vehicle does not appear

        # the days of THIS month covered by any of the vehicle's contracts
        # (so a contract ending/starting mid-month grays out the rest)
        covered = set()
        for c in overlapping:
            s = max(c.start_date, start)
            e = min(c.end_date, end)
            for off in range((e - s).days + 1):
                covered.add((s + timedelta(days=off)).day)

        bd = {"id": bus.id, "name": bus.name, "type": bus.type, "region": bus.region,
              "distance": bus.distance, "covered_days": sorted(covered)}
        days = {}
        for day in range(1, end.day + 1):
            ds = date(year, month, day).isoformat()
            cell = by_cell.get((bus.id, ds), [])
            if cell:
                days[day] = calc.day_color(cell, cfg.cut_morn, cfg.cut_night)
        bd["days"] = days

        # net = result of the contract overlapping the viewed month the most
        chosen, best = None, 0
        for c in overlapping:
            ov = _overlap_days(c.start_date, c.end_date, start, end)
            if ov > best:
                chosen, best = c, ov
        res = compute_contract_result(db, chosen)
        bd.update({
            "net": res["net"], "pct": res["pct"], "is_estimated": res["is_estimated"],
            "contract": {
                "id": chosen.id, "label": chosen.label,
                "start_date": chosen.start_date.isoformat(),
                "end_date": chosen.end_date.isoformat(),
                "revenue": res["revenue"], "loyer": res["loyer"], "fuel": res["fuel"],
            },
        })
        sum_rows.append({"region": bus.region or "—", "loyer": res["loyer"], "net": res["net"]})
        bus_list.append(bd)

    # region summary from the contract-aware rows
    reg = {}
    for r in sum_rows:
        g = reg.setdefault(r["region"], {"region": r["region"], "loyer": 0.0, "net": 0.0, "count": 0})
        g["loyer"] += r["loyer"]; g["net"] += r["net"]; g["count"] += 1
    regions = list(reg.values())
    for g in regions:
        g["pct"] = calc.pct(g["net"], g["loyer"])
    total = {"region": "TOTAL",
             "loyer": sum(g["loyer"] for g in regions),
             "net": sum(g["net"] for g in regions),
             "count": sum(g["count"] for g in regions)}
    total["pct"] = calc.pct(total["net"], total["loyer"])
    summary = {"regions": regions, "total": total}

    return {
        "year": year, "month": month,
        "label": f"{calc.MONTH_FR[month]} {year}",
        "days_in_month": end.day,
        "cut_morn": cfg.cut_morn, "cut_night": cfg.cut_night,
        "buses": bus_list,
        "summary": summary,
    }
