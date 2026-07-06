#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

echo "==> Email Agent install (no Docker)"

if ! command -v python3 >/dev/null; then
  echo "python3 is required"
  exit 1
fi

PYTHON=${PYTHON:-python3}
$PYTHON -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p data data/tokens config

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — edit Google OAuth and sheet settings before running."
fi

if ! command -v ollama >/dev/null; then
  echo ""
  echo "Ollama not found. Install from https://ollama.com/download"
  echo "Then run: ollama pull qwen2.5:7b-instruct"
else
  ollama pull qwen2.5:7b-instruct || true
fi

echo ""
echo "Install complete."
echo "Next:"
echo "  1. Edit .env (Google OAuth, PRICING_SHEET_ID)"
echo "  2. source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo "  3. Open http://YOUR_VPS:8000/dashboard and connect Gmail"
