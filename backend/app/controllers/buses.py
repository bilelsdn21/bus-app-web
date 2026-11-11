"""Bus (vehicle) CRUD."""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_admin, require_user
from .. import models, schemas
from ..services.audit import log_action
from ..services.fleet import fleet_overview
from ..services.lookups import norm_region

# Reads require a signed-in account; writes add require_admin on top.
router = APIRouter(dependencies=[Depends(require_user)])


def _uncovered_ranges(periods, first: date, last: date) -> list[tuple[date, date]]:
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


def _first_known_day(db: Session, bus: models.Bus, periods) -> date | None:
    """The vehicle's earliest day on file — first trip, first contract, or first region
    period, whichever comes first. Everything from there on is history to protect."""
    firsts = [
        db.query(func.min(models.Booking.date)).filter(models.Booking.bus_id == bus.id).scalar(),
        db.query(func.min(models.Contract.start_date)).filter(models.Contract.bus_id == bus.id).scalar(),
        min((p.effective_from for p in periods), default=None),
    ]
    firsts = [d for d in firsts if d]
    return min(firsts) if firsts else None


def _record_move(db: Session, bus: models.Bus, region: str, moved_on: date, admin: str) -> models.BusRegionPeriod:
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
    first_known = _first_known_day(db, bus, periods)
    if first_known and norm_region(bus.region):
        for gap_from, gap_to in _uncovered_ranges(periods, first_known, prev_day):
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


@router.get("/api/buses", response_model=list[schemas.BusOut])
def list_buses(db: Session = Depends(get_db)):
    return db.query(models.Bus).order_by(models.Bus.sort_order).all()


@router.post("/api/buses", response_model=schemas.BusOut)
def create_bus(body: schemas.BusCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    if db.query(models.Bus).filter(models.Bus.name == body.name).first():
        raise HTTPException(409, "Un véhicule avec ce nom existe déjà.")
    bus = models.Bus(**{**body.model_dump(exclude={"region_effective_from"}),
                        "region": norm_region(body.region)})
    db.add(bus); db.flush()
    log_action(db, _admin, "Véhicule", f"Ajout : {bus.name}")
    db.commit(); db.refresh(bus)
    return bus


@router.put("/api/buses/{bus_id}", response_model=schemas.BusOut)
def update_bus(bus_id: int, body: schemas.BusCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    bus = db.get(models.Bus, bus_id)
    if not bus:
        raise HTTPException(404, "Véhicule introuvable.")

    # A region change on a vehicle that already has activity is a MOVE, not a
    # correction: it needs a date, and it is written as a period so the months already
    # recorded keep the region they were actually worked in.
    moving = norm_region(body.region) != norm_region(bus.region)
    # History is not only trips: a contract alone already puts the vehicle on the
    # Calendrier/Analyse of a past month, and an existing region period is history by
    # definition. Any of them makes a region change a dated MOVE.
    has_history = bool(
        db.query(models.Booking).filter(models.Booking.bus_id == bus_id).first()
        or db.query(models.Contract).filter(models.Contract.bus_id == bus_id).first()
        or db.query(models.BusRegionPeriod).filter(models.BusRegionPeriod.bus_id == bus_id).first()
    )
    if moving and has_history and not body.region_effective_from:
        raise HTTPException(422, "Ce véhicule a déjà un historique (sorties, contrats ou périodes de région) : "
                                 "indiquez la date du changement de région, pour que les mois déjà "
                                 "enregistrés gardent la leur.")

    for k, v in body.model_dump(exclude={"region_effective_from", "region"}).items():
        setattr(bus, k, v)
    if moving and has_history:
        _record_move(db, bus, body.region, body.region_effective_from, _admin)
    else:
        bus.region = norm_region(body.region)
    log_action(db, _admin, "Véhicule", f"Modification : {bus.name}")
    db.commit(); db.refresh(bus)
    return bus


@router.delete("/api/buses/{bus_id}", status_code=204)
def delete_bus(bus_id: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    bus = db.get(models.Bus, bus_id)
    if not bus:
        return
    if db.query(models.Booking).filter(models.Booking.bus_id == bus_id).count():
        raise HTTPException(409, "Ce véhicule a des activités enregistrées — suppression bloquée.")
    name = bus.name
    db.delete(bus)
    log_action(db, _admin, "Véhicule", f"Suppression : {name}")
    db.commit()


# ---------- historical region periods (a bus changes region by season) ----------
@router.get("/api/region-periods", response_model=list[schemas.RegionPeriodOut])
def list_region_periods(db: Session = Depends(get_db)):
    return (db.query(models.BusRegionPeriod)
            .order_by(models.BusRegionPeriod.bus_id, models.BusRegionPeriod.effective_from.desc()).all())


@router.post("/api/region-periods/move", response_model=schemas.RegionPeriodOut)
def move_region(body: schemas.RegionMoveIn, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """"This vehicle moved to <region> on <date>" — the normal way to change a region.

    Everything before the date keeps its region and its figures; the calendar and the
    analysis then show the month split in two, one line per region."""
    bus = db.get(models.Bus, body.bus_id)
    if not bus:
        raise HTTPException(404, "Véhicule introuvable.")
    if not norm_region(body.region):
        raise HTTPException(422, "Région manquante.")
    rp = _record_move(db, bus, norm_region(body.region), body.moved_on, _admin)
    db.commit(); db.refresh(rp)
    return rp


@router.put("/api/region-periods", response_model=schemas.RegionPeriodOut)
def upsert_region_period(body: schemas.RegionPeriodIn, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Set a bus's region over an explicit date range (creates or updates) — used to
    back-fill history. Overlapping an existing period is rejected: the day-by-day
    region must stay unambiguous."""
    if body.effective_to and body.effective_to < body.effective_from:
        raise HTTPException(422, "La date de fin est antérieure à la date de début.")
    end = body.effective_to or date.max
    clash = next((p for p in db.query(models.BusRegionPeriod)
                  .filter(models.BusRegionPeriod.bus_id == body.bus_id).all()
                  if p.effective_from != body.effective_from
                  and p.effective_from <= end and (p.effective_to or date.max) >= body.effective_from), None)
    if clash:
        raise HTTPException(409, f"Cette période chevauche une autre ({clash.region} du "
                                 f"{clash.effective_from.isoformat()} au "
                                 f"{clash.effective_to.isoformat() if clash.effective_to else '…'}). "
                                 f"Ajustez-la d'abord, ou utilisez « Déplacer » pour enregistrer un changement de région.")
    rp = (db.query(models.BusRegionPeriod)
          .filter(models.BusRegionPeriod.bus_id == body.bus_id,
                  models.BusRegionPeriod.effective_from == body.effective_from).first())
    if not rp:
        rp = models.BusRegionPeriod(bus_id=body.bus_id, effective_from=body.effective_from)
        db.add(rp)
    rp.effective_to = body.effective_to
    rp.region = norm_region(body.region)
    bus = db.get(models.Bus, body.bus_id)
    log_action(db, _admin, "Région période",
               f"{bus.name if bus else body.bus_id} {body.effective_from}→{body.effective_to}: {body.region}")
    db.commit(); db.refresh(rp)
    return rp


@router.delete("/api/region-periods/{rid}", status_code=204)
def delete_region_period(rid: int, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    rp = db.get(models.BusRegionPeriod, rid)
    if rp:
        bus = db.get(models.Bus, rp.bus_id)
        log_action(db, _admin, "Région période", f"Suppression : {bus.name if bus else rp.bus_id} dès {rp.effective_from}")
        db.delete(rp); db.commit()


# ---------- fleet overview (powers the Véhicules filter) ----------
@router.get("/api/buses/overview")
def buses_overview(db: Session = Depends(get_db)):
    """Every vehicle with the facts the Paramètres > Véhicules filter works on:
    activity span, years, contracts/trips counts, regions visited, and any hole in its
    region history (days whose region is only a fallback to the current one)."""
    return fleet_overview(db)
