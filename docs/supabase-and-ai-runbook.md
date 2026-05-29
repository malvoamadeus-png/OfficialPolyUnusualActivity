# Supabase And AI Runbook

OdailySeer uses Supabase REST from the backend and a public anon key from the
frontend.

## Environment

Required backend variables:

```env
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
SUPABASE_ANON_KEY=...
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
```

Required frontend variables:

```env
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
MARKET_API_URL=...
```

## Migrations

SQL files live in `supabase/migrations/`.

If a Postgres DSN is available, run migrations with a Postgres client. If only
Supabase REST keys are available, use REST for read/write verification and apply
SQL in the Supabase dashboard.

## Read-Only Table Check

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

## Pipeline Commands

```bash
cd backend
python -m src.main anomaly
python -m src.main new-markets --once
python -m src.main late-markets --once
python -m src.main whale --once
python -m src.main whale-trades
python -m src.main scheduler --loop
```

## AI Check

```bash
python - <<'PY'
import os
import requests
from pathlib import Path

for raw in Path(".env").read_text(encoding="utf-8").splitlines():
    text = raw.strip()
    if not text or text.startswith("#") or "=" not in text:
        continue
    key, value = text.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip().strip("'\""))

base = os.environ["OPENAI_BASE_URL"].rstrip("/")
key = os.environ["OPENAI_API_KEY"]
r = requests.get(base + "/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
print("status", r.status_code)
PY
```
