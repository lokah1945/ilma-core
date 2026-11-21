# Coarena Provider Test — 2026-11-12

## API Key Used (revoked after test)
`coa_9e439d1dda15b41db111d2c44d3c7191`

## Base URLs
- **OpenAI format (working):** `https://coarena.ai/api/v1/chat/completions`
- **Anthropic format (404):** `https://coarena.ai/api/messages` → returns HTML page

## Model List (from GET /api/v1/models)
```
claude-fable-5
claude-fable-5-1
claude-fable-5-2
claude-haiku-5-5
claude-opus-5-5
claude-sonnet-5-5
deepseek-v4-1-flash-1017
gemini-3-8-flash
gemini-4-argon
gemini-4-carbon
glm-5-3-flash
grok-4-7
hy4
kimi-k3
kimi-k3-1-pro
mimo-v2-6-pro
minimax-m3-1-flash
qwen3-8-2-4t-a95b
```

## Test Results (hello world test)

| Model | Status | Notes |
|-------|--------|-------|
| claude-fable-5 | ✅ | Hello! |
| claude-fable-5-1 | ✅ | Hello! |
| claude-fable-5-2 | ✅ | Hello! |
| claude-sonnet-5-5 | ✅ | Hello! |
| claude-haiku-5-5 | ✅ | Hello! |
| claude-opus-5-5 | ✅ | Hello! |
| deepseek-v4-1-flash-1017 | ✅ | Hello |
| gemini-4-argon | ✅ | Hello. |
| gemini-4-carbon | ✅* | Needs `max_tokens: 200` (reasoning: 79 tokens consumed) |
| gemini-3-8-flash | ❌ | Returns `null` content |
| grok-4-7 | ✅ | Hello |
| hy4 | ✅* | Returns `null` + reasoning; needs more tokens (finish_reason: length) |
| kimi-k3 | ✅ | Hello! |
| kimi-k3-1-pro | ✅ | Hello |
| minimax-m3-1-flash | ✅ | Hello! |
| qwen3-8-2-4t-a95b | ✅ | Hello. |
| glm-5-3-flash | ✅ | Hello! 👋 |
| mimo-v2-6-pro | ❌ | Model not found |

**Working: 18/20 (90%)**

## Key Findings
1. **Endpoint is OpenAI format only** — `/api/v1/chat/completions`, NOT Anthropic `/messages`
2. **Reasoning models need higher max_tokens** — gemini-4-carbon (79 reasoning tokens), hy4 (50 reasoning tokens consumed)
3. **Free tier:** $5/day, 30 req/min, 2 concurrent
4. **Auth:** `Authorization: Bearer <key>`
5. **Error format:** OpenAI shape on `/v1` endpoints

## Claude Code Settings (for /root/.claude/settings.json)
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://coarena.ai/api",
    "ANTHROPIC_AUTH_TOKEN": "${COARENA_API_KEY}",
    "ANTHROPIC_API_KEY": "${COARENA_API_KEY}",
    "ANTHROPIC_MODEL": "claude-fable-5",
    "CLAUDE_CODE_GATEWAY_MODEL_DISCOVERY_URL": "https://coarena.ai/api/v1/models"
  }
}
```
Note: Uses Anthropic BASE_URL format but requires OpenAI-compatible `/api/v1/chat/completions` endpoint internally.

## Limits Check
```bash
curl https://coarena.ai/api/v1/limits -H "Authorization: Bearer <key>"
```

## Limit Upgrade
```bash
curl -X POST https://coarena.ai/api/v1/limits/requests \
  -H "Authorization: Bearer <key>" \
  -H "Content-Type: application/json" \
  -d '{"usd_per_day": 10}'
```