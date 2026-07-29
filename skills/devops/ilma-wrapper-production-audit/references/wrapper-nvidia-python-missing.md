# Wrapper-Nvidia-Python (Port 9101) Missing Entirely — 2026-07-29

## Symptom
- `/root/wrapper/nvidia-python/` directory exists with full `src/main.py` and systemd service
- BUT `/root/wrapper/nvidia/` exists with ONLY `metrics_data/` - no source code, no service
- The NVIDIA NIM catalog builder + model fetcher is missing
- This is the service that should populate the shared catalog DB

## Root Cause
The `nvidia-python` wrapper (port 9101) IS deployed and running correctly.
But there's a separate `nvidia/` directory that appears to be a placeholder for the catalog builder / model fetcher.

The actual catalog population logic should be in either:
1. `model_fetcher/src/` - but this only has queries, no population script
2. `nvidia-python/src/main.py` - which has NVIDIA NIM model verification but not catalog building
3. A missing `nvidia/` service that was never deployed

## Fix Required
Create catalog population in `model_fetcher/` or `nvidia-python/`:

```bash
# Option 1: Add to model_fetcher
cat > /root/wrapper/model_fetcher/populate_catalog.py << 'EOF'
#!/usr/bin/env python3
"""Populate NVIDIA NIM catalog from public API."""
import sqlite3
import requests

DB = "data/active_nvidia_nim.sqlite3"

def main():
    resp = requests.get("https://integrate.api.nvidia.com/v1/models", timeout=30)
    models = resp.json().get("data", [])
    
    conn = sqlite3.connect(DB)
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
            0.0, 0.0,  # NVIDIA NIM free
            m.get('context_length', 0), m.get('max_completion_tokens', 4096),
            0, str(m.get('supported_parameters', ['temperature', 'top_p', 'max_tokens'])),
            str(m.get('default_parameters', {'temperature': 0.7, 'top_p': 1.0, 'max_tokens': 4096})),
            None, m.get('knowledge_cutoff', ''), None, 'nvidia', None, 'free',
            str({'input_modalities': ['text'], 'output_modalities': ['text'], 'tokenizer': 'unknown', 'instruct_type': 'chat'}),
            'available', 'OK', 'now()', 'nvidia_nim_api'
        ))
    
    conn.commit()
    print(f"Inserted {len(models)} models")
    conn.close()

if __name__ == "__main__":
    main()
EOF

python3 /root/wrapper/model_fetcher/populate_catalog.py
```

## Verification
```bash
curl http://localhost:9101/catalog/models?limit=5 | jq '.count'
# Should be 300+
```

## Related
- `references/model-fetcher-catalog-empty.md`
- `references/wrapper-openrouter-catalog-integration.md`