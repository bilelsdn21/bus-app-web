"""
FastAPI backend for the bus management web app.
Run:  uvicorn app.main:app --reload --port 8000
"""
import os
import hashlib
from datetime import date, timedelta
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Base, engine, get_db, SessionLocal
from . import models, schemas, calc

# Credential + role store. Each entry: "user:password:role" (role = admin | viewer).
# REAL accounts live ONLY in the BUS_USERS env var on the server — never in this code.
# The default below is a throwaway used only for local development.
#   BUS_USERS="aymen:pass1:admin,bilel:pass2:admin,sami:pass3:admin,equipe:pass4:viewer"
def _load_users():
    raw = os.environ.get("BUS_USERS", "dev:dev:admin")
    users = {}
    for entry in raw.split(","):
        parts = entry.split(":")
        if len(parts) >= 2:
            u = parts[0].strip()
            p = parts[1]
            role = parts[2].strip().lower() if len(parts) >= 3 and parts[2].strip() else "admin"
            users[u] = {"password": p, "role": role}
    return users

USERS = _load_users()

def _token(username: str) -> str:
    secret = os.environ.get("BUS_SECRET", "bus-local-secret")
    return hashlib.sha256(f"{username}:{secret}".encode()).hexdigest()

# token -> role, and token -> username, for verifying + auditing requests
TOKENS = {_token(u): info["role"] for u, info in USERS.items()}
TOKEN_USER = {_token(u): u for u in USERS}

def _bearer(authorization: str | None) -> str:
    return authorization[7:] if authorization and authorization.lower().startswith("bearer ") else ""

def _role_of(authorization: str | None) -> str | None:
    return TOKENS.get(_bearer(authorization))

def require_admin(authorization: str = Header(None)):
    """Allow only admin tokens through. Used on every write endpoint."""
    role = _role_of(authorization)
    if role is None:
        raise HTTPException(401, "Non authentifié — reconnectez-vous.")
    if role != "admin":
        raise HTTPException(403, "Action réservée aux administrateurs (compte en lecture seule).")
    return role

Base.metadata.create_all(engine)

app = FastAPI(title="Bus Manager API")

# Allowed origins: local dev by default; in production set
#   CORS_ORIGINS="https://your-app.vercel.app"  (comma-separated for several)
# Trailing slashes are stripped, and any *.vercel.app URL is allowed via regex
# (covers production + Vercel preview deployments) so CORS "just works".
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
_origins = [o.strip().rstrip("/") for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """Record every successful write (POST/PUT/DELETE) with the acting username."""
    response = await call_next(request)
    try:
        path = request.url.path
        if (request.method in ("POST", "PUT", "DELETE")
                and path.startswith("/api") and path != "/api/login"
                and 200 <= response.status_code < 300):
            user = TOKEN_USER.get(_bearer(request.headers.get("authorization", "")))
            if user:
                db = SessionLocal()
                try:
                    db.add(models.AuditLog(username=user, method=request.method,
                                           path=path, status=response.status_code))
                    db.commit()
                finally:
                    db.close()
    except Exception:
        pass  # never let logging break a request
    return response


def get_config(db: Session) -> models.Config:
    cfg = db.query(models.Config).first()
    if not cfg:
        cfg = models.Config(cut_morn=13, cut_night=22)
        db.add(cfg); db.commit(); db.refresh(cfg)
    return cfg


def price_for(db: Session, destination: str, bus_type: str) -> float:
    d = db.query(models.Destination).filter(models.Destination.name == destination).first()
    if not d:
        return 0.0
    return {"MICRO": d.price_micro, "OTOKAR": d.price_otokar, "BUS": d.price_bus}.get(
        (bus_type or "").upper(), 0.0)


@app.get("/api/health")
def health():
    return {"ok": True}


class LoginBody(BaseModel):
    username: str
    password: str

@app.post("/api/login")
def login(body: LoginBody):
    info = USERS.get(body.username)
    if not info or info["password"] != body.password:
        raise HTTPException(401, "Identifiants incorrects.")
    return {"ok": True, "username": body.username, "role": info["role"], "token": _token(body.username)}


@app.get("/api/audit")
def audit(limit: int = 300, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """The activity log — who did what, when. Admin only."""
    rows = (db.query(models.AuditLog)
            .order_by(models.AuditLog.created_at.desc()).limit(min(limit, 1000)).all())
    return [{"time": (r.created_at.isoformat() if r.created_at else None),
             "user": r.username, "method": r.method, "path": r.path, "status": r.status}
            for r in rows]


# ---------- contract result helper ----------
def compute_contract_result(db: Session, contract: models.Contract) -> dict:
    """Load bookings + fuel for the contract window and compute the precise result."""
    books = (db.query(models.Booking)
             .filter(models.Booking.bus_id == contract.bus_id,
                     models.Booking.date >= contract.start_date,
                     models.Booking.date <= contract.end_date).all())
    bdicts = [{"bus_id": b.bus_id, "date": b.date, "type": b.type, "total": b.total} for b in books]

    fuels = (db.query(models.FuelMonth)
             .filter(models.FuelMonth.bus_id == contract.bus_id).all())
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
    return res


# ---------- reference data ----------
@app.get("/api/buses", response_model=list[schemas.BusOut])
def list_buses(db: Session = Depends(get_db)):
    return db.query(models.Bus).order_by(models.Bus.sort_order).all()


@app.post("/api/buses", response_model=schemas.BusOut)
def create_bus(body: schemas.BusCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    if db.query(models.Bus).filter(models.Bus.name == body.name).first():
        raise HTTPException(409, "Un véhicule avec ce nom existe déjà.")
    bus = models.Bus(**body.model_dump())
    db.add(bus); db.commit(); db.refresh(bus)
    return bus


@app.put("/api/buses/{bus_id}", response_model=schemas.BusOut)
def update_bus(bus_id: int, body: schemas.BusCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    bus = db.get(models.Bus, bus_id)
    if not bus:
        raise HTTPException(404, "Véhicule introuvable.")
    for k, v in body.model_dump().items():
        setattr(bus, k, v)
    db.commit(); db.refresh(bus)
    return bus


@app.delete("/api/buses/{bus_id}", status_code=204)
def delete_bus(bus_id: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    bus = db.get(models.Bus, bus_id)
    if not bus:
        return
    if db.query(models.Booking).filter(models.Booking.bus_id == bus_id).count():
        raise HTTPException(409, "Ce véhicule a des activités enregistrées — suppression bloquée.")
    db.delete(bus); db.commit()


@app.get("/api/destinations", response_model=list[schemas.DestinationOut])
def list_destinations(db: Session = Depends(get_db)):
    return db.query(models.Destination).order_by(models.Destination.category, models.Destination.name).all()


@app.post("/api/destinations", response_model=schemas.DestinationOut)
def create_destination(body: schemas.DestinationCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    d = models.Destination(**body.model_dump())
    db.add(d); db.commit(); db.refresh(d)
    return d


@app.put("/api/destinations/{did}", response_model=schemas.DestinationOut)
def update_destination(did: int, body: schemas.DestinationCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    d = db.get(models.Destination, did)
    if not d:
        raise HTTPException(404, "Destination introuvable.")
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    db.commit(); db.refresh(d)
    return d


@app.delete("/api/destinations/{did}", status_code=204)
def delete_destination(did: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    d = db.get(models.Destination, did)
    if d:
        db.delete(d); db.commit()


@app.get("/api/config", response_model=schemas.ConfigOut)
def read_config(db: Session = Depends(get_db)):
    return get_config(db)


@app.put("/api/config", response_model=schemas.ConfigOut)
def update_config(body: schemas.ConfigUpdate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    cfg = get_config(db)
    cfg.cut_morn, cfg.cut_night = body.cut_morn, body.cut_night
    db.commit(); db.refresh(cfg)
    return cfg


# ---------- contracts ----------
@app.get("/api/contracts")
def list_contracts(bus_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Contract)
    if bus_id:
        q = q.filter(models.Contract.bus_id == bus_id)
    contracts = q.order_by(models.Contract.start_date.desc()).all()
    return [compute_contract_result(db, c) for c in contracts]


@app.post("/api/contracts")
def create_contract(body: schemas.ContractCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    if body.end_date < body.start_date:
        raise HTTPException(400, "La date de fin doit être après la date de début.")
    if not db.get(models.Bus, body.bus_id):
        raise HTTPException(404, "Véhicule introuvable.")
    c = models.Contract(**body.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return compute_contract_result(db, c)


@app.put("/api/contracts/{cid}")
def update_contract(cid: int, body: schemas.ContractCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    c = db.get(models.Contract, cid)
    if not c:
        raise HTTPException(404, "Contrat introuvable.")
    if body.end_date < body.start_date:
        raise HTTPException(400, "La date de fin doit être après la date de début.")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit(); db.refresh(c)
    return compute_contract_result(db, c)


@app.delete("/api/contracts/{cid}", status_code=204)
def delete_contract(cid: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    c = db.get(models.Contract, cid)
    if c:
        db.delete(c); db.commit()


@app.get("/api/contracts/{cid}/result")
def contract_result_endpoint(cid: int, db: Session = Depends(get_db)):
    c = db.get(models.Contract, cid)
    if not c:
        raise HTTPException(404, "Contrat introuvable.")
    return compute_contract_result(db, c)


# ---------- fuel ----------
@app.get("/api/fuel", response_model=list[schemas.FuelOut])
def list_fuel(bus_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(models.FuelMonth)
    if bus_id:
        q = q.filter(models.FuelMonth.bus_id == bus_id)
    return q.order_by(models.FuelMonth.year, models.FuelMonth.month).all()


@app.put("/api/fuel", response_model=schemas.FuelOut)
def upsert_fuel(body: schemas.FuelUpsert, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Set estimated and/or actual for a bus + calendar month (creates if missing)."""
    fm = (db.query(models.FuelMonth)
          .filter(models.FuelMonth.bus_id == body.bus_id,
                  models.FuelMonth.year == body.year,
                  models.FuelMonth.month == body.month).first())
    if not fm:
        fm = models.FuelMonth(bus_id=body.bus_id, year=body.year, month=body.month, estimated=0.0)
        db.add(fm)
    if body.estimated is not None:
        fm.estimated = body.estimated
    if body.actual is not None:
        fm.actual = body.actual
    db.commit(); db.refresh(fm)
    return fm


# ---------- the calendar (viewer) ----------
@app.get("/api/calendar/{year}/{month}")
def calendar(year: int, month: int, db: Session = Depends(get_db)):
    if not (1 <= month <= 12):
        raise HTTPException(400, "Mois invalide.")
    cfg = get_config(db)
    start, end = calc.month_bounds(year, month)
    buses = db.query(models.Bus).order_by(models.Bus.sort_order).all()

    # bookings whose [date .. end_date] span OVERLAPS this month (covers multi-day)
    books = (db.query(models.Booking)
             .filter(models.Booking.date <= end,
                     func.coalesce(models.Booking.end_date, models.Booking.date) >= start)
             .all())

    # for the simple-net fallback we only count excursions STARTING in the month
    book_dicts = [{
        "id": b.id, "bus_id": b.bus_id, "date": b.date, "type": b.type, "total": b.total,
    } for b in books if start <= b.date <= end]

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

    # contracts grouped by bus, to pick the one overlapping the viewed month
    contracts = db.query(models.Contract).all()
    contracts_by_bus = {}
    for c in contracts:
        contracts_by_bus.setdefault(c.bus_id, []).append(c)

    def overlap(a0, a1, b0, b1):
        s, e = max(a0, b0), min(a1, b1)
        return (e - s).days + 1 if s <= e else 0

    bus_list = []
    sum_rows = []   # for region summary (contract-aware)
    for bus in buses:
        bd = {"id": bus.id, "name": bus.name, "type": bus.type, "region": bus.region,
              "distance": bus.distance}
        days = {}
        for day in range(1, end.day + 1):
            ds = date(year, month, day).isoformat()
            cell = by_cell.get((bus.id, ds), [])
            if cell:
                days[day] = calc.day_color(cell, cfg.cut_morn, cfg.cut_night)
        bd["days"] = days

        # pick the contract that overlaps the viewed month the most
        chosen, best = None, 0
        for c in contracts_by_bus.get(bus.id, []):
            ov = overlap(c.start_date, c.end_date, start, end)
            if ov > best:
                chosen, best = c, ov

        if chosen:
            res = compute_contract_result(db, chosen)
            bd.update({
                "net": res["net"], "pct": res["pct"], "is_estimated": res["is_estimated"],
                "contract": {
                    "id": chosen.id, "label": chosen.label,
                    "start_date": chosen.start_date.isoformat(),
                    "end_date": chosen.end_date.isoformat(),
                    "revenue": res["revenue"], "loyer": res["loyer"], "fuel": res["fuel"],
                },
            })
            sum_rows.append({"region": bus.region or "—", "loyer": res["loyer"], "net": res["net"]})
        else:
            # no contract covering this month -> nothing to compute (rent lives on contracts)
            bd.update({"net": None, "pct": "—", "is_estimated": False, "contract": None, "no_contract": True})
            sum_rows.append({"region": bus.region or "—", "loyer": 0.0, "net": 0.0})

        bus_list.append(bd)

    # region summary from the contract-aware rows
    reg = {}
    for r in sum_rows:
        g = reg.setdefault(r["region"], {"region": r["region"], "loyer": 0.0, "net": 0.0, "count": 0})
        g["loyer"] += r["loyer"]; g["net"] += r["net"]; g["count"] += 1
    regions = list(reg.values())
    for g in regions:
        g["pct"] = calc.pct(g["net"], g["loyer"])
    total = {"region": "TOTAL",
             "loyer": sum(g["loyer"] for g in regions),
             "net": sum(g["net"] for g in regions),
             "count": sum(g["count"] for g in regions)}
    total["pct"] = calc.pct(total["net"], total["loyer"])
    summary = {"regions": regions, "total": total}

    return {
        "year": year, "month": month,
        "label": f"{calc.MONTH_FR[month]} {year}",
        "days_in_month": end.day,
        "cut_morn": cfg.cut_morn, "cut_night": cfg.cut_night,
        "buses": bus_list,
        "summary": summary,
    }


# ---------- a single day for one bus (mobile entry open) ----------
@app.get("/api/day/{bus_id}/{day_iso}")
def get_day(bus_id: int, day_iso: str, db: Session = Depends(get_db)):
    try:
        d = date.fromisoformat(day_iso)
    except ValueError:
        raise HTTPException(400, "Date invalide.")
    rows = (db.query(models.Booking)
            .filter(models.Booking.bus_id == bus_id, models.Booking.date == d)
            .all())
    return [schemas.BookingOut.model_validate(r).model_dump() for r in rows]


# ---------- save a day (mobile entry submit) ----------
UNAVAIL_CATS = {"Entretien", "Libre", "Repos Chauffeur"}

def _excursion_out(b: models.Booking) -> dict:
    return {
        "id": b.id, "bus_id": b.bus_id,
        "start_date": b.date.isoformat(),
        "end_date": (b.end_date or b.date).isoformat(),
        "type": b.type, "destination": b.destination, "client": b.client,
        "pax": b.pax, "unit_price": b.unit_price, "total": b.total,
        "heure_debut": b.heure_debut, "heure_fin": b.heure_fin, "notes": b.notes,
        "multi_day": (b.end_date is not None and b.end_date != b.date),
    }

def _require_contract(db: Session, bus_id: int, d: date):
    cov = (db.query(models.Contract)
           .filter(models.Contract.bus_id == bus_id,
                   models.Contract.start_date <= d,
                   models.Contract.end_date >= d).first())
    if not cov:
        raise HTTPException(409,
            "Aucun contrat ne couvre cette date pour ce véhicule. "
            "Créez d'abord un contrat (onglet Contrats) couvrant cette période.")

def _apply_excursion(db: Session, b: models.Booking, body: schemas.ExcursionIn):
    bus = db.get(models.Bus, body.bus_id)
    if not bus:
        raise HTTPException(404, "Véhicule introuvable.")
    start = body.start_date
    end = body.end_date or start
    if end < start:
        raise HTTPException(400, "La date de fin doit être ≥ la date de début.")
    cat = (body.category or "").strip()
    dest = (body.destination or "").strip()
    is_unavail = cat in UNAVAIL_CATS
    if not is_unavail and not dest:
        raise HTTPException(400, "Choisissez une destination.")
    _require_contract(db, bus.id, start)   # coverage on the start day
    b.bus_id = bus.id
    b.date = start
    b.end_date = end
    b.client = body.client
    b.pax = body.pax
    b.heure_debut = body.heure_debut
    b.heure_fin = body.heure_fin
    b.notes = body.notes
    if is_unavail:
        b.type = "Unavailable"; b.destination = cat
        b.unit_price = 0; b.total = 0
    else:
        price = price_for(db, dest, bus.type)
        b.type = "Booking"; b.destination = dest
        b.unit_price = price
        b.total = body.total if body.total is not None else price


@app.get("/api/excursions/day/{bus_id}/{day_iso}")
def excursions_for_day(bus_id: int, day_iso: str, db: Session = Depends(get_db)):
    """All excursions ACTIVE on this day for the bus (covers multi-day spans)."""
    try:
        d = date.fromisoformat(day_iso)
    except ValueError:
        raise HTTPException(400, "Date invalide.")
    rows = (db.query(models.Booking)
            .filter(models.Booking.bus_id == bus_id,
                    models.Booking.date <= d,
                    func.coalesce(models.Booking.end_date, models.Booking.date) >= d)
            .order_by(models.Booking.heure_debut).all())
    return [_excursion_out(r) for r in rows]


@app.post("/api/excursions")
def create_excursion(body: schemas.ExcursionIn, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    b = models.Booking()
    _apply_excursion(db, b, body)
    db.add(b); db.commit(); db.refresh(b)
    return _excursion_out(b)


@app.put("/api/excursions/{exc_id}")
def update_excursion(exc_id: int, body: schemas.ExcursionIn, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    b = db.get(models.Booking, exc_id)
    if not b:
        raise HTTPException(404, "Excursion introuvable.")
    _apply_excursion(db, b, body)
    db.commit(); db.refresh(b)
    return _excursion_out(b)


@app.delete("/api/excursions/{exc_id}", status_code=204)
def delete_excursion(exc_id: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    b = db.get(models.Booking, exc_id)
    if b:
        db.delete(b); db.commit()


@app.get("/api/coverage/{bus_id}/{day_iso}")
def coverage(bus_id: int, day_iso: str, db: Session = Depends(get_db)):
    """Does this bus have a contract covering this date? Used by the entry form."""
    try:
        d = date.fromisoformat(day_iso)
    except ValueError:
        raise HTTPException(400, "Date invalide.")
    c = (db.query(models.Contract)
         .filter(models.Contract.bus_id == bus_id,
                 models.Contract.start_date <= d,
                 models.Contract.end_date >= d).first())
    return {"covered": c is not None,
            "contract": ({"id": c.id, "label": c.label,
                          "start_date": c.start_date.isoformat(),
                          "end_date": c.end_date.isoformat()} if c else None)}


@app.post("/api/day")
def save_day(body: schemas.DaySave, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    bus = db.get(models.Bus, body.bus_id)
    if not bus:
        raise HTTPException(404, "Véhicule introuvable.")

    UNAVAIL = {"Entretien", "Libre", "Repos Chauffeur"}

    # Require a contract covering this date IF there is real content to add.
    # (Clearing a day — empty rows — is always allowed.)
    has_content = any((r.category or "").strip() for r in body.rows)
    if has_content:
        covering = (db.query(models.Contract)
                    .filter(models.Contract.bus_id == bus.id,
                            models.Contract.start_date <= body.date,
                            models.Contract.end_date >= body.date).first())
        if not covering:
            raise HTTPException(
                409,
                "Aucun contrat ne couvre cette date pour ce véhicule. "
                "Créez d'abord un contrat (onglet Contrats) couvrant cette période.")

    # replace all existing rows for this bus+date (same semantics as Excel SaveAndReturn)
    db.query(models.Booking).filter(
        models.Booking.bus_id == bus.id, models.Booking.date == body.date
    ).delete()

    saved = 0
    for row in body.rows:
        cat = (row.category or "").strip()
        dest = (row.destination or "").strip()
        if not cat:
            continue
        is_unavail = cat in UNAVAIL
        if not is_unavail and not dest:
            continue  # booking with no destination -> skip
        if is_unavail:
            db.add(models.Booking(
                date=body.date, bus_id=bus.id, type="Unavailable",
                destination=cat, total=0, unit_price=0, notes=body.notes,
                heure_debut=row.heure_debut, heure_fin=row.heure_fin,
            ))
        else:
            price = price_for(db, dest, bus.type)
            db.add(models.Booking(
                date=body.date, bus_id=bus.id, type="Booking",
                destination=dest, client=row.client, pax=row.pax,
                unit_price=price, total=price, notes=body.notes,
                heure_debut=row.heure_debut, heure_fin=row.heure_fin,
            ))
        saved += 1

    db.commit()
    return {"ok": True, "saved": saved}
