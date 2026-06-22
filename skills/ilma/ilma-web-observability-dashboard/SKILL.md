---
name: ilma-web-observability-dashboard
description: "ILMA Web Observability Dashboard — FastAPI backend + React/TypeScript frontend for monitoring ILMA runtime state. 10 pages: Overview, Providers, Models, Benchmarks, Usage, Routing, Workflows, Evidence, Capabilities, System Health. Backend: port 8000. Frontend: port 3000. Tech: FastAPI + SQLModel + SQLite + Uvicorn + React + Vite + Tailwind CSS + Recharts."
triggers:
  - dashboard
  - observability
  - web-dashboard
  - monitoring
  - fastapi-backend
  - react-frontend
category: ilma
version: 1.0.0
tier: SSS
last_updated: 2026-05-13
---

# ILMA Web Observability Dashboard

## Overview

Full-stack web dashboard for monitoring ILMA runtime state. Built during Phase 56.

**Tier:** SSS | **Version:** 1.0.0 | **Status:** OPERATIONAL

## Stack

| Layer | Tech | Port |
|-------|------|------|
| Backend | FastAPI + SQLModel + SQLite + Uvicorn | 8000 |
| Frontend | React + TypeScript + Vite + Tailwind CSS + Recharts | 3001 (systemd) / 3000 (manual npm) |
| Data | 16 providers, 1,284 models, 4 benchmarks, 258 checkpoints | — |

## Quick Start

```bash
# 1. Backend
cd /root/.hermes/profiles/ilma/dashboard/backend
pip3 install fastapi uvicorn sqlmodel pydantic pydantic-settings httpx --break-system-packages -q
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. Frontend (separate terminal)
cd /root/.hermes/profiles/ilma/dashboard/frontend
npm install --legacy-peer-deps -q
npm run dev  # http://localhost:3000
```

## Pages

1. **Overview** — KPI cards + system summary
2. **Providers** — 16 AI providers (NVIDIA NIM, OpenAI, Google, DeepSeek, Anthropic, Qwen Bridge, Use.ai Bridge, Arena.ai Bridge, dll)
3. **Models** — 1,284 models, sortable table (cost, status, context, trust, tools, vision)
4. **Benchmarks** — benchmark scores per model
5. **Usage** — token usage summary
6. **Routing** — 9 sub-agent route chains (coding, creative, research, planning, dll)
7. **Workflows** — workflow definitions
8. **Evidence** — evidence ledger with status filter (VERIFIED/PASSED/FAILED/UNVERIFIED)
9. **Capabilities** — system capabilities registry
10. **System Health** — backend health + API overview data

## API Endpoints

| Endpoint | Status | Description |
|----------|--------|-------------|
| GET /api/health | ✅ 200 | Health check |
| GET /api/overview | ✅ 200 | System overview (providers, models, free/paid counts) |
| GET /api/providers | ✅ 200 | Provider list |
| GET /api/models | ✅ 200 | Model list |
| GET /api/benchmarks | ✅ 200 | Benchmark records |
| GET /api/usage/summary | ✅ 200 | Usage summary |
| GET /api/routing/subagents | ✅ 200 | Route chains |
| GET /api/workflows | ✅ 200 | Workflow definitions |
| GET /api/evidence | ✅ 200 | Evidence records |
| GET /api/capabilities | ✅ 200 | Capability registry |

## Frontend Redesign (2026-05-13)

The frontend was completely redesigned with a professional dark theme + glassmorphism aesthetic.

### Design System
- **Theme:** Dark professional (#0f1419 background, cyan/blue accents)
- **Effects:** Glassmorphism cards with backdrop-blur, subtle borders
- **Typography:** Tailwind CSS utility-first, clear hierarchy
- **Charts:** Recharts library for all data visualizations

### New Components (6)
- `Layout.tsx` — Sidebar navigation + collapsible header
- `StatCard.tsx` — Big number + icon + label + optional trend
- `DataTable.tsx` — Sortable columns, pagination, row hover, loading skeleton
- `Badge.tsx` — Status badges (success/warning/danger/info/purple/default)
- `ChartCard.tsx` — Chart wrapper with title
- `ActivityFeed.tsx` — Timeline of recent activity

### Pages (12 pages, 2,371 lines total)
| Page | Lines | Description |
|------|-------|-------------|
| OverviewPage | 544 | System health, KPI cards, activity feed, mini charts |
| ModelDetailPage | 385 | Full specs, context bar, benchmarks, usage chart |
| ModelsPage | 296 | Searchable/filterable table, pagination |
| RoutingPage | 267 | Routing decision logs with latency |
| BenchmarksPage | 262 | Score comparison charts (Bar, Radar) |
| ProvidersPage | 215 | Provider cards grid with stats |
| Others (6 pages) | 397 | Evidence, Capabilities, Usage, Workflows, Pipelines, Health |

### Build Artifacts
```
✓ 901 modules transformed
✓ dist/assets/index-*.css (21 KB, gzip 5 KB)
✓ dist/assets/index-*.js (697 KB, gzip 195 KB)
✓ Built in 8.07s
```

### Common TypeScript Fixes for React Components
## Subagent Delegation Pattern (HIGHLY EFFECTIVE)

For large dashboard tasks (>5 pages, >1000 lines), delegate to leaf subagents:

```
delegate_task(goal="Fix all TypeScript errors in pages...", toolsets=["terminal","file"])
```

**Why it works:** Leaf agents process in isolation (no conversation context overhead). 1M+ tokens processed in ~9 minutes for 12-page audit.

**Effective subagent workflow:**
1. One subagent per "layer" (backend fixes, frontend fixes, type fixes)
2. Each subagent handles independent files — no shared state conflicts
3. Parent aggregates results and runs final build verification
4. Subagent files may get modified by sibling — always re-read before patching

**Subagent task structure:**
- Specific goal with file paths and expected changes
- `toolsets=["terminal","file"]` for file system work
- `role="leaf"` to prevent infinite spawning

### Zero-Error-Tolerance Audit Checklist (12 Pages)

Every page must have ALL of:
1. **Loading state** — `useState(true)` → skeleton/spinner → `setLoading(false)`
2. **Error state** — `useState<string|null>(null)` → catch block → `setError('...')`
3. **Empty state** — `if (data.length === 0)` → "No data available"
4. **Type safety** — No `any`, use proper interfaces, cast dynamic values to union type
5. **Null coalescing** — `model.name ?? 'Unknown'` for all API-sourced properties
6. **API response handling** — `|| []` or `|| {}` fallback for all responses

```
// ✅ Required pattern for every page
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

useEffect(() => {
  const load = async () => {
    try {
      const data = await apiClient.getData().catch(() => null);
      if (!data) { setError('Failed to load'); setLoading(false); return; }
      setData(data);
    } catch (e) { setError('Failed to load'); }
    setLoading(false);
  };
  load();
}, []);
```

### Common TypeScript Fixes for React Components

When Badge component rejects `style={{ color: ... }}` prop:
```typescript
// ❌ BAD - style prop not in Badge interface
<Badge label="Active" variant="success" style={{ color: 'var(--accent-green)' }} />

// ✅ GOOD - use CSS class instead, or pass style to parent span
<Badge label="Active" variant="success" />
```

When Badge variant type doesn't match:
```typescript
// ❌ BAD - string not assignable to union type
variant={statusColors[c.status] || 'default'}

// ✅ GOOD - cast to union type
variant={(statusColors[c.status] || 'default') as 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'default'}
```

When duplicate React imports appear at end of file:
- Check for imports accidentally placed after the component function closing brace
- Remove duplicate `import { useEffect, useState } from 'react';`

### CSS @import Ordering (Tailwind)
```css
/* ✅ CORRECT - @import must precede @tailwind directives */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;
```

### Backend Error Response Pattern (FastAPI)
```python
# ❌ WRONG - tuple-style return causes JSON serialization issues
return {"error": "Not found"}, 404

# ✅ CORRECT - use HTTPException
from fastapi import HTTPException
raise HTTPException(status_code=404, detail="Provider not found")

# ✅ For safe tuple return (only for 200 OK paths):
return {"providers": [...]}  # Never return tuples
```

### Pitfalls
1. **Lucide icons with style props** — Some icon components don't accept `style`. Use `className` with text color utilities instead (`text-accent-green`).
2. **Badge variant type strictness** — Badge interface only accepts specific string literals. Always cast dynamic values.
3. **Duplicate imports** — Subagent-generated code sometimes places imports after the component function body. Always check end of file.
4. **Style prop removal** — When converting inline styles to Tailwind, remember that `style={{ paddingLeft: '40px' }}` becomes `pl-10` in className.
5. **Subagent file conflicts** — Siblings may modify same file. Always re-read before patching.
6. **Vite proxy setup** — Frontend proxies `/api` → `localhost:8000`. Both must run simultaneously.

## File Structure

```
dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app
│   │   ├── config.py        # Settings
│   │   ├── database.py      # SQLModel/SQLite
│   │   ├── models/__init__.py  # 16 DB tables
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   ├── overview.py
│   │   │   ├── providers.py
│   │   │   ├── models.py
│   │   │   ├── benchmarks.py
│   │   │   ├── usage.py
│   │   │   ├── routing.py
│   │   │   ├── workflows.py
│   │   │   ├── evidence.py
│   │   │   └── capabilities.py
│   │   └── services/
│   │       ├── provider_service.py
│   │       ├── model_service.py
│   │       ├── benchmark_service.py
│   │       ├── usage_service.py
│   │       └── ingestion_service.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # React Router, 12 pages
│   │   ├── main.tsx
│   │   ├── index.css        # Global styles, CSS variables, dark theme
│   │   ├── api/client.ts    # Fetch API client
│   │   ├── types/index.ts   # TypeScript types
│   │   ├── pages/           # 12 page components (Overview, Models, etc.)
│   │   └── components/      # Badge, DataTable, Layout, StatCard, ChartCard, ActivityFeed
│   ├── vite.config.ts
│   └── package.json
└── README.md
```

## Database Tables (16)

providers, models, benchmarks, usage_records, routing_chains, workflows, evidence_records, capabilities, refresh_jobs, token_usage, workflow_runs, subagent_metrics, provider_health, model_metadata, capability_evidence, audit_log

## Tips

- **Proxy:** Vite proxies `/api` → `localhost:8000`. Both must run on same host.
- **Seed data:** Backend auto-seeds providers + models from ilma_capability_registry on first startup.
- **Empty benchmarks/usage:** Normal — no historical data yet, table exists for future ingestion.
- **Screenshot:** `browser_navigate` + `browser_vision` → `send_message(target="telegram:Huda Choirul Anam")` to send to owner.
- **systemd port mismatch:** The systemd service `ilma-dashboard-frontend.service` runs on port **3001**, not 3000. Manual `npm run dev` defaults to 3000. Health check the systemd version at `http://localhost:3001/` (not 127.0.0.1 — Vite binds to `localhost` only by default).
- **systemd crash-loop:** If services show `activating (auto-restart)` with exit code 209, the log directory `run/` is missing. See `hermes-agent-recovery` skill for the fix pattern.
