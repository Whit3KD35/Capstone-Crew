# Capstone Crew Deployment Guide

This repo is a React (Vite) frontend + FastAPI backend. Recommended production split:

- Frontend: Vercel
- Backend API: Render (or Railway/Fly)
- Database: Neon Postgres

## 1) One-time prep in this repo

1. Backend env template: `backend/.env.example`
2. Frontend env template: `frontend/.env.example`
3. Production backend deps: `backend/requirements-prod.txt`
4. PWA/mobile files:
 - `frontend/public/manifest.webmanifest`
 - `frontend/public/sw.js`
 - `frontend/public/icons/*`
5. QR generator script:
 - `scripts/generate_qr.py`

## 2) Deploy backend (Render)

Create a new **Web Service** from this repo with:

- Root directory: `backend`
- Build command: `pip install -r requirements-prod.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set environment variables in Render:

- `DATABASE_URL` = your Neon connection string
- `FERNET_KEY` = secure Fernet key
- `JWT_SECRET_KEY` = secure random string
- `CORS_ORIGINS` = comma-separated list of allowed frontend origins
  - Example: `http://localhost:5173,https://your-frontend.vercel.app`

Important:

- `backend/app/initialize.py` is now safe by default and does **not** drop tables.
- Only set `RESET_DB_ON_STARTUP=true` if you intentionally want to wipe/recreate tables.

## 3) Deploy frontend (Vercel)

Create a new Vercel project from this repo with:

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`

Set environment variable:

- `VITE_API_URL` = your deployed backend URL (example `https://capstone-backend.onrender.com`)

Then redeploy frontend after this variable is saved.

Notes:

- `frontend/vercel.json` includes SPA rewrites so routes like `/patient/simulations` work on refresh.
- PWA manifest + service worker are included for mobile web app behavior.

## 4) Final CORS wiring

After you know your final frontend URL, update backend env:

- `CORS_ORIGINS=http://localhost:5173,https://your-frontend.vercel.app`

Redeploy backend so CORS changes apply.

## 5) Generate QR code for your deployed app URL

From repo root:

```bash
python scripts/generate_qr.py --url "https://your-frontend.vercel.app" --output "frontend/public/deployment-qr.png"
```

You can also place output anywhere:

```bash
python scripts/generate_qr.py --url "https://your-frontend.vercel.app" --output "deployment-qr.png"
```

That QR opens the same URL on phone or desktop.

## 6) Mobile web app check

1. Open deployed frontend URL on phone.
2. Confirm login and API calls work.
3. In browser menu, use **Add to Home Screen** (or install prompt on compatible browsers).
4. Verify basic navigation works from home-screen launch.

## 7) Local sanity commands

Backend (from `backend`):

```bash
pip install -r requirements-prod.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (from `frontend`):

```bash
npm install
npm run build
npm run dev
```

## 8) Security note

If a `.env` with real secrets was ever shared/committed, rotate credentials immediately:

- `DATABASE_URL` password/token
- `FERNET_KEY`
- `JWT_SECRET_KEY`
