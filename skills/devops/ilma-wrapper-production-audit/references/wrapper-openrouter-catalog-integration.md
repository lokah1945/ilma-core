# Wrapper-OpenRouter Catalog Integration Non-Functional — 2026-07-29

## Symptom
- wrapper-openrouter (port 9106) has catalog routes but they return 404
- `/catalog/health` → 404 "Unsupported: /catalog/health"
- `/catalog/models` → 404
- `/mcp/sse` → 404
- Catalog integration code exists but never executes

## Root Cause
Catalog integration registered at **module level** AFTER `app = create_app()`:
```python
# openrouter/src/main.py - LINE ~2987
app = create_app()  # Creates app WITHOUT catalog routes

# THEN catalog integration runs (too late - catch-all already registered)
try:
    from common.catalog_integration import setup_catalog_routes, setup_mcp_server
    setup_catalog_routes(app)
    setup_mcp_server(app, "openrouter")
    ...
except ImportError:
    pass
```

The catch-all route `/v1/{path:path}` is registered INSIDE `create_app()` and intercepts `/catalog/*` before the late module-level catalog registration can handle them.

## Fix Required
Move catalog registration INSIDE `create_app()` BEFORE catch-all:

```python
def create_app() -> FastAPI:
    app = FastAPI(...)
    
    # ... middleware, core routes ...
    
    # CATALOG INTEGRATION - BEFORE CATCH-ALL
    try:
        from common.catalog_integration import setup_catalog_routes, setup_mcp_server, free_only_enabled as _cfe
        setup_catalog_routes(app)
        setup_mcp_server(app, "openrouter")
        free_only_enabled = _cfe
        _HAS_CATALOG_INTEGRATION = True
    except ImportError as _cie:
        _HAS_CATALOG_INTEGRATION = False
    
    # CATCH-ALL - AFTER catalog routes
    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def catch_all(path: str, request: Request):
        # Exclude catalog/mcp
        if path.startswith("catalog/") or path.startswith("mcp/"):
            return JSONResponse(404, {"error": {"message": f"Unknown endpoint: {path}", "type": "invalid_request_error"}})
        # ... proxy logic ...
```

## Verification
After fix:
```bash
curl http://localhost:9106/catalog/health
# {"ok":true,"db":"present"}
curl http://localhost:9106/catalog/models?limit=5 | jq '.count'
# > 0
curl http://localhost:9106/mcp/sse 2>&1 | head -3
# Should return MCP SSE endpoint (422 without request param is expected)
```

## Related
- `references/wrapper-nous-brotli-streaming-bug.md`
- `references/model-fetcher-catalog-empty.md`