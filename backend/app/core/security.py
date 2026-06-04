"""
Authentication + authorization (stateless token auth).

Accounts live ONLY in the BUS_USERS env var on the server — never in code.
Each entry is "user:password:role" (role = admin | viewer), comma-separated:
    BUS_USERS="aymen:pass1:admin,bilel:pass2:admin,equipe:pass3:viewer"
A token is sha256("username:BUS_SECRET"); the frontend sends it as
`Authorization: Bearer <token>`. Write endpoints require an admin token.
"""
import os
import hashlib
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


def _token(username: str) -> str:
    secret = os.environ.get("BUS_SECRET", "bus-local-secret")
    return hashlib.sha256(f"{username}:{secret}".encode()).hexdigest()


# token -> role, and token -> username, for verifying + auditing requests
TOKENS = {_token(u): info["role"] for u, info in USERS.items()}
TOKEN_USER = {_token(u): u for u in USERS}


def _bearer(authorization: str | None) -> str:
    return authorization[7:] if authorization and authorization.lower().startswith("bearer ") else ""


def role_of(authorization: str | None) -> str | None:
    return TOKENS.get(_bearer(authorization))


def authenticate(username: str, password: str) -> dict | None:
    """Validate credentials. Returns {username, role, token} or None."""
    info = USERS.get(username)
    if not info or info["password"] != password:
        return None
    return {"username": username, "role": info["role"], "token": _token(username)}


def require_admin(authorization: str = Header(None)) -> str:
    """FastAPI dependency: allow only admin tokens, and return the acting
    username (so endpoints can record WHO acted in the Journal)."""
    tok = _bearer(authorization)
    role = TOKENS.get(tok)
    if role is None:
        raise HTTPException(401, "Non authentifié — reconnectez-vous.")
    if role != "admin":
        raise HTTPException(403, "Action réservée aux administrateurs (compte en lecture seule).")
    return TOKEN_USER.get(tok, "?")
