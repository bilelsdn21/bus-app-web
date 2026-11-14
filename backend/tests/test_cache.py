"""The result cache must never serve data older than the last write."""
from app import models
from app.core.cache import cached
from app.core.database import Base, SessionLocal, engine


def test_cache_hits_then_clears_on_write():
    Base.metadata.create_all(engine)
    calls = []

    def build():
        calls.append(1)
        return len(calls)

    assert cached("k", build) == 1
    assert cached("k", build) == 1                            # second call is a cache hit
    db = SessionLocal()
    db.add(models.AuditLog(username="t", method="t", detail="t"))
    db.commit()
    db.close()
    assert cached("k", build) == 2                            # a write invalidated it
