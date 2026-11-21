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
| Streaming | `POST /v1/chat/completions` `stream: true` | ✅ SSE chunks with content |
| Models | `GET /v1/models` | ✅ 15+ models from local service |
| Health | `GET /health` | ✅ Status OK |

## Pitfalls

1. **Must start local service first**: `opencode serve --service` (port 49374)
2. **Service password changes on restart** — update `.env` after each `opencode serve --service`
3. **Streaming timeout** — non-streaming requests can take 8s+ (waits for full completion)
4. **Model prefix stripping required** — service expects bare model IDs
5. **Session directory** — must match working directory for file operations

## Files Modified
- `/root/wrapper/opencode/src/main.py` — Added CLI mode logic
- `/root/wrapper/opencode/.env` — CLI mode configuration

## Related References
- `references/opencode-cli-integration.md` — CLI usage patterns
- `references/opencode-console-key-wrapper-discrepancy-2026-11-20.md` — Console key routing issue
- `references/opencode-wrapper-audit-2026-11-20.md` — Full audit notes