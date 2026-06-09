"""
Web Push notifications.

Config (env vars on the server):
  VAPID_PUBLIC_KEY   base64url application server key (also handed to the browser)
  VAPID_PRIVATE_KEY  base64url raw private key
  VAPID_SUBJECT      mailto: or https url identifying the sender (default below)
  NOTIFY_SECRET      shared secret the weekly scheduler must send to trigger a push
"""
import os
import json
import datetime
import calendar as _cal

from sqlalchemy.orm import Session

from .. import models
from .calendar import build_calendar

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:bestimetravel@example.com")
NOTIFY_SECRET = os.environ.get("NOTIFY_SECRET", "")


def _fmt(v: float) -> str:
    sign = "+" if v >= 0 else "-"
    return f"{sign}{abs(round(v)):,} TND".replace(",", " ")


def _short(name: str) -> str:
    # keep it compact for a notification line
    return (name or "").replace("VOYAGES ", "").replace("TRAVEL ", "")[:22]


def build_month_summary(db: Session):
    """Returns (title, body) summarizing the CURRENT month for a notification."""
    today = datetime.date.today()
    data = build_calendar(db, today.year, today.month)
    buses = [b for b in data["buses"] if b.get("net") is not None]
    total = data["summary"]["total"]["net"]

    start = datetime.date(today.year, today.month, 1)
    end = datetime.date(today.year, today.month, _cal.monthrange(today.year, today.month)[1])
    trips = (db.query(models.Booking)
             .filter(models.Booking.type == "Booking",
                     models.Booking.date >= start, models.Booking.date <= end).count())

    parts = [f"Net total {_fmt(total)}", f"{trips} trajets"]
    if buses:
        best = max(buses, key=lambda b: b["net"])
        worst = min(buses, key=lambda b: b["net"])
        parts.append(f"Top {_short(best['name'])} {_fmt(best['net'])}")
        if worst is not best:
            parts.append(f"Bas {_short(worst['name'])} {_fmt(worst['net'])}")
    return f"📊 Résumé {data['label']}", " • ".join(parts)


def send_to_all(db: Session, title: str, body: str, url: str = "/") -> dict:
    """Send a notification to every stored subscription. Prunes dead ones."""
    from pywebpush import webpush, WebPushException
    if not (VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY):
        return {"error": "VAPID keys not configured", "sent": 0}
    subs = db.query(models.PushSubscription).all()
    payload = json.dumps({"title": title, "body": body, "url": url})
    sent = pruned = failed = 0
    for s in subs:
        info = {"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}}
        try:
            webpush(subscription_info=info, data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": VAPID_SUBJECT}, timeout=10)
            sent += 1
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (404, 410):       # subscription gone — drop it
                db.delete(s); pruned += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    if pruned:
        db.commit()
    return {"sent": sent, "pruned": pruned, "failed": failed, "total": len(subs)}
