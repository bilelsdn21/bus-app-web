"""
ORM models. Mirrors the Excel structure but with proper relations, so a booking
references a bus by FK (id) — no more silent name-mismatch lost revenue.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .core.database import Base


class Bus(Base):
    __tablename__ = "buses"
    id        = Column(Integer, primary_key=True)
    name      = Column(String, nullable=False, unique=True)   # e.g. "BUS ISKANDER VOYAGES 370 TU 243"
    plate     = Column(String, index=True)                    # "370 TU 243" — stable vehicle id
    type      = Column(String, default="MICRO")               # MICRO / OTOKAR / BUS
    region    = Column(String, default="")                    # Sousse / Djerba
    loyer     = Column(Float, default=0.0)                     # monthly rent
    distance  = Column(Float, default=0.0)                     # monthly km
    sort_order = Column(Integer, default=0)
    bookings  = relationship("Booking", back_populates="bus", cascade="all, delete-orphan")


class Destination(Base):
    __tablename__ = "destinations"
    id            = Column(Integer, primary_key=True)
    category      = Column(String, default="")
    name          = Column(String, nullable=False)
    price_micro   = Column(Float, default=0.0)
    price_otokar  = Column(Float, default=0.0)
    price_bus     = Column(Float, default=0.0)
    __table_args__ = (UniqueConstraint("category", "name", name="uq_dest"),)


class Booking(Base):
    __tablename__ = "bookings"
    id          = Column(Integer, primary_key=True)
    date        = Column(Date, nullable=False, index=True)   # START day of the excursion
    end_date    = Column(Date, nullable=True, index=True)    # END day (None/=date for single-day)
    bus_id      = Column(Integer, ForeignKey("buses.id"), nullable=False, index=True)
    type        = Column(String, default="Booking")           # Booking / Unavailable
    destination = Column(String, default="")
    client      = Column(String, default="")
    pax         = Column(Integer, default=0)
    unit_price  = Column(Float, default=0.0)
    total       = Column(Float, default=0.0)
    notes       = Column(Text, default="")
    heure_debut = Column(String, default="")                  # "08:00"
    heure_fin   = Column(String, default="")                  # "14:00"
    bus         = relationship("Bus", back_populates="bookings")


class Contract(Base):
    """A billing period for one bus. Arbitrary dates (not the calendar month)."""
    __tablename__ = "contracts"
    id         = Column(Integer, primary_key=True)
    bus_id     = Column(Integer, ForeignKey("buses.id"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date   = Column(Date, nullable=False)
    loyer      = Column(Float, default=0.0)     # rent for THIS period
    label      = Column(String, default="")     # optional note, e.g. "Contrat Mai"
    bus        = relationship("Bus")


class FuelMonth(Base):
    """Fuel spend for one bus in one CALENDAR month.
    `estimated` is set ahead; `actual` replaces it on the 1st of the next month."""
    __tablename__ = "fuel_months"
    id         = Column(Integer, primary_key=True)
    bus_id     = Column(Integer, ForeignKey("buses.id"), nullable=False, index=True)
    year       = Column(Integer, nullable=False)
    month      = Column(Integer, nullable=False)   # 1..12
    estimated  = Column(Float, default=0.0)
    actual     = Column(Float, nullable=True)      # None until actualized
    bus        = relationship("Bus")
    __table_args__ = (UniqueConstraint("bus_id", "year", "month", name="uq_fuel"),)


class Config(Base):
    __tablename__ = "config"
    id         = Column(Integer, primary_key=True)
    cut_morn   = Column(Integer, default=13)   # morning/evening boundary (h)
    cut_night  = Column(Integer, default=22)   # evening/night boundary (h)
    # current destination prices apply from this date onward; before it, the
    # historical price periods are used. NULL => current prices for all dates.
    current_prices_since = Column(Date, nullable=True)


class PricePeriod(Base):
    """A destination's price during a date range [effective_from .. effective_to].
    Excursions dated in that range use this price automatically; outside any range,
    the current Destination price is used. Lets old (negotiated) prices be back-filled."""
    __tablename__ = "price_periods"
    id             = Column(Integer, primary_key=True)
    dest_name      = Column(String, nullable=False, index=True)
    effective_from = Column(Date, nullable=False)
    effective_to   = Column(Date, nullable=True)
    price_micro    = Column(Float, default=0.0)
    price_otokar   = Column(Float, default=0.0)
    price_bus      = Column(Float, default=0.0)
    __table_args__ = (UniqueConstraint("dest_name", "effective_from", name="uq_price_period"),)


class BusRegionPeriod(Base):
    """A bus's region during a date range [effective_from .. effective_to]. Buses move
    between regions by season; the Calendar/Analyse pages for a given month use whichever
    period overlaps that month the most, falling back to the bus's current `region` field
    when no period is defined (fully additive — a bus with no periods behaves as before)."""
    __tablename__ = "region_periods"
    id             = Column(Integer, primary_key=True)
    bus_id         = Column(Integer, ForeignKey("buses.id"), nullable=False, index=True)
    region         = Column(String, nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to   = Column(Date, nullable=True)
    bus            = relationship("Bus")
    __table_args__ = (UniqueConstraint("bus_id", "effective_from", name="uq_region_period"),)


class RentedVehicle(Base):
    """An external vehicle rented FROM someone else for a period — reinforcement,
    not part of our own fleet (no bus_id). Its cost is prorated by day into whichever
    calendar month(s) [start_date..end_date] overlaps (shown on the Calendrier page,
    informational only — see services/rentals.py). `type` (MICRO/OTOKAR/BUS) lets the
    Loués page flag whether a same-type fleet vehicle was actually free that period —
    see services/alternatives.py."""
    __tablename__ = "rented_vehicles"
    id         = Column(Integer, primary_key=True)
    name       = Column(String, nullable=False)
    type       = Column(String, default="MICRO")
    region     = Column(String, default="")
    start_date = Column(Date, nullable=False)
    end_date   = Column(Date, nullable=False)
    cost       = Column(Float, default=0.0)
    notes      = Column(String, default="")


class AuditLog(Base):
    """Who did what, when — one row per write action by an admin."""
    __tablename__ = "audit_log"
    id         = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    username   = Column(String, index=True)
    method     = Column(String)   # POST / PUT / DELETE
    path       = Column(String)   # /api/excursions/5 ...
    status     = Column(Integer)  # HTTP status returned
    detail     = Column(Text, default="")


class PushSubscription(Base):
    """A browser/phone that opted in to push notifications."""
    __tablename__ = "push_subscriptions"
    id         = Column(Integer, primary_key=True)
    endpoint   = Column(String, nullable=False, unique=True)
    p256dh     = Column(String, nullable=False)
    auth       = Column(String, nullable=False)
    username   = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
