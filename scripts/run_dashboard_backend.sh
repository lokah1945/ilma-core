#!/bin/bash
# Run ILMA Dashboard Backend
cd "$(dirname "$0")/../dashboard/backend"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload