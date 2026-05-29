# OdailySeer Frontend And Backend Operations

## Frontend

The public UI lives in `frontend/` and deploys from GitHub to Vercel.

Required Vercel setting:

```text
Root Directory: frontend
```

Required environment variables:

```env
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
MARKET_API_URL=http://<server-host>:8917
```

Local verification:

```bash
cd frontend
npm install
npm run build
```

## Backend

The server runtime lives in `backend/`.

Install locally:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

Common commands:

```bash
python -m src.main scheduler --loop
python -m src.main run-once
python -m src.main anomaly
python -m src.main new-markets --once
python -m src.main late-markets --once
python -m src.main whale --once
python -m src.main whale-trades
python -m src.main market-api
```

## Server Deployment

Deploy into `/opt/OdailySeer` and keep old `/opt/seer` as rollback.

```bash
cd /opt/OdailySeer/backend
sudo bash systemd/install_systemd.sh
```

After restart, verify both service health and business output:

```bash
systemctl status odailyseer-pipeline.service --no-pager -l
journalctl -u odailyseer-pipeline.service -n 120 --no-pager
tail -n 80 /opt/OdailySeer/data/runtime/logs/late_markets.log
systemctl status odailyseer-market-api.service --no-pager -l
```

## Supabase

Migrations live in `supabase/migrations/`.

Read-only table check:

```bash
cd backend
python - <<'PY'
from packages.common.supabase_client import SupabaseClient

sb = SupabaseClient()
for table in [
    "probability_changes",
    "new_markets",
    "late_markets",
    "whale_alerts",
    "whale_trades",
    "market_analysis",
]:
    rows = sb.client.table(table).select("*").limit(1).execute().data or []
    print(table, "ok", len(rows))
PY
```
