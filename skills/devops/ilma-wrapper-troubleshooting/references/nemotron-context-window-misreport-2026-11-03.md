# Nemotron-3-Ultra Context Window Misreport Class (2026-11-03)

## Problem
User reports: "Claude code menggunakan backend wrapper Nvidia. Model di pakai nemotron 3 ultra. Saya mau tahu kenapa max context length nya di deteksi 200K. Sedangkan anda, Hermes agent profile ILMA bisa 1M."

## Root Cause Analysis

### Wrapper Side (CORRECT)
Wrapper-nvidia **correctly returns** `context_window: 1048576` for `nvidia/nemotron-3-ultra-550b-a55b`:
```bash
# List endpoint
curl http://127.0.0.1:9101/v1/models | jq '.data[] | select(.id=="nvidia/nemotron-3-ultra-550b-a55b") | .context_window'
# 1048576

# Individual endpoint
curl http://127.0.0.1:9101/v1/models/nvidia/nemotron-3-ultra-550b-a55b | jq '.context_window'
# 1048576
```

### Client Side (THE PROBLEM)
Standard OpenAI `/v1/models` response spec: `{id, object, created, owned_by}` — **NO `context_window` field**.

Wrapper-nvidia enriches response with extension fields (`context_window`, `context_length`, `max_context_window`), but:
- **OpenAI Python SDK** stores extensions in `model_extra` dict
- **Most clients** (Claude Code, OpenCode, OpenHand, Codex) parse only standard fields
- Clients fall back to **internal defaults** (often 200K for "unknown" models)

### Hermes ILMA (RESOLVES 1M)
Hermes resolves 1M via:
1. Wrapper enrichment + persistent cache (`context_length_cache.yaml`)
2. `get_model_context_length()` reads from cache: `nvidia/nemotron-3-ultra-550b-a55b@http://127.0.0.1:9101/v1: 1048576`
3. Direct probe of `/v1/models` returns 1M

## Client Behavior Comparison

| Client | Context Detection | Result |
|--------|-------------------|--------|
| **Hermes/ILMA** | Cache + `/v1/models` probe | 1M ✓ |
| **OpenAI SDK** | `model_extra.context_window` | 1M ✓ |
| **OpenCode** | Own catalog (`https://opencode.ai/zen/v1/models`) | 200K ✗ (model not in catalog) |
| **Claude Code** | Anthropic SDK / hardcoded default | 200K ✗ |
| **Codex** | OpenAI SDK / hardcoded default | 200K ✗ |

## OpenCode Specifics
- Uses catalog at `https://opencode.ai/zen/v1/models` 
- nemotron-3-ultra **NOT in catalog** (only has nemotron-3.5-super-vl-free, nemotron-3.5-lightning-free)
- Falls back to default 200K

## Solution Applied (2026-11-03)

### OpenCode (`~/.config/opencode/config.json`)
```json
{
  "provider": {
    "nvidia": {
      "models": {
        "nvidia/nemotron-3-ultra-550b-a55b": {
          "contextWindow": 1048576
        }
      }
    }
  }
}
```

### Codex (`~/.codex/config.yaml`)
```yaml
model_provider:
  nvidia:
    base_url: "http://127.0.0.1:9101/v1"
    api_key: "wrapper-local-key"
    models:
      "nvidia/nemotron-3-ultra-550b-a55b":
        context_window: 1048576
```

### Claude Code (`~/.claude/settings.json`)
```json
{
  "env": {
    "CLAUDE_CODE_MODEL_CONTEXT_WINDOW": "1048576"
  }
}
```

## Template for Future Models
When wrapper reports correct context but client falls back:
1. Identify client's config format
2. Add explicit `contextWindow`/`context_window`/`CLAUDE_CODE_MODEL_CONTEXT_WINDOW` override
3. Restart client
4. Verify with client's model info command