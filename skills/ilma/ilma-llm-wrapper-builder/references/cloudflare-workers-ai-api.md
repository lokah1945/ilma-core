# Cloudflare Workers AI API Reference

## Endpoints

### OpenAI-Compatible (recommended for standard chat)

```
POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions
POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/embeddings
```

- Standard OpenAI `chat.completion` request/response shape
- Auth: `Authorization: Bearer {api_token}`
- Does NOT return `reasoning_content` in standard mode

### Native Run (supports reasoning_content)

```
POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/publisher/model-name
```

**Request body:**
```json
{
  "messages": [{"role": "user", "content": "..."}],
  "stream": false,
  "max_tokens": 512
}
```

**Response shape (non-streaming):**
```json
{
  "success": true,
  "result": {
    "response": "Hello! How can I help you today?",
    "reasoning_content": "1. Analyze the input...\n2. Determine the output...\n3. ...",
    "usage": {
      "prompt_tokens": 13,
      "completion_tokens": 317,
      "total_tokens": 330
    }
  },
  "errors": [],
  "messages": []
}
```

**Key fields:**
- `result.response` — Final assistant answer (string)
- `result.reasoning_content` — Chain-of-thought / thinking (string, only on reasoning models)
- `result.usage` — Token counts

### Model Catalog

```
GET https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search
```

Returns `{result: [{id: "model-uuid", name: "..."}]}`. IDs may be UUIDs — supplement with curated list.

## Known Active Models (2026-06-23)

### Flagship
- `@cf/zai-org/glm-5.2` — Reasoning + function calling + code
- `@cf/openai/gpt-oss-120b` — Reasoning + function calling
- `@cf/moonshotai/kimi-k2.7-code` — Vision + reasoning + code

### Fast
- `@cf/z-ai/glm-4.7-flash` — 131K context, function calling

### Reasoning
- `@cf/qwen/qwq-32b`
- `@cf/deepseek/deepseek-r1-distill-qwen-32b`

### Code
- `@cf/qwen/qwen2.5-coder-32b-instruct`

### Vision
- `@cf/meta/llama-3.2-11b-vision-instruct`
- `@cf/google/gemma-4-26b-a4b-it`

### Embedding
- `@cf/baai/bge-large-en-v1.5`

## Rate Limits (Free Tier)

- ~50 RPM per account (observed)
- Per-model limits exist (classified via two-tier RL)
- `Retry-After` header may be present on 429

## Native → OpenAI Conversion

The wrapper auto-converts native `/ai/run/` responses to OpenAI format:

```python
# Native response → OpenAI shape
{
    "id": "cf-{timestamp_ms}",
    "object": "chat.completion",
    "model": "@cf/zai-org/glm-5.2",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "...",
            "reasoning_content": "..."  # PRESERVED from native
        },
        "finish_reason": "stop"
    }],
    "usage": {"prompt_tokens": N, "completion_tokens": M, "total_tokens": N+M}
}
```

## Wrapper Instance

- **Service**: `wrapper-cloudflare.service`
- **Port**: 9104
- **Config path**: `/root/wrapper/cloudflare/`
- **MongoDB collection**: `credentials.llm_providers` (filter: `provider=cloudflare_ai`)
- **Account ID field**: `account_id` in MongoDB doc, or extracted from `last_valid_evidence` regex

## Verified E2E (2026-06-23)

```
curl http://127.0.0.1:9104/ai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"@cf/zai-org/glm-5.2","messages":[{"role":"user","content":"Hallo"}],"stream":false}'

→ HTTP 200, content="Hallo! Wie kann ich dir heute helfen?",
  reasoning_content=5-step chain-of-thought, total_tokens=181
```
