# Model Fetcher Catalog Empty — 300+ NVIDIA NIM Models Missing — 2026-07-29

## Symptom
- `/root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3` exists but has 0 models
- All wrapper `/catalog/models` endpoints return empty or minimal results
- `/catalog/health` returns `{"ok":true,"db":"present"}` but DB is empty
- MCP server returns "Catalog not available" because no models to serve

## Root Cause
The catalog population script was never run. The `model_fetcher/src/catalog_queries.py` has schema and queries but no population logic was executed.

## Fix Required
Run catalog population from NVIDIA NIM API:

```bash
cd /root/wrapper/model_fetcher
python3 -c "
import sqlite3
import requests

# Fetch from NVIDIA NIM public models endpoint
resp = requests.get('https://integrate.api.nvidia.com/v1/models', timeout=30)
models = resp.json().get('data', [])

# Populate SQLite
conn = sqlite3.connect('data/active_nvidia_nim.sqlite3')
cur = conn.cursor()

for m in models:
    cur.execute('''
        INSERT OR REPLACE INTO models 
        (id, canonical_slug, hugging_face_id, name, created, description, 
         context_length, modality, input_modalities, output_modalities,
         tokenizer, instruct_type, pricing_prompt, pricing_completion,
         top_provider_context_length, top_provider_max_completion_tokens,
         top_provider_is_moderated, supported_parameters, default_parameters,
         supported_voices, knowledge_cutoff, expiration_date, provider,
         publisher, tier, architecture, availability_state, reason_code,
         checked_at, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        m.get('id'), m.get('id'), m.get('id'), m.get('id'), 
        m.get('created', 0), m.get('description', ''),
        m.get('context_length', 0), m.get('modality', 'text'),
        str(m.get('input_modalities', ['text'])), str(m.get('output_modalities', ['text'])),
        m.get('tokenizer', 'unknown'), m.get('instruct_type', 'chat'),
        0.0, 0.0,  # NVIDIA NIM free tier
        m.get('context_length', 0), m.get('max_completion_tokens', 4096),
        0, str(m.get('supported_parameters', ['temperature', 'top_p', 'max_tokens'])),
        str(m.get('default_parameters', {'temperature': 0.7, 'top_p': 1.0, 'max_tokens': 4096})),
        None, m.get('knowledge_cutoff', ''), None, 'nvidia', None, 'free',
        str({'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'unknown', 'instruct_type': 'chat'}),
        'available', 'OK', 'now()', 'nvidia_nim_api'
    ))

conn.commit()
print(f'Inserted {len(models)} models')
"
```

## Verification
After population:
```bash
curl http://localhost:9101/catalog/models?limit=5 | jq '.count'
# Should return 300+
curl http://localhost:9102/catalog/models?limit=5 | jq '.count'
# Should return 300+
```

## Related
- `references/wrapper-nous-brotli-streaming-bug.md`
- `references/wrapper-openrouter-catalog-integration.md`