"""Contract result computation (revenue − loyer − prorated fuel), and its split across
region segments when the vehicle moved region during the contract."""
from sqlalchemy.orm import Session
from .. import models
from . import calc


def _balance(parts: list[dict], key: str, total: float) -> None:
    """Push the rounding residual onto the longest part so the segments ALWAYS sum back
    to the contract total to the cent — a split must never create or lose money."""
    if not parts:
        return
    diff = round(total - sum(p[key] for p in parts), 2)
    if abs(diff) >= 0.01:
        big = max(parts, key=lambda p: p["days"])
        big[key] = round(big[key] + diff, 2)


def _split_by_segments(contract, segments, bdicts, fuel_by_month, res) -> list[dict]:
    """One result per region segment of the contract window.

      revenue — EXACT: every booking falls in the segment containing its start date.
      loyer   — prorated by days (a flat monthly rent has no per-day truth).
      fuel    — prorated by day the same way prorate_fuel already does per month.

    Marked `prorated` so the UI can say which figures are measured and which allocated.
    """
    c_days = (contract.end_date - contract.start_date).days + 1
    loyer_total = float(contract.loyer or 0)
    parts = []
    for s in segments:
        s_from = max(s["from"], contract.start_date)
        s_to = min(s["to"], contract.end_date)
        days = (s_to - s_from).days + 1 if s_from <= s_to else 0
        revenue = sum(float(b.get("total") or 0) for b in bdicts
                      if b.get("type") == "Booking" and s_from <= b["date"] <= s_to)
        fuel = calc.prorate_fuel(s_from, s_to, fuel_by_month)[0] if days else 0.0
        parts.append({
            "region": s["region"], "index": s["index"], "count": s["count"],
            "from": s_from.isoformat(), "to": s_to.isoformat(), "days": days,
            "revenue": round(revenue, 2),
            "loyer": round(loyer_total * days / c_days, 2) if c_days else 0.0,
            "fuel": round(fuel, 2),
        })

    _balance(parts, "revenue", res["revenue"])
    _balance(parts, "loyer", res["loyer"])
    _balance(parts, "fuel", res["fuel"])
    for p in parts:
        p["net"] = round(p["revenue"] - p["loyer"] - p["fuel"], 2)
        p["pct"] = calc.pct(p["net"], p["loyer"])
        p["prorated"] = len(parts) > 1
    _balance(parts, "net", res["net"])
    return parts


def preload(db: Session, contracts) -> tuple[list, list]:
    """Bookings and fuel rows needed by many contracts, in 2 queries total."""
    contracts = list(contracts)
    if not contracts:
        return [], []
    ids = {c.bus_id for c in contracts}
    lo = min(c.start_date for c in contracts)
    hi = max(c.end_date for c in contracts)
    books = (db.query(models.Booking)
             .filter(models.Booking.bus_id.in_(ids),
                     models.Booking.date >= lo, models.Booking.date <= hi).all())
    fuels = db.query(models.FuelMonth).filter(models.FuelMonth.bus_id.in_(ids)).all()
    return books, fuels


def compute_contract_result(db: Session, contract: models.Contract, segments=None,
                            books=None, fuels=None) -> dict:
    """Load bookings + fuel for the contract window and compute the precise result.

    `segments` (from lookups.region_segments over the contract window) additionally
    splits that result per region — res["segments"] always sums back to res itself.

    `books` / `fuels` may be passed preloaded (callers handling many contracts do one bulk
    query instead of two per contract); they are filtered to this contract here."""
    if books is None:
        books = (db.query(models.Booking)
                 .filter(models.Booking.bus_id == contract.bus_id,
                         models.Booking.date >= contract.start_date,
                         models.Booking.date <= contract.end_date).all())
    else:
        books = [b for b in books if b.bus_id == contract.bus_id
                 and contract.start_date <= b.date <= contract.end_date]
    bdicts = [{"bus_id": b.bus_id, "date": b.date, "type": b.type, "total": b.total} for b in books]

    if fuels is None:
        fuels = (db.query(models.FuelMonth)
                 .filter(models.FuelMonth.bus_id == contract.bus_id).all())
    else:
        fuels = [f for f in fuels if f.bus_id == contract.bus_id]
    fuel_by_month = {(f.year, f.month): {"estimated": f.estimated, "actual": f.actual} for f in fuels}

    res = calc.contract_result(
        {"bus_id": contract.bus_id, "start_date": contract.start_date,
         "end_date": contract.end_date, "loyer": contract.loyer},
        bdicts, fuel_by_month)
    res.update({
        "contract_id": contract.id, "bus_id": contract.bus_id,
        "start_date": contract.start_date.isoformat(),
        "end_date": contract.end_date.isoformat(), "label": contract.label,
    })
    if segments:
        res["segments"] = _split_by_segments(contract, segments, bdicts, fuel_by_month, res)
    return res
