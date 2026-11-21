# AgentRouter API Discovery Reference
## Session: 2026-10-31 — API Key Testing & Model Discovery

---

## Provider Overview

**AgentRouter** (`https://agentrouter.org`) — Unified LLM gateway with free tier for developers. Chinese-origin service (UI in Chinese/English). Dashboard at `https://ps.air-outer.com/console`.

---

## Endpoints & Formats

| Format | Base URL | Endpoints | Auth Header |
|--------|----------|-----------|-------------|
| **Anthropic** | `https://agentrouter.org` (no `/v1`) | `/v1/messages`, `/v1beta/models` | `x-api-key` + `anthropic-version: 2023-06-01` |
| **OpenAI** | `https://agentrouter.org/v1` | `/chat/completions`, `/models`, `/responses`, `/embeddings`, `/images/*`, `/audio/*` | `Authorization: Bearer` |

**⚠️ Critical:** Don't mix formats. Use Anthropic format for Claude Opus series, OpenAI format for everything else.

---

## Model Discovery Methods

### 1. Dashboard (Authoritative Source)
- URL: `https://ps.air-outer.com/console/personal` (requires login)
- Shows **currently active** models with exact names
- Models change dynamically based on resource availability

### 2. Pricing Page (Secondary)
- URL: `https://ps.air-outer.com/pricing` (requires login)
- Shows model list with pricing/limits

### 3. API `/models` Endpoint
- **Requires valid API key** — returns 401 if unauthorized
- OpenAI format: `GET https://agentrouter.org/v1/models` with `Authorization: Bearer`
- Anthropic format: `GET https://agentrouter.org/v1beta/models` with `x-api-key`

### 4. Documentation (Static, May Be Stale)
- `https://agentrouter.org/docs` → Quick Start → tool-specific guides
- Lists models **at time of writing** — verify against dashboard

---

## Known Models (as of docs snapshot 2026-10-31)

| Provider | Models | Formats Supported |
|----------|--------|-------------------|
| OpenAI | `gpt-5.6-sol`, `gpt-6-astra` | OpenAI + Anthropic |
| Anthropic | `claude-opus-5`, `claude-opus-4-8` | Anthropic + OpenAI |
| Zhipu (智谱) | `glm-5.3` | OpenAI + Anthropic |
| Deepseek | `deepseek-v4-flash` | OpenAI + Anthropic |

**Model names must match exactly** (including hyphens) or get 503 "no available channel".

---

## API Key Testing Pattern

```python
import aiohttp

async def test_provider(base_url, api_key, model, format="openai"):
    if format == "openai":
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": [{"role": "user", "content": "test"}], "max_tokens": 10}
    else:  # anthropic
        url = f"{base_url}/v1/messages"
        headers = {"x-api-key": api_key, "Content-Type": "application/json", "anthropic-version": "2023-06-01"}
        payload = {"model": model, "max_tokens": 10, "messages": [{"role": "user", "content": "test"}]}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
            return resp.status, await resp.text()

# Test both formats
await test_provider("https://agentrouter.org/v1", key, "gpt-6-astra", "openai")
await test_provider("https://agentrouter.org", key, "gpt-6-astra", "anthropic")
```

---

## Error Responses

| Status | Meaning | Action |
|--------|---------|--------|
| 401 | Invalid/expired key | Get new key from `console/token` |
| 503 | Model name wrong or model offline | Check dashboard for exact name |
| 429 | Rate limited | Back off, check quota |
| 200 | Success | Key + model valid |

**401 Response Body:**
```json
{"error":{"message":"unauthorized client detected, contact support for assistance at https://discord.gg/HgekCyHJqB"},"message":"UNAUTHENTICATED","success":false,"type":"unauthorized_client_error"}
```

---

## Getting a Valid Key

1. Register at `https://ps.air-outer.com/console` (GitHub/email)
2. Get token at `https://ps.air-outer.com/console/token`
3. Verify models at `https://ps.air-outer.com/console/personal`

---

## Integration Notes for ILMA

- **Free tier exists** but requires registration + active usage
- **Not suitable for automated/unattended use** without valid account
- **Model list is dynamic** — cache with short TTL (5-10 min) or query dashboard
- **Two base URLs** depending on client format — route correctly in provider kernel
- **Discord support:** `https://discord.gg/HgekCyHJqB` for key issues

---

## Related Skills

- `ilma-model-routing` — Provider registration & routing logic
- `ilma-wrapper-fleet-ops` — Managing local wrapper proxies
- `ilma-capability-registry` — Capability ↔ model mapping