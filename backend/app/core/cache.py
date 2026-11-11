"""Tiny in-process result cache for heavy read endpoints (calendar, analytics).

Entries are keyed by a *data version* that is bumped on every committed write made
through this app's sessions, so a cached page can never outlive a change. A short TTL
is a safety net for writes made outside the app (e.g. a re-seed). The app runs as a
single process, so no cross-process invalidation is needed.
"""
import time
from sqlalchemy import event
from sqlalchemy.orm import Session

_TTL = 300  # seconds
_version = 0
_store: dict = {}


@event.listens_for(Session, "after_commit")
def _bump(session):
    # after_commit fires for read-only commits too; only count real writes
    global _version
    if session.info.pop("_dirty", False):
        _version += 1
        _store.clear()


@event.listens_for(Session, "after_flush")
def _mark_dirty(session, _ctx):
    session.info["_dirty"] = True


def cached(key, build):
    """Return build() for `key`, reusing the last result while no write has happened."""
    hit = _store.get(key)
    now = time.time()
    if hit and hit[0] == _version and now - hit[1] < _TTL:
        return hit[2]
    ver = _version
    value = build()
    if ver == _version:          # don't cache if a write landed while building
        _store[key] = (ver, now, value)
    return value
