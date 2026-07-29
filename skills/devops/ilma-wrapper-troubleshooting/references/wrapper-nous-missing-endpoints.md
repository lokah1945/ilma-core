# wrapper-nous Missing Endpoints — 2026-07-29

## Current State
wrapper-nous (port 9102) exposes:
- `/health` ✅ (liveness)
- `/v1/models` ✅
- `/v1/chat/completions` ✅
- `/v1/messages` ✅
- `/v1/responses` ✅

**MISSING** (required for production monitoring):
- `/ready` — readiness probe (key pool healthy + upstream reachable)
- `/metrics/activity` — recent request log for load verification

## Required Endpoints (Production Standard)
All wrappers should expose:
| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/health` | Liveness — process alive | `{"status":"ok","git_commit":"..."}` |
| `/ready` | Readiness — can serve traffic | `{"ready":true,"keys_available":N,"upstream_ok":true}` |
| `/metrics` | JSON metrics summary | `{"total_requests":N,"total_tokens":N,"error_rate":0.0,...}` |
| `/metrics/prom` | Prometheus format | Prometheus text exposition |
| `/metrics/activity` | Recent requests (last 100) | `[{"ts":...,"method":"POST","path":"/v1/messages","status":200,"latency_ms":123},...]` |

## Implementation Notes
- `/ready` should check: `KEY_POOL.available_keys > 0` AND a quick upstream HEAD/GET to Nous `/v1/models` (or cached) succeeds
- `/metrics/activity` should be a rolling buffer (last 100-1000 requests) with: timestamp, method, path, status, latency_ms, model, key_label
- Use same metrics collection as existing `/metrics` endpoint

## Fix Location
`/root/wrapper/nous/src/main.py` (or `wrapper_nous.py` depending on structure)

Add routes:
```python
@app.get("/ready")
async def ready():
    keys_ok = KEY_POOL.available_keys > 0
    upstream_ok = await check_nous_upstream()
    return {"ready": keys_ok and upstream_ok, "keys_available": KEY_POOL.available_keys, "upstream_ok": upstream_ok}

@app.get("/metrics/activity")
async def metrics_activity():
    return METRICS.recent_activity()  # implement rolling buffer
```

## Verification
```bash
for p in 9101 9102 9103 9104 9105 9106; do
  echo "=== $p ==="
  curl -s http://127.0.0.1:$p/health | jq .status
  curl -s http://127.0.0.1:$p/ready | jq .ready
  curl -s http://127.0.0.1:$p/metrics/activity | jq 'length'
done
```

## Related
- `ilma-wrapper-production-audit` — checks these endpoints in audit
- `references/wrapper-bind-host-inconsistency.md` — same standard across wrappers