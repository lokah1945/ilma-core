---
name: wrapper-development
description: Create, register, and deploy new API proxy wrappers in the /root/wrapper project following standardized patterns.
category: devops
triggers:
  - "create new wrapper"
  - "add wrapper"
  - "register wrapper"
  - "wrapper project"
  - "coarena wrapper"
  - "nvidia-python wrapper"
  - "nous wrapper"
  - "openrouter wrapper"
  - "opencode wrapper"
  - "blackbox wrapper"
  - "opencode cli"
  - "opencode cli integration"
  - "wrapper opencode cli"
---

# Wrapper Development Skill

## Overview
The `/root/wrapper` project hosts standardized API proxy wrappers for various LLM providers. Each wrapper follows a consistent structure and is registered in `wrappers.json`. This skill covers the complete lifecycle: scaffolding, implementation, registration, testing, and deployment.

## Wrapper Project Structure
```\n/root/wrapper/\n├── wrappers.json          # Authoritative registry (source of truth)\n├── common/                # Shared middleware, SSE, catalog integration\n├── nvidia-python/         # Production wrapper (port 9101)\n├── nous/                  # Production wrapper (port 9102)\n├── openrouter/            # Production wrapper (port 9103)\n├── opencode/              # Frozen/pending (port 9104) — CLI mode active\n├── blackbox/              # Frozen/pending (port 9105)\n├── coarena/               # Production wrapper (port 9107)\n├── model-registry/        # Internal service (port 9200)\n├── dashboard/             # Unified control (port 9106)\n└── productions/           # Production reports & artifacts\n```

## Port Allocation Rules
| Port | Service | Status |\n|------|---------|--------|\n| 9100 | model-fetcher MCP HTTP | Fixed |\n| 9101 | nvidia-python | Production |\n| 9102 | nous | Production |\n| 9103 | openrouter | Production |\n| 9104 | opencode | Frozen (reserved) — CLI mode active |\n| 9105 | blackbox | Frozen (reserved) |\n| 9106 | dashboard | Production |\n| 9107 | coarena | Production |\n| 9200 | model-registry | Internal |\n\n**Rule**: Next production wrapper gets next sequential port after dashboard (9106). Frozen wrappers keep reserved ports; if reactivated, they must be moved.

## Standardized Wrapper Structure
Every wrapper directory must contain:
```
wrapper-name/
├── src/
│   └── main.py           # FastAPI app, entry point: main:app
├── .env.example          # Documented env vars (COARENA_API_KEYS, etc.)
├── requirements.txt      # Minimal deps: fastapi, uvicorn, aiohttp, pydantic
├── systemd/
│   └── wrapper-name.service
├── tests/                # Test fixtures
└── (optional) pyproject.toml
```

## wrappers.json Registration
Add entry under `wrappers` object:
```json
"coarena": {
  "port": 9107,
  "module": "src.main",
  "entry_point": "main:app",
  "upstream": "Coarena",
  "status": "production",
  "structure": "standardized",
  "run_command": "uvicorn main:app --host 127.0.0.1 --port 9107",
  "env_prefix": "COARENA_",
  "supports": ["openai_chat", "openai_responses", "anthropic_messages"],
  "dashboard_stream": "polling",
  "dashboard_policy": "unified_only",
  "local_dashboard_routes": "410"
}
```
Then update metadata:
- `production_scope` array
- `port_allocation` string
- `pending_wrappers` if applicable

## Implementation Patterns

### Shared Middleware (from `common/`)
```python
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from common.middleware import RequestSizeLimiter, sanitize_header_value
    from common.sse import iter_chunks_with_idle
    _HAS_SIZE_LIMITER = True
except ImportError:
    _HAS_SIZE_LIMITER = False
    # Fallback sanitizer inline
```

### Key Rotation
```python
API_KEYS = os.environ.get("COARENA_API_KEYS", "").split(",")
API_KEYS = [k.strip() for k in API_KEYS if k.strip()]
# Round-robin selection with asyncio.Lock
```

### Streaming Proxy
```python
async with aiohttp.ClientSession() as session:
    async with session.request(...) as resp:
        if stream:
            return StreamingResponse(
                iter_chunks_with_idle(resp, 30.0),  # Use common SSE
                status_code=resp.status,
                headers=dict(resp.headers),
                media_type=resp.content_type,
            )
```

### HTML Error Page Handling
**Coarena-specific**: Upstream returns HTML 404 pages for unsupported endpoints instead of JSON.
```python
data = await resp.read()
if data and data.strip().startswith(b'<!DOCTYPE html>'):
    return JSONResponse(
        content={"error": {"message": "Upstream returned HTML page", "type": "upstream_error"}},
        status_code=502,
    )
```

### Endpoint Mapping
| Client Format | Coarena Endpoint |
|---------------|------------------|
| OpenAI Chat | `/api/v1/chat/completions` |
| OpenAI Responses | `/api/v1/responses` |
| Anthropic Messages | `/api/v1/messages` (NOT `/api/messages`) |
| Models List | `/api/v1/models` |

## Testing Checklist
- [ ] `/health` returns `{"status": "healthy", "keys": N}`
- [ ] `/v1/models` lists models
- [ ] `/v1/chat/completions` non-stream works
- [ ] `/v1/responses` non-stream works
- [ ] `/v1/messages` non-stream works
- [ ] Streaming: known limitation — upstream closes connection mid-stream
- [ ] Key rotation works with multiple keys
- [ ] `python3 -m common.wrapper_scope` includes wrapper in production

## Deployment
```bash
# Install deps
cd /root/wrapper/wrapper-name && pip install --break-system-packages -r requirements.txt

# Test run
COARENA_API_KEYS=... python3 -m uvicorn main:app --host 127.0.0.1 --port 9107

# Install systemd service
cp systemd/wrapper-name.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now wrapper-name
```

## Pitfalls & Gotchas
1. **Don't use placeholder API keys** — User will provide real key; config must accept env var substitution.
2. **Anthropic base URL** — Coarena uses `/api/v1/messages` not `/api/messages` (returns HTML 404).
3. **Streaming proxy** — `iter_chunks_with_idle` expects `resp` not `resp.content`; idle param is `idle_sec` positional.
4. **RequestSizeLimiter** — Use `app.add_middleware(RequestSizeLimiter)` not `app.middleware("http")(RequestSizeLimiter())`.
5. **Module import path** — `uvicorn.run("main:app")` when running from `src/`, not `"src.main:app"`.
### 6. **Frozen wrappers** — opencode (9104) and blackbox (9105) are pending; do not modify without explicit owner reactivation. **However, frozen wrappers can be architecturally aligned with production wrappers** (shared middleware, env_reload, translations, auth, catalog_integration) while keeping their pending status. This was done for opencode in 2026-11-19 to ensure readiness for future reactivation. **As of 2026-11-20, opencode wrapper has full CLI mode proxy for all three surfaces (chat, responses, messages) routing through local OpenCode service (49374)**, enabling free model access across all protocol surfaces.
7. **Port conflicts** — Check `ss -tlnp | grep :910` before assigning new ports.
8. **PYTHONPATH in systemd** — Production wrappers use `PYTHONPATH=/root/wrapper` (repo root), NOT the wrapper-specific directory. The wrapper code must import `common` via `sys.path.insert(0, str(Path(__file__).resolve().parents[2]))`.
9. **Env reload** — Use `common.env_reload.EnvReloader` (watchdog + polling fallback) instead of custom watchdog observer. The service provides `generation` tracking and `watcher_mode` status.
10. **KeyPool load_from_env timing** — Call `pool.load_from_env()` both at module import (for test compatibility) AND in lifespan startup. EnvReloader calls it on .env changes for hot-reload.
11. **OpenCode Console key SDK compatibility** — OpenCode Console credentials (`oc_sk_...`) may only work with Anthropic Messages API (`/v1/messages`), NOT OpenAI Chat Completions (`/v1/chat/completions`). Adding Console key to wrapper .env means clients MUST use Anthropic SDK (`ANTHROPIC_BASE_URL`). OpenAI SDK will fail with "Model unavailable". This is a per-credential limitation, not a wrapper bug. See `references/opencode-cli-integration.md` for details.

## References
- `references/coarena-api-quirks.md` — Coarena-specific endpoint behaviors
- `references/port-allocation-history.md` — Port assignment decisions
- `references/opencode-freeze-align-pattern.md` — Opencode freeze-and-align session
- `references/opencode-cli-integration.md` — OpenCode CLI usage with wrapper-opencode
- `references/opencode-cli-mode-proxy.md` — CLI mode proxy through local OpenCode service (2026-11-20)
- `references/wrappers-go-audit-2026-11-25.md` — wrappers-go Go rewrite audit (dashboard missing, binary runs)
- `templates/wrapper-scaffold/` — Boilerplate for new wrapper
- `scripts/verify-wrapper.py` — Post-deployment verification script
- `scripts/verify-cli-mode.py` — CLI mode proxy verification across all 3 surfaces