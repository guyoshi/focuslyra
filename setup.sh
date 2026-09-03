#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "[Focuslyra] Creating local Python environment..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[Focuslyra] Created .env from safe defaults."
fi

mkdir -p media/recordings sources indexes

echo
echo "[Focuslyra] Setup complete."
echo "Paid AI remains OFF unless you explicitly change ALLOW_PAID_AI in .env."
