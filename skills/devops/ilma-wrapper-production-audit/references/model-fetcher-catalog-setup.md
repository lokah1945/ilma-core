# Model Fetcher Catalog Setup & MCP Integration

## Architecture
```
/root/wrapper/model_fetcher/
├── data/
│   └── active_nvidia_nim.sqlite3    ← 300+ NVIDIA NIM models (81KB)
├── src/
│   ├── catalog_queries.py           ← SQL queries: search_models, get_model, list_providers, search_provider_models
│   └── env_config.py                ← FREE_ONLY, is_free_model, free_model_allowlist, CATALOG_DB path
├── provider_management.py           ← OpenRouter Management API (CRUD keys, rotation, usage)
└── __init__.py
```

## Catalog DB Schema (active_nvidia_nim.sqlite3)
```sql
CREATE TABLE models (
    id TEXT PRIMARY KEY,           -- e.g., "nvidia/nemotron-3-ultra-550b-a55b"
    canonical_slug TEXT,
    hugging_face_id TEXT,
    name TEXT,
    created INTEGER,
    description TEXT,
    context_length INTEGER,
    modality TEXT,                  -- "text", "vision", "image", "ranking"
    input_modalities TEXT,          -- JSON array: ["text"]
    output_modalities TEXT,         -- JSON array: ["text"]
    tokenizer TEXT,
    instruct_type TEXT,             -- "chat", "completion"
    pricing_prompt REAL,            -- 0.0 for free
    pricing_completion REAL,        -- 0.0 for free
    top_provider_context_length INTEGER,
    top_provider_max_completion_tokens INTEGER,
    top_provider_is_moderated INTEGER,
    supported_parameters TEXT,      -- JSON array: ["temperature", "top_p", "max_tokens"]
    default_parameters TEXT,        -- JSON: {"temperature": 0.7, "top_p": 1.0, "max_tokens": 4096}
    supported_voices TEXT,
    knowledge_cutoff TEXT,          -- "2024-01"
    expiration_date TEXT,
    provider TEXT,                  -- "nvidia"
    publisher TEXT,
    tier TEXT,                      -- "free"
    architecture TEXT,              -- JSON: {"input_modalities":["text"],"output_modalities":["text"],...}
    availability_state TEXT,        -- "available", "unavailable"
    reason_code TEXT,               -- "OK"
    checked_at REAL,                -- Unix timestamp
    source TEXT                     -- "nvidia_nim_api"
);
```

## Key Functions (catalog_queries.py)
```python
search_models(db, query=None, modality=None, tier=None, working_only=False, 
              free_only=False, publisher=None, limit=50) -> list[dict]

get_model(db, catalog_id: str) -> Optional[dict]

list_providers(db) -> list[dict]

search_provider_models(db, provider=None, query=None, free_only=False, limit=50) -> list[dict]

stats(db) -> dict  -- total models, by tier, by modality, by provider
```

## Shared Integration (common/catalog_integration.py)
```python
# Mounted by ALL wrappers in main.py:
from common.catalog_integration import setup_catalog_routes, setup_mcp_server, free_only_enabled

setup_catalog_routes(app)          # → /catalog/health, /catalog/models, /catalog/search, /catalog/providers, /catalog/model, /catalog/provider-models
setup_mcp_server(app, "nous")      # → /mcp/sse (FastMCP SSE transport)

# MCP Tools exposed:
# - search_nim_models(query, modality, tier, working_only, free_only, publisher, limit)
# - get_nim_model(catalog_id)
# - list_providers()
# - search_provider_models(provider, query, free_only, limit)
# - openrouter_list_keys(offset)       # only if management enabled
# - openrouter_key_usage()             # only if management enabled
```

## FREE_ONLY Logic (env_config.py)
```python
# Environment: FREE_ONLY=yes|true|1|on|y
def free_only() -> bool:
    v = os.environ.get("FREE_ONLY", "no").lower()
    return v in ("yes", "true", "1", "on", "y")

# Model ID qualifies as free if:
# - ends with ":free" or "-free"
# - in FREE_MODEL_ALLOWLIST (comma-separated env var)
# - pricing_prompt = 0 in catalog
```

## Population (Manual - needs automation)
Current: DB populated via git commit (model_fetcher/data/active_nvidia_nim.sqlite3 tracked)
Future: Run `model_fetcher/src/populate_catalog.py` (not yet created) to fetch from:
- NVIDIA NIM API: `https://integrate.api.nvidia.com/v1/models`
- OpenRouter API: `https://openrouter.ai/api/v1/models`
- Nous API: `https://inference-api.nousresearch.com/v1/models`

## MCP Server Endpoints
All 4 active wrappers expose:
- `GET /mcp/sse?request=<json>` — SSE transport (requires `request` query param with MCP initialize call)
- `POST /mcp/messages` — message handler

Test:
```bash
curl -s "http://localhost:9102/mcp/sse?request={\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1.0\"}}}"
```

## Verification Checklist
- [ ] `sqlite3 /root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3 "SELECT COUNT(*) FROM models;"` returns > 0
- [ ] `curl http://localhost:9102/catalog/health` → `{"ok":true,"db":"present"}`
- [ ] `curl http://localhost:9102/catalog/models?limit=3` → 3 models with NVIDIA provider
- [ ] `curl http://localhost:9102/catalog/search?q=nemotron&limit=2` → results
- [ ] `curl "http://localhost:9102/mcp/sse?request={\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1.0\"}}}"` → SSE stream