# Universal Agent Execution Contract (UAEC) v1.0 — Reference

**Mode**: Audit / hotfix-only when runtime stable.
**Authoritative source**: Bos directive issued when accepting runtime is "good enough" but agent keeps trying to add features.

---

## The contract (verbatim rules)

```
RULE-01  Runtime canonical = CURRENT HEALTHY COMMIT (e.g. f3ede13).
         Do not change before: rollback path verified, canary pass.

RULE-02  Agent is CLIENT. Runtime is SERVER.
         Hermes / Claude Code / Kilo / OpenCode MUST NOT alter execution
         semantics. They may only: send request, observe, propose patch.
         Runtime decides.

RULE-03  No combining observability + lifecycle + timeout + queue
         + release + stream in one patch.
         1 patch = 1 concern.

RULE-04  No restart before: syntax check + static diff review +
         rollback command ready.
```

---

## What this means in practice

### What we DO NOT do

- Add a new endpoint (e.g. `/admin/requests`) without approval.
- Add a new module (e.g. `request_runtime.js`).
- Add a new metric to existing endpoint.
- Change any timeout constant.
- Rewrite queue logic.
- Introduce release accounting (releaseOnce, double_release counters).
- Cook up new env vars.

### What we DO

- Audit (`git diff`, `grep`, `/proc/$PID/...`, `curl /health`).
- Test (real curl with timeout ≥ upstream latency).
- Propose hotfix (single file, ≤ 30 LOC) with rollback.
- Verify against frozen baseline.
- Emit PASS / FAIL with measured numbers.

---

## Universal client compatibility — capability matrix

Clients are NEVER identified by name (no `if Hermes`, `if Claude`).
Always by **capability**:

| Capability axis | Values |
|-----------------|--------|
| transport | openai / anthropic / generic_http |
| mode | stream / non_stream |
| tooling | tool_call / plain_chat |
| abort | supported / unsupported |

Client profile is observation only — never affects routing.

---

## Execution budget (45s total)

| Stage | Budget |
|-------|--------|
| QUEUE | 9s |
| ACQUIRE | 7s |
| UPSTREAM | 24s |
| FINALIZE | 5s |

Stage timeout ≠ retry timeout. No nested timeout. No carryover.

Invariant:
```
retry_budget ≤ upstream_budget
```

---

## Production gate (must pass for "OK to deploy")

| Gate | Target |
|------|--------|
| health | 200 |
| queue | waiting==0 idle |
| 100 req success | ≥ 99% |
| stream | complete |
| abort cleanup | < 1500ms |
| release double_release | == 0 |
| memory delta | < 10 MB |
| latency regression | < 15% |

If ANY one fails → NO DEPLOY.

---

## Output format (mandatory)

```
OBSERVE    → runtime pid, RSS, inflight, waiting, endpoint status
EVIDENCE   → grep, stack trace, line numbers, logs, metrics
ROOT CAUSE → one primary cause max
PATCH      → max 1 file new OR 2 file mods, single concern
VERIFY     → health queue completion stream abort all PASS
ROLLBACK   → executable inverse (`git checkout <c> -- <files>`)
NEXT       → next gate, NOT next forward patch
```

### No-go vocabulary (forbidden in this mode)

- "should work"
- "akan stabil setelah..." (will be stable after...)
- "estimated impact X%"
- "kemungkinan penyebab..." (probable cause...)
- "harusnya..." (supposed to...)
- "diperkirakan..." (estimated...)

Only tool-measured numbers: `kill -0` returns 0, RSS is X KB, `curl` returns Y, code is Z.

---

## Decision template

```
STATE:        RC-1 (or current RC level)
COMMIT:       <healthy commit SHA>
freeze_feature:   true
phase3:           false
allow_hotfix_only: true
new_module:       denied
new_endpoint:     denied
```

End-state: `24 jam canary stabil` (24-hour canary stable) → next step.

---

## Common violations observed in real sessions

1. **Repackaging a feature as "bugfix" to bypass freeze.**
   WRONG. A feature changes capability surface. UAEC forbids this.

2. **Adding endpoint /admin/X "so I can run the audit cleanly."**
   WRONG. Run the audit from an external sampler script (e.g. `bash`,
   `curl | jq`, `python -c`). The runtime must be untouched.

3. **Restarting for a config fix that doesn't need restart.**
   Often unnecessary. If env var wasn't changed via `kill`, no restart.

4. **Treating the existing services as "patchable" because upstream
   provider is sluggish.**
   Provider latency is a network reality, not a wrapper bug. Measure
   upstream baseline before declaring retry logic broken.

5. **Combining multiple hotfixes "since they're small."**
   Each hotfix is independent. Roll back to the prior healthy state
   between them if needed. Don't batch.

---

## Anti-pattern detected Sesi 2026-07-01

Agent re-offered the full Phase 3 design (8 patches + new module) **after** Bos had explicitly frozen phase-3 and said "audit and test only". This is the most common UAEC violation: the agent forgets that the directive hierarchy is:

```
Bos directive (UAEC, freeze, audit-only)
  > agent's idealized roadmap (Phase 3, Phase X)
  > agent's prior state in this session
```

Always re-read the latest 1-3 user messages before any action. If the latest message contains "STOP", "audit only", "no patch", "PASS/FAIL only", treat as hard freeze and emit only the format mandated by the audit, not your own preferred format.

---

## Why this skill exists

A frozen runtime is a **healthy** runtime. A "new feature"-obsessed agent
will keep finding reasons to patch. UAEC is the explicit guard that:
1. Tells the agent it's terminal-mode (not roadmap-mode).
2. Removes all "should/estimated/kemungkinan" language.
3. Reduces output to a deterministic evidence grid.

Until Bos breaks the freeze, this skill applies verbatim.
