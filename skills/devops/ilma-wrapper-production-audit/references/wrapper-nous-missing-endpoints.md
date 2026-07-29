# Wrapper-Nous Missing Standard Endpoints — 2026-07-29

## Symptom
Wrapper-nous (port 9102) missing standard production endpoints that ALL other wrappers expose:
- `/ready` — readiness probe (key pool + upstream reachable)
- `/metrics` — JSON metrics summary
- `/metrics/prom` — Prometheus format metrics
- `/metrics/activity` — recent request log for load verification

Other wrappers (nvidia-python, opencode, blackbox, vercel) all have these.

## Root Cause
`wrapper_nous.py` is a flat file (no `src/` structure) and these endpoints were simply never implemented. The file has:
- `/healthz` — liveness (alias for `/health`)
- `/health` — basic health
- `/version` — version info
- `/dashboard` — dashboard HTML

But missing the standard production monitoring endpoints.

## Fix Required
Add to `wrapper_nous.py` before catch-all:

```python
@app.get("/ready")
async def ready():
    """Readiness: key pool + upstream reachable."""
    has_credentials = KEY_POOL.total_keys > 0 or bool(_read_token_from_auth_path())
    # Check cached catalog freshness
    if MODEL_STORE.get_catalog(fresh_only=True):
        return {
            "ready": has_credentials,
            "upstream_ok": True,
            "status_code": 200,
            "source": "catalog_cache",
            "catalog_age_sec": MODEL_STORE.catalog_age_sec(),
            "last_error": None,
            "keys": KEY_POOL.total_keys,
            "available": KEY_POOL.available_keys,
        }
    # Fallback: probe upstream (rate-limited)
    now = time.time()
    if now - _ready_probe_state["last_probe"] >= READY_PROBE_MIN_INTERVAL_SEC or _ready_probe_state["status"] is None:
        _ready_probe_state["last_probe"] = now
        status, result = await get_nous_json_with_retries("/v1/models")
        _ready_probe_state["status"] = status
        _ready_probe_state["error"] = None if status == 200 else (result.get("error") if isinstance(result, dict) else str(result))
    status = _ready_probe_state["status"]
    return {
        "ready": has_credentials and status == 200,
        "upstream_ok": status == 200,
        "status_code": status,
        "source": "upstream_probe",
        "last_error": _ready_probe_state["error"],
        "keys": KEY_POOL.total_keys,
        "available": KEY_POOL.available_keys,
    }

@app.get("/metrics")
async def metrics():
    return await METRICS.summary()

@app.get("/metrics/prom")
async def prom_metrics():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(METRICS.prom_metrics(), media_type="text/plain; version=0.0.4")

@app.get("/metrics/activity")
async def metrics_activity(limit: int = 50, offset: int = 0):
    rows = await METRICS.recent_requests(limit, offset)
    return {"limit": limit, "offset": offset, "count": len(rows), "rows": rows}
```

## Verification
```bash
curl http://localhost:9102/ready
# {"ready":true,"upstream_ok":true,"status_code":200,"source":"catalog_cache",...}

curl http://localhost:9102/metrics/activity | jq '.count'
# > 0
```

## Related
- `references/wrapper-nous-brotli-streaming-bug.md`
- `references/wrapper-free-only-inconsistency.md`