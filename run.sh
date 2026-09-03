#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  ./setup.sh
fi

source .venv/bin/activate
( sleep 2; python -m webbrowser -t http://127.0.0.1:8765 >/dev/null 2>&1 || true ) &

echo "[Focuslyra] Starting at http://127.0.0.1:8765"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
