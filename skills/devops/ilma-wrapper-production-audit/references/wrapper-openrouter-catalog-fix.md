# Wrapper-OpenRouter Catalog Integration Fix — 2026-07-29

## Symptom
- `/catalog/health` returns 404 (catch-all intercepts)
- `/catalog/models` returns 404
- `/mcp/sse` returns 404
- Catalog routes registered but not accessible

## Root Cause
In `openrouter/src/main.py`, catalog integration is registered at **module level AFTER** `app = create_app()`:

```python
# Line ~2987 (module level, AFTER create_app())
app = create_app()
# ...
try:
    from common.catalog_integration import setup_catalog_routes, setup_mcp_server
    setup_catalog_routes(app)  # Registers /catalog/* routes
    setup_mcp_server(app, "openrouter")
except ImportError:
    pass
```

But `create_app()` registers the catch-all route (`/{path:path}`) which intercepts ALL unmatched paths. Since catalog routes are added AFTER the catch-all is registered, they never match — the catch-all handles them first and returns 404.

## Fix
Move catalog registration **INSIDE** `create_app()` **BEFORE** the catch-all route is registered, OR add `/catalog/` and `/mcp/` to PUBLIC_PATHS in the auth middleware so they bypass auth and catch-all.

```python
def create_app() -> FastAPI:
    # ... middleware setup ...
    
    # Register catalog BEFORE catch-all
    try:
        from common.catalog_integration import setup_catalog_routes, setup_mcp_server
        setup_catalog_routes(app)
        setup_mcp_server(app, "openrouter")
    except ImportError:
        pass
    
    # ... THEN register catch-all ...
    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def catch_all(path: str, request: Request):
        # Skip catalog/mcp paths
        if path.startswith("catalog/") or path.startswith("mcp/"):
            return JSONResponse(status_code=404, content={"error": {"message": f"Unknown endpoint: /{path}", "type": "invalid_request_error"}})
        return JSONResponse(status_code=404, content={"error": {"message": f"Unsupported: /{path}", "type": "not_found_error"}})
```

## Verification
After fix:
- `curl http://localhost:9106/catalog/health` → `{"ok":true,"db":"present"}`
- `curl http://localhost:9106/catalog/models?limit=5` → returns models
- `curl http://localhost:9106/mcp/sse` → MCP SSE endpoint responds

## Related
- `references/wrapper-nous-brotli-streaming-bug.md` — wrapper-nous has same catch-all issue (now fixed)
- `references/model-fetcher-catalog-empty.md` — DB empty, needs population