"""
ORM models. Mirrors the Excel structure but with proper relations, so a booking
references a bus by FK (id) — no more silent name-mismatch lost revenue.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Date, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .database import Base


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
