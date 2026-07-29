# model_fetcher Catalog Setup (2026-07-29)

## Problem
The shared catalog integration (`common/catalog_integration.py`) couldn't find `catalog_queries.py` because it was located in `model_fetcher/src/` subdirectory, not the root of `model_fetcher/`.

## Solution
Updated `common/catalog_integration.py` to check both:
1. Root of candidate paths (e.g., `/root/wrapper/model_fetcher/`)
2. `src/` subdirectory (e.g., `/root/wrapper/model_fetcher/src/`)

```python
# Added to catalog_integration.py _CANDIDATE_PATHS search
for _p in _CANDIDATE_PATHS:
    if _p and (os.path.isfile(os.path.join(_p, 'catalog_queries.py')) or 
               os.path.isfile(os.path.join(_p, 'src', 'catalog_queries.py'))):
        CATALOG_REPO = _p
        break

# Also add src/ to sys.path
if CATALOG_REPO:
    if CATALOG_REPO not in sys.path:
        sys.path.insert(0, CATALOG_REPO)
    src_path = os.path.join(CATALOG_REPO, 'src')
    if os.path.isdir(src_path) and src_path not in sys.path:
        sys.path.insert(0, src_path)
```

## Also Fixed in OpenRouter
OpenRouter wrapper had hardcoded import from `CATALOG_REPO` without checking `src/` subdirectory. Added same fix.

## Result
All wrappers now load catalog from `/root/wrapper/model_fetcher/src/catalog_queries.py` which reads from `/root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3` (300+ NVIDIA NIM models).

## Verification
```bash
# All 4 wrappers
curl http://localhost:9101/catalog/health  # nvidia-python
curl http://localhost:9102/catalog/health  # nous
curl http://localhost:9103/catalog/health  # opencode
curl http://localhost:9104/catalog/health  # blackbox
# All return: {"ok": true, "db": "present"}
```

## model_fetcher Structure
```
/root/wrapper/model_fetcher/
├── __init__.py
├── data/
│   └── active_nvidia_nim.sqlite3    # 300+ models
├── provider_management.py           # MANAGEMENT_KEY admin API
├── src/
│   ├── catalog_queries.py           # Search, get, list models
│   └── env_config.py                # FREE_ONLY shared logic
└── src/env_config.py
```