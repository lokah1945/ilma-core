---
name: ilma-api-server
description: Hermes API Server — OpenAI-compatible HTTP endpoint for connecting any frontend (Open WebUI, LobeChat, LibreChat) to ILMA. POST /v1/chat/completions and /v1/responses endpoints. SSS Tier.
version: 1.0.0
category: integration
platforms:
  - linux
  - macos
metadata:
  hermes:
    tags: [api, openai, http, open-webui, frontend, endpoints]
    category: integration
---

# ILMA API Server — OpenAI-Compatible HTTP API

## What is the API Server?

Hermes API Server exposes the agent as an OpenAI-compatible HTTP endpoint. Any frontend that speaks OpenAI format can connect to Hermes and use it as a backend.

```
Frontend (Open WebUI, LobeChat, etc.)
        ↓ HTTP
API Server (port 8642)
        ↓
ILMA (full toolset)
        ↓
Response
```

## Quick Start

### 1. Enable API Server

```bash
# Add to ~/.hermes/.env
API_SERVER_ENABLED=true
API_SERVER_KEY=change-me-local-dev

# Optional CORS for browser access
# API_SERVER_CORS_ORIGINS=http://localhost:3000
```

### 2. Start Gateway

```bash
hermes gateway
# Shows: [API Server] API server listening on http://127.0.0.1:8642
```

### 3. Connect Frontend

Point any OpenAI-compatible client at:
```
http://localhost:8642/v1
```

Test with curl:
```bash
curl http://localhost:8642/v1/chat/completions \
  -H "Authorization: Bearer change-me-local-dev" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "hermes-agent",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Endpoints

### POST /v1/chat/completions

Standard OpenAI Chat Completions format. Stateless — full conversation in `messages` array.

**Request:**
```json
{
  "model": "hermes-agent",
  "messages": [
    {"role": "system", "content": "You are a Python expert."},
    {"role": "user", "content": "Write a fibonacci function"}
  ],
  "stream": false
}
```

**Response:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1710000000,
  "model": "hermes-agent",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "Here's a fibonacci function..."},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 50, "completion_tokens": 200, "total_tokens": 250}
}
```

**Image Input** — user messages can send `content` as array of `text` and `image_url`:
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "What is in this image?"},
    {"type": "image_url", "image_url": {"url": "https://example.com/cat.png", "detail": "high"}}
  ]
}
```

**Streaming** (`"stream": true`): SSE with token-by-token chunks + `hermes.tool_progress` events.

### POST /v1/responses

OpenAI Responses API format. Supports **server-side conversation state** via `previous_response_id`.

**Request:**
```json
{
  "model": "hermes-agent",
  "input": "What files are in my project?",
  "instructions": "You are a helpful coding assistant.",
  "store": true
}
```

**Response:**
```json
{
  "id": "resp_abc123",
  "object": "response",
  "status": "completed",
  "model": "hermes-agent",
  "output": [
    {"type": "function_call", "name": "terminal", "arguments": "{\"command\": \"ls\"}", "call_id": "call_1"},
    {"type": "function_call_output", "call_id": "call_1", "output": "README.md src/ tests/"},
    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Your project has..."}]}
  ],
  "usage": {"input_tokens": 50, "output_tokens": 200, "total_tokens": 250}
}
```

**Multi-turn with `previous_response_id`:**
```json
{"input": "Now show me the README", "previous_response_id": "resp_abc123"}
```
Full conversation (tool calls + results) preserved across turns.

**Named conversations:**
```json
{"input": "Hello", "conversation": "my-project"}
{"input": "What's in src/?", "conversation": "my-project"}
{"input": "Run the tests", "conversation": "my-project"}
```
Server chains to latest response in that conversation.

### GET /v1/responses/{id}
Retrieve stored response by ID.

### DELETE /v1/responses/{id}
Delete stored response.

### GET /v1/models
Lists agent as available model. Model name = profile name (or `hermes-agent` for default).

### GET /v1/capabilities
Machine-readable description of API server's stable surface.

## Tool Progress in Streams

**Chat Completions**: Hermes emits `event: hermes.tool_progress` for tool-start visibility (doesn't pollute persisted text).

**Responses**: Hermes emits `function_call` and `function_call_output` output items during SSE stream.

## ILMA API Server Integration Pattern

For ILMA to expose API server:

```python
# In ilma_api_server.py (future implementation)
# FastAPI or Starlette-based OpenAI-compatible server
# - /v1/chat/completions (stateless, OpenAI format)
# - /v1/responses (stateful with response_id chaining)
# - /v1/models (model discovery)
# - /v1/capabilities (capability discovery)
# - CORS support for browser frontends
# - Auth via API_SERVER_KEY
```

## Frontend Integration Examples

| Frontend | Integration |
|----------|-------------|
| Open WebUI | Point to `http://localhost:8642/v1` with Bearer token |
| LobeChat | Add custom OpenAI-compatible endpoint |
| LibreChat | Add custom AI endpoint |
| ChatBox | Use OpenAI API format |

## Security Considerations

1. **API Key authentication** — `API_SERVER_KEY` must be strong
2. **CORS** — Only allow trusted origins in `API_SERVER_CORS_ORIGINS`
3. **Rate limiting** — Consider adding rate limiting middleware
4. **Tool access** — API server exposes full ILMA toolset — ensure trust level

## Streaming Architecture

```
Client → POST /v1/chat/completions (stream: true)
         ↓
    ILMA processes request
         ↓
    For each token: SSE chunk → client
    For each tool start: hermes.tool_progress event → client
         ↓
    Final response + usage stats
```

## Benefits for ILMA

1. **Universal frontend support** — any OpenAI-compatible UI works
2. **Stateful conversations** — `/v1/responses` with previous_response_id
3. **Named conversations** — conversation parameter for session management
4. **Streaming** — real-time tool progress visible to users
5. **Image input** — vision via inline image_url

---

*Hermes v0.13.0 — API Server feature*
*Integrated into ILMA v3.3*