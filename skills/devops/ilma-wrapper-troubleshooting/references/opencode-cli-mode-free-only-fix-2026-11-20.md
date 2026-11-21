# Opencode Wrapper — FREE_ONLY Fix for CLI Mode (2026-11-20)

## Context
Wrapper: `wrapper-opencode` (port 9104, status: pending/frozen per wrappers.json)
Tested by Bos explicitly on 2026-11-20 to verify contract compliance and overhead.

## Architecture
```
Client → wrapper-opencode (9104) → local OpenCode service (49374) → upstream opencode.ai
```
- Auth: Bearer token (wrapper) → Basic Auth (service)
- Model prefix: stripped for local service (`opencode/` → bare)
- Only chat completions uses CLI mode; responses/messages use direct upstream

## FREE_ONLY Fix Applied

### Problem
The CLI mode chat path and models endpoint were not enforcing `FREE_ONLY=yes` filter, allowing paid models to pass through to the local service/upstream.

### Fix Locations (minimal changes ~4 lines each)

**1. CLI chat path** (`src/main.py` line ~1686-1689):
```python
# CLI-compatible mode: proxy through local OpenCode service
if OPENCODE_CLI_MODE:
    try:
        body = await request.json()
    except Exception as e:
        return _jr(400, {"error": {"type": "invalid_request_error", "message": f"Invalid JSON: {e}"}})
    if not isinstance(body, dict):
        return _jr(400, {"error": {"type": "invalid_request_error", "message": "Request body must be a JSON object"}})
    
    model = body.get("model", "")
    messages = body.get("messages", [])
    stream = bool(body.get("stream", False))
    
    # FREE_ONLY check for CLI mode too
    if free_only_enabled() and model and not model_allowed(model):
        return _jr(400, free_only_error(model))
    
    return await _cli_chat_completions(model, messages, stream)
```

**2. CLI models endpoint** (`src/main.py` line ~1517-1519):
```python
if OPENCODE_CLI_MODE:
    try:
        models_data = await _cli_get_models()
        if models_data:
            # Apply FREE_ONLY filter for CLI mode too
            if free_only_enabled():
                models_data = [m for m in models_data if model_allowed(m.get("id", ""))]
            return {"object": "list", "data": models_data, "cli_mode": True}
    except Exception as e:
        logger.warning(f"CLI models failed: {e}")
        # Fall through to normal path
```

### Test Results
- **Free models available**: 23 (filtered from 158 upstream)
- **FREE_ONLY enforced on all 3 surfaces**:
  - `POST /v1/chat/completions` — blocked paid (400), passed free ✅
  - `POST /v1/responses` — blocked paid (400), passed free (upstream 429) ✅
  - `POST /v1/messages` — blocked paid (400), passed free (upstream 429) ✅
  - `GET /v1/models` — returns only 23 free models ✅

### Translation Chain (COMPATIBILITY_LAYER=2)
| Surface | Path | Status |
|---------|------|--------|
| Chat (CLI) | No translation — local service native | Works |
| Responses | Responses→Chat→Anthropic→Chat→Responses | Works (upstream 429) |
| Messages | Chat→Anthropic | Works (upstream 429) |

## Overhead Analysis

### Memory (RSS)
| Process | RSS | Role |
|---------|-----|------|
| wrapper-opencode (9104) | 102 MB | FastAPI proxy |
| opencode serve (49374) | 455 MB | Local service |
| **Total** | **~557 MB** | |

### Latency
| Path | Latency | Notes |
|------|---------|-------|
| Wrapper streaming (TTFT) | **0.5s** | Fast - first token |
| Wrapper non-streaming | **3.0s** | Full round trip |
| Local service full flow | **~3.1s** | Session + prompt + wait + fetch |

**Wrapper overhead ~0-0.5s** (negligible). Bottleneck is local OpenCode service (~3s).

## Key Findings
1. Wrapper code is production-quality — standardized architecture, shared common/ infra
2. CLI mode bypasses upstream quota — uses local service's managed quota
3. Upstream quota exhausted — all free models hit 429 "Free usage limit reached"
4. Error handling correct — returns proper OpenAI/Anthropic error envelopes
5. Only 1 API key configured — no rotation pool (would need multiple OPENCODE_API_KEY_*)

## To Reactivate Fully (requires owner instruction)
1. Add multiple `OPENCODE_API_KEY_*` keys to `.env`
2. Verify upstream quota per key
3. Update `wrappers.json` status → `production`
4. Run client qualification suite (Claude Code, Codex, OpenCode client)

## Risk Notes
- Wrapper remains FROZEN per `wrappers.json` — no deployment changes made
- Responses/messages don't use CLI mode (design choice)
- Local service `opencode serve` must be running separately (not auto-started by wrapper)
- Upstream quota is the limiting factor, not wrapper code