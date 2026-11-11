"""System endpoints: health check, login, and the activity Journal."""
import time
from collections import defaultdict, deque
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import authenticate, require_admin, require_user, require_owner
from ..services.audit import log_action
from .. import models

router = APIRouter()


@router.api_route("/api/health", methods=["GET", "HEAD"])   # uptime monitors usually send HEAD
def health():
    return {"ok": True}


@router.get("/api/health/db")
def health_db():
    """Can the server reach its database right now? Reports ok/ms or the error KIND only
    (no host, user or password)."""
    import time as _t
    from sqlalchemy import text
    from ..core.database import engine
    t0 = _t.time()
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        return {"db": True, "ms": round((_t.time() - t0) * 1000)}
    except Exception as e:
        msg = str(getattr(e, "orig", e)).strip().splitlines()[0][:160] if str(e).strip() else ""
        for secret in (engine.url.host, engine.url.username, engine.url.password):
            if secret:
                msg = msg.replace(str(secret), "***")
        return {"db": False, "ms": round((_t.time() - t0) * 1000),
                "error": type(e).__name__, "detail": msg}


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
    try:
        log_action(db, body.username, "Connexion", f"connecté ({info['role']}) — IP {ip}")
        db.commit()
    except Exception:
        db.rollback()
    return {"ok": True, **info}


@router.post("/api/logout")
def logout(request: Request, db: Session = Depends(get_db), user: str = Depends(require_user)):
    """Records a logout in the Journal (best-effort)."""
    try:
        log_action(db, user, "Déconnexion", f"déconnecté — IP {_client_ip(request)}")
        db.commit()
    except Exception:
        db.rollback()
    return {"ok": True}


# Connection events (logins/logouts) are private to the owner; admins don't see them.
_CONNECTION_ACTIONS = ("Connexion", "Déconnexion", "Connexion échouée")


@router.get("/api/audit")
def get_audit(limit: int = 300, db: Session = Depends(get_db), _owner: str = Depends(require_owner)):
    """The full activity log — who did what, when, INCLUDING logins/logouts. Owner only."""
    rows = (db.query(models.AuditLog)
            .order_by(models.AuditLog.created_at.desc()).limit(min(limit, 1000)).all())
    return [{"time": (r.created_at.isoformat() if r.created_at else None),
             "user": r.username, "action": r.method, "detail": r.detail or ""}
            for r in rows]


@router.get("/api/audit/changes")
def get_audit_changes(limit: int = 300, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Changes-only log (add/edit/delete) for admins — excludes logins/logouts."""
    rows = (db.query(models.AuditLog)
            .filter(~models.AuditLog.method.in_(_CONNECTION_ACTIONS))
            .order_by(models.AuditLog.created_at.desc()).limit(min(limit, 1000)).all())
    return [{"time": (r.created_at.isoformat() if r.created_at else None),
             "user": r.username, "action": r.method, "detail": r.detail or ""}
            for r in rows]
