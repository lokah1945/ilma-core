#!/bin/bash
# scripts/run_dashboard_backend.sh — Launch ILMA Dashboard Backend
set -e

cd /root/.hermes/profiles/ilma/dashboard/backend

# Install deps if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "[setup] Installing requirements..."
    pip install -q -r requirements.txt
fi

# Seed DB if needed
DB_PATH="/root/.hermes/profiles/ilma/data/ilma_dashboard.db"
if [ ! -f "$DB_PATH" ]; then
    echo "[setup] Seeding database..."
    python3 scripts/seed_dashboard_db.py
fi

echo "[start] Starting ILMA Dashboard Backend on http://127.0.0.1:8000"
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
