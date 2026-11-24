"""Test setup: every run uses a throw-away SQLite file, never the real database."""
import os
import sys
import tempfile

_DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = "sqlite:///" + _DB.replace("\\", "/")
os.environ.setdefault("BUS_USERS", "dev:dev:admin")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# The change register is exercised only by its own tests; every other suite runs without it.
from app.core import ledger as _ledger          # noqa: E402

_ledger.ENABLED = False
_ledger.SYNC_JOBS = True
