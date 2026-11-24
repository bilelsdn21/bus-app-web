"""The change register ("ledger"): a permanent, tamper-evident record of everything that can move
the numbers.

How it works
  • Every write through the app's database sessions is captured AUTOMATICALLY (SQLAlchemy
    flush events), inside the same transaction as the change itself: a tracked table cannot be
    modified without a register entry being committed with it.
  • Each entry stores who (user, role, IP), what, the values before and after, which months it
    touches, and whether it is retroactive (touches a month already past) or sensitive.
  • Entries are hash-chained (each one contains the hash of the previous one): altering,
    removing or inserting any entry breaks the chain, and verify_chain() says exactly where.
  • Database triggers refuse UPDATE / DELETE / TRUNCATE on the table (install_guards).
  • Sensitive changes made by anyone other than the owner alert the owner by push notification,
    and (for contracts, regions and past months) the effect on the displayed numbers is measured
    before/after and recorded as an "impact" entry.

Honest limit: this is tamper-EVIDENT. Someone with full administrator access to the database could
still disable the triggers; the chain, the daily snapshots of the numbers and the owner alerts are
what would reveal it.
"""
import contextlib
import hashlib
import json
import logging
import os
import threading
import uuid
from contextvars import ContextVar
from datetime import date, datetime

from sqlalchemy import Float, event, inspect, select, text
from sqlalchemy.orm import Session

from .. import models

log = logging.getLogger("uvicorn.error")

ENABLED = True        # tests of unrelated features switch the register off
SYNC_JOBS = False     # tests run the post-commit job (impact, owner alert) inline instead of in a thread

# ------------------------------------------------------------------ who is acting
_actor: ContextVar = ContextVar("ledger_actor", default=("(hors application)", "", ""))
ERRORS = {"count": 0, "last": ""}      # capture failures never block a save; they are surfaced here


def set_actor(user, role="", ip=""):
    return _actor.set((user or "(anonyme)", role or "", ip or ""))


def reset_actor(token):
    _actor.reset(token)


@contextlib.contextmanager
def as_actor(user, role="", ip=""):
    """For scripts and maintenance: everything written inside is attributed to `user`."""
    tok = set_actor(user, role, ip)
    try:
        yield
    finally:
        reset_actor(tok)


# ------------------------------------------------------------------ hashing
def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _fields(e) -> dict:
    """The part of an entry that is protected by the hash."""
    return {
        "created_at": e.created_at.replace(microsecond=0).isoformat(), "batch": e.batch or "", "kind": e.kind,
        "actor": e.actor or "", "role": e.role or "", "ip": e.ip or "", "action": e.action or "",
        "entity": e.entity or "", "entity_id": e.entity_id, "bus_id": e.bus_id, "bus_name": e.bus_name or "",
        "summary": e.summary or "", "data": e.data or "", "retroactive": bool(e.retroactive),
        "sensitive": bool(e.sensitive),
    }


def compute_hash(prev_hash: str, fields: dict) -> str:
    return hashlib.sha256(((prev_hash or "") + "|" + canonical(fields)).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ what is tracked
TRACKED = {
    models.Contract: "contract", models.Booking: "booking", models.FuelMonth: "fuel",
    models.Destination: "destination", models.PricePeriod: "price", models.BusRegionPeriod: "region",
    models.Bus: "bus", models.Config: "config", models.RentedVehicle: "rented",
}
ENT_FR = {"contract": "Contrat", "booking": "Sortie", "fuel": "Carburant", "destination": "Destination",
          "price": "Prix historique", "region": "Région", "bus": "Véhicule", "config": "Paramètres",
          "rented": "Location"}
LABELS = {
    "loyer": "loyer", "start_date": "début", "end_date": "fin", "label": "libellé", "total": "total",
    "unit_price": "prix unitaire", "destination": "destination", "date": "date", "client": "client",
    "pax": "passagers", "type": "type", "heure_debut": "heure début", "heure_fin": "heure fin",
    "estimated": "estimé", "actual": "réel", "region": "région", "effective_from": "du", "effective_to": "au",
    "price_micro": "prix micro", "price_otokar": "prix otokar", "price_bus": "prix bus", "name": "nom",
    "plate": "plaque", "distance": "distance", "cost": "coût", "notes": "notes", "cut_morn": "seuil matin",
    "cut_night": "seuil nuit", "current_prices_since": "prix actuels depuis", "bus_id": "véhicule",
    "sort_order": "ordre", "year": "année", "month": "mois", "category": "catégorie", "dest_name": "destination",
}
MONEY_FIELDS = {"loyer", "total", "unit_price", "estimated", "actual", "cost", "price_micro", "price_otokar", "price_bus"}
ALWAYS_SENSITIVE = {"contract", "region", "destination", "price", "bus", "config"}


def _json(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def _cv(col, v):
    """JSON-safe value; money columns are always floats (the app may hold 100, the database returns 100.0)."""
    v = _json(v)
    if v is not None and isinstance(col.columns[0].type, Float):
        try:
            return float(v)
        except (TypeError, ValueError):
            return v
    return v


def _values(obj) -> dict:
    out = {}
    for col in inspect(obj).mapper.column_attrs:
        out[col.key] = _cv(col, getattr(obj, col.key, None))
    return out


def _diff(obj, known_old=None):
    """{column: old}, {column: new} for the columns whose value really changed.
    `known_old` holds the previous values read from the database (the ORM forgets them after a commit)."""
    before, after = {}, {}
    st = inspect(obj)
    for col in st.mapper.column_attrs:
        h = st.attrs[col.key].history
        if h.has_changes():
            old = _cv(col, h.deleted[0]) if h.deleted else (known_old or {}).get(col.key)
            new = _cv(col, h.added[0]) if h.added else _cv(col, getattr(obj, col.key, None))
            if old != new:
                before[col.key], after[col.key] = old, new
    return before, after


def _month_of(v):
    try:
        d = date.fromisoformat(v) if isinstance(v, str) else v
        return d.year, d.month
    except Exception:
        return None


def _span(a, b, cap=36):
    """(year, month) from a to b inclusive (dates as iso strings), capped."""
    ma, mb = _month_of(a), _month_of(b or a)
    if not ma or not mb:
        return []
    out, (y, m) = [], ma
    while (y, m) <= mb and len(out) < cap:
        out.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _months(entity, *states) -> list:
    """The months ('YYYY-MM') a change can move the numbers of."""
    ms = set()
    today = date.today().isoformat()
    for v in states:
        if not v:
            continue
        if entity == "contract":
            ms.update(_span(v.get("start_date"), v.get("end_date")))
        elif entity == "booking":
            ms.update(_span(v.get("date"), v.get("end_date") or v.get("date")))
        elif entity == "rented":
            ms.update(_span(v.get("start_date"), v.get("end_date")))
        elif entity == "region":
            ms.update(_span(v.get("effective_from"), v.get("effective_to") or today))
        elif entity == "fuel" and v.get("year") and v.get("month"):
            ms.add((int(v["year"]), int(v["month"])))
    return [f"{y:04d}-{m:02d}" for y, m in sorted(ms)]


def _is_retro(months) -> bool:
    cur = date.today().strftime("%Y-%m")
    return any(m < cur for m in months)


def _fmt(v):
    if v is None or v == "":
        return "—"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, str) and len(v) == 10 and v[4] == "-" and v[7] == "-":
        return f"{v[8:10]}/{v[5:7]}/{v[0:4]}"
    return str(v)


def _describe(entity, action, before, after, bus_name, context=None) -> str:
    vals = after if action != "delete" else before
    # `context` = the whole row (an update only carries the changed columns)
    full = {**(context or {}), **(before or {}), **(after or {})} if action == "update" else (vals or {})
    ent = ENT_FR.get(entity, entity)
    subject = ""
    if entity == "contract":
        subject = f" {bus_name} {_fmt(full.get('start_date'))}→{_fmt(full.get('end_date'))}"
    elif entity == "booking":
        subject = f" {bus_name} {_fmt(full.get('date'))} {full.get('destination') or ''}".rstrip()
    elif entity == "fuel":
        subject = f" {bus_name} {int(full.get('month') or 0):02d}/{full.get('year')}"
    elif entity in ("destination", "rented", "bus"):
        subject = f" {full.get('name') or ''}".rstrip()
    elif entity == "price":
        subject = f" {full.get('dest_name') or ''}".rstrip()
    elif entity == "region":
        subject = f" {bus_name}"
    if action == "update":
        diffs = "; ".join(f"{LABELS.get(k, k)} : {_fmt(before.get(k))} → {_fmt(after.get(k))}" for k in after)
        return f"{ent}{subject} — {diffs}"
    facts = []
    for k in ("loyer", "total", "estimated", "actual", "cost", "region", "price_micro", "price_otokar", "price_bus"):
        if full.get(k) not in (None, "", 0, 0.0):
            facts.append(f"{LABELS.get(k, k)} {_fmt(full[k])}")
    if entity == "region":
        facts.append(f"du {_fmt(full.get('effective_from'))} au {_fmt(full.get('effective_to')) if full.get('effective_to') else '…'}")
    verb = "créé" if action == "create" else "supprimé"
    return f"{ent}{subject} {verb}" + (f" ({', '.join(facts)})" if facts else "")


def _classify(entity, action, before, after, months):
    retro = _is_retro(months)
    sensitive = retro or action == "delete" or entity in ALWAYS_SENSITIVE
    if entity == "booking" and action == "update" and ({"total", "unit_price", "bus_id", "date", "end_date"} & set(after)):
        sensitive = True
    if entity == "rented" and "cost" in after:
        sensitive = True
    return retro, sensitive


def _collect(session, with_ids=True):
    """The tracked creates / updates / deletes of the current flush, as plain records."""
    recs, created_sig, deleted = [], {}, []
    for obj in list(session.new):
        ent = TRACKED.get(type(obj))
        if ent:
            vals = _values(obj)
            recs.append({"entity": ent, "action": "create", "obj": obj, "before": None, "after": vals})
            created_sig[(ent, canonical({k: v for k, v in vals.items() if k != "id"}))] = recs[-1]
    for obj in list(session.deleted):
        ent = TRACKED.get(type(obj))
        if ent:
            vals = _values(obj)
            deleted.append({"entity": ent, "action": "delete", "obj": obj, "before": vals, "after": None})
    for obj in list(session.dirty):
        ent = TRACKED.get(type(obj))
        if ent and session.is_modified(obj, include_collections=False):
            b, a = _diff(obj, session.info.get("ledger_old", {}).get(id(obj)))
            if a:
                recs.append({"entity": ent, "action": "update", "obj": obj, "before": b, "after": a,
                             "full_before": {**_values(obj), **b}})
    # a row deleted and re-created identically in one save (e.g. "replace the day") is not a change
    for d in deleted:
        sig = (d["entity"], canonical({k: v for k, v in d["before"].items() if k != "id"}))
        twin = created_sig.pop(sig, None)
        if twin is not None:
            recs.remove(twin)
        else:
            recs.append(d)
    return recs


def _bus_of(session, rec):
    obj = rec["obj"]
    bus_id = getattr(obj, "id", None) if rec["entity"] == "bus" else getattr(obj, "bus_id", None)
    name = ""
    if rec["entity"] == "bus":
        name = getattr(obj, "name", "") or ""
    elif bus_id:
        try:
            b = session.get(models.Bus, bus_id)
            name = b.name if b else ""
        except Exception:
            name = ""
    return bus_id, name


# ------------------------------------------------------------------ appending entries
def _lock(session):
    """One ledger writer at a time (so the chain cannot fork)."""
    try:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(727001)"))
    except Exception:
        pass


def _prev_hash(session) -> str:
    last = session.info.get("ledger_last_hash")
    if last is not None:
        return last
    _lock(session)
    row = session.execute(select(models.LedgerEntry.hash).order_by(models.LedgerEntry.id.desc()).limit(1)).first()
    return row[0] if row else ""


def append_entry(session, *, kind="change", actor=None, role=None, ip=None, action="", entity="", entity_id=None,
                 bus_id=None, bus_name="", summary="", data=None, retroactive=False, sensitive=False,
                 batch=None, created_at=None):
    """Add one chained entry to `session` (the caller commits)."""
    a, r, i = _actor.get()
    e = models.LedgerEntry(
        created_at=(created_at or datetime.utcnow()).replace(microsecond=0),
        batch=batch or session.info.setdefault("ledger_batch", uuid.uuid4().hex),
        kind=kind, actor=actor if actor is not None else a, role=role if role is not None else r,
        ip=ip if ip is not None else i, action=action, entity=entity, entity_id=entity_id, bus_id=bus_id,
        bus_name=bus_name or "", summary=summary or "",
        data=data if isinstance(data, str) else (canonical(data) if data is not None else ""),
        retroactive=bool(retroactive), sensitive=bool(sensitive),
    )
    e.prev_hash = _prev_hash(session)
    e.hash = compute_hash(e.prev_hash, _fields(e))
    session.add(e)
    session.info["ledger_last_hash"] = e.hash
    return e


# ------------------------------------------------------------------ the flush listeners
def _wants_impact(rec, months) -> bool:
    return bool(months) and (rec["entity"] in ("contract", "region") or _is_retro(months))


def _capture_old(session):
    """For every modified tracked row whose previous value the ORM no longer knows, read it from the
    database now (the UPDATE has not been sent yet)."""
    cache = session.info.setdefault("ledger_old", {})
    for obj in list(session.dirty):
        if not TRACKED.get(type(obj)) or id(obj) in cache:
            continue
        st = inspect(obj)
        need = [c.key for c in st.mapper.column_attrs
                if st.attrs[c.key].history.has_changes() and not st.attrs[c.key].history.deleted]
        cache[id(obj)] = {}
        if need and st.identity:
            row = session.execute(select(*[getattr(type(obj), k) for k in need])
                                  .where(type(obj).id == st.identity[0])).first()
            if row:
                cols = {c.key: c for c in st.mapper.column_attrs}
                cache[id(obj)] = {k: _cv(cols[k], v) for k, v in zip(need, row)}


@event.listens_for(Session, "before_flush")
def _before_flush(session, ctx, instances):
    """Read previous values; measure the displayed numbers of the affected months BEFORE a sensitive change."""
    if not ENABLED or session.info.get("ledger_off"):
        return
    try:
        _capture_old(session)
    except Exception as exc:
        ERRORS["count"] += 1
        ERRORS["last"] = f"capture_old: {exc}"
        log.error("ledger capture_old failed: %s", exc)
    if session.info.get("ledger_impact") is not None:
        return
    try:
        months = set()
        for rec in _collect(session):
            m = _months(rec["entity"], rec.get("full_before") or rec["before"], rec["after"] if rec["action"] != "update"
                        else {**(rec.get("full_before") or {}), **rec["after"]})
            if _wants_impact(rec, m):
                months.update(m)
        cur = date.today().strftime("%Y-%m")
        months = sorted(m for m in months if m <= cur)[-4:]
        if months:
            from ..services import integrity
            session.info["ledger_impact"] = {"months": months, "before": integrity.measure(months)}
    except Exception as exc:                               # never block a save
        ERRORS["count"] += 1
        ERRORS["last"] = f"before_flush: {exc}"
        log.error("ledger before_flush failed: %s", exc)


@event.listens_for(Session, "after_flush")
def _after_flush(session, ctx):
    if not ENABLED or session.info.get("ledger_off"):
        return
    try:
        recs = _collect(session)
        out = []
        for rec in recs:
            obj = rec["obj"]
            bus_id, bus_name = _bus_of(session, rec)
            if rec["action"] == "update":
                full_after = {**(rec.get("full_before") or {}), **rec["after"]}
                months = _months(rec["entity"], rec.get("full_before"), full_after)
            else:
                months = _months(rec["entity"], rec["before"], rec["after"])
            retro, sens = _classify(rec["entity"], rec["action"], rec["before"], rec["after"], months)
            out.append({
                "entity": rec["entity"], "action": rec["action"], "entity_id": getattr(obj, "id", None),
                "bus_id": bus_id, "bus_name": bus_name, "before": rec["before"], "after": rec["after"],
                "months": months, "retro": retro, "sensitive": sens,
                "summary": _describe(rec["entity"], rec["action"], rec["before"] or {}, rec["after"] or {}, bus_name,
                                     {**(rec.get("full_before") or {}), **(rec["after"] or {})}),
            })
        if out:
            session.info.setdefault("ledger_pending", []).extend(out)
    except Exception as exc:
        ERRORS["count"] += 1
        ERRORS["last"] = f"after_flush: {exc}"
        log.error("ledger after_flush failed: %s", exc)


def _dedupe(pending):
    """A row deleted and then re-created identically inside one transaction (e.g. "save the day" with
    nothing changed) is not a change: drop both halves."""
    creates = {}
    for p in pending:
        if p["action"] == "create":
            creates.setdefault((p["entity"], canonical({k: v for k, v in p["after"].items() if k != "id"})), []).append(p)
    dropped = set()
    for p in pending:
        if p["action"] == "delete":
            twins = creates.get((p["entity"], canonical({k: v for k, v in p["before"].items() if k != "id"})))
            if twins:
                dropped.add(id(twins.pop(0)))
                dropped.add(id(p))
    return [p for p in pending if id(p) not in dropped]


@event.listens_for(Session, "before_commit")
def _before_commit(session):
    """Write the register entries of the whole transaction, in the same transaction as the changes."""
    if not ENABLED or session.info.get("ledger_off"):
        return
    if session.new or session.dirty or session.deleted:
        session.flush()                                   # record everything still pending
    pending = session.info.pop("ledger_pending", None)
    if not pending:
        return
    try:
        posted = session.info.setdefault("ledger_posted", [])
        for p in _dedupe(pending):
            append_entry(session, action=p["action"], entity=p["entity"], entity_id=p["entity_id"],
                         bus_id=p["bus_id"], bus_name=p["bus_name"], summary=p["summary"],
                         data={"before": p["before"], "after": p["after"], "months": p["months"]},
                         retroactive=p["retro"], sensitive=p["sensitive"])
            posted.append(p)
    except Exception as exc:
        ERRORS["count"] += 1
        ERRORS["last"] = f"before_commit: {exc}"
        log.error("ledger append failed: %s", exc)


def _clear(session):
    for k in ("ledger_last_hash", "ledger_batch", "ledger_pending", "ledger_posted", "ledger_impact", "ledger_old"):
        session.info.pop(k, None)


@event.listens_for(Session, "after_commit")
def _after_commit(session):
    posted = session.info.get("ledger_posted")
    impact = session.info.get("ledger_impact")
    actor = _actor.get()
    batch = session.info.get("ledger_batch")
    _clear(session)
    if posted:
        if SYNC_JOBS:
            _post_commit_job(posted, impact, actor, batch)
        else:
            threading.Thread(target=_post_commit_job, args=(posted, impact, actor, batch), daemon=True).start()


@event.listens_for(Session, "after_rollback")
def _after_rollback(session):
    _clear(session)


# ------------------------------------------------------------------ after the commit (background)
def _owners() -> list:
    from .security import USERS
    return [u for u, i in USERS.items() if i.get("role") == "owner"]


def _post_commit_job(posted, impact, actor, batch):
    """Impact measurement + owner alert. Runs in a thread, after the change is safely committed."""
    from .database import SessionLocal
    user, role, ip = actor
    try:
        if impact and impact.get("months"):
            from ..services import integrity
            with SessionLocal() as s:
                s.info["ledger_off"] = True
                after = integrity.measure(impact["months"])
                diffs = integrity.diff_measures(impact["before"], after)
                if diffs:
                    s.info.pop("ledger_off", None)
                    total = sum(d["delta"] for d in diffs)
                    append_entry(s, kind="impact", actor=user, role=role, ip=ip, action="impact", entity="numbers",
                                 summary="Effet sur les chiffres affichés : " + "; ".join(
                                     f"{d['month']} net {d['delta']:+,.0f} TND".replace(",", " ") for d in diffs),
                                 data={"months": diffs, "total_delta": round(total, 2)}, batch=batch,
                                 retroactive=any(d["month"] < date.today().strftime("%Y-%m") for d in diffs),
                                 sensitive=True)
                    s.commit()
    except Exception as exc:
        ERRORS["count"] += 1
        ERRORS["last"] = f"impact: {exc}"
        log.error("ledger impact failed: %s", exc)
    try:
        sens = [p for p in posted if p["sensitive"]]
        if sens and role != "owner":
            owners = _owners()
            if owners:
                from ..services import push
                with SessionLocal() as s:
                    s.info["ledger_off"] = True
                    head = sens[0]["summary"]
                    more = f" (+{len(sens) - 1} autre{'s' if len(sens) > 2 else ''})" if len(sens) > 1 else ""
                    push.send_to_users(s, owners, "⚠️ Modification sensible",
                                       f"{user} : {head[:110]}{more}", url="/?tab=console")
    except Exception as exc:
        ERRORS["count"] += 1
        ERRORS["last"] = f"notify: {exc}"
        log.error("ledger notify failed: %s", exc)


# ------------------------------------------------------------------ integrity
def verify_chain(session) -> dict:
    """Recompute the whole chain. Reports the first entry that was altered, removed or inserted."""
    prev, n, head, broken = "", 0, None, None
    for e in session.query(models.LedgerEntry).order_by(models.LedgerEntry.id).yield_per(500):
        n += 1
        if (e.prev_hash or "") != prev:
            broken = {"id": e.id, "reason": "Chaîne rompue : une entrée a été supprimée ou insérée avant celle-ci."}
            break
        if compute_hash(e.prev_hash, _fields(e)) != e.hash:
            broken = {"id": e.id, "reason": "Contenu modifié : l'entrée ne correspond plus à son empreinte."}
            break
        prev = e.hash
        head = {"id": e.id, "hash": e.hash, "created_at": e.created_at.isoformat()}
    return {"ok": broken is None, "checked": n, "head": head, "first_break": broken}


def install_guards(engine):
    """Make the table append-only at the database level (UPDATE / DELETE / TRUNCATE refused)."""
    try:
        with engine.begin() as c:
            if engine.dialect.name == "postgresql":
                c.execute(text("CREATE OR REPLACE FUNCTION ledger_append_only() RETURNS trigger AS $$ "
                               "BEGIN RAISE EXCEPTION 'ledger is append-only'; END; $$ LANGUAGE plpgsql"))
                c.execute(text("DROP TRIGGER IF EXISTS ledger_no_change ON ledger"))
                c.execute(text("CREATE TRIGGER ledger_no_change BEFORE UPDATE OR DELETE ON ledger "
                               "FOR EACH ROW EXECUTE FUNCTION ledger_append_only()"))
                c.execute(text("DROP TRIGGER IF EXISTS ledger_no_truncate ON ledger"))
                c.execute(text("CREATE TRIGGER ledger_no_truncate BEFORE TRUNCATE ON ledger "
                               "FOR EACH STATEMENT EXECUTE FUNCTION ledger_append_only()"))
            elif engine.dialect.name == "sqlite":
                for ev in ("UPDATE", "DELETE"):
                    c.execute(text(f"CREATE TRIGGER IF NOT EXISTS ledger_no_{ev.lower()} BEFORE {ev} ON ledger "
                                   "BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END"))
        return True
    except Exception as exc:
        log.error("ledger guards not installed: %s", exc)
        return False
