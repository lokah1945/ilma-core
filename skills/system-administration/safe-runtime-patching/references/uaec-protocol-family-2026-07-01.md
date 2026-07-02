# UAEC / RMRP / TEP / PRP Protocol Family — Single-Skill Detection

## Why this exists

Within one session (2026-07-01) Bos iterated through **10+ target-execution protocol
variants** for the same runtime (`wrapper-nvidia`):

| Spec name | Acronym | Distinctive invariant |
|-----------|---------|------------------------|
| UAEC v1.0 | Universal Agent Execution Contract | single concern per patch, agent-as-client |
| UEC v2    | Universal Execution Contract | step cascade, no scope expansion |
| RMRP v1   | Resilient Multi-Key Runtime Protocol | MODEL ≠ KEY ≠ PROVIDER; recover until budget exhausted |
| TEP v2    | Target Execution Protocol | 1 metric per M_, sequential VALIDATE→DECIDE |
| TEP v3    | Target Execution Protocol | promotion-rule disallows "observing later" |
| TEP v3.1  | (patch) | adds OWNERSHIP / PASS_DEGRADED |
| PRP v3    | Production Readiness Protocol | single PRODUCTION_GATE; 4 gates M1-M4 |
| CORE OBJECTIVE / FINAL | Output discipline | STOP after STATUS=PASS; no recommendations |

All variants share the SAME 5 axioms:

1. **TARGET** declared verbatim before action (keywords: TARGET, M1, M2, M3)
2. **SUCCESS METRIC** measurable, numeric (200 / success_rate / queue state)
3. **FAIL METRIC** explicit failure conditions (restart / patch / aggregate regression)
4. **STOP CONDITION** self-terminating rule ("3 PASS = STOP")
5. **TIMEBOX** bounded actions, no infinite iteration

What changes between variants is **only the OUTPUT FORMAT and the EVIDENCE GATE**, never
the underlying disciplines.

## Detection rule (in any session)

When Bos issues a protocol-shaped brief with all 5 of these present, **you are in the
family**:

```bash
# Heuristic: TARGET: <line> + SUCCESS: + STOP: + TIMEBOX: + STATUS: <verb>
```

When detected:
- Use the **OUTPUT FORMAT prescribed by the specific variant** — do NOT cross-pollinate.
  (UAEC wants `OBSERVE|EVIDENCE|ROOT CAUSE|PATCH|VERIFY|ROLLBACK|NEXT`. TEP v3 wants
  `STATUS|TARGET|CURRENT|EVIDENCE|BLOCKER|DECISION|NEXT`. RMRP wants
  `STATUS|REQUEST|FAILURE_SCOPE|FINAL_REASON|DECISION|NEXT`.)
- **Always include OWNERSHIP / scope classification** (added by TEP v3.1, accepted
  downstream — RMRP overlaps here with `REQUEST/FAILURE_SCOPE`).
- **Recognize PASS_DEGRADED / READY_DEGRADED / RECOVERED** as legitimate promotion
  decisions when failure is external (upstream/provider), not internal (wrapper).
- **Recognize the lock stop rule**: when STATUS=PASS → DECISION=STOP. Don't add
  recommendations, don't run next phase, don't propose roadmap.

## PASS_DEGRADED — The decision matrix (added in TEP v3.1; carry forward)

| health | completion | root cause | decision |
|--------|-----------|------------|----------|
| 200 | 200 | internal | PASS / PROMOTE |
| 200 | 504 | upstream | **PASS_DEGRADED / PROMOTE_WITH_LIMITATION** |
| 500 | any | internal | FAIL / RECOVER |
| 200 | timeout | unknown | UNKNOWN (1 verification extra) |

This **OWNERSHIP-AWARE** rule predates safe-runtime-patching by ~10 minutes of
edits in the session; it deserves a permanent spot in the SKILL.md output discipline.

## Failure-ownership classifier (RMRP-aligned, dine with UAEC)

```text
INTERNAL failures (runtime owns):
- health endpoint fails
- queue leak / orphan inflight / negative inflight
- double release
- deadlock / crash
- restart forced
- completion fails because of wrapper code path
- denied rises without capacity reason

EXTERNAL failures (runtime doesn't own):
- provider latency > timeout
- upstream 5xx
- network stalls
- DNS / TLS errors
- remote rate-limits
```

**Test:** if the failure reason is in a class the runtime did not author (upstream,
provider, network), classify as EXTERNAL even when the response code is 5xx. Don't
penalize the runtime for what it doesn't own.

## Anti-pattern: "extend the PROTOCOL family"

When Bos issues UEC v2 → TEP v3.1 → RMRP v1 in one session, the temptation is to
synthesize a "Protocol UEC2+TEP3+RMRP hybrid". **Don't.** Each protocol variant is a
strict superset of the previous; the synthesis loses what the specific variant adds
(specifically: UAEC v1 → mode B; TEP v3.1 → ownership matrix; PRP v3 → 4-gate single;
CORE OBJECTIVE → ZERO recommendations rule).

Instead: identify the **highest-version active protocol**, and follow it strictly. If
you're not sure which variant applies, ask: "Apakah pakai PROTOCOL_V2 / V3 / V3.1?"

## Test that requires this knowledge

```bash
# Run in /root/wrapper/nvidia or equivalent runtime dir

curl -fs --max-time 5 http://localhost:9100/health    # M1
curl -fs -X POST --max-time 60 \
  -H "Content-Type: application/json" \
  -d '{"model":"<any>","messages":[{"role":"user","content":"hi"}],"max_tokens":3}' \
  http://localhost:9100/v1/chat/completions            # M2
curl -fs -H "X-Admin-Token: ..." \
  http://localhost:9100/admin/queue                    # M3

# Then output EXACTLY the format the active protocol prescribes.
# No creative extension. No recommendations. STOP after decision.
```

## Cross-references

- `safe-runtime-patching` SKILL.md — Mode B (UAEC v1.0) is fully covered.
- This reference captures the **family** + the later variants (TEP v3.1 ownership,
  PRP v3 promotion gate, CORE OBJECTIVE zero-recommendation rule) — none of which
  existed when the parent SKILL.md was authored 2026-07-01 03:00 UTC.
- See `references/wrapper-nvidia-phase3-postmortem.md` for the parent session's
  failure transcript that motivates prompt-mode discipline.
