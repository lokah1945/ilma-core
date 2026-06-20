# Endpoint Discovery Workflow — Class-Level Pattern

Reusable recipe for discovering the correct `/v1/models` (or equivalent) endpoint for any AI/LLM provider.

## When to use

- New provider added to `api_key.json` or `db.llm_providers`
- Existing provider returns 404 / 401 / 403 unexpectedly
- Bos asks to enable a previously-blocked provider
- Cloudflare 403 issues need diagnosis

## The 4-tier investigation

When an endpoint fails, do NOT immediately conclude "blocked" or "key invalid". Run through these tiers:

### Tier 1: Wrong URL (most common, ~50% of failures)

```
1. Search X / web for "<provider> API v1 models endpoint <year>"
2. Check the provider's official docs URL
3. Try regional variants: -intl, .cn, .com, .io
4. Try path variants: /v1/models, /api/v1/models, /api/v3/models, /zen/go/v1/models
5. Try subdomain variants: api., alpha., inference., inference-api., ark.
```

**Examples from 2026-06-09:**
- alibaba: `dashscope.aliyuncs.com` (CN) → `dashscope-intl.aliyuncs.com` (INTL) ✅
- opencode: `api.opencode.ai` (wrong) → `opencode.ai/zen/go/v1/models` ✅
- byteplus: `ark.byteplus.com` (wrong) → `ark.ap-southeast.bytepluses.com` ✅
- bytez: no public `/v1/models` exists → leave blank, log

### Tier 2: Wrong auth header (~20% of failures)

```
1. Try Authorization: Bearer <key>      ← standard
2. Try x-goog-api-key: <key>            ← Google
3. Try X-Api-Key: <key>                 ← Anthropic / some others
4. Try no header (local server)         ← Ollama
5. Parse the 401/403 error message — server often tells you which header it wants
```

**Examples from 2026-06-09:**
- google: Bearer → 401, x-goog-api-key → 200 ✅
- minimax anthropic-compatible: Bearer → "use X-Api-Key field"
- openai/etc: standard Bearer

### Tier 3: CF/IP block (~20% of failures)

**Symptom:** HTTP 403 with body containing "cloudflare" or "Error 1010: Access denied".

**Fix:** Add browser-like User-Agent to ALL requests:

```python
req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
```

One line, 5-second fix. See `cf-bypass-browser-ua-pattern` skill for full details.

### Tier 4: Key invalid / quota (~10% of failures)

**Symptom:** HTTP 401 with "Incorrect API key" or HTTP 429 with "quota".

**Action:**
1. Read fresh key from `api_key.json` (display-masked, use binary read)
2. Compare with `~/.hermes/profiles/ilma/.env` (often has fresh key)
3. If api_key.json stale: backup file, update from .env
4. If quota exhausted (429): remove provider from registry + MASTER per Bos mandate

## The complete probe script

```python
import json
import urllib.request
import urllib.error
from pathlib import Path

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
cred = json.loads(Path("/root/credential/api_key.json").read_text())

def get_key(pdata):
    if isinstance(pdata, dict):
        if "keys" in pdata and isinstance(pdata["keys"], list) and pdata["keys"]:
            return pdata["keys"][0]
        # dict-of-keys pattern (nvidia)
        for k, v in pdata.items():
            if isinstance(v, dict) and v.get("api_key"):
                return v["api_key"]
    return None

def probe(url, key, extra_headers=None):
    try:
        req = urllib.request.Request(url)
        if key and not extra_headers:
            req.add_header("Authorization", f"Bearer {key}")
        req.add_header("User-Agent", BROWSER_UA)
        if extra_headers:
            for hk, hv in extra_headers.items():
                req.add_header(hk, hv)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            count = len(data.get("data", data.get("models", [])))
            if isinstance(data, list):
                count = len(data)
            return ("ok", count, None)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:100].replace("\n", " ")
        return ("fail", e.code, body)
    except Exception as e:
        return ("error", None, str(e))

# Probe
key = get_key(cred["openai"])
status, count, info = probe("https://api.openai.com/v1/models", key)
print(f"openai: {status} {count} {info}")
```

## When to give up

If after all 4 tiers you still get:
- 404: leave `url_endpoint` blank in registry, mark provider as `skip_sync=True` in manager config
- 401 with "key invalid": rotate the key, or remove provider
- 403 with "blocked" despite browser UA: needs proxy, give up
- 429 quota: remove provider from registry

## Reference

- Full verified endpoint table: `references/url-endpoint-registry-2026-06.md`
- CF bypass skill: `cf-bypass-browser-ua-pattern`
- Display masking pitfall: see `SKILL.md` section "Display Masking Pitfall"
