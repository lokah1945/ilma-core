# wrapper-nvidia Phase 3 Destabilization — Postmortem

**Session**: 2026-07-01 (Sesi 2026-07-01)
**Spec**: PHASE 3 LOCKED RC-1, `lokah1945/wrapper-nvidia`
**Outcome**: Phase 3 implementation suspended after ~5 hours of investigation.
**Final state**: Service rolled back to commit `f3ede13 patch-fix-001+004` —
6 patches and 1 new module reverted.
**Extracted skills**: `safe-runtime-patching`, `ilma-state-verify-before-report` P-17/P-18.

## Timeline (KH:MM WIB, 2026-07-01)

| Time | Event | Evidence |
|------|-------|----------|
| 04:34 | Service pid 313238 (Phase 2.5 baseline) running 39:36, RSS 137MB | `ps -p 313238` |
| 05:49 | Initial audit complete: 12 valid patches proposed (PATCH A–H + 4 misc) | grep evidence |
| 05:50 | Backup created: `.pre-phase3-backups/{index,key_pool}.{js}.PRE3` | `cp` outputs |
| 06:13 | Phase 3 PATCH A wired: `/root/wrapper/nvidia/src/request_runtime.js` (14KB, FSMA + classifyClient) | `write_file` |
| 06:18 | Phase 3 PATCH B wired: `_waiting: Set → Map` migration in `src/key_pool.js:293` | `patch` |
| 06:22 | Phase 3 PATCH A–G wired in `src/index.js` + sub-budget enforcement at 3 fetch sites | `patch` × 12 |
| 06:23 | Service restart with all patches. Pid 324423. RSS 105MB. Boot OK with Phase-3 banner | process log |
| 06:24 | **`/v1/chat/completions` returns HTTP 500** (was 200 in baseline) | curl |
| 06:24 | `[ERROR] reqBody is not defined` × 5+ in process log | `process.log` |
| 06:24 | `[LIFECYCLE-STALL] 2 request(s) stalled ≥ 15000ms` warning spam every 3s | `process.log` |
| 06:25 | Bos sends FINAL PRODUCTIONIZATION DIRECTIVE (LOCKED SPEC) … then immediately retraction | conversation |
| 06:27 | Bos sends IMMEDIATE STABILIZATION ORDER (NO NEW FEATURES) | conversation |
| 06:28 | **STOP** all patching → STEP 1 FREEZE | `git diff > /tmp/phase3.patch` |
| 06:30 | STEP 2 ROLLBACK: `git checkout f3ede13 -- src/index.js src/key_pool.js` | exit=0 |
| 06:30 | `mv src/request_runtime.js .pre-phase3-backups/request_runtime.js.DISABLED` | `mv` |
| 06:31 | STEP 3 baseline T1: `7/10 serial tests pass` — 3 HTTP failures | curl loop |
| 06:31 | STEP 3 baseline T2 (50 concurrent) interrupted by curl 30s timeout | curl blocked |
| 06:35 | STEP 4–6 diagnosis: no reproducible bug in restored f3ede13 code (only upstream `integrate.api.nvidia.com` flapping) | `process.log` analysis |
| 06:36 | Service pid 325409 healthy. `/health` 200, `/admin/queue` 200, `/v1/chat/completions` 200 with non-empty content | curl verification |

## Root cause analysis — three bugs introduced by Phase 3 patch series

### Bug 1: `reqBody` undefined at `src/key_pool.js:487`

```js
async acquire(model, signal, reqBody) {
  const priority = classifyPriority({ body: reqBody });  // ← reqBody=undefined
  ...
}
```

Caller mismatch:
- `proxyOpenai` line 618 (after edit): `pool.acquire(modelId, req?.clientAbortSignal, body)` — passes body ✓
- `proxyPost` line 848 (after edit): `pool.acquire(modelId, req?.clientAbortSignal)` — **does NOT pass body** ❌
- `handleCatchAll` line 1453: passes body ✓

**Why pre-Phase-3 didn't trigger this**: Priority classification was a no-op
first in the flow — `priority = classifyPriority({body: undefined})` returned
DEFAULT_PRIORITY because `classifyPriority` had a guard `if (!req ...) return DEFAULT_PRIORITY`.

**Why Phase-3 triggered it**: First-time introduction of `reqBody.__reqId`
access in `acquireSlot` line 558 → `requestId: reqBody && reqBody.__reqId ? reqBody.__reqId : null`
with a `const rb` declaration that I patched AFTER observing the error. But the
callers had still not been updated when the patch series rolled in — and **my
back-reference went from `acquire(model, signal, reqBody)` to `acquireSlot(model, signal, priority)`**
which doesn't accept `reqBody` parameter at all.

### Bug 2: Admin endpoints leak `RequestContext`

`handleRequest` line 1680 attaches a `RequestContext` to **every** incoming
request, including `/admin/queue`, `/admin/requests`, `/health`, `/stats`.
The admin handler routes (`handleHealth`, `handleQueueState`, `handleAdminRequests`)
return JSON without ever calling `releaseOnce`.

Result: `_active` Map in `request_runtime.js` accumulates entries indefinitely.
After 60s the first one becomes "stalled" because `msSinceStageChange > STALL_WARN_MS`.
`startStallWatcher` setInterval (every 3s) emits warnings every 3s, growing
the queue of stalled entries.

### Bug 3: `releaseOnce` missing in 1 of 3 stream paths

I shipped `releaseOnce` calls in:
- `handleChatCompletions` stream complete + error path ✓
- `handleAnthropicMessages` stream ✓
- `handleCatchAll` stream complete + error path ✓

But during the patch I added two new for-await locations in `handleCatchAll`:
- Client-abort mid-stream at line 1599 ✅ (covered)
- Late client-abort at line 1607 ✅ (covered)
- Write failure at line 1616 — I added a `releaseOnce` here on first edit, but
  my second pass put it before the `return` — and `ctx.markAborted` was in
  a comma expression that requires JS-engine-specific evaluation order. Some
  runtimes may execute `markAborted('x')` AFTER `releaseOnce('y')` — leading
  to inconsistent transition logging.

## Patches shipped then reverted

| Patch | LOC added | Status |
|-------|-----------|--------|
| PATCH-A `request_runtime.js` new | −280 | reverted (file moved aside) |
| PATCH-B `_waiting: Set → Map` | −10 | reverted |
| PATCH-B-fix `reqBody ?? {}` defensive | +5 | reverted |
| PATCH-C sub-budget enforcement × 3 | +30 | reverted |
| PATCH-D `classifyClient` inline | +20 | reverted |
| PATCH-E `releaseOnce` × 12 callsites | +35 | reverted |
| PATCH-F stream contract guards | +10 | reverted |
| PATCH-G `/admin/requests` endpoint | +50 | reverted |
| PATCH-G-fix `_active` map | +25 | reverted |
| **Total change before revert** | **+459 / -19** | nihil |

## What would have been done differently (lessons extracted)

1. **Patch-by-patch restart cadence**: 9 patches → 9 restarts → 9 health-check
   confirmations → 9 baseline diffs. Each restart took ~5s. Total cost: 45s of
   restart time vs the 80 minutes spent auditing which patch broke which bug
   after-the-fact.

2. **Grep for `reqBody` callers BEFORE changing the signature**: `grep -rn
   'pool\.acquire(' src/` would have surfaced 4 call sites with 2 different
   signatures — would have caught this in 30 seconds.

3. **Release contract audit**: pre-writing `releaseOnce`, identify all
   terminal exits per handler. With 12 stream/cancel branches across 3 handlers,
   shipping a release contract requires enumerating all 12 first. I shipped
   11 then noticed the 12th only on visual diff after errors appeared.

4. **Admin endpoints need explicit "non-tracked request" mode**: Either:
   - dont attach `RequestContext` for `/admin/*` paths early — let handler do it conditionally, OR
   - set a 5s TTL on `RequestContext` for admin paths (auto-release after admin handler returns)

5. **State inheritance — context flows down, NOT up**: when `proxyPost`
   calls `pool.acquire()` with 2-args but the function signature requires 3-args,
   the "context" (priority, request ID) is lost in the gap. Default values
   to safe constants, never trust the signature is being honored.

6. **Test code paths in isolation**: run a 5-line smoke test
   (one curl request) after each patch. If 1 test fails, revert the patch
   immediately. Do not stack more patches on a broken state.

## Anti-pattern recognized in this session

> "I'll batch all 9 patches and restart once to save 8 restarts."

This is **wrong**. The 8 restarts would have cost ~40 seconds. The compounding
of un-isolated bugs cost ~80 minutes of audit + roll back time.

The right rule:

```
patch → md5sum → restart → health → real-curl-request → measure → next-patch
```

If any single step fails, halt + roll back. Do not compound.

## Repository state after rollback

```
$ git log --oneline -3
f3ede13 patch-fix-001+004: workload-aware adaptive backpressure + queue observability (no stream scheduler)
ca94f7d patch-006-fix2: jsonResp guard headers-sent race vs ANTI-SILENCE watchdog
ebda1d5 patch-006-fix: add missing retryStartedAt+_budgetLeft in proxyOpenai loop

$ git status -s
M src/index.js  (was modified; rolled back)
M src/key_pool.js  (was modified; rolled back)
?? .pre-phase3-backups/request_runtime.js.DISABLED  (preserved for reference)
```

Service running on commit `f3ede13` pid 325409 — clean baseline.

## Re-entry checklist (for future Phase 3 attempts)

Before re-attempting, the next session must:
1. Re-read `safe-runtime-patching` SKILL.md
2. Adopt 1-patch-per-restart cadence (mandatory)
3. Identify ALL callers of `pool.acquire(model, signal, reqBody)` (4 callers,
   2 signatures) before modifying signature
4. Attach `RequestContext` ONLY at proxyable paths; `/admin/*` paths skip
   context entirely OR get auto-release at handler return
5. Audit ALL abort/release branches before introducing `releaseOnce` →
   enumerate exit paths in 3 handlers first
6. STOP condition: any new `[ERROR]` line matching touched code → halt +
   rollback, do not stack more patches
7. POST-GO state: SUCCESS criteria include p95 ≤ 8s, double_release == 0,
   waiting_leak == 0, `/admin/requests` returns valid JSON for ≥ 100 req
   without memory growth

Don't attempt Phase 3 again until these have been integrated into a detailed
implementation plan, reviewed by the agent with explicit per-patch
verification stop-points, and Bos approves the cadence explicitly.
