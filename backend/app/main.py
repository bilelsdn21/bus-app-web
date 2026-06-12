"""
FastAPI backend for the bus management web app — MVC layout.

  models.py      -> Model        (SQLAlchemy ORM, the data)
  schemas.py     -> View         (Pydantic request/response serialization)
  controllers/   -> Controller   (one APIRouter per resource — the HTTP layer)
  services/      -> domain logic the controllers call (calc, calendar, …)
  core/          -> infrastructure (database, security/auth, config)

Run:  uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .core.database import Base, engine
from .core.config import cors_origins
from . import models  # noqa: F401  (import so tables register before create_all)
from .controllers import (
    system, buses, destinations, config, contracts, fuel, calendar, excursions, days, push,
)

Base.metadata.create_all(engine)

# Security: on Postgres (Supabase) keep Row-Level Security ENABLED on every table
# so the auto-exposed public REST API can't read/write the data. The backend
# connects as the table owner and bypasses RLS, so this doesn't affect us. Runs
# every startup (idempotent) so a re-seed or a new table can't silently re-expose.
if engine.dialect.name == "postgresql":
    try:
        with engine.begin() as _conn:
            for _t in Base.metadata.tables:
                _conn.execute(text(f'ALTER TABLE public."{_t}" ENABLE ROW LEVEL SECURITY'))
    except Exception:
        pass  # never block startup on this

app = FastAPI(title="Bus Manager API")


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return resp


# Auth is via Bearer token (not cookies), so credentials aren't needed -> keep
# them off, which makes the allowed-origins surface much lower-risk.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",  # production + Vercel previews
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    system.router, buses.router, destinations.router, config.router,
    contracts.router, fuel.router, calendar.router, excursions.router, days.router,
    push.router,
):
    app.include_router(router)
