# opencode Configuration Fix — 2026-11-01 Session

## Problem
opencode was failing with:
- `Configuration is invalid: Unrecognized key: plugins` → removed `plugins` array from config
- `ProviderModelNotFoundError: Model not found: nvidia/nemotron-3-ultra-550b-a55b` → model exists in wrapper catalog but opencode couldn't find it
- `Forbidden: Authorization failed` → wrong apiKey in config

## Root Causes & Fixes

### 1. Config File: `~/.config/opencode/opencode.jsonc`

**Before:**
```jsonc
{
  "provider": {
    "wrapper-nvidia": {
      "id": "nvidia",           // WRONG - must match auth.json credential key
      "name": "wrapper-nvidia",
      "options": {
        "baseURL": "http://localhost:9100/v1",  // WRONG PORT
        "apiKey": "wrapper-nvidia-no-auth"      // WRONG KEY
      }
    },
    "nous-portal": {
      "id": "nous",             // WRONG - must match auth.json credential key
      "name": "Nous Portal",
      ...
    }
  },
  "plugins": [...]              // UNRECOGNIZED KEY
}
```

**After (working):**
```jsonc
{
  "provider": {
    "nvidia": {
      "id": "nvidia",           // MATCHES auth.json key "nvidia"
      "name": "wrapper-nvidia",
      "options": {
        "baseURL": "http://localhost:9101/v1",  // CORRECT PORT (nvidia-python)
        "apiKey": "wrapper-local-key"           // MATCHES auth.json value
      }
    },
    "nous-portal": {
      "id": "nous-portal",      // MATCHES auth.json key "nous-portal"
      "name": "Nous Portal",
      ...
    }
  }
}
```

### 2. Credential Matching Rule
**The `id` field in opencode.jsonc MUST exactly match the credential key in `~/.local/share/opencode/auth.json`.**

| auth.json key | opencode.jsonc `id` | Works? |
|--------------|---------------------|--------|
| `wrapper-nvidia` | `nvidia` ✅ | YES |
| `nous-portal` | `nous-portal` ✅ | YES |
| `wrapper-nvidia` | `wrapper-nvidia` ❌ | NO |
| `nous-portal` | `nous` ❌ | NO |

### 3. Port Mapping
| Wrapper Service | Port | opencode provider id |
|----------------|------|---------------------|
| wrapper-nvidia-python | 9101 | `nvidia` |
| wrapper-nous | 9102 | `nous-portal` |
| wrapper-openrouter | 9103 | `openrouter` (auto-configured via env) |

### 4. Model Availability Discrepancy
**Critical finding:** opencode's `models <provider>` shows ONLY what the wrapper exposes, not the full upstream catalog.

| Source | Models Visible |
|--------|----------------|
| `opencode models nvidia` | 25 (from wrapper-nvidia 9101) |
| `opencode models openrouter` | 363 (from direct OpenRouter credentials) |
| `curl http://localhost:9101/v1/models` | 134 (full wrapper catalog) |
| `curl http://localhost:9103/v1/models` | 14 (only `:free` models from wrapper) |

**Why:** wrapper-openrouter (9103) has `FREE_ONLY=true` and only exposes 14 `:free` models. Direct OpenRouter credentials in auth.json bypass this filter.

### 5. Working Model Commands
```bash
# NVIDIA Nemotron via wrapper (works)
opencode run -m "nvidia/nvidia/nemotron-3-ultra-550b-a55b" "Say hello"

# NVIDIA Nemotron via OpenRouter free (works)
opencode run -m "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free" "Say hello"

# Fails: openrouter models without :free suffix (not in wrapper catalog)
opencode run -m "openrouter/qwen/qwen-2.5-coder-32b-instruct" "Say hello"
# Error: No endpoints found that support tool use
```

## Verification Commands
```bash
# Check config validity
opencode --help  # Should not show config error

# List models per provider
opencode models nvidia
opencode models openrouter
opencode models nous-portal

# Test model call
opencode run -m "nvidia/nvidia/nemotron-3-ultra-550b-a55b" "Say hello in 5 words"
```

## Pitfall for Future Sessions
- **Don't assume wrapper catalog = opencode model list.** opencode filters what the wrapper returns.
- **Always match `id` to auth.json credential keys**, not the wrapper service name.
- **Port 9100 is dead** — wrapper-nvidia (legacy) removed. Use 9101 (nvidia-python).
- **`plugins` key is not supported** in opencode config — remove it.