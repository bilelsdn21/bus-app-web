# Bus Manager — Web App (local-first)

Replaces the Excel + VBA workflow with a real web app.
**React + TailwindCSS** frontend · **FastAPI (Python)** backend · **SQLite** locally (→ Supabase Postgres in production).

The current Excel/Streamlit workflow is untouched — this lives entirely in `bus-app-web/`.

## Why this fixes the old pain
- No VBA → no compile errors, no macro security, no Mark-of-the-Web.
- Bookings reference a bus by **ID (foreign key)** → the name-mismatch bug that lost 1,440 TND **cannot happen**.
- One calc module (`backend/app/services/calc.py`) = single source of truth for net, %, colors, summary.

## Backend architecture (MVC)
The FastAPI backend (`backend/app/`) is organized as Model–View–Controller:

| Layer | Location | Responsibility |
|---|---|---|
| **Model** | `models.py` | SQLAlchemy ORM tables (the data). |
| **View** | `schemas.py` | Pydantic request/response schemas (serialization). |
| **Controller** | `controllers/` | One `APIRouter` per resource (buses, contracts, excursions, fuel, calendar, days, destinations, config, system). HTTP only — thin. |
| **Services** | `services/` | Domain logic the controllers call: `calc.py` (pure math), `calendar.py` (grid builder), `contracts.py` (result), `excursions.py` (validation/pricing), `lookups.py`, `audit.py`. |
| **Core** | `core/` | Infrastructure: `database.py` (engine/session), `security.py` (auth/tokens/roles), `config.py` (CORS, constants). |

`main.py` is a thin app factory: it creates the `FastAPI` app, sets CORS, and includes the routers. Start command is unchanged: `uvicorn app.main:app`.

## Run locally

### 1. Backend (terminal 1)
```bash
cd bus-app-web/backend
python -m venv .venv
.venv\Scripts\activate            # Windows (use: source .venv/bin/activate on mac/linux)
pip install -r requirements.txt
python -m app.seed                # imports data/*.json + destinations from ../../final.xlsm
uvicorn app.main:app --reload --port 8000
```
API at http://127.0.0.1:8000 — interactive docs at http://127.0.0.1:8000/docs

### 2. Frontend (terminal 2)
```bash
cd bus-app-web/frontend
npm install
npm run dev
```
App at http://localhost:5173

## Two views
- **📊 Calendrier** (desktop, "top UX"): colored calendar grid, Net Mois / %, region summary cards.
- **✏️ Saisie** (phone): pick bus → date → add activities (category, destination, **Heure Début/Fin**) → Enregistrer. Opens by default on small screens.

## Color rule (same as Excel)
Period by **start time** (cutoffs editable in `config`: 13h / 22h):
🌅 yellow = matin · 🌆 orange = soir · 🌙 purple = nuit · 🟢 green = trips span **different** periods · 🔴 red = indisponible.

## Data model (`backend/app/models.py`)
`buses` (name, plate, type, region, loyer, distance) · `destinations` (category, name, prices) · `bookings` (date, bus_id FK, type, times, total…) · `config` (cutoffs).

## Going live (later, free tier)
1. Create a free **Supabase** project → copy the Postgres connection string.
2. Set `DATABASE_URL=postgresql://...` in `backend/.env` → `python -m app.seed` → deploy backend (Render/Railway free).
3. Deploy frontend on **Vercel** free; set `VITE_API_URL` to the backend URL.
4. Add Supabase Auth for the 2 users.

## Contracts & fuel (precise monthly result)
Each bus has **contracts** with arbitrary start/end dates (not the calendar month) and a loyer.
**Fuel** is tracked per bus per **calendar month** — an `estimated` value, replaced by `actual` on the 1st of next month.

**Result for a contract** = revenue (trips in the window) − loyer − fuel, where fuel from each
calendar month is **prorated by days of overlap** (uses `actual` if present, else `estimated`).
The result is flagged **estimé** until every month it touches is actualized.

Worked example (verified): contract 15 May→14 June, loyer 5000, May fuel actual 2000, June est 1200,
revenue 12270 → fuel = 17/31×2000 + 14/30×1200 = 1656.77 → **Net 5613.23 (estimé)**.

Endpoints: `GET/POST/PUT/DELETE /api/contracts`, `GET/PUT /api/fuel`. UI: **📄 Contrats** tab.

## Login
Two users (override with env `BUS_USERS="user1:pass1,user2:pass2"`). Defaults:
- `admin` / `btt2026`
- `terrain` / `terrain2026`

## Tabs
- **📊 Calendrier** — colored grid; **Net Mois is contract-aware** (uses the contract overlapping the month, prorated fuel, "est" badge). **Click any day cell** → panel with that vehicle's excursions (destination, time, client, pax, price) + day total — like Excel's Fiche Jour.
- **📄 Contrats** — contracts CRUD + monthly fuel grid (estimé/réel) + prorated breakdown.
- **✏️ Saisie** — mobile entry (bus → date → activities with Heure Début/Fin → save).
- **⚙️ Params** — manage **véhicules**, **destinations + prix**, and **périodes** (cutoffs). The user edits all params in-app.

## Status — all built & verified
- [x] Models (buses, destinations, bookings, contracts, fuel_months, config), calc, seed from **final.xlsm** params
- [x] Contract result with **day-prorated fuel** — math verified against worked example
- [x] **Calendar Net contract-aware** + estimé badge + region summary from contracts
- [x] **Day-detail panel** (click a dot → excursions)
- [x] **Params management** (buses, destinations, cutoffs — full CRUD)
- [x] **Login** (2 users)
- [x] Full API smoke test passing
- [ ] Deploy (Supabase Postgres + Render backend + Vercel frontend) — needs your accounts

## Deploy later (free tier)
1. Supabase project → set `DATABASE_URL` in `backend/.env` → `python -m app.seed`.
2. Backend on Render/Railway (free); set `BUS_USERS`, `BUS_SECRET`, `DATABASE_URL`, and CORS to the Vercel URL.
3. Frontend on Vercel (free); set `VITE_API_URL` to the backend URL.
