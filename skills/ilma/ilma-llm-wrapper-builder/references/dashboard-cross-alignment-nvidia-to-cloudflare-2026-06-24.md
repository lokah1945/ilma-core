# Dashboard Cross-Alignment: NVIDIA → Cloudflare (2026-06-24)

## Session Evidence

Bos: "perbaiki dashboard wrapper-cloudflare agar sama persis dengan tampilan wrapper-nvidia"

## Before

Cloudflare `dashboard.html`: 67 lines, 5,204 chars — minimalist card grid with manual refresh button.

Nvidia `dashboard.html`: 1,382 lines, 62,685 chars — full-featured 6-tab SPA (Overview, Tokens, Models, Keys, Activity, Rate Limits) with dark/light/system theme, auto-refresh, model drill-down charts, key cards with RPM gauge, sortable model table, rate limit event log.

## Missing Endpoints Added to cloudflare/main.py

```python
@app.get("/metrics/tokens")                     # L764 — token breakdown
@app.get("/metrics/models")                      # L771 — per-model stats (alias of /metrics/per-model)
@app.get("/metrics/models/timeseries")            # L777 — hourly trend per model
@app.get("/metrics/keys")                         # L782 — per-key stats (alias of /metrics/per-key)
@app.get("/metrics/activity")                     # L795 — recent request log
@app.get("/metrics/rate-limits")                   # L800 — rate limit events + live blocks (alias of /metrics/rate-limit-events)
@app.get("/metrics/chart/hourly")                  # L813 — hourly chart (alias of /metrics/hourly)
```

## Endpoint Path Mapping (NVIDIA ↔ Cloudflare)

| NVIDIA Dashboard JS calls | Cloudflare existing path | Resolution |
|---------------------------|--------------------------|------------|
| `GET /metrics?window=` | same `/metrics` | compatible |
| `GET /metrics/tokens?window=` | ❌ missing | **added** L764 |
| `GET /metrics/models?window=` | `/metrics/per-model` | **added alias** L771 |
| `GET /metrics/models/timeseries?model=&hours=` | ❌ missing | **added** L777 |
| `GET /metrics/keys?window=` | `/metrics/per-key` | **added alias** L782 |
| `GET /metrics/activity?limit=` | ❌ missing | **added** L795 |
| `GET /metrics/rate-limits?limit=&window=` | `/metrics/rate-limit-events` | **added alias** L800 |
| `GET /metrics/chart/hourly?hours=` | `/metrics/hourly` | **added alias** L813 |
| `GET /metrics/chart/daily?days=` | `/metrics/daily` | **added alias** L817 |
| `GET /health` | `/health` | compatible (`**pool.summary()` returns keys) |
| `GET /v1/models` | `/v1/models` | compatible |
| `POST /metrics/reset` | `/metrics/reset` | compatible |

## Branding Substitutions Applied

| String | NVIDIA | Cloudflare |
|--------|--------|------------|
| Title | `wrapper-nvidia · Dashboard` | `wrapper-cloudflare · Dashboard` |
| Icon | `⚡` | `☁️` |
| Logo text | `wrapper-nvidia` | `wrapper-cloudflare` |
| Subtitle | `NVIDIA NIM Rate-Limit Proxy · Dashboard` | `Cloudflare Workers AI Rate-Limit Proxy · Dashboard` |
| Catalog | `from NVIDIA NIM catalog` | `from Cloudflare catalog` |
| Model label | `NVIDIA NIM models ready` | `Cloudflare models ready` |
| Theme key | `wn-theme` | `wc-theme` |

## Verification Results

All 7 new endpoints returned HTTP 200 after restart:
- `/metrics/tokens?window=24h` → 200 (data: prompt=31, completion=480, cached=0, total=511)
- `/metrics/models?window=24h` → 200
- `/metrics/keys?window=24h` → 200
- `/metrics/activity?limit=10` → 200 (rows: 3)
- `/metrics/chart/hourly?hours=24` → 200
- `/metrics/rate-limits?limit=10` → 200
- `/dashboard` → 200

Diff verification: exactly 8 differences found, all branding-only. No structural/JS/CSS differences.
Dashboard line count: 67 → 1,383 (identical to nvidia).

## Service Restart

```bash
systemctl restart wrapper-cloudflare.service  # (system-level service, NOT --user)
```
