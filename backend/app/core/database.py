"""
Database layer. Local dev uses SQLite; production swaps to Supabase Postgres
by setting DATABASE_URL in the environment — no code change needed.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Local default = SQLite file next to the backend. Production sets DATABASE_URL
# to the Supabase Postgres connection string.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./bus_app.db")

# Name the driver explicitly (we ship psycopg2). Newer SQLAlchemy versions treat a bare
# "postgresql://" as psycopg v3, which is not installed -> startup crash.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgresql://"):]

# SQLite needs this flag for multi-threaded FastAPI; Postgres ignores it.
# Postgres: never wait forever for a connection (a stuck pooler used to hang requests until
# the host cut them off with a 502/504); fail fast with a readable error instead.
connect_args = ({"check_same_thread": False} if DATABASE_URL.startswith("sqlite")
                else {"connect_timeout": 10})

_pool = {} if DATABASE_URL.startswith("sqlite") else {
    "pool_size": 5, "max_overflow": 5,
    "pool_timeout": 15,       # wait at most 15 s for a free pooled connection
    "pool_recycle": 240,      # drop connections before the pooler/firewall silently kills them
}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True, **_pool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
