#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  ./setup.sh
fi

source .venv/bin/activate

# Honour FOCUSLYRA_HOST/FOCUSLYRA_PORT from .env instead of hardcoding
# 127.0.0.1:8765 everywhere, so a customised .env actually takes effect.
FOCUSLYRA_HOST="127.0.0.1"
FOCUSLYRA_PORT="8765"
if [ -f .env ]; then
  env_host="$(grep -m1 '^FOCUSLYRA_HOST=' .env | cut -d '=' -f2- || true)"
  env_port="$(grep -m1 '^FOCUSLYRA_PORT=' .env | cut -d '=' -f2- || true)"
  [ -n "${env_host:-}" ] && FOCUSLYRA_HOST="$env_host"
  [ -n "${env_port:-}" ] && FOCUSLYRA_PORT="$env_port"
fi

( sleep 2; python -m webbrowser -t "http://${FOCUSLYRA_HOST}:${FOCUSLYRA_PORT}" >/dev/null 2>&1 || true ) &

echo "[Focuslyra] Starting at http://${FOCUSLYRA_HOST}:${FOCUSLYRA_PORT}"
python -m uvicorn app.main:app --host "$FOCUSLYRA_HOST" --port "$FOCUSLYRA_PORT" --reload
