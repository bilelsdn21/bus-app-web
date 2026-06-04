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

# SQLite needs this flag for multi-threaded FastAPI; Postgres ignores it.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
