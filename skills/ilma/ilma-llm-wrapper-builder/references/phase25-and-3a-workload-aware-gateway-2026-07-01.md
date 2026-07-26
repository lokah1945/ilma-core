# Wrapper-Runtime Hardening Phase 2.5 → 3A — 2026-07-01

> Companion to `references/phase-based-hardening-wrapper-runtime-2026-06-30.md`
> (Phase 1 STABILIZE + Phase 2 VALIDATE 7-test protocol). This captures the
> **post-validation pivot** to `WORKLOAD-AWARE GATEWAY` (PHASE 2.5) and the
> **proof-of-necessity discipline** (PHASE 3A).

## Why This Phase Exists

PHASE 1 verdict: STABLE-CANDIDATE (not production-ready).
PHASE 2 verdict: NOT MULTI-AGENT READY (3/7 pass, T-005 critical fail).

T-005 — queue silently absorbs all — surfaced that fix needs depth
classification, not just threshold tuning. Boss redirected to
**WORKLOAD-AWARE GATEWAY** (priority_class, not per-client queue). Then PHASE 3
universal-agent gateway requested, but only after **audit validation** (3A:
prove the new module is necessary before coding).

## PHASE 2.5: Workload-Aware Backpressure (Approved)

### PATCH-FIX-001 — Backpressure by capacity × priority

**Problem (T-005):**
- 800 req burst → 472 timeout 000, 328 OK
- `MAX_QUEUE_SIZE=500`, `INFLIGHT_SOFT_CAP=50` env-defined but unused in code
- 503 never fired → clients see TCP close

**Design (key_pool.js):**

```js
computeDynamicCapacity() {
  const healthyKeys = this.keys.filter(s => !s.isHardBlocked()).length;
  const effectiveRps = parseInt(process.env.CAPACITY_EFFECTIVE_RPS || '4', 10);
  const targetLatency = parseInt(process.env.CAPACITY_TARGET_LATENCY_MS || '5000', 10);
  const capacity = Math.max(10, Math.min(500, healthyKeys * effectiveRps * targetLatency / 1000));
  return { capacity, soft: capacity * 1.1, reject: capacity * 1.5, healthy: healthyKeys, total: this.keys.length };
}

shouldDenyByCapacity(priority) {
  if (!this._backpressureEnabled) return null;
  const cap = this.computeDynamicCapacity();
  const inflight = this.getInflightTotal();
  if (inflight >= cap.reject) return { reason: 'capacity-reject', inflight, threshold: cap.reject, capacity: cap };
  if (inflight >= cap.soft && priority !== PRIORITY.INTERACTIVE && priority !== PRIORITY.STREAM) {
    return { reason: 'capacity-soft-interactive-only', inflight, threshold: cap.soft };
  }
  return null;
}
```

**Three-tier priority** (replaces per-client fairness):
- `stream=true` body → `STREAM`
- `max_tokens > 4000` → `BATCH`
- else → `INTERACTIVE`
- fallback `BACKGROUND`

**Stream slots** (adaptive): `max(1, floor(active_capacity × min(0.4, stream_ratio)))`

**Acquire signature (canonical, 3-arg):**
```js
pool.acquire(model, signal, reqBody)
// → { key, denied, reason, retry_after_ms, waitedMs, priority }
```

**Wire at 3 sites** (src/index.js 605, 817, 1358):
```js
const keyResult = await pool.acquire(modelId, req?.clientAbortSignal, body);
if (keyResult && keyResult.denied) {
  return { status: 503, data: { error: { message: 'overloaded', type: 'overloaded', reason: keyResult.reason, retry_after_ms: 1000 } }, headers: { 'Retry-After': '1' } };
}
```

**Mid-loop recheck** (acquireSlot line 519-524):
```js
if (typeof dynamicCapacityCheck === 'function') {
  const capMid = dynamicCapacityCheck(priority);
  if (capMid && capMid.deny) return [null, 0.0];
}
```

### PATCH-FIX-004 — Queue Observability (`/admin/queue`)

```js
queueSnapshot() {
  const cap = this.computeDynamicCapacity();
  const inflight = this.getInflightTotal();
  const byPri = {};
  for (const k of Object.keys(this._waitingByPri)) {
    const m = this._waitingByPri[k];
    const arrivalAges = [...m.values()].map(t => Date.now() - t).sort((a,b) => b-a);
    const p50 = arrivalAges[Math.floor(arrivalAges.length * 0.5)] || 0;
    const p95 = arrivalAges[Math.floor(arrivalAges.length * 0.95)] || 0;
    byPri[k] = { waiting: m.size, oldestWaitMs: arrivalAges[0] || 0, p50, p95 };
  }
  return { capacity: cap, inflight, waiting: this._waiting.size, byPri, buckets, eventLogLast };
}
```

**Endpoint** (token-gated):
```json
{
  "capacity": { "capacity": 100, "soft": 110, "reject": 150, "healthy": 5, "total": 5 },
  "inflight": 0, "waiting": 0,
  "byPri": { "interactive": {...}, "stream": {...}, "batch": {...}, "background": {...} },
  "buckets": { "stream": { "admitted": 200, "denied": 0, "totalLatency": 532849 } },
  "eventLogLast": [{"ts": ..., "kind": "admit", "pri": "stream", "waitMs": 5}]
}
```

### PHASE 2.5 Verification

TEST-A v5 with curl burst (200 stream req parallel -P50):
- 170× HTTP 200 (3-30s response)
- 30× HTTP 000 (curl client timeout 30s)
- `/admin/queue` after: `stream.admitted=200, stream.denied=0`
- **0× 503 fired** — backpressure threshold (reject=150) above parallel burst

**Lesson:** Threshold-based backpressure alone is insufficient for
multi-priority admission when burst < capacity ceiling. Need _queue-level_
gate, not just inflight-level. See PHASE 3A.

### Commit

`f3ede13` — `patch-fix-001+004: workload-aware adaptive backpressure + queue observability`

## PHASE 3A: Proof of Necessity Audit (NEW DISCIPLINE)

Bos's lesson: **don't add a new module because it's appealing**. Audit existing
capability before proposing new abstraction.

### The 5-Step Discipline

```
LANGKAH 1: STATE INVENTORY
   Per-stage table:
     received → queued → acquiring → upstream → stream → finalize → release
   Owner module | entry | exit | timeout | abort source | cleanup

LANGKAH 2: MAPPING GAP
   EXISTS / PARTIAL / MISSING per capability
   Module BARU hanya jika MISSING > 30%

LANGKAH 3: DEADLINE SIMULATION
   JANGAN coding. Simulasi 45s budget:
     queue 9s / acquire 7s / upstream 24s / finalize 5s
   Hitung berapa request mati.

LANGKAH 4: CLIENT PROFILING
   JANGAN identify Hermes/Claude/OpenCode by name. Ukur transport signals:
     path, User-Agent substring, anthropic-version, Accept stream,
     tool_calls/body shape.

LANGKAH 5: PROVE REUSE
   Implement capability baru TANPA module baru.
   Jika bisa: TOLAK module.
   Jika tidak: lanjut ke proposal.

GO/NO-GO:
   MISSING > 30% AND reuse < 70% AND LOC < 500 AND memory < 10MB
```

### Applied to PHASE 3 (audit output for `request_runtime.js`)

| Capability | Status | Reuse sufficient? |
|-----------|--------|-------------------|
| Queue gate | EXISTS (`acquireSlot` `_waiting.size >= maxQueueSize` 506) | ✅ |
| Capacity reject | EXISTS (`shouldDenyByCapacity` 890) | ✅ |
| Mid-loop capacity check | EXISTS (`dynamicCapacityCheck` 519-524) | ✅ |
| Abort signal to upstream | EXISTS (`AbortSignal.any([timeout, client])` 638-640, 831-833, 1384-1386) | ✅ |
| Client disconnect cancel | EXISTS (`req.clientAbortSignal` 1047, 1057) | ✅ |
| Release on stream completion | EXISTS (`streamReleased` guard 1035) | ✅ |
| Retry budget cap | EXISTS (`RETRY_BUDGET_MS=15000` + `_budgetLeft()`) | ✅ |
| Provider circuit breaker | EXISTS (`ErrorTaxonomy.recordProviderFail` + `acquireProviderCircuitCheck`) | ✅ |
| Anti-silence watchdog 45s | EXISTS (`handleRequestWithSilenceGuard` 2198) | ✅ |
| Stream heartbeat | EXISTS (`installHeartbeatInterval` 28, env-gated OFF) | ✅ |
| Queue observability | EXISTS (`/admin/queue`) | ✅ |
| **Lifecycle FSM (RECEIVED→DEADLINE_EXCEEDED)** | **MISSING** | ❌ no per-request state |
| **Per-request deadline_at** | **MISSING** (only `AbortSignal.timeout` per-fetch) | ❌ no deadline tracking |
| **Sub-budget split** | **MISSING** | ❌ single retry budget |
| **Lifecycle warning >15s** | **PARTIAL** (anti-silence 45s last-ditch) | ❌ no interval watcher |
| **Client capability detection** | **MISSING** | (inline ~50 LOC possible) |
| **Cancellation cleanup 1500ms** | **MISSING** (best-effort) | ❌ |
| **/admin/requests endpoint** | **MISSING** | (extend `/admin/queue`) |
| **Per-stage latency histogram** | **MISSING** (only total) | ❌ |

**EXISTS=10, PARTIAL=1, MISSING=8 → MISSING ratio = 42% > 30%** ✅ GO criterion.

### Reuse Test Results

| Capability | Reuse possible? | Why |
|-----------|----------------|-----|
| Lifecycle warning 15s | ❌ | `_waiting: Set<number>` no timestamp → can't detect "one tiket stuck" |
| Sub-budget enforcement | ❌ | Need identity per request for per-stage time bounds |
| Cancellation cleanup 1500ms | ❌ | Need enforced cutoff at 4 stream sites |
| Client classification | ✅ | Inline function di handleRequest ~50 LOC, no module |
| `/admin/requests` | ✅ | Reuse observability layer + add fields |
| Per-stage latency histogram | ❌ | Need timestamp per stage |

**Reuse score**: 2/6 = 33% → **< 70% → GO runtime module**.

### Module Decision (PHASE 3A recommendation)

| Layer | LOC | Contents |
|-------|-----|----------|
| `src/request_runtime.js` (NEW) | ~180 | FSM (RECEIVED→QUEUED→ACQUIRING→UPSTREAM→STREAMING→COMPLETED/FAILED/CANCELLED/DEADLINE_EXCEEDED), deadline_at, lifecycle logging |
| `src/key_pool.js` (modify) | +30 | `_waiting: Set<number>` → `Map<id, ctx>` for deadline |
| `src/index.js` (modify) | +50 | Wire `RequestContext` di 4 callsites, `/admin/requests`, lifecycle watcher |
| `client_profile.js` (skip — inline) | 0 | Inline `classifyClient(req, body)` di handleRequest ~50 LOC |
| **Total delta** | **~260 LOC** | Within 500 LOC threshold |

### Hard-Won Lessons

1. **Audit before coding is non-negotiable.** Phase 2.5 nearly coded
   `request_runtime.js` (full FSM) — Bos interrupted with "approval
   bersyarat", forcing audit-first. Audit revealed **50%+ already existed**
   → saved ~120 LOC.

2. **MISSING > 30% is the green light, not "module is appealing".** Counting
   EXISTS/PARTIAL/MISSING per capability (not per-line) gives defensible
   threshold.

3. **Reuse 70% = bar, not suggestion.** Even with MISSING > 30%, if reuse
   can cover ≥70%, refactor existing instead of module new.

4. **Inline-class-over-module for transport signals.** Client detection via
   path/UA/anthropic-version header doesn't need module — one function inline
   suffices.

5. **Lifecycle watcher setInterval needs identity per-tiket.** `Set<number>`
   can't detect "request stuck" → `Map<id, ctx>` minimal refactor.

6. **Production-ready proof = evidence-bound.** Phase 2 T-005 "silent queue
   absorbs all" is concrete evidence. `[ref: silent queue absorbs 472/500
   timeout]` stronger than `[ref: theoretically overflows]`.

7. **Live snapshot verifies wiring, not just code presence.** TEST-A v5
   showed `stream.denied=0` even at 200 parallel — proving code presence
   ≠ behavior. Always measure real output.

## Verification Commands (for future audits)

```bash
# Phase 2.5 backpressure live check
curl -s -H "X-Admin-Token: changeme" http://localhost:9100/admin/queue | jq '{capacity, inflight, waiting, buckets}'

# State inventory grep (post-PHASE 3A expectations)
grep -nE "RECEIVED|QUEUED|ACQUIRING|DEADLINE_EXCEEDED" src/index.js src/key_pool.js
# 0 hits pre-Phase-3; new hits after FSM module lands

# Reuse test — inline client classifier
grep -nE "classifyClient|user-agent|userAgent" src/index.js
```

## Companion Files

- `references/phase-based-hardening-wrapper-runtime-2026-06-30.md` (predecessor)
- `references/nodejs-wrapper-bug-audit-2026-06-28.md` (Node.js variant)
- `references/silent-hang-audit-wrapper-nvidia-2026-06-30.md` (predecessor audit)
