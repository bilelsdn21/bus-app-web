"""System endpoints: health check, login, and the activity Journal."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import authenticate, require_admin
from .. import models

router = APIRouter()


@router.get("/api/health")
def health():
    return {"ok": True}


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/api/login")
def login(body: LoginBody):
    info = authenticate(body.username, body.password)
    if not info:
        raise HTTPException(401, "Identifiants incorrects.")
    return {"ok": True, **info}


@router.get("/api/audit")
def get_audit(limit: int = 300, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """The activity log — who did what, when. Admin only."""
    rows = (db.query(models.AuditLog)
            .order_by(models.AuditLog.created_at.desc()).limit(min(limit, 1000)).all())
    return [{"time": (r.created_at.isoformat() if r.created_at else None),
             "user": r.username, "action": r.method, "detail": r.detail or ""}
            for r in rows]
