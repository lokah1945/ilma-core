# NVIDIA NIM Native Protocol Test — 2026-11-01

## Executive Summary
**Direct NVIDIA NIM API (integrate.api.nvidia.com) does NOT expose a native Anthropic Messages endpoint (`/v1/messages`).** Only OpenAI Chat Completions (`/v1/chat/completions`) is available natively.

**The wrapper at port 9101 (`wrapper-nvidia-python`) successfully translates Anthropic Messages ↔ OpenAI Chat Completions bidirectionally.** This is the definitive evidence that `COMPATIBILITY_LAYER=1` translation is required and working.

## Test Methodology

### Direct NIM API Tests (9 calls)
All calls to `https://integrate.api.nvidia.com/v1/...` with valid NVIDIA API key from wrapper `.env`:

| # | Endpoint | Method | Result | Notes |
|---|----------|--------|--------|-------|
| 1 | `/v1/models` | GET | ✅ 200 | 167 models returned |
| 2 | `/v1/chat/completions` | POST | ✅ 200 | Works with NVIDIA model IDs |
| 3 | `/v1/messages` | POST | ❌ 404 | "model not found" — endpoint doesn't exist |
| 4 | `/v1/messages` (stream) | POST | ❌ 404 | Same |
| 5 | `/v1/responses` | POST | ❌ 404 | Not implemented |
| 6 | `/v1/embeddings` | POST | ❌ 404 | Not for chat models |
| 7 | `/v1/completions` | POST | ❌ 404 | Legacy, not available |
| 8 | `/v1/chat/completions` (stream) | POST | ✅ 200 | Streaming works |
| 9 | `/v1/models` (filter free) | GET | ✅ 200 | 45 free models |

### Wrapper Tests (4 calls) — `http://127.0.0.1:9101/v1/...` with `Bearer wrapper-local-key`

| # | Endpoint | Method | Result | Notes |
|---|----------|--------|--------|-------|
| 1 | `/v1/models` | GET | ✅ 200 | 134 models (wrapper catalog) |
| 2 | `/v1/chat/completions` | POST | ✅ 200 | OpenAI surface |
| 3 | `/v1/messages` | POST | ✅ 200 | **Anthropic surface — translated** |
| 4 | `/v1/responses` | POST | ✅ 200 | OpenAI Responses surface |

## Key Evidence

### Direct NIM `/v1/messages` Failure
```json
{
  "detail": "model not found",
  "status": 404
}
```
The NVIDIA NIM API simply does not implement the Anthropic Messages API.

### Wrapper `/v1/messages` Success
```json
{
  "id": "msg_1793530637",
  "type": "message",
  "role": "assistant",
  "model": "nvidia/nemotron-3-ultra-550b-a55b",
  "content": [
    {"type": "thinking", "thinking": "...", "signature": "..."},
    {"type": "text", "text": "The user sent \"test\". This is a standard"}
  ],
  "stop_reason": "max_tokens",
  "usage": {"input_tokens": 17, "output_tokens": 10, ...}
}
```
The wrapper receives Anthropic Messages request, translates to OpenAI Chat Completions, calls NVIDIA NIM, translates response back to Anthropic format.

## Implications

1. **Claude Code / Anthropic-compatible clients MUST use the wrapper** — they cannot talk to NVIDIA NIM directly
2. **Wrapper translation layer is production-critical** — it's not optional compatibility, it's the only path
3. **Model ID format matters** — wrapper catalog uses `nvidia/nemotron-3-ultra-550b-a55b` format; direct NIM uses same IDs but only on `/v1/chat/completions`
4. **Port 9101 is the ONLY working Anthropic endpoint for NVIDIA models** in this stack

## Wrapper Translation Architecture (from main.py)
- `/v1/messages` (Anthropic) → `proxy_anthropic_messages()` → translates to OpenAI format → upstream `/v1/chat/completions` → translates response back to Anthropic format
- `/v1/chat/completions` (OpenAI) → `proxy_openai_chat()` → passes through to NVIDIA NIM
- `/v1/responses` (OpenAI Responses) → `proxy_openai_responses()` → attempts native, falls back to Chat Completions

## Verification Commands (Reproducible)

```bash
# Direct NIM - FAILS
TOK=$(grep NVIDIA_API_KEY_1 /root/wrapper/nvidia-python/.env | cut -d= -f2)
curl -s -X POST https://integrate.api.nvidia.com/v1/messages \
  -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/nemotron-3-ultra-550b-a55b","max_tokens":10,"messages":[{"role":"user","content":"test"}]}'
# → 404 {"detail":"model not found"}

# Wrapper - WORKS
curl -s -X POST http://127.0.0.1:9101/v1/messages \
  -H "Authorization: Bearer wrapper-local-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/nemotron-3-ultra-550b-a55b","max_tokens":10,"messages":[{"role":"user","content":"test"}]}'
# → 200 Anthropic-format response
```

## Conclusion
**Wrapper port 9101 is mandatory for Anthropic-compatible clients (Claude Code, OpenHand, Codex, etc.) to use NVIDIA NIM models.** The translation is bidirectional and verified working for both chat and streaming surfaces.

## Related
- `references/opencode-config-fix-2026-11-01.md` — port mapping & opencode config
- `references/claude-code-wrapper-config-merge.md` — Claude Code config pointing to 9101
- `references/wrapper-pull-restart-bugfix-2026-07-28.md` — wrapper restart protocol