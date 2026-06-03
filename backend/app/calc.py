"""
Single source of truth for all business calculations — ported from the Excel
VBA/formulas so the web app behaves identically:

  - Net Mois  = sum(Booking totals for the month) - monthly loyer
  - % Result  = net / loyer
  - Dot color = by START-time period; green only if 2+ trips span different periods
  - Region summary = totals per region
"""
from datetime import date
import calendar as _cal

MONTH_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}

# period codes
MORNING, EVENING, NIGHT, UNKNOWN = 1, 2, 3, 0


def get_period(heure: str, cut_morn: int, cut_night: int) -> int:
    """Return MORNING/EVENING/NIGHT from a 'HH:MM' start time, UNKNOWN if blank/bad."""
    if not heure or ":" not in heure:
        return UNKNOWN
    try:
        h = int(heure.split(":")[0])
    except (ValueError, IndexError):
        return UNKNOWN
    if h < cut_morn:
        return MORNING
    if h < cut_night:
        return EVENING
    return NIGHT


def day_color(day_bookings, cut_morn=13, cut_night=22) -> str:
    """
    Day dot color. Returns one of: "" | red | green | yellow | orange | purple
      - red    : unavailable only
      - green  : RESERVED — a multi-day excursion covers this day, OR
                 two+ excursions fall in different time periods
      - yellow/orange/purple : a single time period (matin / soir / nuit)
    """
    books = [b for b in day_bookings if b.get("type") == "Booking"]
    unavail = [b for b in day_bookings if b.get("type") != "Booking"]
    if not day_bookings:
        return ""
    if unavail and not books:
        return "red"
    # a multi-day excursion reserves the whole span -> green
    if any(b.get("multi") for b in books):
        return "green"
    # two+ excursions in different periods -> green
    periods = {get_period(b.get("heure_debut", ""), cut_morn, cut_night) for b in books}
    periods.discard(UNKNOWN)
    if len(periods) > 1:
        return "green"
    p = next(iter(periods)) if periods else UNKNOWN
    return {MORNING: "yellow", EVENING: "orange", NIGHT: "purple"}.get(p, "green")


def month_bounds(year: int, month: int):
    last = _cal.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def bus_net(bus, month_bookings) -> float:
    """Revenue (Booking totals) - loyer, for one bus in the month."""
    rev = sum(float(b.get("total") or 0)
              for b in month_bookings
              if b["bus_id"] == bus["id"] and b.get("type") == "Booking")
    return rev - float(bus.get("loyer") or 0)


def pct(net: float, loyer: float) -> str:
    if not loyer:
        return "—"
    p = net / loyer * 100
    return f"{'+' if p >= 0 else ''}{p:.1f}%"


def iter_months(start: date, end: date):
    """Yield (year, month) for every calendar month touched by [start, end]."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1; y += 1


def prorate_fuel(start: date, end: date, fuel_by_month: dict):
    """
    Spread each calendar month's fuel across the contract window by DAY overlap.
    fuel_by_month: {(year, month): {"estimated": x, "actual": y_or_None}}
    Returns (total_fuel, is_estimated, breakdown[]).
    is_estimated = True if any overlapped month has no actual yet.
    """
    total = 0.0
    estimated_flag = False
    breakdown = []
    for (y, m) in iter_months(start, end):
        days_in_month = _cal.monthrange(y, m)[1]
        m_start = date(y, m, 1)
        m_end = date(y, m, days_in_month)
        ov_start = max(start, m_start)
        ov_end = min(end, m_end)
        if ov_start > ov_end:
            continue
        days_overlap = (ov_end - ov_start).days + 1
        fm = fuel_by_month.get((y, m), {})
        actual = fm.get("actual")
        est = fm.get("estimated") or 0.0
        value = actual if actual is not None else est
        is_actual = actual is not None
        if not is_actual:
            estimated_flag = True
        contrib = (value or 0.0) * days_overlap / days_in_month
        total += contrib
        breakdown.append({
            "year": y, "month": m, "days": days_overlap, "days_in_month": days_in_month,
            "fuel_month": value or 0.0, "is_actual": is_actual,
            "contribution": round(contrib, 2),
        })
    return round(total, 2), estimated_flag, breakdown


def contract_result(contract, bookings, fuel_by_month):
    """
    Precise per-contract result.
      revenue = Σ Booking totals dated within [start, end]
      net     = revenue - loyer - prorated_fuel
    bookings: list of dicts with bus_id, date(date obj), type, total
    """
    start, end = contract["start_date"], contract["end_date"]
    revenue = sum(
        float(b.get("total") or 0)
        for b in bookings
        if b["bus_id"] == contract["bus_id"]
        and b.get("type") == "Booking"
        and start <= b["date"] <= end
    )
    loyer = float(contract.get("loyer") or 0)
    fuel, est_flag, breakdown = prorate_fuel(start, end, fuel_by_month)
    net = revenue - loyer - fuel
    return {
        "revenue": round(revenue, 2),
        "loyer": round(loyer, 2),
        "fuel": fuel,
        "net": round(net, 2),
        "pct": pct(net, loyer),
        "is_estimated": est_flag,
        "fuel_breakdown": breakdown,
        "days": (end - start).days + 1,
    }


def region_summary(buses, month_bookings):
    """Totals per region + grand total. Loyer/net always computed from the SAME bus set."""
    regions = {}
    for bus in buses:
        reg = bus.get("region") or "—"
        r = regions.setdefault(reg, {"region": reg, "loyer": 0.0, "net": 0.0, "count": 0})
        r["loyer"] += float(bus.get("loyer") or 0)
        r["net"]   += bus_net(bus, month_bookings)
        r["count"] += 1
    rows = list(regions.values())
    for r in rows:
        r["pct"] = pct(r["net"], r["loyer"])
    grand = {
        "region": "TOTAL",
        "loyer": sum(r["loyer"] for r in rows),
        "net":   sum(r["net"] for r in rows),
        "count": sum(r["count"] for r in rows),
    }
    grand["pct"] = pct(grand["net"], grand["loyer"])
    return {"regions": rows, "total": grand}
