# Node.js Wrapper Bug Audit — 2026-06-28

**Project:** wrapper-nvidia Node.js variant at `/root/wrapper/nvidia/`
**Version:** package.json 4.4.0, index.js VERSION 4.5.0-node, hardcoded 4.1.0
**Scope:** Full source audit of 7 src/ files (3,663 lines) + test + service
**Method:** Complete source read + Node.js runtime verification + control flow tracing

## Findings Summary

| # | Severity | Bug | Location | Status |
|---|----------|-----|----------|--------|
| 1 | 🔴 CRITICAL | `result.retry` dead-code — outer retry loop never fires | index.js L661, L758 | OPEN |
| 2 | 🔴 CRITICAL | In-flight key leak on Anthropic error path | index.js L806-814 | OPEN |
| 3 | 🔴 CRITICAL | `readBody()` no size limit — OOM vector | index.js L64-69 | OPEN |
| 4 | 🟠 MEDIUM | Stream `catch {}` swallows errors + loses metrics | index.js L685, L775 | OPEN |
| 5 | 🟠 MEDIUM | Potential double-release in handleChatCompletions error path | index.js L727 | OPEN |
| 6 | 🟠 MEDIUM | Hardcoded version `4.1.0` outdated | index.js | OPEN |
| 7 | 🟠 MEDIUM | proxyPost image/binary path key release unclear | index.js L607+ | NEEDS VERIFICATION |
| 8 | 🟡 LOW | Default port 9101 ≠ service port 9100 | index.js L25 | OPEN |
| 9 | 🟡 LOW | `total429s` double-count (recordRateLimit + onRateLimit) | key_pool.js L164-194 | OPEN |
| 10 | 🟡 LOW | Mutex double-release risk | key_pool.js L47-53 | OPEN |

## BUG-1: `result.retry` Dead-Code

### Detail

`proxyOpenai()` has an **internal** retry loop (`while (attempt <= MAX_RETRIES)`) that handles 429, 400 (param strip), 500, and network errors by incrementing `attempt` and `continue`. All return paths from `proxyOpenai()` return plain status objects — **none** include `retry: true`:

```js
// Return paths — NONE have retry property:
L371:  return { status: 404, data: {...} };
L392:  return { status: 503, data: {...} };
L432:  return { status: 429, data: {...} };   // ← retried internally, returns final 429
L463:  return { status: 400, data: {...} };
L486:  return { status: resp.status, data };
L490:  return { status: 200, stream, key, model, startMs, pacingMs };
L503:  return { status: 200, data, key };
L520:  return { status: 408/502, data };
```

Meanwhile, `handleChatCompletions` (L657-731) and `handleAnthropicMessages` (L734-817) have outer retry loops:

```js
// L659 handleChatCompletions
while (retries <= QUIET_RETRIED_429) {    // QUIET_RETRIED_429 = 3
    const result = await proxyOpenai(...);
    if (result.retry && retries < QUIET_RETRIED_429) {  // ← ALWAYS FALSE
        retries++;
        continue;
    }
    // ... handle result
}
```

### Impact

Outer retry loop always exits after 1 iteration. `QUIET_RETRIED_429=3` is effectively 0. When internal retries fail, the 429 is returned to client with no chance for outer handler to try a different approach.

### Recommended Fix

**Option A (cleaner):** Remove dead outer retry from both handlers. ProxyOpenai already retries internally.

**Option B (richer):** Have proxyOpenai return `{ status: 429, retry: true, data }` when internal retries are exhausted but a key-switch retry at the outer level might help. This enables the outer loop to re-acquire a potentially different key.

## BUG-2: In-Flight Key Leak on Anthropic Error Path

### Detail

```js
// L799-803 — SUCCESS path (key released ✅)
if (result.status === 200 && result.data) {
    const anthroResp = openaiToAnthropic(result.data, aBody.model);
    jsonResp(res, 200, anthroResp);
    if (result.key) pool.releaseSuccess(result.key);
    return;
}

// L806-814 — ERROR path (key NOT released ❌)
const errData = result.data || {};
const errMsg = errData?.error?.message || `Upstream error ${result.status}`;
const errType = result.status === 429 ? 'rate_limit_error' : ...;
jsonResp(res, result.status, anthropicError(errType, errMsg));
// ← NO pool.releaseSuccess(result.key) before return
return;
```

### Impact

Every non-200 response from proxyOpenai in the Anthropic path leaks `inFlight` counter on the key. Over time, `key.inFlight` monotonically increases → `key.effectiveLoad` rises → `acquireSlot()` avoids the key → permanent throughput degradation.

Note: For some proxyOpenai return paths (400, non-200 generic), the key was **already released inside proxyOpenai** (L462, L485). Releasing again in the handler would cause double-release → `inFlight` goes negative. The correct fix requires understanding **which return statuses have already-released keys**.

### Key Release Ownership Map (proxyOpenai returns)

| Status | Key released in proxyOpenai? | Handler should release? |
|--------|------------------------------|------------------------|
| 404 (L371) | Yes (no key acquired yet at this point) | No |
| 503 (L392) | Yes (acquire returned null) | No key to release |
| 429 (L432) | Yes (L421: releaseRateLimited) | No |
| 400 (L463) | Yes (L462: releaseSuccess) | No — double-release risk |
| 5xx retry exhausted | N/A (loop exits with continue → doesn't return) | — |
| Non-200 other (L486) | Yes (L485: releaseSuccess) | No — double-release risk |
| 200 stream (L490) | No (key still in-flight for streaming) | Yes (after stream complete) |
| 200 data (L503) | Yes (L502: releaseSuccess) | No — double-release risk |
| 408/502 network (L520) | Yes (L519: releaseSuccess) | No — double-release risk |

**Critical realization:** Most proxyOpenai error return paths have ALREADY released the key. Only the 200-stream path leaves the key in-flight. So BUG-2 is actually a **non-issue** for error paths — the key was already released. The real risk is the opposite: handler **double-releasing** on paths where proxyOpenai already released.

This changes BUG-2 from a "leak" to a "potential double-release" — still a bug, but different impact.

## BUG-3: readBody() No Size Limit

### Vulnerability

```js
function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));          // ← No limit
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}
```

A single request with `Content-Length: 1073741824` (1GB) causes ~1GB heap allocation → OOM crash, taking down the entire proxy.

### Fix

```js
const MAX_BODY = 10 * 1024 * 1024; // 10MB
function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', c => {
      size += c.length;
      if (size > MAX_BODY) {
        reject(new Error('Body too large'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}
```

## Additional Findings

### KeyPool.acquireSlot() — Well-Structured

The `acquireSlot()` method (L416-531) uses a Mutex-protected loop with:
- Ticket-based fairness (`_waiting` Set + myTicket sequencing)
- Pacing timeout (`pacingMaxWait = 60s`)
- Dual wait targets: RPM-based (`rpm_ok`) + admission interval (`admitOk`)
- Round-robin tiebreaking on equal-load keys

No race conditions found in the acquire path. Mutex acquisition and release are properly paired in try/finally.

### Mutex Implementation — Lightweight but Lacks Guard

```js
class Mutex {
  acquire() { ... }
  release() {
    if (this._queue.length > 0) { const next = this._queue.shift(); next(); }
    else { this._locked = false; }   // ← No guard against double-release
  }
}
```

Double-release sets `_locked = false` while a holder is still in critical section → two concurrent holders possible.

### Stream Processing — Two Implementations

1. **OpenAI path** (handleChatCompletions L673-724): Direct `reader.read()` loop, buffer-accumulates stream, parses `lastUsage` from final SSE chunk. Error swallowed by `catch {}`.
2. **Anthropic path** (handleAnthropicMessages L763-796): Uses `streamOpenaiToAnthropic()` generator from `anthropic_compat.js`. More sophisticated (proper SSE event conversion, tool call tracking). Also error swallowed by `catch {}`.

Both paths have the same `catch {}` issue — stream errors are invisible to the client and metrics.

### Version Inconsistency

| Source | Version |
|--------|---------|
| package.json | 4.4.0 |
| index.js `VERSION` const | 4.5.0-node |
| key_pool.js version ref | 4.4.0-node |
| Hardcoded string in code | wrapper-nvidia-4.1.0 |

Recommend: Unify to single source. VERSION const in index.js should be the authoritative version; package.json matches on release.

### Port Default Mismatch

| Context | Port |
|---------|------|
| index.js default (`process.env.LISTEN_PORT \|\| '9101'`) | 9101 |
| wrapper-nvidia.service `Environment=LISTEN_PORT=9100` | 9100 |

When running `node src/index.js` directly (no env var), wrapper listens on 9101 — not matching service convention.

## Architecture Notes

### Dual Retry Architecture

```
Client Request
  → handleChatCompletions (outer retry: QUIET_RETRIED_429 = 3 tries)
      → proxyOpenai() (inner retry: MAX_RETRIES = 3 attempts per call)
          → pool.acquire() → key acquisition
          → undiciFetch() → upstream request
          → handle status: 429/400/500/network with internal retry
      ← result object (NO retry property ever set)
  → handleChatCompletions checks result.retry → ALWAYS FALSE → exits after 1 iteration
```

This is a redundant double-retry where only the inner one actually works.

### Key Lifecycle

```
pool.acquire(model) → key = keyResult.key → key.incrementInFlight()
  → proxyOpenai() uses key
  → Success: pool.releaseSuccess(key) → key.decrementInFlight()
  → 429: pool.releaseRateLimited(key) → key.decrementInFlight() + recordRateLimit
  → Error: pool.releaseSuccess(key) in proxyOpenai → key.decrementInFlight()
  → handler receives result
  → If handler ALSO calls releaseSuccess → DOUBLE DECREMENT → inFlight negative
```

**Lesson:** When proxy function and handler both can release keys, ownership MUST be documented per return path. Without it, either leaks or double-releases are inevitable.

## Audit Checklist Template (Reusable for Any Wrapper)

1. [ ] Body size limits on all request readers
2. [ ] `result.retry` / retry-loop: producer sets it? consumer checks it?
3. [ ] Key in-flight: EVERY acquire has a matching release on ALL paths
4. [ ] Key release ownership: document who owns release per status code
5. [ ] Stream error handling: catch block logs + records partial metrics
6. [ ] Mutex / lock: double-release guard
7. [ ] Counter integrity: no double-increment on same event
8. [ ] Version consistency: package.json = VERSION const = hardcoded strings
9. [ ] Port consistency: code default = service Environment=
10. [ ] Error boundaries: no empty catch blocks that swallow silent failures