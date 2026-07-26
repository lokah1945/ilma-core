---
name: safe-runtime-patching
description: Class-level skill for patching long-running production daemons safely — audit-before-code, per-patch evidence gates, ≤30 LOC hotfix rule, GO/NO-GO matrix, rollback-first discipline. Triggered whenever the plan touches a running service (wrapper, proxy, queue, daemon, watch loop) and the task is "improve X, fix Y, add metric Z". Distinct from `ilma-comprehensive-optimizer` (whole-system sweep via cron) and from one-shot debugging skills (those address an open bug, not a closed-loop patch workflow). Critical for Sesi 2026-07-01 wrapper-nvidia Phase 3 (459-line patch reverted; 3.5+ hour stabilization). Activated on user requests like "patch production safely", "audit before code", "rollback when broken", "small batch only", "evidence-gated patch", "RC-1 LOCKED", or any LOCKED SPEC where Bos explicitly demands INVESTIGATE → DESIGN → APPROVE → IMPLEMENT → VERIFY.
---

# Safe Runtime Patching — protocol for production daemons

## When to apply

Apply **before** opening a `patch` / `write_file` against a file that runs in a long-lived process when:
- The service is on systemd / supervisor / watch loop (PPID=1, restart-on-exit, etc.)
- The patch involves state ownership, lifetime, or shutdown
- The change touches shared state (queue, inflight, retry, abort, signal)
- Total LOC across all sub-patches is > 30

If any of the above is true, run the full INVESTIGATE → DESIGN → APPROVE → IMPLEMENT → VERIFY loop.
Otherwise, a single targeted hotfix may skip directly to step 4.

## The 5-step protocol

```
INVESTIGATE  →  DESIGN  →  APPROVAL  →  IMPLEMENT (one at a time)  →  VERIFY
```

### Step 1 — INVESTIGATE (no code changes, only read + tool calls)

Produce:
- **State inventory**: per stage — owner module, entry, exit, timeout, abort source, cleanup
- **Gap matrix** (EXISTS / PARTIAL / MISSING + count of each)
- **Hard evidence**: `grep -rn`, `read_file`, `process_log`, `/proc/<PID>/cwd`, `systemctl status`, `curl /health`
- **Real numbers**: RSS, uptime, inflight, waiting, error rate, p95 — from curl + `/admin/queue`

Forbid: "should be", "likely", "probably", "estimated". Only "is / is not / observed".

### Step 2 — DESIGN (no code, only patch plan)

Output **per patch** with this shape:
```
PATCH-XXX
  Problem:    (1 line describing what is wrong)
  Root Cause: (file:line + why it manifests)
  Design:     (1-3 line description of the change)
  Risk:       (what can break)
  Rollback:   (how to undo — usually `git checkout <commit> -- <files>`)
  Verification: (curl command + expected exit + timeout window)
```

Constraints:
- One file per hotfix (`hotfix-NNN`)
- ≤ 30 LOC per hotfix patch (excluding comments)
- No new module unless `MISSING > 30%` of capability surface
- No new endpoint unless asked
- No new env var unless asked
- Public-API-stable — call sites match without modification if possible

### Step 3 — APPROVAL

Bos must approve BEFORE implementing. STOP signal:
> "STOP. TUNGGU PERSETUJUAN."

Show ONLY the patch plan, the risks, the rollback mechanism, and **wait**. Do not implement until explicit "OK lanjutkan" / "GO" / "implement" comes.

### Step 4 — IMPLEMENT (one patch at a time, never batch)

For each PATCH-XXX:
1. `cp <file> .pre-phaseN-backups/<file>.PRE<N>` — backup
2. `node -c <file>` — syntax check **before**
3. `md5sum <file>` — record baseline
4. `patch <file>` with the planned change
5. `node -c <file>` — syntax check **after**
6. `md5sum <file>` — confirm the diff is bounded
7. (if runtime is restarted) restart and verify `/health` and one real request

**Hard rule**: do NOT begin PATCH-N+1 until PATCH-N's verification runs. If PATCH-N's verification fails, STOP and rollback.

### Step 5 — VERIFY (must pass before next patch)

Minimum verification per patch:
- `node -c <file>` → exit 0
- `/health` if exposed → 200
- Real proxy/health endpoint → 200 with expected JSON shape
- `/admin/queue` (or equivalent observability) — capture inflight/waiting/healthy counts before & after — diff ≤ baseline noise
- One real-world-shape request — record status code, body sample, latency — must pass

STOP conditions (immediate halt + rollback):
- p95 latency regression > 15% from baseline
- Any HTTP 500 in the proxy path
- `kill -0 <PID>` returns non-zero
- Process log shows new ERROR lines matching touched code
- Memory RSS delta > ±10 MB
- New `double_release` or `negative_inflight` or `waiting_leak` metric non-zero
- Provider OPEN > 5 minutes during patch verification

## Audit gate (before any code is written)

Output required BEFORE any `patch` call:
- Lifecycle state inventory (each stage: owner, entry, exit, timeout, abort source, cleanup)
- Gap matrix
- Concrete repro for any reported issue
- Failure recovery chain already documented

## GO / NO-GO matrix (must pass before implementation)

| Gate | Threshold | Test |
|------|-----------|------|
| Reuse score ≥ 70% | `existing_modules / total_needed ≥ 0.7` | static count |
| MISSING ratio ≥ 30% | justified need for new module | static count |
| LOC growth ≤ 500 | sum of proposed patch LOC | code review |
| Memory delta < 10 MB | estimated Map/interval overhead × items | compute |
| Latency overhead < 1% per request | Map lookup vs Set lookup, ~ns | compute |

If any gate fails: do NOT proceed to DESIGN — return to INVESTIGATE with the constraint to reuse more aggressively.

## Rollback protocol (when verification fails mid-implementation)

```bash
# Identify last healthy commit
git log --oneline -10
# Last commit with /health 200 + 1 successful real proxy before the patch series

# Roll back ONLY tracked source files (R1: do not touch backup jars / systemd units / .env)
git checkout <healthy_commit> -- src/<file1> src/<file2> ...

# Restart
kill <PID>; sleep 2
<restart_command>

# Verify clean state
curl -fs http://localhost:<port>/health && \
curl -fs -H "X-Admin-Token: ..." http://localhost:<port>/admin/queue

# Pause and inform Bos
# Output: "RUNTIME ROLLED BACK TO <healthy_commit>. <N> patches reverted. Pausing for analysis."
```

NEVER "patch forward" to fix a patch that broke something. The bug you don't understand won't be fixed by stacking more changes on top.

## Execution modes (recognize which one Bos is invoking)

Determine the mode from the brief BEFORE writing any patch plan. Bos has
three recurring modes when talking about runtime evolution:

### Mode A — INVESTIGATE / DESIGN / APPROVE / IMPLEMENT / VERIFY
- Default mode. Full 5-step protocol above applies.
- Trigger: "audit X", "design patch", "implement Y", "review Z".

### Mode B — UAEC v1.0 LOCKED CONTRACT (audit-only, hotfix-or-nothing)
- Trigger phrases: "UAEC", "freeze_feature=true", "allow_hotfix_only=true",
  "no new endpoints/modules", "no new observability", "hotfix only if
  reproducible+isolated+rollbackable", "RC-1 STABLE", "STOP CONDITION:
  p95>15s/double_release>0/waiting leak>0/provider open>5m/RSS+15%".
- Strict contract:
  1. **Agent is CLIENT, runtime is SERVER** — never let agent name (Hermes /
     Claude Code / OpenCode) determine execution semantics; clients are
     observed by capability (transport, mode, tooling, abort support), not
     labeled.
  2. **Single concern per patch** — never combine observability + lifecycle
     + timeout + queue + release + stream into one patch.
  3. **No restart before** syntax check + static diff review + rollback
     command ready.
  4. **Output format**: literal `OBSERVE | EVIDENCE | ROOT CAUSE | FIX |
     VERIFY | ROLLBACK | NEXT`. No "should", "akan", "estimated",
     "kemungkinan", "harusnya", "diperkirakan" — only tool-measured
     numbers and `kill -0`-style facts.
  5. **Hotfix only when**: (a) bug is reproducible, (b) change is isolated
     to ≤1 file, (c) rollback mechanism exists, AND (d) `git diff` is the
     verification proof.
- Default decision template when asked "implement X" under UAEC:
  ```
  STATE: RC-1 FROZEN
  COMMIT: f3ede13
  freeze_feature=true
  phase3=false
  allow_hotfix_only=true
  new_module=denied
  new_endpoint=denied
  Verification gate before any patch:
    health=200 queue=stable 100_reqs≥99% stream complete
    abort<1500ms release double_release==0 memory<+15%
  ```
- See `references/uaec-v1.0-contract.md` for the full spec.

### Mode C — RC-N PROMOTION AUDIT (audit/test only, no patch)
- Trigger phrases: "RC-1 → RC-2 promotion", "audit and test only",
  "PASS/FAIL + evidence", "no patch", "no restart", "no feature",
  "promotion plan", "multi_agent=true".
- Strict contract:
  1. **No patch**, **no restart**, **no feature**, **no new endpoint**.
  2. **Output**: only PASS / FAIL or PASS / FAIL / DEFERRED / NOT-RUN with
     measured evidence.
  3. **Phases** (run sequentially, no skipping):
     - **PHASE 0 LOCK**: confirm `git log -1` = frozen commit, `git diff`
       empty, runtime pid alive. 3 PASS items only, no creative leeway.
     - **PHASE 1 CANARY**: sample /health, /admin/queue (or admin/requests
       if present), RSS, healthy_keys every N seconds. External sampler
       script only — never add observability to runtime.
     - **PHASE 2 CLIENT CERT**: capability matrix × {openai, anthropic,
       generic_http} × {stream, non_stream} × {tool_call, plain_chat} ×
       {abort, no-abort}. Pass = HTTP 200 + correct content shape.
     - **PHASE 3 LOAD**: N=100, N=300, N=800 sequential or concurrent
       senders; success rate ≥ 99% / 98% / 95%. Backpressure is owned
       by runtime, asserted by client.
     - **PHASE 4 FAILURE INJECTION**: provider timeout, provider 5xx,
       client disconnect, retry exhausted, abort mid-stream. Pass =
       runtime recovers without restart, no orphaned tickets.
     - **PHASE 5 DECISION**: emit explicit verdict (PASS / INCONCLUSIVE /
       FAIL) based on which phases ran vs which were DEFERRED. Never
       claim PASS for a DEFERRED gate.
  4. **Stop signals**: any FAIL → STOP. Any NOT-RUN → INCONCLUSIVE
     (do NOT promote).
- See `references/rc-promotion-runbook.md` for the full template + sampler
  script.

### ❌ Antipattern 1: "I'll batch all patches and restart once"
Saves restarts but loses isolatability. When roll back time comes, you revert N patches you didn't actually need to revert.

### ❌ Antipattern 2: "This patch fails — I'll patch again to fix it"
Compounds errors. Creates N+1 patches wrong. Use rollback to last known-good.

### ❌ Antipattern 3: "Cleanup contract is non-essential — the OS reclaims it"
Until your daemon has 80k open sockets and the file descriptor pool exhausts. Cleanup is mandatory.

### ❌ Antipattern 4: "I'll test in production — there's no other env"
Run the test suite in this same daemon via curl + new endpoint. If real request fails 500, that's the test failing in production — STOP.

### ❌ Antipattern 5: "Documentation says X — that's enough evidence"
Read the actual file. `grep` the behavior. Trust the runtime, not the spec sheet.

### ❌ Antipattern 6: "Caller is 2-arg, callee is 3-arg — JS errors will be obvious"
**Confirmed twice in production** (2026-07-01). When you change a function's
signature, every caller with the OLD signature must be migrated in the same
patch — otherwise JS throws `ReferenceError: <param> is not defined` deep
inside the call, which surfaces as HTTP 500 to clients with no obvious
trace. Pattern:
```js
// OLD caller: pool.acquire(model, signal)
// NEW signature: pool.acquire(model, signal, reqBody)
const safeBody = (typeof reqBody === 'object' && reqBody) || {};
const priority = classifyPriority({ body: safeBody });  // defensive
```
Always include the defensive default at the signature change. Then
`grep -rn 'pool\\.acquire(' src/` and verify all 4 callers match.

### ❌ Antipattern 7: "Attach request-tracker to every entry path"
When introducing a `RequestContext`-style tracker, every endpoint that
touches `req` (including `/health`, `/admin/*`) starts accruing entries.
If the admin/control handlers don't call `releaseOnce`, the entries leak
indefinitely and an upstream "stall detector" setInterval will fire every
3s with growing lists. Options:
(a) Only attach at proxyable paths (skip `/admin/*`, `/health`),
(b) Auto-release at handler return,
(c) Set TTL on the tracker map.

### ❌ Antipattern 8: "I'll re-attempt the same Phase-3 patch series with fixes"
If Phase-3 destabilized the runtime once, the next attempt must:
1. Run 1-patch-per-restart cadence (NOT batch-then-restart),
2. Replay each previous bug category with the **defensive patches**
   preemptively in place (Antipatterns 6, 7),
3. Confirm `/health=200` AND a real proxy request 200 BEFORE
   moving to the next patch,
4. STOP at the first new ERROR line, do not stack more.

The same bugs will recur if not addressed at category level, not patch
level.

### ❌ Antipattern 9: "The daemon is up ⇒ systemd unit exists"
**Confirmed 2026-07-01**. Runtime may be PPID=1 (orphan) with no systemd
unit. `systemctl --user status <name>` returns `Unit could not be found`
even when pid is alive. To discover:
```bash
PID=$(ps aux | grep -E 'node.*src/index.js' | grep -v grep | awk '{print $2}' | head -1)
readlink -f /proc/$PID/cwd
cat /proc/$PID/environ | tr '\0' '\n' | grep -E '^(LISTEN_)?PORT='
cat /proc/$PID/cmdline | tr '\0' ' '; echo
```
Then use those values, never guess. See `ilma-state-verify-before-report`
P-13b for the full /proc archaeology pattern.

## Verification recipe (universal)

```bash
# 1. Pre-condition: process alive, port bound
kill -0 $<DAEMON_PID> && \
ss -tlnp | grep -E "$<PORT>" >/dev/null

# 2. Health endpoint responds
curl -fs --max-time 5 http://localhost:$<PORT>/health | jq -e '.status == "ok"'

# 3. Real proxy request shape (use smallest reasonable payload)
curl -fs --max-time 30 \
  -X POST http://localhost:$<PORT>/<endpoint> \
  -H "Content-Type: application/json" \
  -d '<<minimal_payload>>' | jq -e '.errors | not'

# 4. Observability snapshot diff vs baseline
curl -fs -H "X-Admin-Token: $<TOKEN>" http://localhost:$<PORT>/admin/queue

# 5. Process log: no new ERROR lines matching touched files
tail -100 $<LOG_PATH> | grep -E "ERROR" | grep -E "(<touched_symbol>)"
# (above should return empty)
```

## Output format mandated

Every patch message MUST use:
```
### Mode C — RC-N PROMOTION AUDIT (audit/test only, no patch)
- Trigger phrases: "RC-1 → RC-2 promotion", "audit and test only",
  "PASS/FAIL + evidence", "no patch", "no restart", "no feature",
  "promotion plan", "multi_agent=true".
- Strict contract:
  1. **No patch**, **no restart**, **no feature**, **no new endpoint**.
  2. **Output**: only PASS / FAIL or PASS / FAIL / DEFERRED / NOT-RUN with
     measured evidence.
  3. **Phases** (run sequentially, no skipping):
     - **PHASE 0 LOCK**: confirm `git log -1` = frozen commit, `git diff`
       empty, runtime pid alive. 3 PASS items only, no creative leeway.
     - **PHASE 1 CANARY**: sample /health, /admin/queue (or admin/requests
       if present), RSS, healthy_keys every N seconds. External sampler
       script only — never add observability to runtime.
     - **PHASE 2 CLIENT CERT**: capability matrix × {openai, anthropic,
       generic_http} × {stream, non_stream} × {tool_call, plain_chat} ×
       {abort, no-abort}. Pass = HTTP 200 + correct content shape.
     - **PHASE 3 LOAD**: N=100, N=300, N=800 sequential or concurrent
       senders; success rate ≥ 99% / 98% / 95%. Backpressure is owned
       by runtime, asserted by client.
     - **PHASE 4 FAILURE INJECTION**: provider timeout, provider 5xx,
       client disconnect, retry exhausted, abort mid-stream. Pass =
       runtime recovers without restart, no orphaned tickets.
     - **PHASE 5 DECISION**: emit explicit verdict (PASS / INCONCLUSIVE /
       FAIL) based on which phases ran vs which were DEFERRED. Never
       claim PASS for a DEFERRED gate.
  4. **Stop signals**: any FAIL → STOP. Any NOT-RUN → INCONCLUSIVE
     (do NOT promote).
- See `references/rc-promotion-runbook.md` for the full template + sampler
  script.

### Mode D — OWNERSHIP-AWARE PROMOTION (TEP v3.1 / RMRP v1)
- Trigger phrases: "PASS_DEGRADED", "PROMOTE_WITH_LIMITATION", "FINAL_REASON",
  "FAILURE_SCOPE", "DECISION", explicit ownership table, "kandidat habis".
- The rule is **the runtime owns only its own class of failures**:
  - INTERNAL: health / queue leak / restart / deadlock / denial storm
    without reason / completion fails because of wrapper code
  - EXTERNAL: upstream latency > timeout / provider 5xx / network stall /
    remote rate-limit
- Decision matrix (must follow, no creative variation):
  ```
  health=200  completion=200  internal   → PASS / PROMOTE
  health=200  completion=504  upstream   → PASS_DEGRADED / PROMOTE_WITH_LIMITATION
  health=500  any             internal   → FAIL / RECOVER
  health=200  completion=timeout unknown → UNKNOWN (1 verification extra)
  ```
- Output format variants exist (TEP v3, RMRP v1, PRP v3) but SHARE the matrix
  above. When Bos issues a new spec, **classify per this matrix first**, then
  format output per the specific protocol variant.
- Critical anti-pattern: penalize runtime for what it doesn't own. If watchdog
  fires at SLA `ANTI_SILENCE_TIMEOUT_MS=45000` because upstream takes >45s,
  that is EXTERNAL. The runtime executed correctly (recover attempt was made,
  queue was kept clean, request was released). Decision = PROMOTE_WITH_LIMITATION.

## Mode Detection Order (before any patch or test)
1. Read the BOS message. Look for: LOCKED SPEC / freeze_feature / no patch / RC-1
   / UAEC / UEC / RMRP / TEP / PRP / CORE OBJECTIVE / PASS_DEGRADED /
   PROMOTE_WITH_LIMITATION / FINAL_REASON.
2. If a protocol name is present → map to Mode A / B / C / D above.
3. If multiple layers (e.g. "PRP v3 with UAEC v1.0 constraints") → Mode D
   overlays on B (no patch + ownership matrix).
4. If unclear → ask ONE clarification question with the mode options.
   Do NOT default to the lightest mode.

## See also

- `references/wrapper-nvidia-phase3-postmortem.md` — concrete transcript
  of the Phase-3 destabilization (459-line bundle reverted to `f3ede13`)
  that this skill was extracted from. **Read before planning any multi-patch
  series on a production daemon.**
- `references/uaec-v1.0-contract.md` — Universal Agent Execution Contract
  v1.0 (Mode B): agent-as-client, runtime-as-server, freeze_feature=true,
  single-concern-per-patch, hotfix-only discipline. Read when Bos issues a
  LOCKED SPEC with "no new endpoints/modules/observability".
- `references/rc-promotion-runbook.md` — RC-N → RC-(N+1) promotion audit
  (Mode C): 5-phase PASS/FAIL evidence gates with no patch/restart/feature
  permission. Read when Bos says "audit and test only, only PASS/FAIL with
  evidence" or invokes RC promotion flow.
- `ilma-state-verify-before-report` — companion skill for runtime/state
  verification. Pitfalls P-17 (big-batch antipattern) and P-18 (rollback-
  first discipline) are siblings to this skill.
- `ilma-state-verify-before-report` P-13b — for verifying wrapper/daemon
  cwd + port via `/proc` archaeology when the systemd unit is missing.
- `ilma-comprehensive-optimizer` — full-system sweep via cron. NOT a
  substitute for per-patch evidence gating; this skill governs the
  per-patch loop within the optimizer's larger cycle.
- `bug-hunter` — reactive bug triage. Distinct from this skill which
  is proactive patch-workflow discipline.
