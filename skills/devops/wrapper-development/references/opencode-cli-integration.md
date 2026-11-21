# OpenCode CLI Integration with wrapper-opencode (2026-11-20)

## Overview
OpenCode CLI (v2.3.2+) can use wrapper-opencode as a drop-in replacement for the official OpenCode API. The wrapper exposes standard Anthropic and OpenAI SDK-compatible endpoints that OpenCode CLI can connect to.

## Configuration

### Anthropic SDK Mode (Claude Code compatible)
```bash
ANTHROPIC_BASE_URL=http://127.0.0.1:9104/v1 \
ANTHROPIC_API_KEY=wrapper-local-key \
opencode run -m opencode/tidepool-alpha-free "Say hello"
```

### OpenAI SDK Mode (Codex compatible)
```bash
OPENAI_BASE_URL=http://127.0.0.1:9104/v1 \
OPENAI_API_KEY=wrapper-local-key \
opencode run -m opencode/beam-free "Say hi"
```

## Model Naming
OpenCode CLI expects models prefixed with `opencode/`:
- `opencode/tidepool-alpha-free`
- `opencode/deepseek-v4.1-flash-free`
- `opencode/mimo-v2.6-flash-free`
- `opencode/beam-free`
- `opencode/nemotron-3.5-lightning-free`

The wrapper strips this prefix internally for upstream routing.

## Verified Working Endpoints (2026-11-20)

| Endpoint | SDK | Tested Models | Result |
|----------|-----|---------------|--------|
| `/v1/messages` | Anthropic | tidepool-alpha-free, deepseek-v4.1-flash-free, mimo-v2.6-flash-free | ✅ |
| `/v1/chat/completions` | OpenAI | beam-free, nemotron-3.5-lightning-free | ✅ |
| `/v1/responses` | OpenAI | Not directly tested via CLI | Should work |

## Key Behaviors

### Free Tier Rate Limits
- OpenCode free tier has strict per-key limits
- 6 real keys in .env → all hit 429 "Free usage limit exceeded" within 12 model tests
- Wrapper correctly returns 429 with proper OpenAI/Anthropic error envelopes
- Model-scoped cooldown: each key blocked per model for 300s

### Model-Specific Quirks
| Model | Behavior |
|-------|----------|
| `flint-40b-free` | Triggers agent skills (task-observer) → 60s timeout |
| `tidepool-alpha-free` | Fast, reliable |
| `deepseek-v4.1-flash-free` | Fast, reliable |
| `mimo-v2.6-flash-free` | Fast, reliable |
| `beam-free` | Fast, reliable |
| `nemotron-3.5-lightning-free` | Fast, reliable |

### Wrapper Architecture Notes
- **FREE_ONLY=yes** enforced in production .env (blocks paid models)
- Dynamic aliases (`sonnet`/`opus`/`haiku`) require `DYNAMIC_ALIAS_TARGET` to be set
- COMPATIBILITY_LAYER=1 (OpenAI compatible) is default
- All 3 surfaces work: chat/completions, responses, messages

## Testing Checklist for Reactivation
- [ ] `/health` returns keys=6, status=ok
- [ ] OpenCode CLI with Anthropic SDK → `/v1/messages` works
- [ ] OpenCode CLI with OpenAI SDK → `/v1/chat/completions` works
- [ ] Free model list: 12 models ending in `-free`
- [ ] Rate limit behavior: 429 after free tier exhausted
- [ ] Streaming: verify SSE works end-to-end

## Key Quota Discovery (2026-11-20)

### OpenCode CLI Stored Credentials ≠ Wrapper .env Keys

| Source | Key Prefix | Quota |
|--------|------------|-------|
| OpenCode CLI (stored in `~/.config/opencode/auth.json`) | `oc_sk_b535b03411ff...` | Your personal OpenCode Console account quota |
| Wrapper .env (6 keys) | `oc_sk_bc96fa9b...`, `oc_sk_eba23d5a...`, etc. | Separate account quotas |

**They do NOT share quotas.** The CLI uses its own stored credential; the wrapper uses its own 6 keys from `.env`. Rate limits are per-API-key, not per-client.

### Verification
```bash
# OpenCode CLI → uses → stored Console credential
opencode run -m opencode/tidepool-alpha-free "hi"  # ✅ Works (your quota)

# Wrapper → uses → its own .env keys
curl -H "Authorization: Bearer ***" http://127.0.0.1:9104/v1/chat/completions  # 429 (their quota)

# To share quota: add Console key to wrapper .env
OPENCODE_API_KEY_1=oc_sk_...V784
```

## Console Key Routing Behavior (2026-11-20)

### Critical Finding: Console Key Only Works with Anthropic SDK

When the OpenCode Console key (`oc_sk_b535b03411ff_iTNR28vCPb3BZF0I4CHGT11mC2toV784`) was added to wrapper .env:

| SDK / Endpoint | Result | Reason |
|----------------|--------|--------|
| Anthropic SDK → `/v1/messages` | ✅ Works | Console key has access to Messages API |
| OpenAI SDK → `/v1/chat/completions` | ❌ "Model unavailable" | Console key's account lacks OpenAI-compatible access for free models |

**Implication**: If wrapper uses Console key, clients **must use Anthropic SDK** (`/v1/messages`). OpenAI SDK (`/v1/chat/completions`) will fail with "Model unavailable" even though the model exists in catalog.

### Routing Logic Impact
The wrapper routes free models to `/chat/completions` by default (see `_zen_family()` returning `'chat'` for free models). With Console key, this routing fails. Solutions:

1. **Force Anthropic SDK** — Clients use `ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY`
2. **Modify routing** — Detect Console key and route to `/messages` endpoint (breaks multi-key rotation assumption)
3. **Use OpenRouter/NVIDIA keys** for OpenAI-compatible access

### Recommendation
For production with Console key: document that clients MUST use Anthropic SDK. Update wrapper README with SDK compatibility matrix.

## Risk Notes
- Free tier extremely limited — not suitable for production workloads
- Some models trigger background agent skills causing CLI timeouts
- Wrapper must be running (port 9104) before CLI calls
- Real OpenCode API keys required (from https://opencode.ai/auth)
- Rate limits are PER-KEY, not per-client — adding Console key to wrapper .env shares that key's quota
- Console key ≠ full API access — SDK compatibility varies by credential