#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-odailyseer}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
APP_ROOT="${APP_ROOT:-/opt/OdailySeer}"
BACKEND_DIR="$APP_ROOT/backend"
ENV_DIR="${ENV_DIR:-/etc/odailyseer}"
ENV_FILE="$ENV_DIR/odailyseer.env"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root."
  exit 1
fi

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /bin/bash "$APP_USER"
fi

mkdir -p "$APP_ROOT" "$ENV_DIR" "$APP_ROOT/data/runtime/logs" "$APP_ROOT/data/runtime/state"
chown -R "$APP_USER:$APP_GROUP" "$APP_ROOT"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$BACKEND_DIR/systemd/odailyseer.env.example" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Created $ENV_FILE from example. Fill in real secrets before starting services."
fi

python3 -m venv "$BACKEND_DIR/.venv"
"$BACKEND_DIR/.venv/bin/pip" install --upgrade pip
"$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
"$BACKEND_DIR/.venv/bin/python" -m playwright install chromium

cp "$BACKEND_DIR/systemd/odailyseer-pipeline.service" /etc/systemd/system/
cp "$BACKEND_DIR/systemd/odailyseer-market-api.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable odailyseer-pipeline.service odailyseer-market-api.service
systemctl restart odailyseer-pipeline.service odailyseer-market-api.service

systemctl --no-pager --full status odailyseer-pipeline.service || true
systemctl --no-pager --full status odailyseer-market-api.service || true
