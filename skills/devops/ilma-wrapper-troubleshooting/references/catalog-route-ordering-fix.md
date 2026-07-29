# Catalog Route Ordering Fix — 2026-07-29

## Problem
All wrapper catalog routes (`/catalog/health`, `/catalog/models`, `/mcp/sse`) returned 404 "Unsupported" on 4/5 wrappers (nous, opencode, blackbox, vercel).

## Root Cause
Catch-all route (`/{path:path}`) registered **BEFORE** catalog integration in `create_app()` / module scope.

Route registration order (WRONG):
```python
@app.api_route("/{path:path}", methods=["GET", "POST"])
async def catch_all(path: str, request: Request):
    return 404

# Module-level - runs AFTER app creation
from common.catalog_integration import setup_catalog_routes
setup_catalog_routes(app)  # Never reached - catch-all intercepts first
```

## Fix Applied
Moved catalog integration **BEFORE** catch-all in all 4 wrappers:

```python
# CORRECT ORDER in create_app() / module scope:

# 1. Core API routes
@app.get("/health")
async def health(): ...

# 2. Catalog + MCP integration (BEFORE catch-all)
from common.catalog_integration import setup_catalog_routes, setup_mcp_server
setup_catalog_routes(app)
setup_mcp_server(app, "wrapper-name")

# 3. Catch-all LAST with path exclusions
@app.api_route("/{path:path}", methods=["GET", "POST"])
async def catch_all(path: str, request: Request):
    # Skip catalog/mcp paths - they have dedicated handlers
    if path.startswith("catalog/") or path.startswith("mcp/"):
        return JSONResponse(status_code=404, content={
            "error": {"message": f"Unknown endpoint: /{path}", "type": "invalid_request_error"}
        })
    return JSONResponse(status_code=404, content={
        "error": {"message": f"Unsupported: /{path}", "type": "not_found_error"}
    })
```

## Files Modified
- `/root/wrapper/nous/src/main.py` - moved catalog integration before catch-all
- `/root/wrapper/opencode/src/main.py` - moved catalog integration before catch-all
- `/root/wrapper/blackbox/src/main.py` - moved catalog integration before catch-all
- `/root/wrapper/vercel/src/main.py` - moved catalog integration before catch-all (then removed)
- `/root/wrapper/common/catalog_integration.py` - added `src/` subdirectory path resolution

## Verification
```bash
# All 4 wrappers now serve catalog endpoints:
for p in 9101 9102 9103 9104; do
  curl -s http://127.0.0.1:$p/catalog/health
  # {"ok":true,"db":"present"}
done
```

## Prevention
- **Rule:** Catch-all route MUST be the LAST route registered
- **Rule:** Always add path exclusions for catalog/mcp prefixes in catch-all
- **Rule:** Register shared middleware/integrations inside `create_app()` before catch-all