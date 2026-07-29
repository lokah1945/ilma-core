# Catalog Route Ordering Fix (2026-07-29)

## Problem
All wrapper services (nous, opencode, blackbox, vercel) had catch-all route (`/{path:path}`) registered **BEFORE** catalog/MCP integration routes. This caused `/catalog/health`, `/catalog/models`, `/mcp/sse` to return 404 "Unsupported" because the catch-all intercepted them first.

Only `wrapper-nvidia-python` had correct ordering (catalog routes registered inside `create_app()` before `server._register_routes()` which contains the catch-all).

## Root Cause
In `wrapper-nous/src/main.py`, `wrapper-opencode/src/main.py`, `wrapper-blackbox/src/main.py`, `wrapper-vercel/src/main.py`:
```python
# WRONG ORDER:
@app.api_route("/{path:path}", methods=["GET", "POST"])
async def catch_all(path: str, request: Request):
    return 404  # Intercepts /catalog/* and /mcp/*

# Catalog integration AFTER catch-all (module level, after app creation)
from common.catalog_integration import setup_catalog_routes
setup_catalog_routes(app)
```

## Fix Applied
Moved catalog/MCP integration **BEFORE** catch-all in all 4 wrappers:
```python
# CORRECT ORDER:
# 1. Core API routes (/health, /ready, /v1/*, etc.)
# 2. Catalog + MCP integration (BEFORE catch-all)
from common.catalog_integration import setup_catalog_routes, setup_mcp_server
setup_catalog_routes(app)
setup_mcp_server(app, "wrapper-name")

# 3. Catch-all LAST, with catalog/mcp exclusions
@app.api_route("/{path:path}", methods=["GET", "POST"])
async def catch_all(path: str, request: Request):
    if path.startswith("catalog/") or path.startswith("mcp/"):
        return 404 with type="invalid_request_error"  # let dedicated handlers handle
    return 404 with type="not_found_error"
```

## Files Modified
- `nous/src/main.py` — moved catalog integration before catch-all, added exclusions
- `opencode/src/main.py` — moved catalog integration before catch-all, added exclusions
- `blackbox/src/main.py` — moved catalog integration before catch-all, added exclusions
- `vercel/src/main.py` — moved catalog integration before catch-all, added exclusions
- `nvidia-python/src/main.py` — already correct (catalog inside `create_app()`)

## Verification
All 4 active wrappers now serve:
- `GET /catalog/health` → `{"ok": true, "db": "present"}`
- `GET /catalog/models?limit=5` → 300+ NVIDIA NIM models
- `GET /catalog/search?q=nemotron` → filtered results
- `GET /mcp/sse` → FastMCP SSE transport (requires `?request=` param)

## Pattern for Future Wrappers
When creating a new wrapper, **always** register catalog/MCP routes BEFORE the catch-all, and add the path exclusions to the catch-all handler.