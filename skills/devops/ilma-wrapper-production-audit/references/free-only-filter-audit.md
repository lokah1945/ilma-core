# FREE_ONLY Filter Audit (2026-07-29)

## Summary
After comprehensive curl testing of all wrappers with "hallo" prompts, discovered critical inconsistencies in the `FREE_ONLY` and `FREE_MODEL_ALLOWLIST` settings across wrapper services.

## Actual .env Settings (Verified via grep)

| Wrapper | Port | FREE_ONLY | FREE_MODEL_ALLOWLIST | Impact |
|---------|------|-----------|---------------------|--------|
| nvidia-python | 9101 | ❌ Not set | — | ✅ Working (NVIDIA NIM is free by default) |
| opencode | 9103 | ✅ `FREE_ONLY=yes` | `big-pickle` | ⚠️ Only 1 model allowed |
| nous | 9102 | ✅ `FREE_ONLY=yes` | *(empty)* | ❌ Blocks ALL models |
| blackbox | 9104 | ✅ `FREE_ONLY=yes` | `blackboxai/nvidia/nemotron-nano-12b-v2-vl` | ⚠️ Only 1 model allowed |
| openrouter | 9106 | ✅ `FREE_ONLY=yes` | *(empty)* | ❌ Blocks ALL models |

## Test Results

| Wrapper | Model Used | Result |
|---------|------------|--------|
| NVIDIA (9101) | `deepseek-ai/deepseek-v4-flash` | ✅ "Hallo! Wie kann ich dir helfen?" |
| Nous (9102) | `poolside/laguna-s-2.1:free` | ✅ "Hallo! Wie kann ich Ihnen helfen?" |
| OpenCode (9103) | `laguna-s-2.1-free` | ✅ "Hallo! Wie kann ich Ihnen helfen?" |
| Blackbox (9104) | `blackboxai/nvidia/nemotron-nano-12b-v2-vl` | ✅ "Hallo! 😊 Wie kann ich dir heute helfen?" |
| OpenRouter (9106) | `poolside/laguna-s-2.1:free` | ✅ "Hello! How can I assist you today?" |

## Root Cause Analysis

**Pitfall:** Empty `FREE_MODEL_ALLOWLIST` blocks ALL models when `FREE_ONLY=yes`.

The wrappers use a two-tier filter:
1. `FREE_ONLY=yes` enables the filter
2. `FREE_MODEL_ALLOWLIST` specifies which models are permitted

When `FREE_MODEL_ALLOWLIST` is empty, NO models pass the filter, even if they are free.

## Audit Command

```bash
cd /root/wrapper
grep -E "^FREE_ONLY|^FREE_MODEL_ALLOWLIST" */.env
```

## Recommended Fixes

### Option 1: Disable FREE_ONLY (simplest)
```bash
# In each .env, set:
FREE_ONLY=no
```

### Option 2: Populate FREE_MODEL_ALLOWLIST
For each wrapper, list all available free models:

```bash
# OpenCode - discover all free models first
curl -s http://127.0.0.1:9103/v1/models | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(','.join([m['id'] for m in d.get('data',[]) if 'free' in m['id'].lower()]))
"

# Then add to .env:
FREE_MODEL_ALLOWLIST=<comma-separated-list>
```

### Option 3: Remove FREE_ONLY and rely on provider-level filtering
Since most providers have free tiers built-in, remove the wrapper-level restriction and use provider-native free model selection.

## Verification After Fix

```bash
# Test each wrapper with a simple "hallo"
for port in 9101 9102 9103 9104 9106; do
  echo "=== Port $port ==="
  curl -s -m 10 -X POST http://127.0.0.1:$port/v1/chat/completions \
    -H "Content-Type: application/json" -H "Authorization: Bearer wrapper-local-key" \
    -d '{"model":"<known-free-model>","messages":[{"role":"user","content":"hallo"}],"max_tokens":20}'
done
```

## Related
- Skill: `ilma-wrapper-production-audit`
- Reference: `references/smoke-and-load-targets.md`