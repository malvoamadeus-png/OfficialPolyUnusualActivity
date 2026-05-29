# OdailySeer

OdailySeer monitors Polymarket probability moves, new markets, late markets,
large holder alerts, and large trade activity.

## Structure

```text
backend/    Python pipelines, scheduler, and market analyzer API
frontend/   Next.js app deployed by Vercel
supabase/   SQL migrations for the Supabase project
data/       Runtime data, logs, exports, and local state
docs/       Operations and project notes
```

## Common Commands

```bash
cd backend
python -m src.main scheduler --loop
python -m src.main late-markets --once
python -m src.main market-api
```

```bash
cd frontend
npm install
npm run dev
```

Vercel should use `frontend` as the project Root Directory.
