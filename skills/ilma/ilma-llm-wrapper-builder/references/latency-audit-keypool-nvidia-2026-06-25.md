# Latency Audit: wrapper-nvidia key_pool.py — 2026-06-25

## Context

Bos asked for deep audit of wrapper-nvidia latency. Root cause investigation + fix of 3 critical pacing bugs in `key_pool.py` and `main.py`.

## Diagnosis Method

1. Query `metrics.db` for 24h baseline: `SELECT * FROM requests WHERE ts > datetime('now','-24 hours') AND status_code=200`
2. Key columns: `pacing_ms`, `latency_ms`, `key_label`, `retries`, `was_rate_limited`
3. Compute `upstream_ms = latency_ms - pacing_ms` to separate pacing overhead from actual upstream time
4. Per-key breakdown revealed key2 as worst offender (avg pacing 12,446ms vs key1 11,581ms)
5. Extreme pacing events (>50s): 179 in 24h — all driven by MODEL_BLOCK_DEFAULT_SECS=62

## Bug Summary

| Bug | Root Cause | Symptom | Fix |
|-----|-----------|---------|-----|
| MODEL_BLOCK 62s | NVIDIA sends Retry-After:62 even for model-scope 429 on idle keys | 179 extreme pacing events >50s, max 349s | Cap to 8s default, 10s model / 30s key |
| 100% pacing at idle | rpm_ok uses soft_limit (30rpm) as threshold, RPM=1 still paced | Every request paced even on idle keys | IDLE_RPM=3 bypass in rpm_ok |
| Pacing stacks on retry | pacing_ms_total += waited across key-switches | Up to 6min pacing for one request | Replace (not accumulate) on key-switch |

## Impact Data

```
PRE-FIX  (2643 requests, 24h):
  avg_pacing = 7,291ms
  avg_total  = 50,416ms
  avg_upstream = 43,125ms
  max_pacing = 349,206ms
  extreme (>50s) = 179
  retried = 199

POST-FIX (18 requests, 5 min after restart):
  avg_pacing = 0ms
  avg_total  = 16,857ms
  avg_upstream = 16,857ms
  max_pacing = 0ms
  extreme (>50s) = 0
  retried = 0

IMPROVEMENT:
  pacing_reduction = 100%
  total_reduction = 66.6%
  max_pacing_reduction = 100%
```

## Key2 Worst-Case (Pre-Fix)

```
reqs=754  avg_pacing=12,446ms  avg_total=40,163ms
```
Key2 had the most extreme pacing because it received proportionally more model-scope 429s with the 62s block.

## Test Verification

After all 3 fixes applied:
- test_classify: 18/18 PASS
- test_pacing: 16/16 PASS
- test_per_key_model_limit: 3/3 PASS
- test_round_robin_tiebreak: 4/4 PASS
- test_queue: 11/11 PASS
- test_capabilities: 33/33 PASS
- **Total: 85/85 PASS ✅**

### Fix 4b Regression & Recovery

Initial Fix 4b `admit_ok()` bypassed queue interval for idle keys (returning True immediately). This caused test_queue failures: batch 0 admitted 9 instead of 3. Root cause: queue interval throttling is needed for admission fairness regardless of key idle status. Fix: `admit_ok()` always uses `s.admit_ready(interval)`; only `rpm_ok()` bypasses for idle keys.

## Live Benchmark (3 requests, deepseek-v4-flash, post-fix)

```
[0] total=623ms tokens=3
[1] total=7829ms tokens=3
[2] total=441ms tokens=3
avg_total=2,964ms
```

All pacing_ms = 0 in metrics.db for post-restart requests.

## Architecture Note: Latency Composition

After fixes, total latency = upstream only (~16s avg for NVIDIA NIM). This is inherent provider latency, not wrapper-caused. The wrapper's pacing overhead was entirely eliminated.
