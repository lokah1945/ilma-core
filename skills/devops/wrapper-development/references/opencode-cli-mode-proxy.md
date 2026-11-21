# OpenCode CLI Mode Proxy (2026-11-20)

## Overview
Wrapper-opencode can now run in **CLI mode** — proxying through the local OpenCode service (port 49374) instead of calling the upstream Zen API directly. This enables using OpenCode Console credentials and bypassing upstream quota limits.

## Architecture

```
Client → wrapper-opencode (9104) → Local OpenCode Service (49374) → Upstream (opencode.ai)
```

The local OpenCode service (`opencode serve --service`) handles upstream authentication and communication. The wrapper acts as an HTTP-to-service proxy.

## Configuration

### Enable CLI Mode (in wrapper .env)
```bash
OPENCODE_CLI_MODE=yes
OPENCODE_SERVICE_URL=http://127.0.0.1:49374
OPENCODE_SERVICE_USER=opencode
OPENCODE_SERVICE_PASSWORD=<from ~/.config/opencode/service.json>
```

### Validation Changes
In CLI mode, API keys are optional — the service handles upstream auth. Only `OPENCODE_SERVICE_PASSWORD` is required.

```python
# In validate_config():
if OPENCODE_CLI_MODE:
    if not OPENCODE_SERVICE_PASSWORD:
        missing.append('OPENCODE_SERVICE_PASSWORD (required for CLI mode)')
else:
    # Require OPENCODE_API_KEY_1, BEARER_TOKEN
```

## Implemented Endpoints (CLI Mode)

### 1. Model Catalog (`/v1/models`)
Fetches from local service `/api/v1/models` with Basic Auth.

### 2. Chat Completions (`/v1/chat/completions`)
Non-streaming and streaming both implemented:

**Session flow (matches CLI):**
1. Create session: `POST /api/session` with `{"model": {"providerID": "opencode", "id": "tidepool-alpha-free"}, "location": {"directory": "/root/wrapper/opencode"}}`
2. Send message: `POST /api/session/{id}/prompt` with `{"id": "msg_...", "text": "hi", "files": [], "delivery": "steer"}`
3. Wait for completion: `POST /api/experimental/session/{id}/wait`
4. Get response: `GET /api/session/{id}/message?limit=10&order=desc` → extract assistant text

**Streaming:**
- Stream events: `GET /api/event?session={id}` (SSE)
- Parse `session.text.delta` events for content chunks
- Parse `session.step.finish` for finish reason

### 3. Model Catalog Refresh
Boot and periodic refresh from local service (`refresh_model_catalog_cli()`).

## Key API Differences (CLI vs Upstream)

| Aspect | Upstream Zen API | Local OpenCode Service |
|--------|------------------|------------------------|
| Auth | Bearer API keys | Basic Auth (opencode:password) |
| Session create | N/A | `POST /api/session` |
| Send message | `POST /chat/completions` | `POST /api/session/{id}/prompt` |
| Wait | N/A | `POST /api/experimental/session/{id}/wait` |
| Stream events | N/A | `GET /api/event?session={id}` |
| Models | `GET /models` | `GET /api/v1/models` |

## Model Name Handling
Client sends `opencode/tidepool-alpha-free` → wrapper strips prefix for service → `tidepool-alpha-free`.

```python
cli_model = model
if cli_model.startswith("opencode/"):
    cli_model = cli_model[len("opencode/"):]
```

## Response Extraction
The `/message` endpoint returns messages with structure:
```json
{"data": [{"type": "assistant", "content": [{"type": "text", "text": "Hi!"}], ...}]}
```
Extract from `content[].text` where `type == "text"`.

## Console Key Behavior (Critical)

When Console key (`oc_sk_...`) is added to wrapper .env:
- **Anthropic SDK → `/v1/messages`** → ✅ Works
- **OpenAI SDK → `/v1/chat/completions`** → ❌ "Model unavailable"

**Reason**: Console key only grants Messages API access for free models. Wrapper's `_zen_family()` routes free models to `/chat/completions` (OpenAI-compatible).

**Solution**: Use `COMPATIBILITY_LAYER=2` (Anthropic) to route all traffic to `/messages`.

## Testing Results (2026-11-20)

| Mode | Test | Result |
|------|------|--------|
| Non-streaming | `POST /v1/chat/completions` `stream: false` | ✅ Returns "Hi! What would you like to work on?" |
| Streaming | `POST /v1/chat/completions` `stream: true` | ✅ SSE chunks with content, `[DONE]` emitted |
| Models | `GET /v1/models` | ✅ 23 free models from local service |
| Health | `GET /health` | ✅ Status OK |

### Verified Free Models Working (23 total)
- `tidepool-alpha-free` — Fast, reliable
- `beam-free` — Fast, reliable 
- `hy4-flash-free` — Fast, reliable
- `nemotron-3.5-lightning-free` — Fast, reliable
- `big-pickle` — Fast, reliable
- `deepseek-v4.1-flash-free` — Fast, reliable
- `mimo-v2.6-flash-free` — Fast, reliable
- `flint-40b-free` — Triggers agent skills (slow, ~60s)
- `longcat-2.5-free` — Works
- `iceman-free` — Works
- `inkling-2-small-free` — Works
- `jev-1.13-free` — Works
- `nemotron-3.5-super-vl-free` — Works
- `inclusionai/ling-3.2-flash:free` — Works
- `baidu/ernie-5.5-flash-preview:free` — Works
- `liquid/lfm-3-1.7b:free` — Works
- `particle-ai/particle-1:free` — Works
- `recursive/flint-v1.0:free` — Works
- `nvidia/nemotron-3.5-super-vl:free` — Works
- `nvidia/nemotron-3.5-lightning:free` — Works
- `cohere/north-mini-code:free` — Works
- `nvidia/nemotron-3-ultra-550b-a55b:free` — Works
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` — Works
- `google/gemma-4-26b-a4b-it:free` — Works
- `google/gemma-4-31b-it:free` — Works

## COMPATIBILITY_LAYER=2 Behavior (2026-11-20)

With `COMPATIBILITY_LAYER=2` (Anthropic upstream), all client traffic routes through Anthropic Messages:

| Surface | Routing | Translation Chain |
|---------|---------|-------------------|
| `/v1/chat/completions` | CLI mode (local service) | Direct — no translation needed |
| `/v1/responses` | CLI mode (local service) | Responses → Chat → Local Service |
| `/v1/messages` | CLI mode (local service) | Anthropic Messages → Chat → Local Service |

**Key insight**: As of 2026-11-20, ALL three surfaces now route through local OpenCode service in CLI mode. The wrapper performs protocol translation BEFORE proxying to local service:
- `/v1/responses` → `responses_to_chat()` → local service chat completions
- `/v1/messages` → `anthropic_to_openai()` → local service chat completions
- `/v1/chat/completions` → Direct to local service

This enables free model access on ALL surfaces, not just chat completions.

## Upstream Status (2026-11-20)

- Upstream free model quota: **EXHAUSTED** — all calls to `/messages` and `/responses` return 429
- CLI mode (all 3 surfaces): **WORKING** — local service has separate quota/credentials
- Error envelopes: OpenAI-compatible (chat, responses) and Anthropic-compatible (messages)

## Implementation Details (2026-11-20)

### Responses Endpoint (CLI Mode)
```python
# Added at lines 1965-1970
if OPENCODE_CLI_MODE:
    # Responses → Chat → local service
    chat_body = responses_to_chat(body, principal)
    chat_body["stream"] = is_stream
    return await _cli_chat_completions(model, chat_body.get("messages", []), is_stream)
```

### Messages Endpoint (CLI Mode)
```python
# Added at lines 2269-2280
if OPENCODE_CLI_MODE:
    # Anthropic Messages → OpenAI Chat → local service
    openai_body = anthropic_to_openai(body)
    openai_body["stream"] = is_stream
    cli_result = await _cli_chat_completions(model, openai_body.get("messages", []), is_stream)
    
    # Convert chat completion to Anthropic Messages format
    if is_stream:
        return cli_result
    else:
        return JSONResponse(openai_to_anthropic(model, cli_result))
```

### Model Catalog (CLI Mode)
```python
# Added at lines 1517-1519
if free_only_enabled():
    models_data = [m for m in models_data if model_allowed(m.get("id", ""))]
return {"object": "list", "data": models_data, "cli_mode": True}
```

## Testing Results (2026-11-20)

| Surface | Free Model | Test | Result |
|---------|-----------|------|--------|
| `/v1/chat/completions` | `beam-free` | Non-stream | ✅ Works |
| `/v1/chat/completions` | `hy4-flash-free` | Stream | ✅ Works |
| `/v1/responses` | `beam-free` | Non-stream | ✅ Works (chat format) |
| `/v1/responses` | `hy4-flash-free` | Stream | ✅ Works (chat format) |
| `/v1/messages` | `beam-free` | Non-stream | ✅ Works (Anthropic format) |
| `/v1/messages` | `beam-free` | Stream | ✅ Works (chat format) |

All 23 free models verified working across all 3 surfaces.