"""Region history of a vehicle: dated periods, moves, and retroactive re-assignment.

A bus's region is never a single overwritten value but a set of dated periods
(BusRegionPeriod). Everything on the Calendrier / Analyse is derived day by day from them,
so changing a period changes where the trips and the money of those days are counted.

Three writers, all here:
  record_move        "from this date on the bus is in X"        (the period it was in is closed)
  assign_region_range "between these two dates the bus was in X" (any past/future window)
  (the explicit "+ Période" editor in the controller for fine-grained history)
"""
from datetime import date, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from .audit import log_action
from .lookups import norm_region, _region_on_day

DAY = timedelta(days=1)
MAX_SPAN_DAYS = 3660     # ten years: more than any realistic correction


def uncovered_ranges(periods, first: date, last: date) -> list[tuple[date, date]]:
    """The stretches of [first..last] that NO period covers.

    Those are exactly the days whose region silently falls back to the bus's `region`
    field — i.e. the days a future move would re-attribute. Returned so they can be
    pinned down before the move happens."""
    gaps, cur = [], first
    for p in sorted(periods, key=lambda p: p.effective_from):
        p_end = p.effective_to or date.max
        if p_end < cur:
            continue                       # entirely behind us
        if p.effective_from > cur:
            gaps.append((cur, min(p.effective_from - timedelta(days=1), last)))
        if p_end >= last:
            break                          # the rest of the window is covered
        cur = p_end + timedelta(days=1)
    else:
        if cur <= last:
            gaps.append((cur, last))
    return [(a, b) for a, b in gaps if a <= b]


def first_known_day(db: Session, bus: models.Bus, periods) -> date | None:
    """The vehicle's earliest day on file — first trip, first contract, or first region
    period, whichever comes first. Everything from there on is history to protect."""
    firsts = [
        db.query(func.min(models.Booking.date)).filter(models.Booking.bus_id == bus.id).scalar(),
        db.query(func.min(models.Contract.start_date)).filter(models.Contract.bus_id == bus.id).scalar(),
        min((p.effective_from for p in periods), default=None),
    ]
    firsts = [d for d in firsts if d]
    return min(firsts) if firsts else None


def record_move(db: Session, bus: models.Bus, region: str, moved_on: date, admin: str) -> models.BusRegionPeriod:
    """Record a region move: close what the vehicle was in the day BEFORE, open the new
    period from `moved_on`.

    This is the single writer of region history. Everything the vehicle did before
    `moved_on` keeps the region it had then, only the days from `moved_on` on get the
    new one — a region change can never re-attribute a past month's figures."""
    region = norm_region(region)
    prev_day = moved_on - timedelta(days=1)
    periods = db.query(models.BusRegionPeriod).filter(models.BusRegionPeriod.bus_id == bus.id).all()

    # Pin down EVERY past day that no period covers, with the region the vehicle is
    # LEAVING — otherwise those days keep falling back to `bus.region`, which is about
    # to become the new region, and the past silently moves with it.
    # All the holes are filled, not just the one right before the move: history entered
    # month by month leaves gaps everywhere, and any one of them would flip.
    first_known = first_known_day(db, bus, periods)
    if first_known and norm_region(bus.region):
        for gap_from, gap_to in uncovered_ranges(periods, first_known, prev_day):
            db.add(models.BusRegionPeriod(bus_id=bus.id, region=norm_region(bus.region),
                                          effective_from=gap_from, effective_to=gap_to))

    for p in periods:                       # nothing may stay open across the move date
        if p.effective_to is None or p.effective_to >= moved_on:
            if p.effective_from < moved_on:
                p.effective_to = prev_day
            else:
                db.delete(p)                # a later period is superseded by this move

    rp = models.BusRegionPeriod(bus_id=bus.id, region=region, effective_from=moved_on, effective_to=None)
    db.add(rp)
    bus.region = region                     # the `region` field only means "where it is now"
    log_action(db, admin, "Région période", f"{bus.name} → {region} dès le {moved_on.isoformat()}")
    return rp


def _bus_periods(db: Session, bus: models.Bus) -> list:
    return db.query(models.BusRegionPeriod).filter(models.BusRegionPeriod.bus_id == bus.id).all()


def assign_region_range(db: Session, bus: models.Bus, region: str, d_from: date, d_to: date | None,
                        admin: str) -> models.BusRegionPeriod:
    """Declare that `bus` was in `region` from `d_from` to `d_to` (inclusive).

    The window may overlap any existing periods: they are trimmed, split or removed so the
    day-by-day region stays unambiguous, and neighbours already in the same region are
    merged (no confetti of tiny periods). Nothing outside the window is touched.

    `d_to=None` means "from this date on" and is exactly a move.
    If the window contains today, the vehicle IS in that region now: `bus.region` ("where
    it is now") follows, after the days it used to cover by default are pinned to the
    region it is leaving, so no other part of the past silently changes.
    """
    region = norm_region(region)
    if d_to is None:
        return record_move(db, bus, region, d_from, admin)

    periods = _bus_periods(db, bus)
    covers_today = d_from <= date.today() <= d_to
    old_region = norm_region(bus.region)

    if covers_today and old_region and old_region != region:
        first_known = first_known_day(db, bus, periods)
        if first_known and first_known < d_from:
            for g_from, g_to in uncovered_ranges(periods, first_known, d_from - DAY):
                db.add(models.BusRegionPeriod(bus_id=bus.id, region=old_region,
                                              effective_from=g_from, effective_to=g_to))
            db.flush()
            periods = _bus_periods(db, bus)

    # carve the window out of whatever it overlaps
    pieces = []
    for p in periods:
        p_end = p.effective_to or date.max
        if p_end < d_from or p.effective_from > d_to:
            continue                                    # no overlap
        left, right = p.effective_from < d_from, p_end > d_to
        if left and right:                              # the window sits inside: split in two
            pieces.append((p.region, d_to + DAY, p.effective_to))
            p.effective_to = d_from - DAY
        elif left:
            p.effective_to = d_from - DAY
        elif right:
            p.effective_from = d_to + DAY
        else:
            db.delete(p)
    db.flush()                                          # deletions first: unique (bus, start) keys
    for reg, f, t in pieces:
        db.add(models.BusRegionPeriod(bus_id=bus.id, region=reg, effective_from=f, effective_to=t))
    db.flush()

    # insert the window, merged with same-region neighbours
    periods = _bus_periods(db, bus)
    prev = next((p for p in periods if p.effective_to == d_from - DAY and norm_region(p.region) == region), None)
    nxt = next((p for p in periods if p.effective_from == d_to + DAY and norm_region(p.region) == region), None)
    if prev and nxt:
        prev.effective_to = nxt.effective_to
        db.delete(nxt)
        result = prev
    elif prev:
        prev.effective_to = d_to
        result = prev
    elif nxt:
        nxt.effective_from = d_from
        result = nxt
    else:
        result = models.BusRegionPeriod(bus_id=bus.id, region=region, effective_from=d_from, effective_to=d_to)
        db.add(result)

    if covers_today:
        bus.region = region
    log_action(db, admin, "Région période",
               f"{bus.name} : {region} du {d_from.isoformat()} au {d_to.isoformat()}")
    return result


def preview_assign(db: Session, bus: models.Bus, region: str, d_from: date, d_to: date | None) -> dict:
    """What would assign_region_range change? Nothing is written.

    Counts, per region the days used to belong to, the days and the recorded trips/revenue
    that would move to `region`."""
    region = norm_region(region)
    today = date.today()
    last = d_to or max(today, d_from)
    if d_to is None and d_from > today:
        last = d_from - DAY                              # open-ended in the future: nothing to move yet
    periods = _bus_periods(db, bus)
    fallback = norm_region(bus.region)

    def old_region(day):
        return norm_region(_region_on_day(periods, day, fallback))

    moved: dict[str, dict] = {}
    total_days = unchanged = 0
    day = d_from
    while day <= last:
        total_days += 1
        r = old_region(day)
        if r == region:
            unchanged += 1
        else:
            moved.setdefault(r or "—", {"region": r or "—", "days": 0, "trips": 0, "revenue": 0.0})["days"] += 1
        day += DAY

    if last >= d_from:
        trips = (db.query(models.Booking)
                 .filter(models.Booking.bus_id == bus.id, models.Booking.type == "Booking",
                         models.Booking.date >= d_from, models.Booking.date <= last).all())
        for b in trips:
            r = old_region(b.date)
            if r != region:
                g = moved.setdefault(r or "—", {"region": r or "—", "days": 0, "trips": 0, "revenue": 0.0})
                g["trips"] += 1
                g["revenue"] = round(g["revenue"] + float(b.total or 0), 2)

    rows = sorted(moved.values(), key=lambda g: -g["days"])
    return {
        "to_region": region, "open_ended": d_to is None,
        "days": total_days, "unchanged_days": unchanged,
        "changed_days": sum(g["days"] for g in rows),
        "trips": sum(g["trips"] for g in rows),
        "revenue": round(sum(g["revenue"] for g in rows), 2),
        "from": rows,
    }
