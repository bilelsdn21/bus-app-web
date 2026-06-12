"""
Authentication + authorization.

Accounts live ONLY in the BUS_USERS env var on the server — never in code.
Each entry is "user:password:role" (role = admin | viewer), comma-separated:
    BUS_USERS="aymen:pass1:admin,bilel:pass2:admin,equipe:pass3:viewer"

Tokens are stateless but **signed and expiring**:
    token = base64url("username|exp") + "." + HMAC_SHA256(BUS_SECRET, "username|exp|password")
so a token (a) can't be forged without BUS_SECRET, (b) expires after TOKEN_TTL_HOURS,
and (c) is invalidated the moment that user's password changes in BUS_USERS.
The frontend sends it as `Authorization: Bearer <token>`.
"""
import os
import time
import hmac
import hashlib
import base64
from fastapi import Header, HTTPException


def _load_users() -> dict:
    raw = os.environ.get("BUS_USERS", "dev:dev:admin")   # dev default only
    users = {}
    for entry in raw.split(","):
        parts = entry.split(":")
        if len(parts) >= 2:
            u = parts[0].strip()
            p = parts[1]
            role = parts[2].strip().lower() if len(parts) >= 3 and parts[2].strip() else "admin"
            users[u] = {"password": p, "role": role}
    return users


USERS = _load_users()


def _secret() -> str:
    return os.environ.get("BUS_SECRET", "bus-local-secret")


def _ttl_seconds() -> int:
    try:
        hours = float(os.environ.get("TOKEN_TTL_HOURS", "336"))  # default 14 days
    except ValueError:
        hours = 336.0
    return int(hours * 3600)


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).rstrip(b"=").decode()


def _unb64(s: str) -> str:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode()


def _sign(payload: str, password: str) -> str:
    return hmac.new(_secret().encode(), f"{payload}|{password}".encode(), hashlib.sha256).hexdigest()


def make_token(username: str, password: str) -> str:
    exp = int(time.time()) + _ttl_seconds()
    payload = f"{username}|{exp}"
    return _b64(payload) + "." + _sign(payload, password)


def verify_token(token: str) -> str | None:
    """Return the username iff the token is valid (good signature, not expired,
    password unchanged), else None."""
    try:
        b64payload, sig = token.split(".", 1)
        payload = _unb64(b64payload)
        username, exp_s = payload.rsplit("|", 1)
        exp = int(exp_s)
    except Exception:
        return None
    if exp < int(time.time()):
        return None
    info = USERS.get(username)
    if not info:
        return None
    if not hmac.compare_digest(sig, _sign(payload, info["password"])):
        return None
    return username


def _bearer(authorization: str | None) -> str:
    return authorization[7:] if authorization and authorization.lower().startswith("bearer ") else ""


def role_of(authorization: str | None) -> str | None:
    u = verify_token(_bearer(authorization))
    return USERS.get(u, {}).get("role") if u else None


def authenticate(username: str, password: str) -> dict | None:
    """Validate credentials. Returns {username, role, token} or None."""
    info = USERS.get(username)
    if not info or not hmac.compare_digest(info["password"], password):
        return None
    return {"username": username, "role": info["role"], "token": make_token(username, password)}


def require_user(authorization: str = Header(None)) -> str:
    """FastAPI dependency: allow any authenticated account (admin OR viewer)."""
    u = verify_token(_bearer(authorization))
    if not u:
        raise HTTPException(401, "Non authentifié — reconnectez-vous.")
    return u


def require_admin(authorization: str = Header(None)) -> str:
    """FastAPI dependency: allow only admins, returning the acting username."""
    u = verify_token(_bearer(authorization))
    if not u:
        raise HTTPException(401, "Non authentifié — reconnectez-vous.")
    if USERS.get(u, {}).get("role") != "admin":
        raise HTTPException(403, "Action réservée aux administrateurs (compte en lecture seule).")
    return u
