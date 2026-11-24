"""Numbers integrity: what the app SHOWS, measured, snapshotted and compared over time.

  measure(months)      the displayed figures (per region, total, per vehicle) of some months
  diff_measures(a, b)  what moved between two measurements
  take_snapshot(db)    store the figures of the last 13 months in the ledger (hash-chained)
  drift_report(db)     which months' figures changed between snapshots / since the last one,
                       and which registered changes explain it. A change that NOTHING in the
                       register explains is flagged: that is what a hidden edit looks like.
"""
import json
import threading
import time
from datetime import date, datetime, timedelta

from .. import models
from ..core import ledger
from ..core.database import SessionLocal
from .calendar import build_calendar

SNAPSHOT_EVERY = timedelta(hours=24)


def month_summary(db, year: int, month: int) -> dict:
    cal = build_calendar(db, year, month)
    buses: dict = {}
    for r in cal["buses"]:
        k = str(r["id"])
        buses[k] = round(buses.get(k, 0.0) + float(r["net"] or 0), 2)
    t = cal["summary"]["total"]
    return {
        "regions": {g["region"]: {"loyer": round(g["loyer"], 2), "net": round(g["net"], 2), "count": g["count"]}
                    for g in cal["summary"]["regions"]},
        "total": {"loyer": round(t["loyer"], 2), "net": round(t["net"], 2), "count": t["count"]},
        "buses": buses,
    }


def measure(months) -> dict:
    """Figures of each 'YYYY-MM' month, computed on a private session (never touches the caller's)."""
    out = {}
    with SessionLocal() as s:
        s.info["ledger_off"] = True          # reading must never write to the register
        for ym in months:
            y, m = int(ym[:4]), int(ym[5:7])
            out[ym] = month_summary(s, y, m)
        s.rollback()
    return out


def snapshot_months(today: date | None = None) -> list:
    t = today or date.today()
    y, m, out = t.year, t.month, []
    for _ in range(13):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return sorted(out)


def diff_measures(before: dict, after: dict) -> list:
    """Months whose figures differ, with the regions and vehicles that moved."""
    rows = []
    for ym in sorted(set(before) | set(after)):
        a, b = before.get(ym), after.get(ym)
        if a is None or b is None:
            continue
        ta, tb = a["total"]["net"], b["total"]["net"]
        regions = []
        for r in sorted(set(a["regions"]) | set(b["regions"])):
            na = (a["regions"].get(r) or {}).get("net", 0.0)
            nb = (b["regions"].get(r) or {}).get("net", 0.0)
            if abs(nb - na) >= 0.5:
                regions.append({"region": r, "before": na, "after": nb, "delta": round(nb - na, 2)})
        buses = []
        for k in sorted(set(a["buses"]) | set(b["buses"])):
            na, nb = a["buses"].get(k, 0.0), b["buses"].get(k, 0.0)
            if abs(nb - na) >= 0.5:
                buses.append({"id": int(k), "before": na, "after": nb, "delta": round(nb - na, 2)})
        buses.sort(key=lambda x: -abs(x["delta"]))
        loyer_changed = abs(b["total"]["loyer"] - a["total"]["loyer"]) >= 0.5
        if abs(tb - ta) >= 0.5 or regions or loyer_changed:
            rows.append({"month": ym, "total_before": ta, "total_after": tb, "delta": round(tb - ta, 2),
                         "loyer_before": a["total"]["loyer"], "loyer_after": b["total"]["loyer"],
                         "regions": regions, "buses": buses[:12]})
    return rows


# ------------------------------------------------------------------ snapshots
def take_snapshot(db, actor="système (instantané quotidien)"):
    months = snapshot_months()
    data = {"months": {}, "generated": datetime.utcnow().isoformat(timespec="seconds")}
    prev = db.info.get("ledger_off")
    db.info["ledger_off"] = True
    try:
        for ym in months:
            data["months"][ym] = month_summary(db, int(ym[:4]), int(ym[5:7]))
    finally:
        if prev is None:
            db.info.pop("ledger_off", None)
    e = ledger.append_entry(db, kind="snapshot", actor=actor, role="", ip="", action="snapshot", entity="numbers",
                            summary=f"Instantané des chiffres affichés ({len(months)} mois)", data=data)
    db.commit()
    return e


def last_snapshots(db, n=2):
    return (db.query(models.LedgerEntry).filter(models.LedgerEntry.kind == "snapshot")
            .order_by(models.LedgerEntry.id.desc()).limit(n).all())


_state = {"checked": 0.0, "running": False}


def maybe_snapshot_async(force_check=False):
    """Cheap to call often: at most one database check per 30 minutes, and a snapshot only when the
    last one is older than 24 h. Runs in a thread so no request ever waits for it."""
    now = time.time()
    if _state["running"] or (not force_check and now - _state["checked"] < 1800):
        return
    _state["checked"] = now

    def job():
        _state["running"] = True
        try:
            with SessionLocal() as s:
                last = last_snapshots(s, 1)
                if not last or datetime.utcnow() - last[0].created_at >= SNAPSHOT_EVERY:
                    take_snapshot(s)
        except Exception as exc:                                   # pragma: no cover
            ledger.ERRORS["count"] += 1
            ledger.ERRORS["last"] = f"snapshot: {exc}"
        finally:
            _state["running"] = False

    threading.Thread(target=job, daemon=True).start()


# ------------------------------------------------------------------ drift
def _explainers(db, since, until, months):
    """Register entries written in [since, until] that touch any of `months`."""
    q = db.query(models.LedgerEntry).filter(models.LedgerEntry.kind == "change",
                                            models.LedgerEntry.created_at >= since)
    if until is not None:
        q = q.filter(models.LedgerEntry.created_at <= until)
    out = {m: [] for m in months}
    for e in q.order_by(models.LedgerEntry.id):
        try:
            ms = json.loads(e.data or "{}").get("months", [])
        except Exception:
            ms = []
        for m in ms:
            if m in out:
                out[m].append({"id": e.id, "at": e.created_at.isoformat(), "actor": e.actor, "summary": e.summary})
    return out


def _bus_names(db):
    return {b.id: b.name for b in db.query(models.Bus).all()}


def drift_report(db, live=False) -> dict:
    snaps = last_snapshots(db, 2)
    rep = {"snapshots": [{"id": s.id, "at": s.created_at.isoformat()} for s in snaps],
           "between": None, "live": None, "unexplained": 0}
    names = _bus_names(db)

    def decorate(diffs, since, until):
        exp = _explainers(db, since, until, [d["month"] for d in diffs])
        for d in diffs:
            d["explained_by"] = exp.get(d["month"], [])
            d["explained"] = bool(d["explained_by"])
            for b in d["buses"]:
                b["name"] = names.get(b["id"], f"#{b['id']}")
        return diffs

    if len(snaps) == 2:
        new, old = snaps
        diffs = decorate(diff_measures(json.loads(old.data)["months"], json.loads(new.data)["months"]),
                         old.created_at, new.created_at)
        rep["between"] = {"from": old.created_at.isoformat(), "to": new.created_at.isoformat(), "months": diffs}
        rep["unexplained"] += sum(1 for d in diffs if not d["explained"])
    if live and snaps:
        latest = snaps[0]
        base = json.loads(latest.data)["months"]
        now_months = measure(sorted(base))
        diffs = decorate(diff_measures(base, now_months), latest.created_at, None)
        rep["live"] = {"since": latest.created_at.isoformat(), "months": diffs}
        rep["unexplained"] += sum(1 for d in diffs if not d["explained"])
    return rep
