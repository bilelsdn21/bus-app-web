"""Builds the monthly calendar grid (day colors + contract-aware net + summary)."""
from datetime import date, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from . import calc
from .lookups import get_config, region_periods_by_bus, region_segments
from .contracts import compute_contract_result, preload
from .rentals import rented_vehicles_summary


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

    periods_by_bus = region_periods_by_bus(db)

    # contracts grouped by bus, to pick the one overlapping the viewed month
    contracts = db.query(models.Contract).all()
    contracts_by_bus = {}
    for c in contracts:
        contracts_by_bus.setdefault(c.bus_id, []).append(c)

    # bulk-load what every contract result needs (2 queries total, not 2 per vehicle)
    all_books, all_fuels = preload(db, [c for cs in contracts_by_bus.values() for c in cs
                                        if _overlap_days(c.start_date, c.end_date, start, end) > 0])

    bus_list = []
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

        days = {}
        for day in range(1, end.day + 1):
            ds = date(year, month, day).isoformat()
            cell = by_cell.get((bus.id, ds), [])
            if cell:
                days[day] = calc.day_color(cell, cfg.cut_morn, cfg.cut_night)

        # net = result of the contract overlapping the viewed month the most
        chosen, best = None, 0
        for c in overlapping:
            ov = _overlap_days(c.start_date, c.end_date, start, end)
            if ov > best:
                chosen, best = c, ov

        # the contract window cut into single-region stretches: one row per stretch, so
        # a vehicle that moved mid-contract appears under BOTH region blocks, each row
        # holding only its own days and its own share of the result
        segs = region_segments(bus, chosen.start_date, chosen.end_date, periods_by_bus)
        res = compute_contract_result(db, chosen, segments=segs,
                                      books=all_books, fuels=all_fuels)
        contract_block = {
            "id": chosen.id, "label": chosen.label,
            "start_date": chosen.start_date.isoformat(),
            "end_date": chosen.end_date.isoformat(),
            "revenue": res["revenue"], "loyer": res["loyer"], "fuel": res["fuel"],
            "net": res["net"],
        }
        base = {"id": bus.id, "name": bus.name, "type": bus.type, "distance": bus.distance,
                "is_estimated": res["is_estimated"], "contract": contract_block,
                "_sort": bus.sort_order or 0}

        if len(segs) == 1:
            bus_list.append({**base, "key": str(bus.id), "region": segs[0]["region"],
                             "covered_days": sorted(covered), "days": days,
                             "net": res["net"], "pct": res["pct"],
                             "revenue": res["revenue"], "loyer": res["loyer"], "fuel": res["fuel"],
                             "segment": None})
            continue

        parts = res["segments"]
        for i, (s, p) in enumerate(zip(segs, parts)):
            # display window: the segment's days inside the month, with the first/last
            # segment stretched to the month edges so activity outside the contract
            # window is still shown exactly once (never hidden, never duplicated).
            # A segment sitting entirely in another month shows no day at all — its
            # share of the result still appears, dated by the chip on the row.
            ov_from, ov_to = max(s["from"], start), min(s["to"], end)
            if ov_from > ov_to:
                d_from, d_to, span = 0, 0, set()
            else:
                d_from = 1 if i == 0 else ov_from.day
                d_to = end.day if i == len(segs) - 1 else ov_to.day
                span = set(range(d_from, d_to + 1))
            bus_list.append({
                **base, "key": f"{bus.id}-{i}", "region": s["region"],
                "covered_days": sorted(covered & span),
                "days": {d: c for d, c in days.items() if d in span},
                "net": p["net"], "pct": p["pct"],
                "revenue": p["revenue"], "loyer": p["loyer"], "fuel": p["fuel"],
                "segment": {
                    "region": s["region"], "index": i, "count": len(segs),
                    "from": p["from"], "to": p["to"], "days": p["days"],
                    "prev_region": segs[i - 1]["region"] if i > 0 else None,
                    "next_region": segs[i + 1]["region"] if i < len(segs) - 1 else None,
                    "moved_on": s["from"].isoformat() if i > 0 else None,
                    "day_from": d_from, "day_to": d_to,
                    "prorated": True,
                },
            })

    # keep the fleet order, but group rows by region so each region block stays
    # contiguous even when one vehicle contributes a row to two of them
    block = {}
    for r in bus_list:
        block.setdefault(r["region"], len(block))
    bus_list.sort(key=lambda r: (block[r["region"]], r["_sort"]))
    for r in bus_list:
        r.pop("_sort", None)

    # region summary — built from the SEGMENT rows, so a mid-month move lands on both
    # sides in exactly the right proportion
    reg = {}
    seen = {}
    for r in bus_list:
        k = r["region"] or "—"
        g = reg.setdefault(k, {"region": k, "loyer": 0.0, "net": 0.0, "count": 0})
        g["loyer"] += r["loyer"]; g["net"] += r["net"]
        seen.setdefault(k, set()).add(r["id"])
    for k, g in reg.items():
        g["count"] = len(seen[k])
    # vehicles counted in more than one region because they moved during the month
    shared = len([b for b in {r["id"] for r in bus_list}
                  if sum(1 for s in seen.values() if b in s) > 1])

    # externally rented reinforcement vehicles (not part of our fleet): shown as an
    # informational total on the Calendrier page, but NOT subtracted from the fleet's
    # Net/region totals below — the Loués page's data is purely informative here.
    rentals = rented_vehicles_summary(db, year, month)

    regions = list(reg.values())
    for g in regions:
        g["pct"] = calc.pct(g["net"], g["loyer"])
    total = {"region": "TOTAL",
             "loyer": sum(g["loyer"] for g in regions),
             "net": sum(g["net"] for g in regions),
             # distinct vehicles — a vehicle that moved is one vehicle, not two
             "count": len({r["id"] for r in bus_list})}
    total["pct"] = calc.pct(total["net"], total["loyer"])
    summary = {"regions": regions, "total": total, "rentals": rentals, "shared": shared}

    return {
        "year": year, "month": month,
        "label": f"{calc.MONTH_FR[month]} {year}",
        "days_in_month": end.day,
        "cut_morn": cfg.cut_morn, "cut_night": cfg.cut_night,
        "buses": bus_list,
        "summary": summary,
    }
