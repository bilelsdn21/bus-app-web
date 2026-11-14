"""Money rules: fuel proration, contract result, day colors."""
from datetime import date

from app.services import calc


def test_fuel_is_prorated_by_days_and_flagged_estimated():
    # README worked example: contract 15 May -> 14 Jun, loyer 5000,
    # May fuel actual 2000, June fuel estimated 1200, revenue 12270.
    contract = {"bus_id": 1, "start_date": date(2026, 5, 15), "end_date": date(2026, 6, 14), "loyer": 5000}
    bookings = [{"bus_id": 1, "date": date(2026, 5, 20), "type": "Booking", "total": 12270}]
    fuel = {(2026, 5): {"estimated": 1800, "actual": 2000}, (2026, 6): {"estimated": 1200, "actual": None}}
    r = calc.contract_result(contract, bookings, fuel)
    assert r["fuel"] == 1656.77            # 17/31*2000 + 14/30*1200
    assert r["net"] == 5613.23
    assert r["is_estimated"] is True
    assert r["days"] == 31


def test_result_is_not_estimated_once_every_month_has_an_actual():
    contract = {"bus_id": 1, "start_date": date(2026, 5, 1), "end_date": date(2026, 5, 31), "loyer": 100}
    fuel = {(2026, 5): {"estimated": 10, "actual": 20}}
    assert calc.contract_result(contract, [], fuel)["is_estimated"] is False


def test_only_bookings_inside_the_contract_count_as_revenue():
    contract = {"bus_id": 1, "start_date": date(2026, 5, 10), "end_date": date(2026, 5, 20), "loyer": 0}

    def row(d, t="Booking", bus=1):
        return {"bus_id": bus, "date": d, "type": t, "total": 100}

    rows = [row(date(2026, 5, 9)), row(date(2026, 5, 10)), row(date(2026, 5, 20)), row(date(2026, 5, 21)),
            row(date(2026, 5, 15), t="Unavailable"), row(date(2026, 5, 15), bus=2)]
    assert calc.contract_result(contract, rows, {})["revenue"] == 200


def test_percentage_text():
    assert calc.pct(50, 100) == "+50.0%"
    assert calc.pct(-25, 100) == "-25.0%"
    assert calc.pct(10, 0) == "—"


def test_rental_cost_is_split_by_day_across_months():
    # 10 days, 5 of them in May -> half the cost lands in May
    assert calc.prorate_period_cost(date(2026, 5, 27), date(2026, 6, 5), 1000, 2026, 5) == 500


def test_day_colors():
    unavail = [{"type": "Unavailable"}]
    morning = [{"type": "Booking", "heure_debut": "08:00", "heure_fin": "11:00"}]
    evening = [{"type": "Booking", "heure_debut": "15:00", "heure_fin": "18:00"}]
    long_trip = [{"type": "Booking", "heure_debut": "06:00", "heure_fin": "17:00"}]
    multi = [{"type": "Booking", "multi": True}]
    assert calc.day_color([]) == ""
    assert calc.day_color(unavail) == "red"
    assert calc.day_color(morning) == "yellow"
    assert calc.day_color(evening) == "orange"
    assert calc.day_color(morning + evening) == "green"     # two different periods
    assert calc.day_color(long_trip) == "green"             # one trip spanning two periods
    assert calc.day_color(multi) == "green"
