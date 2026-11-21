# Client Config Fix for Wrapper Context Window Propagation

## Problem
Wrapper-nvidia correctly returns `context_window: 1048576` for `nvidia/nemotron-3-ultra-550b-a55b` in both `/v1/models` and `/v1/models/{id}` endpoints. However, clients (Claude Code, OpenCode, Codex, OpenHand) parse only standard OpenAI Model fields (`id`, `object`, `created`, `owned_by`) and ignore the `context_window` extension field. This causes them to fall back to internal defaults (often 200K).

## Root Cause
- Standard OpenAI `/v1/models` response: `{id, object, created, owned_by}` — NO `context_window`
- Wrapper-nvidia enriches response with `context_window`, `context_length`, `max_context_window` as extension fields
- OpenAI Python SDK stores extensions in `model_extra` dict
- Most clients use strict schema validation or don't read `model_extra`

## Client Config Fixes Applied (2026-11-03)

### OpenCode (`~/.config/opencode/config.json`)
```json
{
  "provider": {
    "nvidia": {
      "id": "nvidia",
      "name": "wrapper-nvidia",
      "options": {
        "baseURL": "http://localhost:9101/v1",
        "apiKey": "wrapper-local-key"
      },
      "models": {
        "nvidia/nemotron-3-ultra-550b-a55b": {
          "contextWindow": 1048576
        }
      }
    }
  }
}
```
Key: `models.{model_id}.contextWindow` — OpenCode reads this for context window.

### Codex (`~/.codex/config.yaml`)
```yaml
system_prompt: '@/root/project/AgentEnhancements/unified-integration/prompts/codex-system-prompt.txt'
model_provider:
  nvidia:
    base_url: "http://127.0.0.1:9101/v1"
    api_key: "wrapper-local-key"
    models:
      "nvidia/nemotron-3-ultra-550b-a55b":
        context_window: 1048576
skills:
  directory: /root/project/AgentEnhancements/unified-integration/skills
  auto_load: true
...
```
Key: `model_provider.{provider}.models.{model_id}.context_window` — Codex reads this.

### Claude Code (`~/.claude/settings.json`)
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:9101",
    "ANTHROPIC_AUTH_TOKEN": "wrapper-local-key",
    "ANTHROPIC_API_KEY": "wrapper-local-key",
    "ANTHROPIC_MODEL": "nvidia/nemotron-3-ultra-550b-a55b",
    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
    "CLAUDE_CODE_GATEWAY_MODEL_DISCOVERY_URL": "http://localhost:9101/v1/models",
    "CLAUDE_CODE_MODEL_CONTEXT_WINDOW": "1048576"
  }
}
```
Key: `CLAUDE_CODE_MODEL_CONTEXT_WINDOW` environment variable — Claude Code reads this for context window override.

## Verification
After applying fixes, each client should report 1M context for nemotron-3-ultra instead of 200K.

## Template for New Models
For any model where wrapper reports correct context but client falls back:
1. Identify client's config format
2. Add explicit `contextWindow`/`context_window`/`CLAUDE_CODE_MODEL_CONTEXT_WINDOW` override
3. Restart client
4. Verify with client's model info command