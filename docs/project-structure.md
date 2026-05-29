# Project Structure

OdailySeer is now a single monorepo. The frontend is deployed by Vercel from
`frontend/`; the backend runs on the Linux server from `backend/`.

## Directories

- `backend/`
  Python pipelines, scheduler, Supabase REST client, and market analyzer API.
- `frontend/`
  Next.js public UI.
- `supabase/migrations/`
  SQL schema files for the shared Supabase project.
- `data/`
  Runtime logs, state files, raw data, processed data, and exports.
- `docs/`
  Project and operations runbooks.

## Frontend

Main pages:

- `/`: probability changes from `probability_changes`
- `/analyze`: market analyzer, proxied to the backend API
- `/new-markets`: selected new markets from `new_markets`
- `/late-markets`: late markets from `late_markets`
- `/whale-alerts`: large holder alerts from `whale_alerts`
- `/whale-trades`: large trades from `whale_trades`

Vercel must use:

```text
Root Directory: frontend
```

## Backend

Main entrypoint:

```bash
cd backend
python -m src.main <command>
```

Important commands:

- `scheduler --loop`: server scheduler
- `run-once`: one reduced test run
- `anomaly`: probability anomaly detection
- `new-markets --once`: Polymarket new market selection
- `late-markets --once`: high-volume markets ending soon
- `whale --once`: large holder monitor
- `whale-trades`: large trades fetcher
- `market-api`: FastAPI analyzer on port `8917`

Runtime logs and state are stored under `data/runtime/`, not inside code
directories.

## Deployment

The production server should use `/opt/OdailySeer` and keep old `/opt/seer` as a
rollback copy. Systemd templates live in `backend/systemd/`.
