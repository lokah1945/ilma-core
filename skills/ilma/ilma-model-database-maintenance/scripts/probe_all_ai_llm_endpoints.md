---
name: probe_all_ai_llm_endpoints
description: Curl-style probe of every AI/LLM provider in /root/credential/api_key.json, using the `url_endpoint` field. Returns status, model count, and auth method. Re-runnable to validate the SOT.
version: 1.0.0
author: ILMA
---

# probe_all_ai_llm_endpoints

Curl-style probe of every AI/LLM provider in `/root/credential/api_key.json`. Reads the `url_endpoint` field (added 2026-06-09), probes with browser-like User-Agent, and returns status + model count per provider.

**Usage:**
```bash
python3 scripts/probe_all_ai_llm_endpoints.py [--provider openai] [--filter working|broken|all]
```

**Exit codes:**
- 0 — all probed providers either 200 OK or had no key/endpoint
- 1 — at least one provider with a key AND endpoint returned non-200 (suggests config drift)

**Sample output:**
```
[openai]     200 OK | 120 models | url=https://api.openai.com/v1/models
[google]     200 OK | 50 models  | url=https://generativelanguage.googleapis.com/v1beta/models?key=API_KEY
[felo]       401     | (url set, but auth failed)
[perplexity] SKIP    | no url_endpoint
```

**When to run:**
- After editing `api_key.json` (verify the change works)
- After updating `ilma_model_db_manager.py:PROVIDER_CONFIGS` (verify the manager picks it up)
- Before reporting sync status to Bos (always have fresh data)
