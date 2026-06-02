"""
FastAPI backend for the bus management web app.
Run:  uvicorn app.main:app --reload --port 8000
"""
import os
import hashlib
from datetime import date
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from . import models, schemas, calc

# Simple credential store for the 2 users. Override in production with env:
#   BUS_USERS="aymen:motdepasse1,bilel:motdepasse2"
def _load_users():
    raw = os.environ.get("BUS_USERS", "admin:btt2026,terrain:terrain2026")
    users = {}
    for pair in raw.split(","):
        if ":" in pair:
            u, p = pair.split(":", 1)
            users[u.strip()] = p
    return users

USERS = _load_users()

def _token(username: str) -> str:
    secret = os.environ.get("BUS_SECRET", "bus-local-secret")
    return hashlib.sha256(f"{username}:{secret}".encode()).hexdigest()

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
    expected = USERS.get(body.username)
    if not expected or expected != body.password:
        raise HTTPException(401, "Identifiants incorrects.")
    return {"ok": True, "username": body.username, "token": _token(body.username)}


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
def create_bus(body: schemas.BusCreate, db: Session = Depends(get_db)):
    if db.query(models.Bus).filter(models.Bus.name == body.name).first():
        raise HTTPException(409, "Un véhicule avec ce nom existe déjà.")
    bus = models.Bus(**body.model_dump())
    db.add(bus); db.commit(); db.refresh(bus)
    return bus


@app.put("/api/buses/{bus_id}", response_model=schemas.BusOut)
def update_bus(bus_id: int, body: schemas.BusCreate, db: Session = Depends(get_db)):
    bus = db.get(models.Bus, bus_id)
    if not bus:
        raise HTTPException(404, "Véhicule introuvable.")
    for k, v in body.model_dump().items():
        setattr(bus, k, v)
    db.commit(); db.refresh(bus)
    return bus


@app.delete("/api/buses/{bus_id}", status_code=204)
def delete_bus(bus_id: int, db: Session = Depends(get_db)):
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
def create_destination(body: schemas.DestinationCreate, db: Session = Depends(get_db)):
    d = models.Destination(**body.model_dump())
    db.add(d); db.commit(); db.refresh(d)
    return d


@app.put("/api/destinations/{did}", response_model=schemas.DestinationOut)
def update_destination(did: int, body: schemas.DestinationCreate, db: Session = Depends(get_db)):
    d = db.get(models.Destination, did)
    if not d:
        raise HTTPException(404, "Destination introuvable.")
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    db.commit(); db.refresh(d)
    return d


@app.delete("/api/destinations/{did}", status_code=204)
def delete_destination(did: int, db: Session = Depends(get_db)):
    d = db.get(models.Destination, did)
    if d:
        db.delete(d); db.commit()


@app.get("/api/config", response_model=schemas.ConfigOut)
def read_config(db: Session = Depends(get_db)):
    return get_config(db)


@app.put("/api/config", response_model=schemas.ConfigOut)
def update_config(body: schemas.ConfigUpdate, db: Session = Depends(get_db)):
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
def create_contract(body: schemas.ContractCreate, db: Session = Depends(get_db)):
    if body.end_date < body.start_date:
        raise HTTPException(400, "La date de fin doit être après la date de début.")
    if not db.get(models.Bus, body.bus_id):
        raise HTTPException(404, "Véhicule introuvable.")
    c = models.Contract(**body.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return compute_contract_result(db, c)


@app.put("/api/contracts/{cid}")
def update_contract(cid: int, body: schemas.ContractCreate, db: Session = Depends(get_db)):
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
def delete_contract(cid: int, db: Session = Depends(get_db)):
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
def upsert_fuel(body: schemas.FuelUpsert, db: Session = Depends(get_db)):
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
    books = (db.query(models.Booking)
             .filter(models.Booking.date >= start, models.Booking.date <= end).all())

    book_dicts = [{
        "id": b.id, "bus_id": b.bus_id, "date": b.date.isoformat(), "type": b.type,
        "destination": b.destination, "client": b.client, "pax": b.pax,
        "unit_price": b.unit_price, "total": b.total, "notes": b.notes,
        "heure_debut": b.heure_debut, "heure_fin": b.heure_fin,
    } for b in books]

    # group bookings per (bus_id, day)
    by_cell = {}
    for b in book_dicts:
        by_cell.setdefault((b["bus_id"], b["date"]), []).append(b)

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
              "loyer": bus.loyer, "distance": bus.distance}
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
            # no contract yet -> simple month net (revenue this month - default loyer, no fuel)
            net = calc.bus_net({"id": bus.id, "loyer": bus.loyer}, book_dicts)
            bd.update({"net": net, "pct": calc.pct(net, bus.loyer), "is_estimated": False, "contract": None})
            sum_rows.append({"region": bus.region or "—", "loyer": bus.loyer, "net": net})

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
@app.post("/api/day")
def save_day(body: schemas.DaySave, db: Session = Depends(get_db)):
    bus = db.get(models.Bus, body.bus_id)
    if not bus:
        raise HTTPException(404, "Véhicule introuvable.")

    UNAVAIL = {"Entretien", "Libre", "Repos Chauffeur"}

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
