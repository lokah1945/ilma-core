# Model Fetcher Catalog Setup — 2026-07-29

## Context
The `/root/wrapper/model_fetcher/` directory provides the central model catalog for all wrappers via `common/catalog_integration.py`. It was empty (0 models in SQLite DB) before this session.

## Architecture
```
/root/wrapper/model_fetcher/
├── __init__.py
├── data/
│   └── active_nvidia_nim.sqlite3    # 300+ NVIDIA NIM models
├── provider_management.py            # Admin API for provider keys
└── src/
    ├── catalog_queries.py            # search_models, get_model, list_providers, etc.
    └── env_config.py                 # FREE_ONLY config (shared across wrappers)
```

## Catalog Integration Flow
```
common/catalog_integration.py
  → imports from model_fetcher.src.catalog_queries
  → opens /root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3
  → mounts /catalog/* routes on each wrapper
  → mounts /mcp/sse (FastMCP SSE transport)
```

## Population (This Session)
The SQLite DB was empty. It was populated with 300+ NVIDIA NIM models from the NVIDIA NIM API / OpenRouter model list.

```sql
-- Schema
CREATE TABLE models (
    id TEXT PRIMARY KEY,
    canonical_slug TEXT,
    hugging_face_id TEXT,
    name TEXT,
    created INTEGER,
    description TEXT,
    context_length INTEGER,
    modality TEXT,
    input_modalities TEXT,      -- JSON array
    output_modalities TEXT,     -- JSON array
    tokenizer TEXT,
    instruct_type TEXT,
    pricing_prompt REAL,
    pricing_completion REAL,
    top_provider_context_length INTEGER,
    top_provider_max_completion_tokens INTEGER,
    top_provider_is_moderated INTEGER,
    supported_parameters TEXT,   -- JSON array
    default_parameters TEXT,     -- JSON object
    supported_voices TEXT,
    knowledge_cutoff TEXT,
    expiration_date TEXT,
    provider TEXT,
    publisher TEXT,
    tier TEXT,                    -- free, paid
    architecture TEXT,           -- JSON object
    availability_state TEXT,     -- available, retired, etc.
    reason_code TEXT,            -- OK, QUOTA, etc.
    checked_at REAL,             -- Unix timestamp
    source TEXT                  -- nvidia_nim_api, openrouter, etc.
);
```

## Verification
```bash
# Check DB has models
sqlite3 /root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3 "SELECT COUNT(*) FROM models;"
# → 300+

# Test catalog endpoints on all wrappers
for p in 9101 9102 9103 9104; do
  curl -s http://127.0.0.1:$p/catalog/health
  curl -s http://127.0.0.1:$p/catalog/models?limit=3
done

# Test MCP tools
curl -s "http://127.0.0.1:9102/mcp/sse?request={\"method\":\"tools/call\",\"params\":{\"name\":\"search_nim_models\",\"arguments\":{\"query\":\"nemotron\",\"limit\":2}}}"
```

## FREE_ONLY Config
`model_fetcher/src/env_config.py` provides the shared `free_only_enabled()` function used by all wrappers. This ensures consistent FREE-TIER-FIRST behavior.

```python
def free_only_enabled() -> bool:
    """Returns True if FREE_ONLY mode is active (default: True)."""
    return os.environ.get("FREE_ONLY", "true").lower() in ("1", "true", "yes")
```

Wrappers override via `common/catalog_integration.py`:
```python
from common.catalog_integration import free_only_enabled as _cfe
free_only_enabled = _cfe  # override local with shared version
```

## Maintenance
- **Re-populate catalog**: Run the model fetcher population script (TBD - likely in model_fetcher/src/)
- **Update frequency**: Weekly or when new NVIDIA NIM models released
- **Backup**: DB is committed to git (committed this session)

## Pitfalls
- `catalog_queries.py` is in `model_fetcher/src/` NOT `model_fetcher/` root — `common/catalog_integration.py` was fixed to check both locations
- SQLite is read-only in production (URI `file:path?mode=ro`) — writes need separate process
- DB path configurable via `CATALOG_DB` env var, defaults to `model_fetcher/data/active_nvidia_nim.sqlite3`