# Model Fetcher Catalog Setup — 2026-07-29

## Problem
The shared model catalog at `/root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3` had schema but 0 rows. All wrapper catalog endpoints returned "not_available" / "MCP not available".

## Root Cause
The catalog population script was never run. The `model_fetcher` module in `model_fetcher/src/` was not discoverable because `common/catalog_integration.py` only checked root directory, not `src/` subdirectory.

## Fix Applied

### 1. Fixed Import Path Resolution
Updated `/root/wrapper/common/catalog_integration.py`:
```python
# Check both root and src/ subdirectory
if _p and (os.path.isfile(os.path.join(_p, 'catalog_queries.py')) or 
           os.path.isfile(os.path.join(_p, 'src', 'catalog_queries.py'))):
    CATALOG_REPO = _p
    break

# Add both root and src/ to sys.path
if CATALOG_REPO:
    if CATALOG_REPO not in sys.path:
        sys.path.insert(0, CATALOG_REPO)
    src_path = os.path.join(CATALOG_REPO, 'src')
    if os.path.isdir(src_path) and src_path not in sys.path:
        sys.path.insert(0, src_path)
```

### 2. Populated Catalog DB
The SQLite database now contains 300+ NVIDIA NIM models with full metadata:
- `id`, `name`, `description`, `context_length`, `modality`
- `pricing_prompt`, `pricing_completion`, `tier` (free/paid)
- `provider`, `publisher`, `architecture`
- `availability_state`, `reason_code`, `checked_at`
- `source` (nvidia_nim_api, openrouter, etc.)

## Verification
```bash
# All wrappers serve catalog data
curl -s http://127.0.0.1:9101/catalog/models?limit=3
# {"count":3,"models":[{"id":"01-ai/yi-large",...}]}

curl -s http://127.0.0.1:9102/catalog/health
# {"ok":true,"db":"present"}
```

## Files
- `/root/wrapper/model_fetcher/src/catalog_queries.py` - Query API
- `/root/wrapper/model_fetcher/src/env_config.py` - Shared FREE_ONLY logic
- `/root/wrapper/model_fetcher/src/provider_management.py` - Admin API
- `/root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3` - 300+ models
- `/root/wrapper/common/catalog_integration.py` - Path resolution fix

## Prevention
- Run catalog population script after any schema change
- Verify `catalog_queries.py` import works from all wrappers
- Add pre-deployment check: `python3 -c "from catalog_queries import search_models; print('OK')"`