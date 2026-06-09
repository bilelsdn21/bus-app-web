"""Push notification endpoints: opt-in/out, weekly trigger, admin test."""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import require_user, require_admin
from .. import models
from ..services import push as push_svc

router = APIRouter()


class SubKeys(BaseModel):
    p256dh: str
    auth: str


class SubIn(BaseModel):
    endpoint: str
    keys: SubKeys


@router.get("/api/push/key")
def push_key():
    """Public VAPID key the browser needs to subscribe."""
    return {"key": push_svc.VAPID_PUBLIC_KEY}


@router.post("/api/push/subscribe")
def subscribe(body: SubIn, db: Session = Depends(get_db), user: str = Depends(require_user)):
    existing = db.query(models.PushSubscription).filter(models.PushSubscription.endpoint == body.endpoint).first()
    if existing:
        existing.p256dh = body.keys.p256dh; existing.auth = body.keys.auth; existing.username = user
    else:
        db.add(models.PushSubscription(endpoint=body.endpoint, p256dh=body.keys.p256dh,
                                       auth=body.keys.auth, username=user))
    db.commit()
    return {"ok": True}


@router.post("/api/push/unsubscribe")
def unsubscribe(body: SubIn, db: Session = Depends(get_db), user: str = Depends(require_user)):
    db.query(models.PushSubscription).filter(models.PushSubscription.endpoint == body.endpoint).delete()
    db.commit()
    return {"ok": True}


@router.post("/api/notify/weekly")
def notify_weekly(x_notify_secret: str = Header(None), db: Session = Depends(get_db)):
    """Called by the scheduled job. Sends the current-month summary to everyone."""
    if not push_svc.NOTIFY_SECRET or x_notify_secret != push_svc.NOTIFY_SECRET:
        raise HTTPException(403, "Secret invalide.")
    title, body = push_svc.build_month_summary(db)
    return push_svc.send_to_all(db, title, body, url="/")


@router.post("/api/notify/test")
def notify_test(db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Admin-only: send the month summary right now to verify it works."""
    title, body = push_svc.build_month_summary(db)
    return push_svc.send_to_all(db, title, body, url="/")
