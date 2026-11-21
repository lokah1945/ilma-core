# OpenCode Console Key vs Wrapper Discrepancy (2026-11-20)

## Summary
The OpenCode Console key (obtained via `opencode auth export`) works **directly with OpenCode CLI** but **fails through wrapper-opencode** when routing through `/v1/chat/completions` (OpenAI format).

## Root Cause
The Console key is tied to an account that only grants access to **Anthropic Messages API** (`/v1/messages`) for free models — NOT the OpenAI-compatible `/v1/chat/completions` endpoint.

## Evidence

### Works (Direct CLI)
```bash
ANTHROPIC_BASE_URL=https://opencode.ai/zen/v1 \
ANTHROPIC_API_KEY=oc_sk_b535b03411ff_iTNR28vCPb3BZF0I4CHGT11mC2toV784 \
opencode run -m opencode/tidepool-alpha-free "hi"
# ✅ Works - uses Anthropic Messages API directly
```

### Works (CLI → Wrapper via Anthropic)
```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:9104/v1 \
ANTHROPIC_API_KEY=*** \
opencode run -m opencode/tidepool-alpha-free "hi"
# ✅ Works - wrapper routes to /messages
```

### Fails (Wrapper HTTP → OpenAI format)
```bash
curl -X POST http://127.0.0.1:9104/v1/chat/completions \
  -H "Authorization: Bearer ***" \
  -d '{"model": "opencode/tidepool-alpha-free", ...}'
# ❌ "Upstream request failed: Model is unavailable"
```

### Fails (Wrapper HTTP → Anthropic format with same key)
```bash
curl -X POST http://127.0.0.1:9104/v1/messages \
  -H "Authorization: Bearer ***" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model": "opencode/tidepool-alpha-free", ...}'
# ❌ Same error - upstream quota exhausted
```

## Wrapper Configuration Required

### COMPATIBILITY_LAYER=2
```bash
# /root/wrapper/opencode/.env
COMPATIBILITY_LAYER=2  # Anthropic mode - all traffic goes to /messages
```

### Only Console Key
```bash
OPENCODE_API_KEY_1=oc_sk_b535b03411ff_iTNR28vCPb3BZF0I4CHGT11mC2toV784
# Other keys commented out - they don't work with /messages for free models
```

## Free Model Routing with Console Key

The wrapper's `_zen_family()` function routes free models to `chat` (OpenAI format), but Console key needs `messages` (Anthropic format).

### Current Behavior (Wrong for Console Key)
```python
def _zen_family(model: str) -> str:
    if is_free_model(m):
        return 'chat'  # Routes to /chat/completions
```

### Needed Behavior
When using Console key, free models should route to `messages`:
```python
def _zen_family(model: str) -> str:
    if is_free_model(m) and using_console_key():
        return 'messages'  # Route to /v1/messages
```

## Quota Behavior

| Access Path | Quota Bucket |
|-------------|--------------|
| OpenCode CLI direct | Console key's free tier |
| CLI → Wrapper (Anthropic) | Same Console key quota |
| Wrapper HTTP (any) | Wrapper keys' quota (exhausted) |

**Key insight**: The Console key has its OWN free-tier quota. Using both CLI and wrapper drains the SAME quota. The wrapper's 6 keys have THEIR OWN quotas (all exhausted).

## Debugging Recipe

```bash
# 1. Check which key is in .env
cat /root/wrapper/opencode/.env | grep OPENCODE_API_KEY

# 2. Verify COMPATIBILITY_LAYER
grep COMPATIBILITY_LAYER /root/wrapper/opencode/.env

# 3. Test direct upstream with Console key
curl -X POST "https://opencode.ai/zen/v1/messages" \
  -H "Authorization: Bearer oc_sk_..." \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model": "opencode/tidepool-alpha-free", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}'

# 4. Test wrapper routing
curl -X POST http://127.0.0.1:9104/v1/messages \
  -H "Authorization: Bearer wrapper-local-key" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model": "opencode/tidepool-alpha-free", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}'
```

## Risk
- Free tier limits are strict per credential
- Console key quota is shared between CLI and wrapper
- For production, need paid tier or more keys
- Wrapper routing logic needs key-aware model family selection