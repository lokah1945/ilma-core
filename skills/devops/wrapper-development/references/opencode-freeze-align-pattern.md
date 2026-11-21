# Opencode Freeze-and-Align Pattern (2026-11-19)

## Context
The opencode wrapper (port 9104) was frozen/pending since 2026-10-07 per `wrappers.json`. However, the owner requested it be architecturally aligned with production wrappers (nvidia-python, nous, openrouter, coarena) while keeping its frozen status — so it's ready for immediate reactivation when needed.

## What Was Done

### Files Updated
1. **`pyproject.toml`** — Matched production wrapper format (hatchling, version 1.0.5, requires-python >=3.11)
2. **`systemd/wrapper-opencode.service`** — Fixed PYTHONPATH to `/root/wrapper` (repo root), consistent with production wrappers
3. **`src/main.py`** — Complete rewrite using shared infrastructure from `common/`:
   - `common.middleware.RequestSizeLimiter`, `sanitize_header_value`
   - `common.sse.iter_chunks_with_idle`, `ClosingStreamingResponse`
   - `common.env_reload.EnvReloader` (watchdog + polling fallback)
   - `common.auth.check_auth` (fail-closed)
   - `common.translations` (all Anthropic↔OpenAI↔Responses protocol conversions)
   - `common.catalog_integration` (catalog + MCP routes)
   - `common.body_guard.JSONBodyGuard` (non-object JSON rejection)
   - `common.model_state.ModelStateStore` (model catalog/verification)
   - `common.model.LocalModelRegistry`, `ModelRegistryClient`
   - `common.compat` (upstream compatibility layer)
4. **`README.md`** — Updated to reflect frozen status + standardized architecture
5. **`.env.example`** — All standardized env vars matching production wrappers

### Architecture Alignment Achieved
- ✅ Shared KeyPool with multi-key rotation, model-scoped blocks, RPM tracking
- ✅ Shared streaming with heartbeat + anti-silence via `common.sse.iter_chunks_with_idle`
- ✅ Shared env reloader (`EnvReloader`) with watchdog + polling fallback
- ✅ Shared auth (`check_auth`) — fail-closed, constant-time comparison
- ✅ Shared translations for Anthropic↔OpenAI↔Responses protocol conversions
- ✅ Shared model state (`ModelStateStore`) with SQLite persistence
- ✅ Standard routes: `/health`, `/ready`, `/metrics`, `/metrics/prom`, `/metrics/model-status`, `/dashboard`, `/version`, `/v1/models`, `/api/tags`, `/v1/capabilities`
- ✅ Catalog + MCP integration via `common.catalog_integration`
- ✅ Graceful shutdown with in-flight drain
- ✅ Per-IP rate limiting + load shedding (configurable)
- ✅ X-Request-ID + X-Process-Time headers on all responses

### OpenCode Zen-Specific Logic Preserved
- `_zen_family()` model routing (GPT→responses, Claude→messages, Qwen→messages, Gemini→google, free→chat)
- Dynamic alias system (`sonnet`/`opus`/`haiku` → `DYNAMIC_ALIAS_TARGET`)
- FREE_ONLY mode with allowlist (`big-pickle`)
- COMPATIBILITY_LAYER support (1=OpenAI, 2=Anthropic, 3=Auto)
- Native Responses passthrough for GPT models
- Translate via chat/completions for non-GPT models

### Key Implementation Details

**KeyPool load_from_env timing:**
- Called at module import (for FastAPI TestClient compatibility)
- Called again in lifespan startup (for production via uvicorn)
- EnvReloader calls it on .env changes for hot-reload

**EnvReloader integration:**
```python
if HAS_ENV_RELOADER:
    _env_reloader = EnvReloader(
        env_path=Path(__file__).resolve().parent.parent / '.env',
        on_reload=lambda: pool.load_from_env(),
    )
    _env_reloader.start()
```

**PYTHONPATH in systemd:**
```ini
Environment=PYTHONPATH=/root/wrapper  # repo root, NOT wrapper-specific
```

**Common imports pattern:**
```python
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.middleware import RequestSizeLimiter, sanitize_header_value
```

## Verification Results
All endpoints working:
- `/health` — returns keys, available, metrics, model_registry status
- `/ready` — requires auth, checks upstream
- `/v1/models` — 52 models from cached catalog + aliases
- `/api/tags` — Ollama-compatible, 52 models
- `/v1/capabilities` — 55 models
- `/v1/messages/count_tokens` — works
- `/metrics`, `/metrics/prom`, `/metrics/model-status` — works
- `/dashboard`, `/version` — works
- All 3 protocol surfaces: `/v1/chat/completions`, `/v1/responses`, `/v1/messages` (routing works, upstream fails with test keys as expected)

## CLI Mode Activation (2026-11-20)

### What Was Added
1. **CLI Mode toggle**: `OPENCODE_CLI_MODE=yes` in `.env`
2. **Local service proxy**: `/v1/chat/completions` routes through local OpenCode service (port 49374)
3. **Basic Auth**: Service user/password instead of API keys
4. **Session management**: Create session → send message → wait → get response
5. **Streaming support**: SSE events from local service (`session.text.delta`, `session.step.finish`)
6. **Model catalog**: `/v1/models` fetches from local service `/api/v1/models`
7. **FREE_ONLY enforcement**: Added to CLI chat path and models endpoint

### Configuration
```bash
# .env
OPENCODE_CLI_MODE=yes
OPENCODE_SERVICE_URL=http://127.0.0.1:49374
OPENCODE_SERVICE_USER=opencode
OPENCODE_SERVICE_PASSWORD=<from ~/.config/opencode/service.json>
```

### Verification Results (2026-11-20, COMPATIBILITY_LAYER=2)
| Surface | Mode | Free Models | Result |
|---------|------|-------------|--------|
| `/v1/chat/completions` | CLI (local) | 23 | ✅ Working |
| `/v1/responses` | Upstream direct | 23 (filtered) | ⚠️ Upstream 429 |
| `/v1/messages` | Upstream direct | 23 (filtered) | ⚠️ Upstream 429 |
| `/v1/models` | CLI (local) | 23 | ✅ Filtered correctly |

### COMPATIBILITY_LAYER=2 Behavior
With `COMPATIBILITY_LAYER=2` (Anthropic upstream), all client traffic routes through Anthropic Messages:

| Surface | Routing | Translation Chain |
|---------|---------|-------------------|
| `/v1/chat/completions` | CLI mode (local service) | Direct — no translation needed |
| `/v1/responses` | Upstream direct | OpenAI Responses → Chat → Anthropic Messages → Chat → Responses |
| `/v1/messages` | Upstream direct | OpenAI Chat → Anthropic Messages → Chat → Anthropic |

**Key insight**: CLI mode only applies to `/v1/chat/completions`. Responses and Messages surfaces still call upstream Zen API directly with full translation chain. This is by design — CLI mode is a chat-only optimization.

### OpenCode CLI Stored Credentials ≠ Wrapper .env Keys

| Source | Key Prefix | Quota |
|--------|------------|-------|
| OpenCode CLI (stored in `~/.config/opencode/auth.json`) | `oc_sk_b535b03411ff...` | Your personal OpenCode Console account quota |
| Wrapper .env (6 keys) | `oc_sk_bc96fa9b...`, `oc_sk_eba23d5a...`, etc. | Separate account quotas |

**They do NOT share quotas.** Rate limits are per-API-key, not per-client.

### Verified Working CLI Models (via wrapper)
| Model | SDK | Result |
|-------|-----|--------|
| `opencode/tidepool-alpha-free` | Anthropic | ✅ |
| `opencode/deepseek-v4.1-flash-free` | Anthropic | ✅ |
| `opencode/mimo-v2.6-flash-free` | Anthropic | ✅ |
| `opencode/beam-free` | OpenAI | ✅ |
| `opencode/nemotron-3.5-lightning-free` | OpenAI | ✅ |

### Model-Specific Quirks
| Model | Behavior |
|-------|----------|
| `flint-40b-free` | Triggers agent skills (task-observer) → 60s timeout |
| `tidepool-alpha-free` | Fast, reliable |
| `deepseek-v4.1-flash-free` | Fast, reliable |
| `mimo-v2.6-flash-free` | Fast, reliable |
| `beam-free` | Fast, reliable |
| `nemotron-3.5-lightning-free` | Fast, reliable |

## When to Reactivate
1. Owner explicitly requests opencode reactivation
2. Update `wrappers.json` status from `pending` → `production`
3. Update `production_scope` to include `opencode`
4. Update `pending_wrappers` to remove `opencode`
5. Verify with production test suite (smoke tests for all 3 surfaces + streaming)
6. Deploy systemd service and enable

## Risk Notes
- Test keys used in verification are invalid — upstream returns "Model is unavailable" (expected)
- 1 key cooled down due to auth_or_quota during catalog refresh (expected with test keys)
- FREE_ONLY defaults to `no` in test env but `yes` in production .env.example
- Dashboard HTML is legacy (71KB) — could be replaced with shared template

## OpenCode CLI Integration & Quota Discovery (2026-11-20)

### OpenCode CLI Stored Credentials ≠ Wrapper .env Keys

| Source | Key Prefix | Quota |
|--------|------------|-------|
| OpenCode CLI (stored in `~/.config/opencode/auth.json`) | `oc_sk_b535b03411ff...` | Your personal OpenCode Console account quota |
| Wrapper .env (6 keys) | `oc_sk_bc96fa9b...`, `oc_sk_eba23d5a...`, etc. | Separate account quotas |

**They do NOT share quotas.** Rate limits are per-API-key, not per-client.

### Verification
```bash
# OpenCode CLI → uses → stored Console credential
opencode run -m opencode/tidepool-alpha-free "hi"  # ✅ Works (your quota)

# Wrapper → uses → its own .env keys
curl -H "Authorization: Bearer ***" http://127.0.0.1:9104/v1/chat/completions  # 429 (their quota)

# To share quota: add Console key to wrapper .env
OPENCODE_API_KEY_1=oc_sk_...V784
```

### Verified Working CLI Models (via wrapper)
| Model | SDK | Result |
|-------|-----|--------|
| `opencode/tidepool-alpha-free` | Anthropic | ✅ |
| `opencode/deepseek-v4.1-flash-free` | Anthropic | ✅ |
| `opencode/mimo-v2.6-flash-free` | Anthropic | ✅ |
| `opencode/beam-free` | OpenAI | ✅ |
| `opencode/nemotron-3.5-lightning-free` | OpenAI | ✅ |

### Model-Specific Quirks
| Model | Behavior |
|-------|----------|
| `flint-40b-free` | Triggers agent skills (task-observer) → 60s timeout |
| `tidepool-alpha-free` | Fast, reliable |
| `deepseek-v4.1-flash-free` | Fast, reliable |
| `mimo-v2.6-flash-free` | Fast, reliable |
| `beam-free` | Fast, reliable |
| `nemotron-3.5-lightning-free` | Fast, reliable |