"""Per-vehicle overview for the Paramètres > Véhicules list.

Everything you can sensibly filter a vehicle on that is NOT on the Bus row itself:
when it actually worked, how much is recorded against it, which regions it has been
in, and — the reason this exists — whether its region history has holes.

A hole is a day the vehicle was on file (contract or trip) that no BusRegionPeriod
covers. Those days fall back to the bus's CURRENT `region` field, so they flip to
wherever the vehicle is today. That is what makes an old year suddenly show a
vehicle under the wrong region block. Only vehicles that HAVE periods are checked:
one with none has never moved, and the fallback is then its only, correct, region.
"""
from datetime import date, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from .lookups import norm_region

DAY = timedelta(days=1)


def _merge(spans: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """Sorted, non-overlapping spans; touching spans are joined."""
    out: list[list[date]] = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1] + DAY:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def _subtract(base: list[tuple[date, date]], cuts: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """`base` minus `cuts` — the parts of base no cut covers."""
    cuts = sorted(cuts)
    rest: list[tuple[date, date]] = []
    for s, e in base:
        cur = s
        for cs, ce in cuts:
            ce = min(ce, e)                 # clamp: cuts may be open-ended
            if ce < cur or cs > e:
                continue
            if cs > cur:
                rest.append((cur, cs - DAY))
            cur = max(cur, ce + DAY)    # ce is clamped to e, so this never overflows
            if cur > e:
                break
        if cur <= e:
            rest.append((cur, e))
    return [(a, b) for a, b in rest if a <= b]


def fleet_overview(db: Session) -> list[dict]:
    """One row per vehicle, enriched with the facts the Véhicules filter works on."""
    contracts: dict[int, list[tuple[date, date]]] = {}
    for bus_id, s, e in db.query(models.Contract.bus_id, models.Contract.start_date,
                                 models.Contract.end_date).all():
        contracts.setdefault(bus_id, []).append((s, e))

    trips: dict[int, list[tuple[date, date]]] = {}
    for bus_id, s, e in db.query(models.Booking.bus_id, models.Booking.date,
                                 func.coalesce(models.Booking.end_date, models.Booking.date)).all():
        trips.setdefault(bus_id, []).append((s, e))

    periods: dict[int, list[models.BusRegionPeriod]] = {}
    for p in db.query(models.BusRegionPeriod).all():
        periods.setdefault(p.bus_id, []).append(p)

    rows = []
    for bus in db.query(models.Bus).order_by(models.Bus.sort_order, models.Bus.id).all():
        ctr, trp, per = contracts.get(bus.id, []), trips.get(bus.id, []), periods.get(bus.id, [])
        activity = _merge(ctr + trp)

        # years the vehicle is on the Calendrier/Analyse — those pages are contract-gated
        years = sorted({y for s, e in ctr for y in range(s.year, e.year + 1)})

        # every region the vehicle has ever been in, current one included
        regions = sorted({norm_region(p.region) for p in per if norm_region(p.region)}
                         | ({norm_region(bus.region)} if norm_region(bus.region) else set()))

        # A hole AFTER the last declared period is the normal "it is there now and we
        # never wrote it down" case. A hole BEFORE or BETWEEN periods is the harmful
        # one: those are past days whose region is guessed from where the vehicle is
        # today, which is how an old year ends up under the wrong region block.
        gaps = []
        if per and activity:
            covered = [(p.effective_from, p.effective_to or date.max) for p in per]
            last_end = max((p.effective_to or date.max) for p in per)
            for a, z in _subtract(activity, covered):
                gaps.append({"from": a.isoformat(), "to": z.isoformat(),
                             "days": (z - a).days + 1,
                             "kind": "trailing" if a > last_end else "past"})

        rows.append({
            "id": bus.id, "name": bus.name, "plate": bus.plate or "", "type": bus.type,
            "region": norm_region(bus.region), "distance": bus.distance or 0.0,
            "contracts": len(ctr), "trips": len(trp),
            "first_day": activity[0][0].isoformat() if activity else None,
            "last_day": activity[-1][1].isoformat() if activity else None,
            "years": years,
            "regions": regions,
            "moved": len(regions) > 1,
            "region_periods": len(per),
            # days on file whose region is only a fallback to `region` above
            "region_gaps": gaps,
            "gap_days": sum(g["days"] for g in gaps),
            # only the holes that sit in already-recorded history
            "past_gap_days": sum(g["days"] for g in gaps if g["kind"] == "past"),
        })
    return rows
