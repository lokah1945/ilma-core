# wrapper-openrouter Catalog Integration Fix — 2026-07-29

## Symptom
- wrapper-openrouter (port 9106) has catalog routes defined (`/catalog/health`, `/catalog/models`, `/mcp/sse`)
- But ALL return errors: `{"ok":false,"catalog":"not_available"}` or `{"error":"MCP not available"}`
- The catalog DB exists at `/root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3` (though empty)

## Root Cause
In `/root/wrapper/openrouter/src/main.py`:
1. Catalog routes are registered at **module level** (after `app = create_app()`)
2. The catch-all proxy route is registered **INSIDE** `create_app()` via `server._register_routes()`
3. FastAPI matches routes in registration order — catch-all (`/{path:path}`) intercepts `/catalog/*` before catalog routes can match

```python
# At module level (line ~2987):
app = create_app()  # Registers catch-all INSIDE

# Later at module level (line ~2987-3005):
# Integrate catalog routes
if _HAS_CATALOG:
    @app.get("/catalog/health")  # ← Registered AFTER catch-all
    async def catalog_health(): ...
```

## Fix
Move catalog route registration **INSIDE** `create_app()` function, **before** the catch-all route is registered.

Option A: Call a helper from inside `create_app()`:
```python
def create_app():
    ...
    app = FastAPI(...)
    ...
    # Register catalog routes BEFORE catch-all
    if _HAS_CATALOG:
        from openrouter.src.main import _register_catalog_routes
        _register_catalog_routes(app)
    
    server._register_routes(app)  # This registers catch-all
    return app
```

Option B: Add catalog paths to `PUBLIC_PATHS` in auth middleware so they bypass auth AND are matched before catch-all (but this doesn't fix route ordering).

## Evidence
```bash
# Test before fix
curl -s http://127.0.0.1:9106/catalog/health
# {"ok":false,"catalog":"not_available"}  ← catch-all proxied to NVIDIA, returned 404

# Test after fix (expected)
curl -s http://127.0.0.1:9106/catalog/health
# {"ok":true,"catalog":"available"}  ← or "db_missing" if DB empty
```

## Related
- `references/model-fetcher-catalog-empty.md` — even after route fix, catalog is empty (0 models)
- `ilma-wrapper-production-audit` — Technique: "Integrate catalog routes"