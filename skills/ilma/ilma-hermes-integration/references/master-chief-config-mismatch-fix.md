# Master-Chief Profile Config Mismatch Fix — 2026-11-16

## Problem
The `master-chief` Hermes profile (PID 789, running as `hermes-gateway-master-chief.service`) was receiving messages but failing to generate responses. The gateway showed "Transient agent failure" and responses were not reaching the user.

## Root Cause
**Config mismatch in `/root/.hermes/profiles/master-chief/config.yaml`:**

```yaml
# BROKEN
model:
  default: nvidia/nemotron-3-ultra-550b-a55b
  provider: wrapper-nvidia   # resolves to FIRST matching provider
providers:
  custom:
  - name: wrapper-nvidia
    base_url: http://127.0.0.1:9100/v1    # ← model_fetcher MCP catalog server (NO chat completions)
    api_key: wrapper-local-key
    model: z-ai/glm-5.2
  wrapper-nvidia:                          # ← actual inference wrapper (orphaned)
    base_url: http://127.0.0.1:9101/v1
    key_env: MASTER_CHIEF_WRAPPER_NVIDIA_API_KEY
```

Hermes resolves `provider: wrapper-nvidia` to the **first** provider with that name — the `custom` entry at port 9100. Port 9100 is the `model_fetcher` MCP server (catalog-only, no `/v1/chat/completions`). The actual inference wrapper at port 9101 was never used.

## Evidence
- `GET http://127.0.0.1:9100/v1/models` → `Not Found` (catalog server)
- `POST http://127.0.0.1:9100/v1/chat/completions` → `Not Found`
- `GET http://127.0.0.1:9101/v1/models` → 168 models, 33 available
- `POST http://127.0.0.1:9101/v1/chat/completions` with `nvidia/nemotron-3-ultra-550b-a55b` → 200 OK, valid response

## Fix Applied
Removed the incorrect `custom` entry and made the named provider canonical:

```yaml
# FIXED
model:
  default: nvidia/nemotron-3-ultra-550b-a55b
  provider: wrapper-nvidia
providers:
  wrapper-nvidia:
    name: wrapper-nvidia
    base_url: http://127.0.0.1:9101/v1
    key_env: MASTER_CHIEF_WRAPPER_NVIDIA_API_KEY
    transport: chat_completions
    default_model: nvidia/nemotron-3-ultra-550b-a55b
    models:
      nvidia/nemotron-3-ultra-550b-a55b: {}
    discover_models: true
```

## Verification Steps
1. Send `SIGHUP` (USR1) to gateway PID to reload config: `kill -USR1 <pid>`
2. Wait for systemd restart helper to restart the service (~5-10s)
3. Check logs for "Starting Hermes Gateway..." → "✓ telegram connected"
4. Verify model responds: `curl -X POST http://127.0.0.1:9101/v1/chat/completions -H "Authorization: Bearer wrapper-local-key" -d '{"model":"nvidia/nemotron-3-ultra-550b-a55b","messages":[{"role":"user","content":"test"}],"max_tokens":10}'`

## Lesson
**Always verify which provider `model.provider` actually resolves to.** Hermes uses the first matching name in the providers list. Multiple providers with the same `name` field create ambiguity — the first wins, regardless of whether it's the intended one.

This pattern could affect any profile that has both a `custom` entry and a named provider with the same name. Audit other profiles for the same issue:
- `/root/.hermes/profiles/ilma/config.yaml`
- Any other active profile

## Files Modified
- `/root/.hermes/profiles/master-chief/config.yaml` — provider config fixed
- Gateway restarted via systemd (PID changed from 789 → 2749823 → 2780514 → 2819848)