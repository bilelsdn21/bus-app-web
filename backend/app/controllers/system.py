"""System endpoints: health check, login, and the activity Journal."""
import time
from collections import defaultdict, deque
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import authenticate, require_admin
from ..services.audit import log_action
from .. import models

router = APIRouter()


@router.get("/api/health")
def health():
    return {"ok": True}


class LoginBody(BaseModel):
    username: str
    password: str


# Simple in-memory brute-force guard: max failed attempts per IP per window.
_FAILS: dict = defaultdict(deque)   # ip -> deque[timestamps of failures]
_MAX_FAILS = 6
_WINDOW = 300  # 5 minutes


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?"))


@router.post("/api/login")
def login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    now = time.time()
    fails = _FAILS[ip]
    while fails and now - fails[0] > _WINDOW:
        fails.popleft()
    if len(fails) >= _MAX_FAILS:
        raise HTTPException(429, "Trop de tentatives. Réessayez dans quelques minutes.")

    info = authenticate(body.username, body.password)
    if not info:
        fails.append(now)
        try:
            log_action(db, "système", "Connexion échouée", f"{body.username} (IP {ip})")
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(401, "Identifiants incorrects.")

    _FAILS.pop(ip, None)  # clear on success
    return {"ok": True, **info}


@router.get("/api/audit")
def get_audit(limit: int = 300, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """The activity log — who did what, when. Admin only."""
    rows = (db.query(models.AuditLog)
            .order_by(models.AuditLog.created_at.desc()).limit(min(limit, 1000)).all())
    return [{"time": (r.created_at.isoformat() if r.created_at else None),
             "user": r.username, "action": r.method, "detail": r.detail or ""}
            for r in rows]
