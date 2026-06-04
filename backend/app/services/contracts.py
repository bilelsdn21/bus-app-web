"""Contract result computation (revenue − loyer − prorated fuel)."""
from sqlalchemy.orm import Session
from .. import models
from . import calc


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
