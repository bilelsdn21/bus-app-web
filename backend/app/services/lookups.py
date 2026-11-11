"""Small DB lookups shared across controllers/services."""
import re as _re
from datetime import date as _date, timedelta as _timedelta
from sqlalchemy.orm import Session
from .. import models


def norm_region(name) -> str:
    """The ONE canonical spelling of a region name.

    Regions are compared and grouped as plain text everywhere (calendar blocks, region
    segments, analytics). "Djerba", "Djerba " and "DJERBA" must therefore be the same
    region, or the calendar shows two Djerba blocks and a vehicle that stays put looks
    like it moved. Whitespace is collapsed and each word is capitalised ("Nord-Ouest",
    "M'saken"); every read AND every write goes through here."""
    s = " ".join(str(name or "").split())
    return _re.sub(r"[^\s\-]+", lambda m: m.group(0)[:1].upper() + m.group(0)[1:].lower(), s)


def get_config(db: Session) -> models.Config:
    """The single Config row (period cutoffs). Created with defaults if missing."""
    cfg = db.query(models.Config).first()
    if not cfg:
        cfg = models.Config(cut_morn=13, cut_night=22)
        db.add(cfg); db.commit(); db.refresh(cfg)
    return cfg


def price_for(db: Session, destination: str, bus_type: str, on_date=None) -> float:
    """Unit price for a destination given the bus type (MICRO/OTOKAR/BUS).

    If `on_date` is given, the price IN EFFECT on that date is used: the current
    destination price for dates >= Config.current_prices_since, otherwise the most
    recent historical PricePeriod (<= on_date) for that destination — falling back
    to the current price if the destination had no different historical price."""
    bt = (bus_type or "").upper()
    d = db.query(models.Destination).filter(models.Destination.name == destination).first()
    if not d:
        return 0.0
    current = {"MICRO": d.price_micro, "OTOKAR": d.price_otokar, "BUS": d.price_bus}.get(bt, 0.0)
    if on_date is None:
        return current

    # a price period whose [from .. to] range contains the trip's date wins;
    # otherwise the current destination price applies.
    p = (db.query(models.PricePeriod)
         .filter(models.PricePeriod.dest_name == destination,
                 models.PricePeriod.effective_from <= on_date,
                 (models.PricePeriod.effective_to == None) | (models.PricePeriod.effective_to >= on_date))  # noqa: E711
         .order_by(models.PricePeriod.effective_from.desc()).first())
    if p:
        return {"MICRO": p.price_micro, "OTOKAR": p.price_otokar, "BUS": p.price_bus}.get(bt, 0.0)
    return current  # date is outside every period -> current price


def region_periods_by_bus(db: Session) -> dict[int, list]:
    """All BusRegionPeriod rows, grouped by bus_id — load once per request, reuse per bus."""
    out: dict[int, list] = {}
    for p in db.query(models.BusRegionPeriod).all():
        out.setdefault(p.bus_id, []).append(p)
    return out


def _region_on_day(periods: list, day: _date, fallback: str) -> str:
    """The region declared for one day. If several periods cover it (overlapping rows),
    the one declared LAST (greatest effective_from) wins — a newer decision supersedes
    an older one. No period covering the day -> the bus's current `region` field."""
    best = None
    for p in periods:
        p_end = p.effective_to or _date.max
        if p.effective_from <= day <= p_end:
            if best is None or p.effective_from > best.effective_from:
                best = p
    return norm_region(best.region if best else fallback)


def region_on(bus, day: _date, periods_by_bus: dict[int, list]) -> str:
    """The bus's region on ONE precise day — the day-level truth everything else is
    derived from (a trip belongs to the region the bus was in on the day it ran)."""
    return _region_on_day(periods_by_bus.get(bus.id, []), day, bus.region or "")


def region_segments(bus, start: _date, end: _date, periods_by_bus: dict[int, list]) -> list[dict]:
    """Cut [start..end] into consecutive stretches, each in ONE region.

    This is the permanent answer to "the bus moved mid-period": instead of forcing a
    whole month/contract into a single region, the window is split at the move date and
    each side keeps its own days — so revenue booked before the move stays in the old
    region and revenue booked after stays in the new one, forever, with nothing rewritten.

    A bus that never moved yields exactly ONE segment covering the whole window, which
    is why every caller behaves identically to before for such buses.
    Returns [{region, from, to, days, index, count}], contiguous and gapless.
    """
    fallback = norm_region(bus.region)
    periods = periods_by_bus.get(bus.id, [])
    segs: list[dict] = []
    day = start
    while day <= end:
        r = _region_on_day(periods, day, fallback)
        if segs and segs[-1]["region"] == r:
            segs[-1]["to"] = day
        else:
            segs.append({"region": r, "from": day, "to": day})
        day += _timedelta(days=1)
    for i, s in enumerate(segs):
        s["days"] = (s["to"] - s["from"]).days + 1
        s["index"] = i
        s["count"] = len(segs)
    return segs


def region_for(bus, start: _date, end: _date, periods_by_bus: dict[int, list]) -> str:
    """A SINGLE region label for a window — the segment holding the most days.

    Kept for anything that can only display one label. Do NOT use it for figures: it
    collapses a mid-window move onto one side, which is exactly the loss of precision
    region_segments() exists to prevent."""
    segs = region_segments(bus, start, end, periods_by_bus)
    return max(segs, key=lambda s: s["days"])["region"] if segs else norm_region(bus.region)
