# /root/wrapper LLM Proxy Endpoints (as of 2026-07-28)

All wrappers run locally on `127.0.0.1`, OpenAI-compatible at `/v1`.

| Wrapper | Port | Upstream | Auth (client) | /v1/models count | Notes |
|---------|------|----------|---------------|------------------|-------|
| nvidia | 9101 | nvidia-nim | `Bearer wrapper-local-key` | 117 | git_commit 92893e7; NVIDIA NIM models. Port 9100 in OLD config was DEAD. |
| nous | 9102 | nous (free-only) | `Bearer wrapper-local-key` | 22 | dynamic_alias_target `tencent/hy3:free`. |
| opencode | 9103 | opencode-zen (free-only) | `Bearer wrapper-local-key` | 9 | `big-pickle`, `deepseek-v4-flash-free`, etc. |
| blackbox | 9104 | blackbox-ai (free-only) | `Bearer wrapper-local-key` | 7 | `blackboxai/*` model ids. |
| model-registry | 9200 | control-plane | admin token | n/a | NOT an LLM provider — do not register in OpenCode. |

## Health check (all return JSON `{...}`)
```
curl -s http://127.0.0.1:9101/health   # nvidia
curl -s http://127.0.0.1:9102/health   # nous
curl -s http://127.0.0.1:9103/health   # opencode
curl -s http://127.0.0.1:9104/health   # blackbox
```

## Model list (with auth)
```
curl -s -H "Authorization: Bearer wrapper-local-key" http://127.0.0.1:9102/v1/models
```

## Direct chat smoke test (proves wrapper side works)
```
curl -s -X POST http://127.0.0.1:9102/v1/chat/completions \
  -H "Authorization: Bearer wrapper-local-key" -H "Content-Type: application/json" \
  -d '{"model":"tencent/hy3:free","messages":[{"role":"user","content":"reply exactly: PONG"}],"max_tokens":10}'
```

## Gotchas
- Some upstream models (e.g. nous `ling-3.0-flash-free`) return `Internal Server Error` at the wrapper
  (`aiohttp.client_exceptions.ClientPayloadError: 400` from upstream). This is an upstream model issue,
  NOT an OpenCode wiring issue. Default alias `tencent/hy3:free` is reliable.
- `BEARER_TOKEN` value is `wrapper-local-key` for all four wrappers (confirmed in each `*/.env`).
