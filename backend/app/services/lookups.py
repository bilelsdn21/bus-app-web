"""Small DB lookups shared across controllers/services."""
from datetime import date as _date
from sqlalchemy.orm import Session
from .. import models


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


def region_for(bus, start: _date, end: _date, periods_by_bus: dict[int, list]) -> str:
    """The bus's region for a calendar month [start..end]: the historical region period
    overlapping it the most (same "most overlap wins" rule used to pick a contract for
    the month), or the bus's current `region` field if it has no periods."""
    best, best_ov = None, 0
    for p in periods_by_bus.get(bus.id, []):
        p_end = p.effective_to or _date.max
        s, e = max(p.effective_from, start), min(p_end, end)
        ov = (e - s).days + 1 if s <= e else 0
        if ov > best_ov:
            best, best_ov = p, ov
    return best.region if best else (bus.region or "")
