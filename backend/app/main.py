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

from .core.database import Base, engine
from .core.config import cors_origins
from . import models  # noqa: F401  (import so tables register before create_all)
from .controllers import (
    system, buses, destinations, config, contracts, fuel, calendar, excursions, days,
)

Base.metadata.create_all(engine)

app = FastAPI(title="Bus Manager API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",  # production + Vercel previews
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    system.router, buses.router, destinations.router, config.router,
    contracts.router, fuel.router, calendar.router, excursions.router, days.router,
):
    app.include_router(router)
