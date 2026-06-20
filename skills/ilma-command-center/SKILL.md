---
name: ilma-command-center
description: "ILMA v5.0 Command Center Dashboard — Lightweight secure web dashboard for ILMA heartbeat monitoring. Runs on port 18790. Features: Real-time Genesis Daemon worker pool, Foundry CI/CD metrics, Provider Gateway stats, JWT auth with hardcoded admin/admin123, non-blocking metrics reading. SSS-OMEGA Tier."
triggers:
  - command-center
  - dashboard
  - monitoring
  - fastapi
  - web-dashboard
  - port-18790
  - hermes-webui
  - hermes-tui
  - api-server
  - open-webui
version: 5.1.0
tier: SSS-OMEGA
last_updated: 2026-06-03
---

# ILMA v5.0 — COMMAND CENTER DASHBOARD

## Overview

**Tier:** SSS-OMEGA
**Version:** 5.1.0
**Status:** NOT CURRENTLY RUNNING — verify with `ss -tlnp | grep 18790` before use

**IMPORTANT:** This skill documents multiple Hermes/ILMA web interfaces. The Command Center Dashboard itself (port 18790) is NOT currently running. See "All Hermes Web Interfaces" section below for actual status.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMMAND CENTER — SECURE DASHBOARD                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Browser → https://vps:18790 → FastAPI → Metrics Collector                  │
│                                              │                              │
│                                              ├── Genesis State (JSON)        │
│                                              ├── Foundry State (JSON)       │
│                                              ├── Gateway Metrics (JSON)     │
│                                              └── System Stats (psutil)       │
│                                                                              │
│  Auth Flow:                                                                  │
│  1. /login → POST /api/login (username=admin, password=admin123)           │
│  2. Server creates JWT token (HS256, 30min expiry)                          │
│  3. Browser stores token in HttpOnly cookie                                 │
│  4. All /api/* endpoints require valid JWT                                  │
│                                                                              │
│  Metrics Reading (Non-Blocking):                                            │
│  - Genesis Daemon writes state to: memory/genesis_daemon_state.json          │
│  - Foundry writes state to: memory/foundry_state.json                        │
│  - Gateway writes metrics to: run/gateway_metrics.json                       │
│  - Command Center reads these files (read-only, no SQLite lock)             │
│  - Uses ThreadPoolExecutor for heavy I/O                                     │
│  - Cache with 5s TTL to prevent hammering disk                               │
│                                                                              │
│  Dashboard Sections:                                                         │
│  1. GENESIS DAEMON — worker pool, tasks completed, success rate            │
│  2. FOUNDRY CI/CD — active deployments, promotions, rollbacks              │
│  3. PROVIDER GATEWAY — request counts, latency, error rate                 │
│  4. SYSTEM — CPU, memory, disk usage                                        │
│  5. WORKER POOL — 50-worker grid visualization                             │
│  6. ACTIVE DEPLOYMENTS — shadow deployment progress                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Usage

```bash
# Start dashboard
python3 /root/.hermes/profiles/ilma/scripts/ilma_command_center.py

# Access: http://localhost:18790
# Login: admin / admin123
---

## All Hermes Web Interfaces — Status Check

Use this section when user asks about "Hermes webui", "web interface", "dashboard", "TUI", or "API server".

```bash
# Quick status check — all Hermes web interfaces
ss -tlnp | grep -E "3000|8642|18790|5173|8000"
ps aux | grep -E "hermes|api_server|command_center|vite" | grep -v grep
```

### 1. Hermes TUI (Terminal UI)
| Item | Detail |
|------|--------|
| Lokasi | `/root/.hermes/hermes-agent/ui-tui/` |
| Tech | React + Ink |
| Command | `hermes --tui` |
| Status | Source code tersedia — perlu запустить manually |
| Note | Opens in terminal, not a web interface |

### 2. Hermes API Server (OpenAI-compatible)
| Item | Detail |
|------|--------|
| Port | **8642** (default, configurable via API_SERVER_PORT env) |
| Purpose | OpenAI-compatible API — connects to Open WebUI, LibreChat, etc. |
| Endpoint | `POST /v1/chat/completions`, `GET /v1/models`, `GET /health`, `GET /v1/capabilities` |
| Config | `gateway/platforms/api_server.py` in hermes-agent repo |
| Status | **Not running** — no process on port 8642 |
| Auth | API_SERVER_KEY via config.yaml |
| Enable | Start via gateway: `hermes gateway run` (loads api_server platform) |

### 3. ILMA Command Center Dashboard (FastAPI)
| Item | Detail |
|------|--------|
| Port | **18790** |
| Backend | FastAPI |
| Tech Stack | `/root/.hermes/profiles/ilma/dashboard/` (FastAPI backend + React/Vite frontend) |
| Auth | admin/admin123 (JWT, 30min expiry) |
| Status | **Not running** — no process on port 18790 |
| Start | `python3 /root/.hermes/profiles/ilma/scripts/ilma_command_center.py` |
| Files | - Backend: `/root/.hermes/profiles/ilma/dashboard/backend/app/main.py` (FastAPI, 10 routers) |
| | - Frontend: `/root/.hermes/profiles/ilma/dashboard/frontend/` (Vite + React) |
| | - Script: `/root/.hermes/profiles/ilma/scripts/ilma_command_center.py` |

### 4. WhatsApp Bridge (Active ✅)
| Item | Detail |
|------|--------|
| Port | **3000** ✅ ACTIVE |
| Process | `node /root/.hermes/profiles/ilma/lsp/bin/... --port 3000 --mode bot` |
| Status |Berjalan |

### 5. ILMA Web Observability Dashboard (alternative)
| Item | Detail |
|------|--------|
| Port | Not started (separate from Command Center) |
| Backend | FastAPI + SQLite |
| Path | `/root/.hermes/profiles/ilma/dashboard/backend/` |
| Tables | providers, models, usage, benchmarks, specializations, routing, workflows, evidence, capabilities |
| Note | Different from Command Center — more data-heavy, less real-time |

## Quick Activation Commands

```bash
# Activate Hermes API Server (for Open WebUI etc.)
# Edit config.yaml: add platforms: { api_server: { enabled: true } } under the appropriate section
# Or: hermes gateway run --platforms api_server

# Activate ILMA Command Center (port 18790)
python3 /root/.hermes/profiles/ilma/scripts/ilma_command_center.py &

# Activate ILMA Web Dashboard (separate backend)
cd /root/.hermes/profiles/ilma/dashboard/backend && uvicorn app.main:create_app &
```

---

## State File Paths

| Component | File Path | Written By | Read By |
|-----------|-----------|------------|---------|
| Genesis State | `memory/genesis_daemon_state.json` | Genesis Daemon | Command Center |
| Foundry State | `memory/foundry_state.json` | Foundry | Command Center |
| Gateway Metrics | `run/gateway_metrics.json` | Provider Gateway | Command Center |

## Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| GET / | Yes | Main dashboard HTML |
| GET /login | No | Login page |
| POST /api/login | No | Authenticate (form: username, password) |
| POST /api/logout | Yes | Logout and invalidate token |
| GET /api/metrics | Yes | JSON metrics (auto-refreshes) |
| GET /api/health | No | Health check |

## Files

- /root/.hermes/profiles/ilma/scripts/ilma_command_center.py (1,149 lines)

---

**ILMA v5.1 — THE EYES OF THE SYSTEM**