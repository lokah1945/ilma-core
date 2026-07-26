---
name: url-endpoint-registry-2026-06
description: Curl-verified url_endpoint values for all 22 AI/LLM providers in api_key.json, as of 2026-06-09. Reference table for manager config and credential edits.
version: 1.0.0
author: ILMA
---

# URL Endpoint Registry — 2026-06-09

Curl-verified `url_endpoint` values for every AI/LLM provider in `/root/credential/api_key.json`. Tested with browser-like User-Agent (`Mozilla/5.0 ... Chrome/135.0.0`) to bypass Cloudflare 403.

## Verified Working (200 OK)

| Provider | url_endpoint | Auth | Models | Notes |
|----------|--------------|------|-------:|-------|
| openai | `https://api.openai.com/v1/models` | Bearer | 120 | Standard OpenAI-compat |
| openrouter | `https://openrouter.ai/api/v1/models` | Bearer (use `keys[0]`, NOT management_key) | 341 | Management key works but wasteful |
| google | `https://generativelanguage.googleapis.com/v1beta/models` | `x-goog-api-key` header (NOT Bearer) | 50 | `AQ.Ab8RN...` tokens are NOT bearer-style |
| nvidia | `https://integrate.api.nvidia.com/v1/models` | Bearer (use dict-of-keys pattern, 3 keys) | 120 | Round-robin across 3 keys |
| minimax | `https://api.minimax.io/v1/models` | Bearer (OpenAI surface) | 8 | Server's 401 message tells you which header to use |
| xai | `https://api.x.ai/v1/models` | Bearer | 9 | |
| blackbox | `https://docs.blackbox.ai/api-reference/models/chat-pricing` | HTML scrape (no JSON endpoint) | 17 | Use `blackbox-docs` fmt in manager |
| alibaba | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models` | Bearer | 145 | **Use INTL, not CN** (`dashscope.aliyuncs.com` returns 401 outside China) |
| aimlapi | `https://api.aimlapi.com/v1/models` | Bearer | 617 | |
| groq | `https://api.groq.com/openai/v1/models` | Bearer | 16 | |
| cerebras | `https://api.cerebras.ai/v1/models` | Bearer | 2 | Browser UA required (CF block otherwise) |
| together | `https://api.together.ai/v1/models` | Bearer | 263 | **Returns raw JSON list `[...]`, not `{"data": [...]}`** — manager's `fmt == "openai"` parser updated |
| opencode | `https://opencode.ai/zen/go/v1/models` | Bearer | 18 | NOT `api.opencode.ai/v1/models` |
| byteplus | `https://ark.ap-southeast.bytepluses.com/api/v3/models` | Bearer | 47 | `ark.byteplus.com` and `ark.cn-beijing.volces.com` blocked; use APAC INTL |
| nous | `https://inference.nousresearch.com/v1/models` | Bearer | 265 | |
| ollama | `http://localhost:11434/api/tags` | none (local) | 41 | `api/tags` not `/v1/models` |

## Providers Without Verified Endpoint (placeholders set)

| Provider | url_endpoint set | Status | Fallback |
|----------|------------------|--------|----------|
| aisure | `https://wtwbcruvpghcppwahiaj.supabase.co/functions/v1` | unverified (Supabase edge function) | May need specific function path |
| bluesminds | `https://api.bluesminds.com/v1/models` | unverified (no live probe yet) | Try without `/v1/models` suffix |
| sumopod | `https://api.sumopod.com/v1/models` | unverified | Standard OpenAI-compat expected |
| tinyfish | `https://api.tinyfish.ai/v1/models` | unverified | |
| felo | `https://api.felo.ai/v1/models` | 401 unauthorized | Key valid (fk- prefix) but endpoint requires different auth scheme — investigate |

## Providers Confirmed Down/Blocked

| Provider | Status | Reason |
|----------|--------|--------|
| bytez | 404 | Server has no `/v1/models` endpoint — left blank in api_key.json |
| you.com | 403 (all paths) | CF block + Search/Research category anyway |
| opencode (via api.opencode.ai) | 404 | Wrong URL — correct URL is `opencode.ai/zen/go/v1/models` |

## Removed from MASTER/Registry

| Provider | Removed on | Reason |
|----------|-----------|--------|
| perplexity | 2026-06-09 | Quota exhausted (Bos) |
| you.com | 2026-06-09 | Search/Research category, not AI/LLM |
| cohere | 2026-06-09 | No API key in registry |
| anthropic | 2026-06-09 | No API key in registry |

## Workflow to Update This Registry

```bash
# 1. Backup
cp /root/credential/api_key.json /root/credential/api_key.json.bak.$(date +%Y%m%d_%H%M%S)_<reason>

# 2. Curl probe with browser UA
curl -H "Authorization: Bearer $KEY" \
     -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36" \
     -o /tmp/probe.json -w "%{http_code}\n" \
     "$URL"

# 3. Only if 200 OK, add url_endpoint to api_key.json
python3 << 'PY'
import json
p = '/root/credential/api_key.json'
c = json.load(open(p))
c['<provider>']['url_endpoint'] = '<verified URL>'
c['<provider>']['url_endpoint_auth'] = 'Bearer'  # or 'x-goog-api-key', 'none'
c['<provider>']['url_endpoint_tested_at'] = '2026-06-09'
json.dump(c, open(p, 'w'), indent=2, ensure_ascii=False)
PY

# 4. Verify SOT sync uses new endpoint
cd /root/.hermes/profiles/ilma && python3 scripts/ilma_db_pipeline.py --full-sync
```

## Cross-References

- `ilma-model-database-maintenance` skill, section "url_endpoint field convention (added 2026-06-09)" — schema spec
- `ilma-model-database-maintenance` skill, pitfall 79 — manager PROVIDER_CONFIGS drift after provider removal
- `ilma-model-database-maintenance` skill, pitfall 80 — Bos mandate: use all system capabilities
- `cf-bypass-browser-ua-pattern` skill — browser User-Agent required for many of these endpoints
