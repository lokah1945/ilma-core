# Coarena API Quirks & Behaviors

## Endpoint Mapping
| Client Format | Coarena Endpoint | Notes |
|---------------|------------------|-------|
| OpenAI Chat | `POST /api/v1/chat/completions` | Works, streaming supported |
| OpenAI Responses | `POST /api/v1/responses` | Works |
| Anthropic Messages | `POST /api/v1/messages` | **NOT** `/api/messages` |
| Models List | `GET /api/v1/models` | Returns 18 models |

## Critical: `/api/messages` vs `/api/v1/messages`
- **`/api/messages`** → Returns HTML 404 page (Next.js "Page not found")
- **`/api/v1/messages`** → Returns valid Anthropic-format JSON response

This is because Coarena's website and API are on the same domain. The `/api` path without version serves the website, while `/api/v1` serves the actual API.

## Model Status (tested 2026-11-12)

### Working (18/18 non-streaming)
- claude-fable-5, claude-fable-5-1, claude-fable-5-2
- claude-sonnet-5-5, claude-haiku-5-5, claude-opus-5-5
- deepseek-v4-1-flash-1017
- gemini-4-argon, gemini-4-carbon (needs higher max_tokens for reasoning)
- gemini-3-8-flash → returns `null` content
- grok-4-7
- hy4 → returns `null` content with reasoning; needs more tokens
- kimi-k3, kimi-k3-1-pro
- minimax-m3-1-flash
- qwen3-8-2-4t-a95b
- glm-5-3-flash

### Not Working
- mimo-v2-6-pro → "Model not found"

## Streaming Behavior
- Direct API call: Works, returns SSE with reasoning tokens
- Via wrapper proxy: Upstream closes connection mid-stream (`aiohttp.client_exceptions.ClientConnectionError: Connection closed`)
- Root cause: Coarena's streaming may use connection pooling or timeout that conflicts with proxy

## Rate Limits (Free Tier)
- $5/day model usage
- 30 requests/minute
- 2 concurrent requests
- Upgrade via `POST /api/v1/limits/requests {"usd_per_day": 10}`

## Error Format
- OpenAI endpoints: OpenAI error shape
- Anthropic `/messages` endpoint: Anthropic error shape
- HTML pages returned for unsupported routes (not JSON errors)

## API Key Format
- Prefix: `coa_`
- Example: `coa_9e439d1dda15b41db111d2c44d3c7191`
- Header: `Authorization: Bearer <key>`