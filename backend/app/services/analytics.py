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
from .contracts import compute_contract_result, preload
from .lookups import region_periods_by_bus, region_segments


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


def _time_stats(bks, w_from, w_to) -> dict:
    """Occupancy stats restricted to one window [w_from..w_to] (already clipped to the
    month). Worked DAYS are counted day by day, while a trip's count/hours belong to the
    window containing its START date — the same rule the revenue split uses, so the
    windows of a vehicle that moved region never double-count anything."""
    worked, multi_days = set(), set()
    timed_hours, timed_days, missing_time, trips = 0.0, 0, 0, 0
    for b in bks:
        is_multi = b.end_date is not None and b.end_date != b.date
        s, e = max(b.date, w_from), min(b.end_date or b.date, w_to)
        for off in range((e - s).days + 1 if s <= e else 0):
            d = s + timedelta(days=off)
            worked.add(d)
            if is_multi:
                multi_days.add(d)
        if not (w_from <= b.date <= w_to):
            continue
        trips += 1
        if not is_multi:
            h = _hours(b.heure_debut or "", b.heure_fin or "")
            if h is not None:
                timed_hours += h
                timed_days += 1
            else:
                missing_time += 1
    return {
        "trips": trips, "worked_days": len(worked), "multi_days": len(multi_days),
        "timed_hours": round(timed_hours, 1),
        "avg_hours": round(timed_hours / timed_days, 1) if timed_days else None,
        "missing_time": missing_time,
    }


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

    periods_by_bus = region_periods_by_bus(db)

    chosen_pool = [c for cs in contracts_by_bus.values() for c in cs
                   if _overlap_days(c.start_date, c.end_date, start, end) > 0]
    all_books, all_fuels = preload(db, chosen_pool)

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

        # result from the contract overlapping the month the most
        chosen, best = None, 0
        for c in overlapping:
            ov = _overlap_days(c.start_date, c.end_date, start, end)
            if ov > best:
                chosen, best = c, ov

        # one row per single-region stretch of the contract: a vehicle that changed
        # region mid-month is analysed once per region, on its own days only
        segs = region_segments(bus, chosen.start_date, chosen.end_date, periods_by_bus)
        res = compute_contract_result(db, chosen, segments=segs,
                                      books=all_books, fuels=all_fuels)
        bks = books_by_bus.get(bus.id, [])
        parts = res["segments"] if len(segs) > 1 else [None]

        for i, p in enumerate(parts):
            if p is None:      # never moved -> the whole month, exactly as before
                w_from, w_to, region, seg = start, end, segs[0]["region"], None
                revenue, loyer, fuel, net = res["revenue"], res["loyer"], res["fuel"], res["net"]
            else:
                s = segs[i]
                ov_from, ov_to = max(s["from"], start), min(s["to"], end)
                w_from = start if i == 0 else ov_from
                w_to = end if i == len(segs) - 1 else ov_to
                if ov_from > ov_to:       # stretch lies entirely in another month
                    w_from, w_to = end + timedelta(days=1), end
                region = s["region"]
                revenue, loyer, fuel, net = p["revenue"], p["loyer"], p["fuel"], p["net"]
                seg = {"region": region, "index": i, "count": len(segs),
                       "from": p["from"], "to": p["to"], "days": p["days"],
                       "moved_on": s["from"].isoformat() if i > 0 else None,
                       "prorated": True}

            seg_covered = len([d for d in covered if w_from <= d <= w_to])
            st = _time_stats(bks, w_from, w_to)
            rows.append({
                "id": bus.id, "key": f"{bus.id}-{i}" if seg else str(bus.id),
                "name": bus.name, "type": bus.type, "region": region or "—", "segment": seg,
                "revenue": revenue, "loyer": loyer, "fuel": fuel, "net": net,
                "is_estimated": res["is_estimated"],
                "coverage": round(revenue / loyer * 100) if loyer > 0 else None,
                "covered_days": seg_covered,
                "day_occ": round(st["worked_days"] / seg_covered * 100) if seg_covered else 0,
                "time_complete": st["missing_time"] == 0,   # is the time data complete?
                **st,
            })

    return {"year": year, "month": month, "label": f"{calc.MONTH_FR[month]} {year}", "buses": rows}
