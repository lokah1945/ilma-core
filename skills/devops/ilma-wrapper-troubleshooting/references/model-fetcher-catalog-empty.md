# model_fetcher Catalog Empty — 2026-07-29

## Current State
DB at `/root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3`:
- Schema: EXISTS ✅ Tables created (models, indexes)
 ❌ **0 rows** in models table

```bash
sqlite3 /root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3 "SELECT COUNT(*) FROM models"
# -> 0
```

## Impact
All wrapper catalog integrations non-functional:
| Endpoint | Response |
|----------|----------|
| `/catalog/health` | `{"ok":false,"catalog":"not_available"}` |
| `/catalog/models` | `{"error":"Catalog not available — install model_fetcher"}` |
| `/catalog/stats` | `{"error":"Catalog not available"}` |
| `/mcp/sse` | `{"error":"MCP not available"}` |

## Root Cause
The catalog population script was never run. Likely candidates:
1. `wrapper/nvidia-python/src/populate_catalog.py` — missing (wrapper-nvidia-python not deployed)
2. `model_fetcher/src/populate.py` — missing
3. Manual one-off script that was never executed

## Required Population
Need to fetch models from NVIDIA NIM API and populate the DB with:
- `id` (e.g., `nvidia/llama-3.3-nemotron-super-49b-v1`)
- `canonical_slug`, `hugging_face_id`, `name`, `created`, `description`
- `context_length`, `modality`, `tokenizer`, `instruct_type`
- `pricing_prompt`, `pricing_completion` (for FREE_ONLY filtering)
- `top_provider_context_length`, `top_provider_max_completion_tokens`
- `top_provider_is_moderated`, `supported_parameters`, `default_parameters`
- `supported_voices`, `knowledge_cutoff`, `expiration_date`
- `provider` (e.g., `nvidia`), `publisher` (e.g., `nvidia`)
- `tier` (free/paid), `architecture` (JSON), `availability_state`, `reason_code`
- `checked_at` (timestamp), `source` (e.g., `nvidia_nim`)

## Population Script Template
```python
#!/usr/bin/env python3
# populate_catalog.py
import os, sys, json, sqlite3, requests, time

CATALOG_DB = os.environ.get('CATALOG_DB', '/root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3')
NVIDIA_NIM_MODELS_URL = 'https://integrate.api.nvidia.com/v1/models'

def populate():
    # Fetch from NVIDIA NIM (requires API key with model list access)
    # Or from OpenRouter public model list (free)
    pass

if __name__ == '__main__':
    populate()
```

## Verification
```bash
# After population
sqlite3 /root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3 "SELECT COUNT(*) FROM models"
# Should show 300+

curl http://127.0.0.1:9106/catalog/health
# Should show: {"ok":true,"catalog":"available"}

curl http://127.0.0.1:9106/catalog/models | jq '.models | length'
# Should show >0
```

## Related
- `references/wrapper-openrouter-catalog-fix.md` — catalog routes broken even after DB populated
- `ilma-wrapper-production-audit` — checks catalog availability