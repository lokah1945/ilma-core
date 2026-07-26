# Smoke & Load Targets (known-good per wrapper)

Verified 2026-07-25. Use these exact models in `--smoke-all` / explicit smoke.
All return `returned_model == requested` (no substitution) on a healthy upstream.

| Wrapper | Port | Known-good model | Surfaces to test | Notes |
|---------|------|------------------|-----------------|-------|
| nvidia-python | 9101 | `nvidia/llama-3.3-nemotron-super-49b-v1` | chat, responses | Responses API works (`/v1/responses`, `max_output_tokens`) |
| nous | 9102 | `poolside/laguna-s-2.1:free` | chat, messages | Anthropic `/v1/messages` schema; `returned_model` matches |
| opencode | 9103 | `deepseek-v4-flash-free` | chat, messages | **Flaky upstream** — opencode.ai zen API "No capacity" 503 → BLOCKED not FAIL |
| blackbox | 9104 | `blackboxai/nvidia/nemotron-nano-12b-v2-vl` | chat, messages | Do NOT use `sonnet` (remaps to nemotron-3, identity mismatch) |

## Load test (nvidia primary)
```bash
WRAPPER_API_KEY='wrapper-local-key' API_KEY='wrapper-local-key' \
  PYTHONDONTWRITEBYTECODE=1 \
  python3 tests/perf/load_agent_sim.py \
    --base-url http://127.0.0.1:9101/v1 \
    --model 'nvidia/llama-3.3-nemotron-super-49b-v1' \
    --requests 50 --concurrency 5
```
Emits: `ok=N/M error=K`, `latency_ms p50=.. p95=.. p99=.. mean=..`,
`ttft_ms p50=.. p95=.. p99=..`. The audit runner captures this into the report's
`bounded load` block — if that block is empty, the load script path/args are wrong.

## OpenCode reliability note (M-02)
opencode.ai free tier periodically returns `{"error":{"message":"No capacity"}}`
with HTTP 503 and `available_keys=0/6` in `/health` (`status=degraded`). This is
external, recovers without action. Audit classifies as BLOCKED
(`external_outage=opencode.ai`), never FAIL. Smoke retry-with-backoff: 3 attempts,
sleep 2 + 3*n seconds on 429/503.
