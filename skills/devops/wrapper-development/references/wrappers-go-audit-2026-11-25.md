# wrappers-go Audit (2026-11-25)

## Overview
Session audit of the Go rewrite project at `/root/project/wrappers-go`. User asked to check if the project and dashboard are running.

## Project Structure
```
/root/project/wrappers-go/
├── wrappers-go                    # Main binary (ELF 64-bit, 23MB, built 2026-11-25 21:10)
├── wrappers                       # Old binary (23MB, built 2026-11-25 20:20)
├── .env.example                   # Configuration template (203 lines, comprehensive)
├── test.env                       # Test config with BEARER_TOKEN/ADMIN_TOKEN
├── go.mod / go.sum                # Go module
├── cmd/wrappers/main.go           # Entry point (port 9900)
├── internal/
│   ├── gateway/                   # Gateway with routes for /dashboard
│   ├── config/                    # Config loading
│   ├── keypool/                   # Key pool management
│   ├── discovery/                 # Model/provider discovery
│   ├── providers/                 # Provider adapters (nvidia, nous, openrouter, coarena, frozen)
│   ├── registry/                  # Model registry
│   ├── compatibility/             # Protocol translation
│   ├── streaming/                 # SSE streaming
│   ├── storage/                   # SQLite response store
│   └── telemetry/                 # Metrics (Prometheus)
├── dashboard/                     # EMPTY directory (no assets)
├── data/                          # SQLite DBs
├── docs/                          # Documentation
├── productions/                   # Production artifacts
├── scripts/                       # Build scripts
├── tests/                         # Test files
├── report/                        # Audit reports (PREFLIGHT, FEATURE_PARITY, E2E_AUDIT, IMPLEMENTATION_SUMMARY)
├── master_capability_map.json     # Capability mapping
├── audit_report.json              # Audit data
└── discovery.test                 # Test binary
```

## Dashboard Status: NOT RUNNING

### Binary Status
- ✅ Binary exists and runs
- ✅ Config validation passes (`./wrappers-go --dry-run --config test.env`)
- ✅ Server starts on port 9900
- ✅ Routes registered: `GET /dashboard`, `GET /dashboard/*path`

### Handler Implementation (gateway.go:3882-3888)
```go
func (g *Gateway) handleDashboard(c *gin.Context) {
    c.HTML(http.StatusOK, "dashboard.html", nil)  // Template NOT loaded
}

func (g *Gateway) handleDashboardAssets(c *gin.Context) {
    c.Status(http.StatusNotFound)  // Hardcoded 404
}
```

### Root Cause
1. **No template loading** — `gin.SetMode(gin.ReleaseMode)` + `gin.New()` but no `LoadHTMLGlob()` or `SetHTMLTemplate()`
2. **No embedded assets** — No `go:embed` for dashboard HTML/JS/CSS
3. **Dashboard folder empty** — `/root/project/wrappers-go/dashboard/` has 0 files
4. **No static file serving** — `handleDashboardAssets` returns 404 hardcoded

### Test Result
```bash
curl -v http://127.0.0.1:9900/dashboard
# HTTP/1.1 500 Internal Server Error (template not found)
```

### Audit Report References
- `report/COMPREHENSIVE_E2E_AUDIT.md:283` — "Unified dashboard at `/dashboard` | ❌ Not started | MISSING"
- `report/COMPREHENSIVE_E2E_AUDIT.md:399` — "**Dashboard completely missing** | CRITICAL | LARGE"
- `report/IMPLEMENTATION_SUMMARY.md:223` — "Dashboard at `/dashboard` | ⏳ Not started"

## Implementation Progress (from reports)
- Core infrastructure: 100%
- Provider adapters: 80% (stubs ready)
- Verification: 10% (basic server runs)
- Dashboard: NOT STARTED (0%)
- Packaging/Publication: 0%

## To Make Dashboard Work
1. Embed dashboard assets via `go:embed` (reuse Python dashboard's `index.html` 102KB + assets)
2. Add `router.LoadHTMLGlob()` or `SetHTMLTemplate()` in `gateway.New()`
3. Implement `handleDashboardAssets` to serve static files
4. Add systemd service for production deployment

## Related Files
- `/root/project/wrappers-go/report/00_PREFLIGHT.md` — Preflight audit
- `/root/project/wrappers-go/report/01_FEATURE_PARITY_MATRIX.md` — 142 features mapped
- `/root/project/wrappers-go/report/COMPREHENSIVE_E2E_AUDIT.md` — Deep audit findings
- `/root/project/wrappers-go/report/IMPLEMENTATION_SUMMARY.md` — Progress summary