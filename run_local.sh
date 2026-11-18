#!/usr/bin/env bash
# One-command local run (Linux/macOS). Usage: ./run_local.sh
set -e
cd "$(dirname "$0")"
[ -d backend/.venv ] || python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -q -r requirements-train.txt
if [ ! -f backend/models/best_model.joblib ]; then
  echo ">> First run: training the model on real Open-Meteo data (10-25 min)..."
  python tools/run_local_training.py
fi
(cd frontend && [ -d node_modules ] || npm install)
echo ">> Backend  http://localhost:8000/docs   Frontend http://localhost:5173"
(cd backend && uvicorn app.main:app --port 8000) &
BACK=$!
trap "kill $BACK" EXIT
cd frontend && npm run dev -- --port 5173
