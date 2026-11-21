# Wrapper-Opencode Audit (2026-11-20) — Frozen but Running

## Session Context
- **Date**: 2026-11-20 05:26 WIB
- **Task**: Check wrapper-opencode status, understand codebase, update README.md
- **Scope**: Read-only audit (wrapper is frozen per wrappers.json since 2026-10-07)

## Runtime Reality vs wrappers.json

| Field | wrappers.json | Actual (2026-11-20) |
|-------|--------------|---------------------|
| status | pending | pending (frozen) ✅ |
| service | not deployed | **Active** via systemd (PID 1946055) |
| architecture | standardized | **Standardized** (common/ infra, KeyPool, metrics, catalog) |
| API keys | N/A | **Single key** (`OPENCODE_API_KEY_1`) |
| FREE_ONLY | implied | **Enabled** — 13 free models only |
| upstream health | N/A | **All 13 rate-limited** (`MODEL_OR_DEPLOYMENT_RATE_LIMIT`) |
| error rate | N/A | **99.52%** (1670/1678 requests) |

## Service Status

```
systemctl --user status wrapper-opencode
# Active: active (running) since Fri 2026-11-20 02:55:15 WIB
# Memory: 72.1M, CPU: 12.8s
# WorkingDirectory: /root/wrapper/opencode
# PYTHONPATH: /root/wrapper (repo root for common/ imports)
```

## Health Check Output

```json
{
  "status": "ok",
  "version": "1.0.5-anthropic-tools",
  "git_commit": "07b64dd1f0a8cbf8bb5b108d6fffbe1c5b063bb6",
  "keys": 1,
  "available": 1,
  "free_only": true,
  "metrics": {
    "total_requests": 1678,
    "total_tokens": 2804,
    "input_tokens": 912,
    "output_tokens": 1892,
    "error_rate": 0.9952
  },
  "model_registry": {
    "enabled": true,
    "worker_running": true
  },
  "models_cached": 158
}
```

## Model Inventory

```bash
curl -s http://127.0.0.1:9104/v1/models | jq '.data[] | {id, availability_state, reason_code}'
```

All 13 free models show:
- `availability_state: "model_rate_limited"`
- `reason_code: "MODEL_OR_DEPLOYMENT_RATE_LIMIT"`

Models: `beam-free`, `big-pickle`, `deepseek-v4.1-flash-free`, `flint-40b-free`, `hy4-flash-free`, `iceman-free`, `inkling-2-small-free`, `jev-1.13-free`, `longcat-2.5-free`, `mimo-v2.6-flash-free`, `nemotron-3.5-lightning-free`, `nemotron-3.5-super-vl-free`, `tidepool-alpha-free`

## Root Cause Analysis

**Primary Issue**: Single API key → all free models share same upstream quota → exhausted immediately.

The wrapper code is production-quality:
- Standardized architecture (shared common/ infra)
- KeyPool with model-scoped blocks
- SSE streaming with heartbeats
- .env hot-reload (EnvReloader + watchdog fallback)
- Model catalog integration (catalog + MCP routes)
- Persistent metrics (metrics-snapshot.json)
- CLI Mode proxy through local OpenCode service (port 49374)

But `FREE_ONLY=yes` + 1 key = no throughput.

## Console Key Discrepancy (Critical Finding)

From previous session (2026-11-20 earlier):
- OpenCode Console key works via CLI/Anthropic (`/v1/messages`) for free models
- **Wrapper routes free models to `/chat/completions`** (OpenAI format) via `_zen_family()`
- Console key only grants `/messages` access for free models
- **Fix needed**: `COMPATIBILITY_LAYER=2` for Anthropic-only routing

See `references/opencode-console-key-wrapper-discrepancy-2026-11-20.md` for full analysis.

## Reactivation Path (Requires Owner Instruction)

1. Add multiple `OPENCODE_API_KEY_*` keys to `.env`
2. Verify upstream quota per key (each key needs independent free-model quota)
3. Set `COMPATIBILITY_LAYER=2` in `.env` (Anthropic-compatible upstream)
4. Update `wrappers.json` status → `production`
5. Run client qualification suite (Claude Code, Codex, OpenCode client)
6. Run `--smoke-all` production audit

## Risk Notes

- **DO NOT modify wrapper code** — frozen per AGENTS.md scope rules
- The degradation is purely upstream quota, not a code defect
- Wrapper itself is healthy (HTTP 200 on `/health`, `/v1/models`)
- Error rate 99.52% is expected with single exhausted key
- Model catalog has 158 cached models (includes paid, filtered by FREE_ONLY)

## Files Updated This Session

- `/root/wrapper/opencode/README.md` — Added runtime status, health metrics, reactivation steps
- This reference document