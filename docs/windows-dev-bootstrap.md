# Windows Dev Bootstrap

This document covers local Windows development after the monorepo migration.

## Python

Use Python `3.11` or `3.12` when possible.

Backend setup:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Build check:

```powershell
cd frontend
npm.cmd run build
```

## Environment

Backend reads `.env`, `backend/.env`, and `/etc/odailyseer/odailyseer.env`.

Frontend reads `frontend/.env.local`.

Required backend keys:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_ANON_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`

Required frontend keys:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `MARKET_API_URL`

## Backend Commands

Run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m src.main market-api
.\.venv\Scripts\python.exe -m src.main new-markets --once
.\.venv\Scripts\python.exe -m src.main late-markets --once
.\.venv\Scripts\python.exe -m src.main anomaly
.\.venv\Scripts\python.exe -m src.main scheduler --loop
```

## Self Check

```powershell
@'
import importlib.util
mods = ["requests", "playwright", "fastapi", "uvicorn"]
for name in mods:
    print(name, bool(importlib.util.find_spec(name)))
'@ | .\backend\.venv\Scripts\python.exe -
```
