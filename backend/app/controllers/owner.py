"""Owner console API: monitoring, the change register, its integrity, snapshots and drift.

Everything here is OWNER-ONLY and read-only except "take a snapshot now" (which only appends).
There is deliberately no endpoint that edits or deletes a register entry."""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .. import models
from ..core import ledger
from ..core.database import engine, get_db
from ..core.security import USERS, require_owner
from ..services import integrity

router = APIRouter(dependencies=[Depends(require_owner)])

STARTED_AT = time.time()
L = models.LedgerEntry
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _iso(dt) -> str | None:
    return dt.isoformat() + "Z" if dt else None          # stored in UTC


def _row(e: models.LedgerEntry) -> dict:
    try:
        data = json.loads(e.data) if e.data else {}
    except Exception:
        data = {}
    if e.kind == "snapshot":
        data = {"months": sorted((data.get("months") or {}).keys())}
    return {
        "id": e.id, "at": _iso(e.created_at), "kind": e.kind, "actor": e.actor, "role": e.role, "ip": e.ip,
        "action": e.action, "entity": e.entity, "entity_id": e.entity_id, "bus_id": e.bus_id,
        "bus_name": e.bus_name, "summary": e.summary, "retroactive": bool(e.retroactive),
        "sensitive": bool(e.sensitive), "batch": e.batch, "hash": (e.hash or "")[:12], "data": data,
    }


# ------------------------------------------------------------------ the register
@router.get("/api/owner/ledger")
def list_ledger(limit: int = 50, before_id: int | None = None, kind: str | None = None, entity: str | None = None,
                actor: str | None = None, bus_id: int | None = None, retro: bool = False, sensitive: bool = False,
                q: str | None = None, since: str | None = None, until: str | None = None,
                db: Session = Depends(get_db)):
    """The register, newest first. By default: changes and their measured impact (not snapshots)."""
    limit = max(1, min(limit, 200))
    query = db.query(L)
    query = query.filter(L.kind == kind) if kind else query.filter(L.kind.in_(("change", "impact")))
    if before_id:
        query = query.filter(L.id < before_id)
    if entity:
        query = query.filter(L.entity == entity)
    if actor:
        query = query.filter(L.actor == actor)
    if bus_id:
        query = query.filter(L.bus_id == bus_id)
    if retro:
        query = query.filter(L.retroactive.is_(True))
    if sensitive:
        query = query.filter(L.sensitive.is_(True))
    if q:
        query = query.filter(L.summary.ilike(f"%{q}%"))
    for val, op in ((since, "ge"), (until, "le")):
        if val:
            try:
                d = datetime.fromisoformat(val)
                query = query.filter(L.created_at >= d) if op == "ge" else query.filter(L.created_at <= d + timedelta(days=1))
            except ValueError:
                pass
    rows = query.order_by(L.id.desc()).limit(limit + 1).all()
    more = len(rows) > limit
    rows = rows[:limit]
    return {"rows": [_row(e) for e in rows], "next_before_id": rows[-1].id if more and rows else None}


@router.get("/api/owner/ledger/since")
def ledger_since(id: int = 0, db: Session = Depends(get_db)):
    """How many register entries are newer than `id` (drives the badge on the Console tab)."""
    base = db.query(func.count(L.id)).filter(L.id > id, L.kind == "change")
    head = db.query(func.max(L.id)).scalar() or 0
    return {"new": base.scalar() or 0, "sensitive": base.filter(L.sensitive.is_(True)).scalar() or 0, "head_id": head}


@router.get("/api/owner/ledger/verify")
def ledger_verify(db: Session = Depends(get_db)):
    """Recompute the whole hash chain and report the first entry that was altered, removed or inserted."""
    return ledger.verify_chain(db)


# ------------------------------------------------------------------ snapshots and drift
@router.get("/api/owner/drift")
def drift(live: bool = False, db: Session = Depends(get_db)):
    """Did the numbers shown for past months change between snapshots (and since the last one)?
    Every difference is attributed to the register entries that explain it; a difference that no entry
    explains is `explained: false` — what a change made outside the app looks like."""
    return integrity.drift_report(db, live=live)


@router.post("/api/owner/snapshot")
def snapshot_now(db: Session = Depends(get_db)):
    e = integrity.take_snapshot(db, actor="propriétaire (instantané manuel)")
    return {"ok": True, "id": e.id, "at": _iso(e.created_at)}


# ------------------------------------------------------------------ overview
@router.get("/api/owner/overview")
def overview(db: Session = Depends(get_db)):
    integrity.maybe_snapshot_async(force_check=True)           # make sure a daily snapshot exists
    now = datetime.utcnow()
    d1, d7, d30 = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)
    changes = L.kind == "change"

    def cnt(*f):
        return db.query(func.count(L.id)).filter(*f).scalar() or 0

    head = db.query(L).order_by(L.id.desc()).first()
    total = cnt()
    by_actor = (db.query(L.actor, func.count(L.id)).filter(changes, L.created_at >= d7)
                .group_by(L.actor).order_by(func.count(L.id).desc()).all())
    by_entity = (db.query(L.entity, func.count(L.id)).filter(changes, L.created_at >= d30)
                 .group_by(L.entity).order_by(func.count(L.id).desc()).all())
    recent = (db.query(L).filter(changes, L.sensitive.is_(True)).order_by(L.id.desc()).limit(6).all())
    verify = ledger.verify_chain(db) if total <= 100_000 else {"ok": None, "checked": 0, "head": None, "first_break": None}
    snaps = integrity.last_snapshots(db, 1)
    drift_rep = integrity.drift_report(db, live=False)

    A = models.AuditLog
    login_methods = ("Connexion", "Connexion échouée", "Déconnexion")
    sec_rows = db.query(A).filter(A.method.in_(login_methods)).order_by(A.id.desc()).limit(25).all()
    ips = set()
    for r in db.query(A.detail).filter(A.method.in_(login_methods), A.created_at >= d7).limit(2000):
        m = re.search(r"IP\s+([0-9a-fA-F:.]+)", r[0] or "")
        if m:
            ips.add(m.group(1))

    t0 = time.time()
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        db_ok = True
    except Exception:
        db_ok = False
    db_ms = round((time.time() - t0) * 1000)

    counts = {}
    for label, model in (("Véhicules", models.Bus), ("Contrats", models.Contract), ("Sorties", models.Booking),
                         ("Carburant", models.FuelMonth), ("Destinations", models.Destination),
                         ("Périodes de région", models.BusRegionPeriod), ("Locations", models.RentedVehicle),
                         ("Journal", models.AuditLog), ("Registre", models.LedgerEntry)):
        counts[label] = db.query(func.count(model.id)).scalar() or 0
    subs = dict(db.query(models.PushSubscription.username, func.count(models.PushSubscription.id))
                .group_by(models.PushSubscription.username).all())

    return {
        "now": _iso(now),
        "ledger": {
            "total": total, "last_24h": cnt(changes, L.created_at >= d1), "last_7d": cnt(changes, L.created_at >= d7),
            "retroactive_30d": cnt(changes, L.retroactive.is_(True), L.created_at >= d30),
            "sensitive_7d": cnt(changes, L.sensitive.is_(True), L.created_at >= d7),
            "head": {"id": head.id, "hash": head.hash, "at": _iso(head.created_at)} if head else None,
            "by_actor_7d": [{"actor": a, "count": n} for a, n in by_actor],
            "by_entity_30d": [{"entity": e, "count": n} for e, n in by_entity],
            "recent_sensitive": [_row(e) for e in recent],
        },
        "integrity": {"ok": verify["ok"], "checked": verify["checked"], "first_break": verify["first_break"],
                      "unexplained_drift": drift_rep["unexplained"],
                      "last_snapshot": _iso(snaps[0].created_at) if snaps else None,
                      "snapshots": cnt(L.kind == "snapshot")},
        "security": {
            "logins_7d": db.query(func.count(A.id)).filter(A.method == "Connexion", A.created_at >= d7).scalar() or 0,
            "failed_7d": db.query(func.count(A.id)).filter(A.method == "Connexion échouée", A.created_at >= d7).scalar() or 0,
            "distinct_ips_7d": len(ips),
            "recent": [{"at": _iso(r.created_at), "user": r.username, "event": r.method, "detail": r.detail}
                       for r in sec_rows],
        },
        "users": [{"username": u, "role": i.get("role", ""), "push_devices": subs.get(u, 0)} for u, i in USERS.items()],
        "tables": counts,
        "server": {
            "db": engine.dialect.name, "db_ok": db_ok, "db_ms": db_ms, "uptime_s": round(time.time() - STARTED_AT),
            "commit": (os.environ.get("RENDER_GIT_COMMIT") or "")[:8], "service": os.environ.get("RENDER_SERVICE_NAME", ""),
            "python": sys.version.split()[0], "register_errors": ledger.ERRORS["count"],
            "register_last_error": ledger.ERRORS["last"],
        },
    }


# ------------------------------------------------------------------ export (the owner's off-site copy)
@router.get("/api/owner/export/ledger")
def export_ledger(db: Session = Depends(get_db)):
    """The whole register as Excel, with its integrity verdict: keep a copy somewhere the app cannot touch."""
    verify = ledger.verify_chain(db)
    wb = Workbook()
    ws = wb.active
    ws.title = "Registre"
    head = ["N°", "Date (UTC)", "Type", "Acteur", "Rôle", "IP", "Action", "Élément", "Véhicule", "Résumé",
            "Avant", "Après", "Mois touchés", "Rétroactif", "Sensible", "Empreinte"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1A3A5C")
        c.alignment = Alignment(vertical="center")
    for e in db.query(L).filter(L.kind.in_(("change", "impact"))).order_by(L.id).yield_per(500):
        try:
            d = json.loads(e.data) if e.data else {}
        except Exception:
            d = {}
        ws.append([e.id, e.created_at.strftime("%Y-%m-%d %H:%M:%S"), e.kind, e.actor, e.role, e.ip, e.action, e.entity,
                   e.bus_name, e.summary, json.dumps(d.get("before"), ensure_ascii=False) if d.get("before") else "",
                   json.dumps(d.get("after"), ensure_ascii=False) if d.get("after") else "",
                   ", ".join(d.get("months", [])) if isinstance(d.get("months"), list) and d.get("months")
                   and isinstance(d["months"][0], str) else "",
                   "oui" if e.retroactive else "", "oui" if e.sensitive else "", e.hash])
    for col, w in zip("ABCDEFGHIJKLMNOP", (7, 19, 8, 18, 9, 15, 9, 12, 28, 70, 38, 38, 22, 10, 9, 20)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    wi = wb.create_sheet("Intégrité")
    wi.append(["Exporté le (UTC)", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")])
    wi.append(["Chaîne vérifiée", "OUI — aucune entrée modifiée ni supprimée" if verify["ok"] else "NON — " + (verify["first_break"] or {}).get("reason", "")])
    wi.append(["Entrées contrôlées", verify["checked"]])
    wi.append(["Dernière entrée n°", (verify["head"] or {}).get("id")])
    wi.append(["Empreinte de la dernière entrée", (verify["head"] or {}).get("hash")])
    wi.append([])
    wi.append(["Conservez ce fichier hors de l'application : l'empreinte ci-dessus prouve l'état du registre à cette date."])
    wi.column_dimensions["A"].width = 34
    wi.column_dimensions["B"].width = 70
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type=XLSX,
                             headers={"Content-Disposition": 'attachment; filename="Registre_des_modifications.xlsx"'})
