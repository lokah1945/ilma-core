---
name: ilma-frontend-patterns
description: "ILMA Frontend Patterns — React/TypeScript dashboard development: dark theme, glassmorphism, TypeScript strict, zero-error pages, subagent delegation, Recharts, Tailwind CSS, Vite. Trigger on: frontend, dashboard, react, typescript, ui, vite, recharts, tailwind, component, page, typescript error, react component, build error."
triggers:
  - frontend
  - dashboard
  - react
  - typescript
  - ui
  - vite
  - recharts
  - tailwind
  - component
  - page
  - typescript error
  - react component
  - build error
version: 2.0.0
tier: SSS
last_updated: 2026-05-13
---

# ILMA Frontend Patterns — SSS Tier

Production-tested patterns from building the ILMA Web Observability Dashboard (12 pages, React + TypeScript + Vite + Tailwind CSS + Recharts).

## Zero-Error Page Template

Every dashboard page MUST have this exact structure:

```typescript
import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';

export default function ExamplePage() {
  const [data, setData] = useState<ExampleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const result = await apiClient.getExamples().catch(() => null);
        if (!result) { setError('Failed to load'); setLoading(false); return; }
        setData(Array.isArray(result) ? result : []);
      } catch (e) { setError('Failed to load'); }
      setLoading(false);
    };
    load();
  }, []);

  if (loading) return <SkeletonPage />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (data.length === 0) return <EmptyState />;

  return (/* actual content */);
}
```

## Required States Per Page

| State | When | UI |
|-------|------|---|
| **Loading** | `loading === true` | Skeleton cards with pulse animation |
| **Error** | `error !== null` | Red border box + message + retry button |
| **Empty** | `data.length === 0` | Icon + "No data" message |
| **Content** | All above pass | Actual rendered page |

## Badge Component — Correct Usage

```typescript
// ❌ WRONG — style prop not in interface
<Badge label="Active" variant="success" style={{ color: 'var(--accent-green)' }} />

// ❌ WRONG — string not assignable to union type
variant={statusColors[c.status] || 'default'}

// ✅ CORRECT — cast to union type
variant={(statusColors[c.status] || 'default') as 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'default'}

// ✅ CORRECT — direct literal
<Badge label="Active" variant="success" />
```

## Icon Components — Correct Usage

```typescript
// ❌ WRONG — style prop rejected by Lucide icons
<SomeIcon style={{ color: 'var(--accent-green)' }} />

// ✅ CORRECT — use className with Tailwind text utilities
<SomeIcon className="w-5 h-5 text-accent-green" />
```

## CSS @import Order (Tailwind)

```css
/* ✅ CORRECT — @import MUST precede @tailwind directives */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;
```

## TypeScript Strict Patterns

```typescript
// Always use explicit types, never `any`
interface MyItem { id: number; name: string; }

// Null coalescing for all API-sourced properties
const displayName = item.display_name ?? item.canonical_model_id ?? 'Unknown';

// Array fallback
const items = Array.isArray(data) ? data : [];

// Union type cast for dynamic values
variant={(statusColors[c.status] || 'default') as BadgeVariant}
```

## Subagent Delegation Pattern (Large Tasks)

For dashboard tasks involving >5 pages or >1000 lines:

```
delegate_task(goal="Fix all TypeScript errors in pages...", toolsets=["terminal","file"])
```

- One subagent per layer (backend, frontend, types)
- Subagents process in isolation — no conversation context overhead
- 1M+ tokens in ~9 minutes for 12-page audit
- Siblings may modify same file — re-read before patching

## FastAPI Backend Patterns

```python
# ❌ WRONG — tuple return causes JSON serialization issues
return {"error": "Not found"}, 404

# ✅ CORRECT — use HTTPException
from fastapi import HTTPException
raise HTTPException(status_code=404, detail="Provider not found")

# ✅ Safe tuple return — only for 200 OK paths
return {"providers": [...]}  # Never return tuples
```

## Build Verification

```bash
cd /path/to/frontend && npm run build
# Must show: ✓ built in X.XXs — ZERO error TS
```

## Key Files Reference

```
dashboard/
├── frontend/
│   ├── src/
│   │   ├── pages/           # 12 page components
│   │   ├── components/      # Badge, DataTable, Layout, StatCard, ChartCard, ActivityFeed
│   │   ├── api/client.ts    # Fetch API client (axios, baseURL=/api, timeout=10000)
│   │   ├── types/index.ts   # TypeScript interfaces
│   │   └── index.css        # Global styles, CSS variables, dark theme
│   └── vite.config.ts       # Proxy: /api → localhost:8000
├── backend/
│   └── app/
│       ├── main.py          # FastAPI app (16 routers)
│       ├── models/__init__.py  # 16 DB tables (SQLModel)
│       └── routers/__init__.py # All API route handlers
```

## Dashboard Quick Start

```bash
# Backend
cd /root/.hermes/profiles/ilma/dashboard/backend
pip3 install fastapi uvicorn sqlmodel --break-system-packages -q
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd /root/.hermes/profiles/ilma/dashboard/frontend
npm install --legacy-peer-deps -q
npm run dev  # http://localhost:3000
```

## Pitfalls

1. **Lucide icons with style props** — Icon components don't accept `style`. Use `className="text-*"`.
2. **Badge variant type strictness** — Always cast dynamic values to union type.
3. **Duplicate imports** — Check end of file for imports after closing brace.
4. **Vite proxy** — Both servers must run; proxy maps `/api` → `localhost:8000`.
5. **Subagent file conflicts** — Re-read before patching after sibling writes.

## See Also

- [ilma-web-observability-dashboard](../ilma/ilma-web-observability-dashboard/SKILL.md) — Full dashboard skill with reference files
- [ilma-model-database-maintenance](../ilma/ilma-model-database-maintenance/SKILL.md) — Model DB patterns

---

**SSS Tier - Military Grade - ILMA System**