# Wrapper-NVIDIA Silent-Hang Audit — 2026-06-30

## Scope
End-to-end deep audit of `/root/wrapper/nvidia` (Node.js variant, v4.6.0, 5 API keys, 121 models cached).
Triggered by: Bos report "proses berjalan terhenti tanpa ada konfirmasi apapun" (silent hang).

## 3 Bugs Found & Fixed

### Bug #1: 404 retry cascade (Pitfall #38)
- **Root cause:** `isRetryableError` included 404 → retried across all 5 keys → 75s key cooldown cascade
- **Symptom:** Request to retired/absent model hangs 5-10s. During cascade, concurrent requests queue-starved.
- **Fix:** Remove 404 from `isRetryableError` + `markModel(unavailable)` on 404
- **Evidence:** 404 response latency: ~10s → 13ms (500x faster)

### Bug #2: maxAttempts too aggressive (Pitfall #39)
- **Root cause:** `Math.max(MAX_RETRIES+1, pool.totalKeys) = 5` attempts per request
- **Symptom:** On 5xx upstream degradation, all keys get 15s cooldown sequentially → key pool exhaustion
- **Fix:** `maxAttempts = MAX_RETRIES + 1` (=4)
- **Evidence:** P95 latency: 41.4s → 1.5s (28x faster)

### Bug #3: Verify sweep monopolizes key pool (Pitfall #40)
- **Root cause:** `VERIFY_CONCURRENCY=8`, `VERIFY_INTERVAL=600s` (10min), 70/121 models unavailable
- **Symptom:** Concurrent 8-key reservation during sweep → regular requests queue → 503 cascade
- **Fix:** `VERIFY_CONCURRENCY=4`, `VERIFY_INTERVAL=1200s` (20min)
- **Evidence:** 0 rate-limited events post-patch; no 503 cascade during sweep windows

## Live Metrics (Post-Patch)

| Metric | Before | After |
|--------|--------|-------|
| 404 model latency | 5-10s | 13ms |
| Working model P50 | 9.8s | 0.6s |
| Working model P95 | 41.4s | 1.5s |
| Stream aborts (6h) | 16 | 0 |
| Key pool starvation | Frequent | 0 events |

## Diagnostic Commands Used

```bash
# Service health
systemctl is-active wrapper-nvidia.service
curl -s http://127.0.0.1:9100/health

# Live metrics
curl -s 'http://127.0.0.1:9100/metrics?window=1h' | python3 -c "import sys,json; d=json.load(sys.stdin); ..."

# Rate limit events
curl -s 'http://127.0.0.1:9100/metrics/rate-limits?limit=50' | python3 -c "..."

# Recent request activity
curl -s 'http://127.0.0.1:9100/metrics/activity?limit=20' | python3 -c "..."

# Journal stream errors/warnings (6h)
journalctl -u wrapper-nvidia.service --since "6 hours ago" --no-pager | grep -E 'STREAM WARN|UPSTREAM ERROR|ABORT' | tail -30

# Test 404 response speed
time curl -s --max-time 5 http://127.0.0.1:9100/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"nvidia/meta/llama-3.3-70b-instruct","messages":[{"role":"user","content":"test"}],"max_tokens":5}'

# Test working model
time curl -s --max-time 30 http://127.0.0.1:9100/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"z-ai/glm-5.1","messages":[{"role":"user","content":"test"}],"max_tokens":5}'
```

## Git Commit

```
d50b396 fix(audit-2026-06-30): 3 critical hang fixes — R-404, R-maxretry, R-verify
```
Pushed to `origin/master`.
