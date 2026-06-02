"""Pydantic request/response schemas."""
from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ---- Bus ----
class BusBase(BaseModel):
    name: str
    plate: Optional[str] = ""
    type: str = "MICRO"
    region: str = ""
    loyer: float = 0.0
    distance: float = 0.0

class BusCreate(BusBase):
    pass

class BusOut(BusBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---- Destination ----
class DestinationBase(BaseModel):
    category: str = ""
    name: str
    price_micro: float = 0.0
    price_otokar: float = 0.0
    price_bus: float = 0.0

class DestinationCreate(DestinationBase):
    pass

class DestinationOut(DestinationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---- Booking ----
class BookingBase(BaseModel):
    date: date
    bus_id: int
    type: str = "Booking"
    destination: str = ""
    client: str = ""
    pax: int = 0
    unit_price: float = 0.0
    total: float = 0.0
    notes: str = ""
    heure_debut: str = ""
    heure_fin: str = ""

class BookingCreate(BookingBase):
    pass

class BookingOut(BookingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---- Contract ----
class ContractBase(BaseModel):
    bus_id: int
    start_date: date
    end_date: date
    loyer: float = 0.0
    label: str = ""

class ContractCreate(ContractBase):
    pass

class ContractOut(ContractBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---- Fuel ----
class FuelUpsert(BaseModel):
    bus_id: int
    year: int
    month: int
    estimated: Optional[float] = None
    actual: Optional[float] = None

class FuelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    bus_id: int
    year: int
    month: int
    estimated: float = 0.0
    actual: Optional[float] = None


# ---- Config ----
class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cut_morn: int = 13
    cut_night: int = 22

class ConfigUpdate(BaseModel):
    cut_morn: int
    cut_night: int


# ---- Day save (mobile entry: one bus + date, several activity rows) ----
class DayRow(BaseModel):
    category: str = ""
    destination: str = ""
    client: str = ""
    pax: int = 0
    heure_debut: str = ""
    heure_fin: str = ""

class DaySave(BaseModel):
    bus_id: int
    date: date
    notes: str = ""
    rows: list[DayRow] = []
