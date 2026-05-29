# Agent Operations Runbook

This runbook is for Codex sessions working on OdailySeer.

## Rules

- Do not print `.env`, database URLs, API keys, tokens, cookies, or private keys.
- Print only whether sensitive variables are set.
- Do not use `git add .`.
- Do not run destructive Git commands unless the user explicitly asks.
- `systemctl active` is not enough; check journal logs and business output.

## GitHub

The official repository is:

```text
git@github.com:malvoamadeus-png/OfficialPolyUnusualActivity.git
```

The default branch is `master`.

Check status:

```bash
git status --short
git branch --show-current
git remote -v
```

Push from WSL with the GitHub key:

```bash
GIT_SSH_COMMAND='ssh -i ~/.ssh/id_rsa_A_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new' \
git push origin master
```

## Secret-Safe Env Check

```bash
python - <<'PY'
from pathlib import Path

keys = {}
for env_name in [".env", "frontend/.env.local", "backend/.env"]:
    path = Path(env_name)
    if not path.exists():
        continue
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = raw.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        keys[key.strip()] = bool(value.strip().strip("'\""))

for key in [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_ANON_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "MARKET_API_URL",
]:
    print(f"{key}=" + ("set" if keys.get(key) else "missing"))
PY
```

## Linux Deployment

Use MCP server `ssh-prod` in new Codex sessions. If it is not available, use the
fallback SSH command documented in `docs/CODEX_LINUX_ACCESS.md`.

Production path:

```text
/opt/OdailySeer
```

Keep `/opt/seer` for rollback until the new service has been verified.

Read-only preflight:

```bash
ssh root@47.76.243.147 '
cd /opt/OdailySeer &&
git rev-parse --short HEAD &&
git status --short &&
systemctl is-active odailyseer-pipeline.service || true &&
systemctl is-active odailyseer-market-api.service || true
'
```

Install or refresh systemd:

```bash
cd /opt/OdailySeer/backend
sudo bash systemd/install_systemd.sh
```

Verify:

```bash
systemctl status odailyseer-pipeline.service --no-pager -l
journalctl -u odailyseer-pipeline.service -n 120 --no-pager
tail -n 80 /opt/OdailySeer/data/runtime/logs/late_markets.log
systemctl status odailyseer-market-api.service --no-pager -l
journalctl -u odailyseer-market-api.service -n 80 --no-pager
```

## Frontend

Vercel must build from:

```text
Root Directory: frontend
```

Local verification:

```bash
cd frontend
npm run build
```
