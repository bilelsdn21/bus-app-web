"""Precise per-vehicle monthly analytics.

Two layers, both built from exactly-recorded data:
  • Rentability (always exact): revenue, loyer, net, rent-coverage % — from contract results.
  • Time occupancy (exact when trips carry hours/spans): days worked vs contracted days,
    and active hours from each trip's Heure début / Heure fin. Trips missing their hours are
    counted as worked days but flagged so the page can show how complete the data is.
"""
from datetime import timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from . import calc
from .contracts import compute_contract_result


def _overlap_days(a0, a1, b0, b1) -> int:
    s, e = max(a0, b0), min(a1, b1)
    return (e - s).days + 1 if s <= e else 0


def _hours(hd: str, hf: str):
    """Duration in hours from two 'HH:MM' strings; None if missing/invalid/overnight."""
    try:
        h0, m0 = map(int, hd.split(":"))
        h1, m1 = map(int, hf.split(":"))
        mins = (h1 * 60 + m1) - (h0 * 60 + m0)
        return round(mins / 60, 1) if mins > 0 else None
    except Exception:
        return None


def build_analytics(db: Session, year: int, month: int) -> dict:
    start, end = calc.month_bounds(year, month)

    books = (db.query(models.Booking)
             .filter(models.Booking.type == "Booking",
                     models.Booking.date <= end,
                     func.coalesce(models.Booking.end_date, models.Booking.date) >= start)
             .all())
    books_by_bus = {}
    for b in books:
        books_by_bus.setdefault(b.bus_id, []).append(b)

    contracts_by_bus = {}
    for c in db.query(models.Contract).all():
        contracts_by_bus.setdefault(c.bus_id, []).append(c)

    rows = []
    for bus in db.query(models.Bus).order_by(models.Bus.sort_order).all():
        overlapping = [c for c in contracts_by_bus.get(bus.id, [])
                       if _overlap_days(c.start_date, c.end_date, start, end) > 0]
        if not overlapping:
            continue  # no contract this month -> not on the analysis

        # contracted days that fall in this month
        covered = set()
        for c in overlapping:
            s, e = max(c.start_date, start), min(c.end_date, end)
            for off in range((e - s).days + 1):
                covered.add(s + timedelta(days=off))
        covered_days = len(covered)

        # result from the contract overlapping the month the most
        chosen, best = None, 0
        for c in overlapping:
            ov = _overlap_days(c.start_date, c.end_date, start, end)
            if ov > best:
                chosen, best = c, ov
        res = compute_contract_result(db, chosen)
        revenue, loyer = res["revenue"], res["loyer"]
        coverage = round(revenue / loyer * 100) if loyer > 0 else None

        # time occupancy from the trips themselves
        bks = books_by_bus.get(bus.id, [])
        worked, multi_days = set(), set()
        timed_hours, timed_days, missing_time = 0.0, 0, 0
        for b in bks:
            s, e = max(b.date, start), min(b.end_date or b.date, end)
            is_multi = b.end_date is not None and b.end_date != b.date
            for off in range((e - s).days + 1):
                d = s + timedelta(days=off)
                worked.add(d)
                if is_multi:
                    multi_days.add(d)
            if not is_multi:
                h = _hours(b.heure_debut or "", b.heure_fin or "")
                if h is not None:
                    timed_hours += h
                    timed_days += 1
                else:
                    missing_time += 1

        worked_days = len(worked)
        rows.append({
            "id": bus.id, "name": bus.name, "type": bus.type, "region": bus.region or "—",
            "revenue": revenue, "loyer": loyer, "fuel": res["fuel"], "net": res["net"],
            "is_estimated": res["is_estimated"], "coverage": coverage,
            "trips": len(bks), "covered_days": covered_days, "worked_days": worked_days,
            "day_occ": round(worked_days / covered_days * 100) if covered_days else 0,
            "timed_hours": round(timed_hours, 1),
            "avg_hours": round(timed_hours / timed_days, 1) if timed_days else None,
            "multi_days": len(multi_days),
            "missing_time": missing_time,           # same-day trips with no hours entered
            "time_complete": missing_time == 0,     # is the time data complete for this bus?
        })

    return {"year": year, "month": month, "label": f"{calc.MONTH_FR[month]} {year}", "buses": rows}
