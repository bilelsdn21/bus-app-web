# Deploy (free tier) — Supabase + Render + Vercel

Do these in order. You only do the account clicks; I'll do the local commands with you.

## 1. Database — Supabase (free Postgres)
1. https://supabase.com → sign in with GitHub → **New project**.
2. Name it, pick a region near Tunisia (e.g. **West EU / Frankfurt**), set a DB password (save it).
3. Wait ~2 min for it to provision.
4. **Settings → Database → Connection string → URI**. Copy it. It looks like:
   `postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres`
5. Give me that URI (with the password filled in). We seed it locally:
   ```
   cd bus-app-web/backend
   .venv\Scripts\activate
   set DATABASE_URL=postgresql://...   (Windows: use `set`)
   python -m app.seed
   ```
   → pushes all 23 buses, 944 bookings, 120 destinations, contracts + fuel into Supabase.

## 2. Code on GitHub
1. https://github.com/new → create an empty repo, e.g. `bus-app-web` (no README).
2. I'll run:
   ```
   cd bus-app-web
   git remote add origin https://github.com/YOURNAME/bus-app-web.git
   git branch -M main
   git push -u origin main
   ```

## 3. Backend — Render (free)
1. https://render.com → sign in with GitHub → **New + → Blueprint** → pick the `bus-app-web` repo (it reads `render.yaml`).
2. Set env vars when prompted:
   - `DATABASE_URL` = the Supabase URI
   - `BUS_USERS` = `admin:YOURPASS,terrain:YOURPASS2`
   - `CORS_ORIGINS` = (leave for now; we set it after Vercel)
   - `BUS_SECRET` = auto-generated
3. Deploy → you get a URL like `https://bus-app-backend.onrender.com`. Test `…/api/health` → `{"ok":true}`.

## 4. Frontend — Vercel (free)
1. https://vercel.com → sign in with GitHub → **Add New → Project** → import `bus-app-web`.
2. **Root Directory** = `frontend`. Framework = Vite (auto).
3. Env var: `VITE_API_URL` = your Render backend URL.
4. Deploy → you get `https://bus-app.vercel.app`.

## 5. Connect CORS
Back in Render → env var `CORS_ORIGINS` = your Vercel URL → save (redeploys). Done.

## Notes
- Render free sleeps after 15 min idle; first hit wakes it (~30 s). Fine for 2 users; upgrade later.
- If Postgres connection fails, append `?sslmode=require` to `DATABASE_URL`.
- Re-seed anytime from updated `final.xlsm` by running step 1's seed again (it resets the DB).
