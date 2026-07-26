# Systemd Exit 209 Crash-Loop — Session Evidence 2026-06-23

## Session Trigger
Bos asked for full system report. Discovered 3 services in crash-loop:
- `ilma-command-center.service`
- `ilma-dashboard-backend.service`
- `ilma-dashboard-frontend.service`

## Diagnosis Walk

1. `systemctl --user status <svc>` → all showed `activating (auto-restart)`, exit code 209
2. Checked binary paths → all scripts existed (`ilma_command_center.py`, `app/main.py`, `vite`)
3. Python deps → all importable (uvicorn, fastapi, jose, passlib, bcrypt)
4. Node binary → `node_modules/.bin/vite` existed (found at `node_modules/vite/bin/vite.js`)
5. Log files → `run/command_center.log`, `run/dashboard_backend.log`, `run/dashboard_frontend.log` all: **NO SUCH FILE**
6. Log directory `/root/.hermes/profiles/ilma/run/` → **MISSING**

## Root Cause
systemd `StandardOutput=append:...` and `StandardError=append:...` require the target directory to exist. When the `run/` directory was absent (likely cleared by a reboot or manual cleanup), systemd could not open the log file for stdout/stderr redirection → process exits 209 → `Restart=always` → crash-loop.

## Fix Applied
```bash
mkdir -p /root/.hermes/profiles/ilma/run
systemctl --user restart ilma-command-center.service
systemctl --user restart ilma-dashboard-backend.service
systemctl --user restart ilma-dashboard-frontend.service
```

## Verification Results
| Service | Status | Health Check |
|---------|--------|-------------|
| ilma-command-center | active | HTTP 303 (login redirect) |
| ilma-dashboard-backend | active | HTTP 200 |
| ilma-dashboard-frontend | active | HTTP 200 via localhost |

## Vite Gotcha
Frontend Vite dev server binds to `localhost` only (not `0.0.0.0`). `curl http://127.0.0.1:3001/` returns exit code 7 (connection refused). Must use `curl http://localhost:3001/` instead.

## MongoDB Note (separate issue)
MongoDB is NOT on this VPS — it's on Yapsi server `172.16.103.253:27017` (requires auth). The `mongod` service being inactive on this host is by design, not an error.
