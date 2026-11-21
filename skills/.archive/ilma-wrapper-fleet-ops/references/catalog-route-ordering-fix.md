# Catalog Route Ordering Fix — 2026-07-29

## Problem
All wrappers except `nvidia-python` had their `/catalog/health`, `/catalog/models`, `/catalog/search`, `/mcp/sse` endpoints returning 404 "Unsupported: /catalog/health" or "Unsupported: /mcp/sse".

## Root Cause
FastAPI registers routes in order. The catch-all route (`/{path:path}`) was registered **BEFORE** the catalog/MCP integration routes in 3 wrappers:

```python
# WRONG ORDER (nous, opencode, blackbox, vercel)
@app.api_route("/{path:path}", methods=["GET", "POST"])
async def catch_all(path: str, request: Request):
    return 404  # Intercepts /catalog/* before catalog routes see them

# Catalog integration at MODULE LEVEL (after app creation, AFTER catch-all)
try:
    from common.catalog_integration import setup_catalog_routes, setup_mcp_server
    setup_catalog_routes(app)
    setup_mcp_server(app, "nous")
except ImportError:
    pass
```

FastAPI's routing: first match wins. Catch-all matches everything → catalog routes never reached.

## Correct Order (as in nvidia-python)
```python
def create_app() -> FastAPI:
    app = FastAPI()
    
    # 1. Core routes (/health, /ready, /v1/*, etc.)
    # ... middleware, auth, etc.
    
    # 2. Catalog + MCP integration (MUST BE BEFORE catch-all)
    try:
        from common.catalog_integration import setup_catalog_routes, setup_mcp_server
        setup_catalog_routes(app)
        setup_mcp_server(app, "nous")
    except ImportError:
        pass
    
    # 3. Catch-all (LAST)
    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def catch_all(path: str, request: Request):
        # Skip catalog/mcp paths so they 404 with proper error type
        if path.startswith("catalog/") or path.startswith("mcp/"):
            return JSONResponse(404, {"error": {"message": f"Unknown endpoint: /{path}", "type": "invalid_request_error"}})
        return JSONResponse(404, {"error": {"message": f"Unsupported: /{path}", "type": "not_found_error"}})
    
    return app
```

## Fix Applied (2026-07-29)
Moved catalog/MCP integration **BEFORE** catch-all in:
- `nous/src/main.py` ✅
- `opencode/src/main.py` ✅
- `blackbox/src/main.py` ✅
- `vercel/src/main.py` ✅ (removed entirely)

Also added `/catalog/` and `/mcp/` path exclusions to catch-all handlers so they return proper `invalid_request_error` instead of `not_found_error`.

## Verification
```bash
for p in 9101 9102 9103 9104; do
  echo "Port $p:"
  curl -s http://127.0.0.1:$p/catalog/health
  curl -s http://127.0.0.1:$p/mcp/sse
done
# All return: {"ok":true,"db":"present"} and MCP SSE endpoint (422 = request required, not 404)
```

## Catalog Integration Architecture
```
common/catalog_integration.py
  ├── setup_catalog_routes(app) → mounts /catalog/* router
  │   ├── /catalog/health
  │   ├── /catalog/stats
  │   ├── /catalog/providers
  │   ├── /catalog/models
  │   ├── /catalog/model?id=
  │   ├── /catalog/provider-models
  │   └── /catalog/keys-status (if management available)
  │
  └── setup_mcp_server(app, wrapper_name) → mounts /mcp/sse (FastMCP SSE transport)
      ├── search_nim_models
      ├── get_nim_model
      ├── list_providers
      ├── search_provider_models
      └── (openrouter_* tools if openrouter)
```

## Root Cause of the Bug
The catalog integration was added at module level (after `app = create_app()` or after server class instantiation) in a separate try/except block. The catch-all was defined INSIDE the server class or `create_app()` before that block ran. Route registration order:
1. Core routes (inside server class / create_app)
2. Catch-all (inside server class / create_app)
3. Catalog routes (module-level try/except, runs AFTER create_app returns)

## Prevention
1. **Always register catalog/MCP routes inside `create_app()` or server `__init__` BEFORE catch-all**
2. **Add path exclusions to catch-all for `/catalog/` and `/mcp/`**
3. **Add smoke test in production audit for `/catalog/health` and `/mcp/sse`**
4. **nvidia-python is the reference implementation — copy its pattern**

## Related Fixes This Session
- `common/catalog_integration.py`: Fixed `catalog_queries.py` discovery to check both root and `src/` subdirectory
- `openrouter/src/main.py`: Added `src/` path to sys.path for catalog imports
- `model_fetcher/`: Committed with populated SQLite DB (300+ NVIDIA NIM models)