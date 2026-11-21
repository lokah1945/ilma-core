# OpenCode Protocol Reverse Engineering (2026-11-20)

## Objective
Reverse-engineer the OpenCode CLI communication protocol to enable wrapper-opencode to proxy through the local OpenCode service without CLI overhead.

## Tools Used
- `curl` with `-v` for endpoint discovery
- Local service inspection at `http://127.0.0.1:49374`
- Basic Auth credentials from `~/.config/opencode/service.json`

## Discovered Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/model` | GET | Basic | Model catalog (full) |
| `/api/v1/models` | GET | Basic | Model catalog (alternate) |
| `/api/session` | POST | Basic | Create new session |
| `/api/session/{id}/prompt` | POST | Basic | Send user message |
| `/api/session/{id}/wait` | POST | Basic | Wait for completion (deprecated?) |
| `/api/event?session={id}` | GET | Basic | Stream events (SSE) |
| `/api/session/{id}/message` | GET | Basic | Fetch messages |
| `/api/session/{id}` | GET | Basic | Fetch session info |

## Session Creation Protocol

```http
POST /api/session
Authorization: Basic base64(opencode:password)
Content-Type: application/json

{
  "model": {"providerID": "opencode", "id": "tidepool-alpha-free"},
  "location": {"directory": "/root/wrapper/opencode"}
}

Response: {"data": {"id": "ses_xxx", "projectID": "...", "model": {...}, "cost": 0, ...}}
```

## Message Send Protocol

```http
POST /api/session/{session_id}/prompt
Authorization: Basic base64(opencode:password)
Content-Type: application/json

{
  "id": "msg_1795118723495",
  "text": "hi",
  "files": [],
  "delivery": "steer"
}

Response: {"data": {"id": "msg_...", "sessionID": "...", "type": "user", "payload": {"text": "hi"}, "delivery": "steer"}}
```

## Event Stream Protocol (SSE)

```
GET /api/event?session={session_id}
Authorization: Basic base64(opencode:password)
Accept: text/event-stream

data: {"id":"evt_...","type":"server.connected","data":{}}
: heartbeat
data: {"id":"evt_...","type":"session.step.started","data":{...}}
data: {"id":"evt_...","type":"session.step.first-token","data":{...}}
data: {"id":"evt_...","type":"session.text.started","data":{...}}
data: {"id":"evt_...","type":"session.text.delta","data":{"delta":"Hi!"}}
data: {"id":"evt_...","type":"session.reasoning.started","data":{...}}
data: {"id":"evt_...","type":"session.reasoning.ended","data":{...}}
data: {"id":"evt_...","type":"session.text.ended","data":{"text":"Hi! How can I help you today?"}}
data: {"id":"evt_...","type":"session.step.streamed","data":{...}}
data: {"id":"evt_...","type":"session.step.ended","data":{...}}
```

### Key Event Types for Streaming

| Event Type | Usage |
|------------|-------|
| `session.text.delta` | Content chunks (stream) |
| `session.step.ended` / `session.step.finish` / `session.step.streamed` | Completion signal |

## Response Extraction Protocol

```http
GET /api/session/{session_id}/message?limit=10&order=desc
Authorization: Basic base64(opencode:password)

Response: {"data": [
  {"id":"msg_...","type":"assistant","content":[{"type":"reasoning","text":"..."},{"type":"text","text":"Hi!"}],"finish":"stop"},
  {"id":"msg_...","type":"user","text":"hi"}
]}
```

Extract assistant response from:
- `data[].type == "assistant"`
- `content[].type == "text"`
- Use `content[].text`

## Authentication

- **Type**: HTTP Basic Auth
- **Username**: `opencode` (fixed)
- **Password**: From `~/.config/opencode/service.json` → `service.password`
- **Format**: `Authorization: Basic base64(opencode:password)`

## Model Names

- **CLI format**: `opencode/tidepool-alpha-free` (with prefix)
- **Service format**: `tidepool-alpha-free` (bare ID)
- Wrapper must strip `opencode/` prefix when calling service

## Key Differences: CLI vs Upstream Zen API

| Aspect | Upstream Zen API | Local Service |
|--------|------------------|---------------|
| Auth | Bearer API keys | Basic Auth |
| Base URL | `https://opencode.ai/zen/v1` | `http://127.0.0.1:49374` |
| Chat endpoint | `POST /chat/completions` | Session + prompt + event stream |
| Models | `GET /models` | `GET /api/model` |
| Model prefix | `opencode/model-name` | `model-name` |
| Streaming | Direct SSE | Event stream via `/api/event` |

## Implementation in wrapper-opencode

The wrapper implements a proxy that:
1. Accepts OpenAI/Anthropic SDK requests on port 9104
2. Creates session with local service
3. Sends user message
4. Streams events (streaming) or waits + fetches messages (non-streaming)
5. Returns standard OpenAI/Anthropic format

## Files Modified

- `/root/wrapper/opencode/src/main.py` — CLI mode implementation
- `/root/wrapper/opencode/.env` — CLI mode configuration
- `/root/wrapper/opencode/README.md` — CLI mode documentation
- `/root/wrapper/opencode/.env.example` — CLI mode config example

## Lessons Learned

1. **Local service is the gateway** — CLI talks to local service, not directly to upstream
2. **Session-based protocol** — Unlike stateless upstream, service uses sessions
3. **Event-driven streaming** — Multiple event types, must handle all completion signals
4. **Basic Auth, not Bearer** — Different auth scheme from upstream
4. **Model ID mapping** — Prefix stripping required
5. **Service must be running** — `opencode serve --service` before wrapper starts