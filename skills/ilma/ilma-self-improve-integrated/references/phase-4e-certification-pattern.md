# Phase 4E Certification Pattern — Reference

Class-level pattern for certifying ILMA capability tiers honestly. Captured 2026-06-04.

## When to Use

Use this pattern whenever:
- Promoting ILMA to a new capability tier (L1/L2/L3/L4)
- Certifying a system component for production readiness
- Auditing a multi-phase work effort
- Bos explicitly requests certification or tier verdict

## The 8-Step Certification Flow

| Step | Output | Why |
|------|--------|-----|
| 1. Rehydrate evidence | `*_EVIDENCE_INDEX.md` | Don't trust old reports blindly — verify artifacts still exist |
| 2. Re-run regression tests | `*_REGRESSION_TEST_RESULTS.json` | Re-run, don't just cite prior phase results |
| 3. Secret scan + redact | `*_SECRET_SCAN_RESULTS.json` + `*_SECRET_SAFETY_CERTIFICATION.md` | Re-scan after redaction |
| 4. Tier verdict | `*_CODING_TIER_CERTIFICATION.md` | Use exact status enum |
| 5. Production readiness matrix | `*_PRODUCTION_READINESS_MATRIX.yaml` | Per-component risk |
| 6. Claude Code verdict | `*_CLAUDE_CODE_CERTIFICATION.md` | Always `AVAILABLE_BUT_NOT_POLICY_COMPLIANT_FOR_DEFAULT` unless integrated |
| 7. Canary plan | `*_CONTROLLED_CANARY_PLAN.md` | 24h or 20 tasks minimum |
| 8. Final certification report | `*_FINAL_CERTIFICATION_REPORT.md` + `*_FINAL_GATE.json` | Skeptical verdict required |

## Tier Status Enum (use exactly)

```
UNVERIFIED              — No evidence at all
PROVISIONAL             — Evidence exists but gaps
VERIFIED                — All criteria met
PRODUCTION_READY_CONTROLLED — Verified + canary plan + risk register
```

| Tier | Minimum Status to Recommend |
|------|-----------------------------|
| L1_LIGHT | VERIFIED or PRODUCTION_READY_CONTROLLED |
| L2_MEDIUM | PRODUCTION_READY_CONTROLLED |
| L3_HEAVY | PRODUCTION_READY_CONTROLLED (with canary) |
| L4_SUPER_HEAVY | UNVERIFIED (unless large-codebase migration evidence exists) |

## Per-Tier Evidence Requirements

### L1_LIGHT
- single-file or small utility task
- model route trace
- tests pass
- diff captured
- rollback available

### L2_MEDIUM
- multi-file enhancement
- integration into existing component
- tests pass
- rollback available
- no policy bypass
- no source-of-truth duplication

### L3_HEAVY
- routing/runtime/stress validation
- concurrent or multi-provider stress
- fallback proof
- health state proof
- regression tests
- rollback
- clear limitation report

### L4_SUPER_HEAVY
- large codebase migration
- long-running benchmark
- canary deployment
- repeated success across multiple repos
- external audit

**Default for L4**: UNVERIFIED. Only promote to PROVISIONAL_ONLY with concrete evidence.

## Status Mapping to Bos's Language

| Bos says | Map to status |
|----------|---------------|
| "Jangan klaim SSS+++" | Never use SSS+++ as a literal status — use the 4-tier enum above |
| "L4 jangan dinaikkan" | L4 = UNVERIFIED unless explicit evidence |
| "production-grade" | PRODUCTION_READY_CONTROLLED + canary passed |
| "evidence-based" | Each tier cites the specific artifacts that justified promotion |
| "jujur" | Skeptical Verdict section listing what is NOT being claimed |

## Anti-Patterns to Avoid

1. **Trusting old reports without re-running** — Phase 4E specifically requires re-running regression tests, not just citing Phase 4B/4C results
2. **Using "production-ready" without canary** — PRODUCTION_READY means "ready for canary", not "ready for full prod"
3. **Promoting L4 on theoretical grounds** — L4 requires actual large-codebase work
4. **Hiding failures in summary** — Failed tests must be listed explicitly, not buried
5. **Padding capability claims** — If you only have 1 L3 test, that's PROVISIONAL, not VERIFIED
6. **Auto-claiming SSS+++** — Forbidden by Bos rule #11 in Phase 4E gate

## Production Readiness Status Enum (matrix entries)

```
READY_CONTROLLED          — All criteria met, low risk
READY_WITH_LIMITATIONS    — Met criteria but acknowledged gaps
PROVISIONAL               — Not production ready, evidence incomplete
NOT_READY                 — Critical gaps, cannot deploy
```

| Component | Common Status (Phase 4E) |
|-----------|--------------------------|
| model_routing | READY_CONTROLLED |
| free_model_policy | READY_CONTROLLED |
| credential_handling | READY_WITH_LIMITATIONS (rotation history) |
| provider_intelligence | READY_CONTROLLED |
| coding_worker | READY_CONTROLLED |
| claude_code | PROVISIONAL (always) |
| heartbeat | READY_WITH_LIMITATIONS (no real Telegram) |
| rollback | READY_CONTROLLED |
| parallel_execution | READY_WITH_LIMITATIONS (simulated) |
| monitoring | READY_WITH_LIMITATIONS (no real-time alerts) |

## Claude Code Verdict Template

```yaml
claude_code:
  binary_available: true
  usable_as_direct_worker: false
  can_force_internal_model_router: false
  can_enforce_free_policy: false
  can_capture_diff: unknown
  can_run_tests: unknown
  can_rollback: unknown
  policy_status: AVAILABLE_BUT_NOT_POLICY_COMPLIANT_FOR_DEFAULT
  production_default_allowed: false
  allowed_use:
    - optional isolated diagnostic worker
    - non-default comparison worker only if no policy bypass
  verdict: NOT_READY_FOR_PRODUCTION_DEFAULT
```

## Canary Plan Template

```yaml
canary:
  duration:
    initial: 24h_or_20_tasks
  allowed_tasks:
    - L1 small fixes
    - L2 medium enhancements
    - L3 routing stress diagnostics
  blocked_tasks:
    - destructive system changes
    - credential modifications
    - database migrations without approval
    - large repo rewrite
    - paid provider fallback
  required_per_task:
    - route trace
    - model/provider used
    - free policy status
    - diff
    - test result
    - rollback
    - confidence score
    - final verdict
  success_criteria:
    task_success_rate: ">= 90%"
    rollback_artifact_rate: "100%"
    no_secret_leak: true
    paid_provider_touched: false
    direct_api_bypass: false
    critical_failure: 0
    unhandled_timeout: 0
```

## Final Gate Minimum (11 checks)

1. Evidence index done
2. Regression tests pass
3. Secret scan pass
4. L1/L2/L3 tier evidence-based
5. L4 not raised without evidence
6. Production readiness matrix complete
7. Claude Code verdict clear
8. Canary plan complete
9. No raw/prefix credential in outputs
10. No new source-of-truth
11. No SSS+++ claim

## Lesson from Phase 4E (2026-06-04)

Initial gate verification had 3 false-positive FAILs (checks 11, 12, 13) because the detection logic was too aggressive:
- `nvapi-` matched in "0 nvapi- leaks after redaction" (negation context)
- `MASTER*.json` glob matched backups + docs
- `sss+++` matched in "❌ Claim SSS+++" (negation context)

**Fix**: When writing secret/SSS detection logic, check for negation context (`'no ' in before`, `'dilarang'`, `'forbidden'`, `'❌'`, `'not '`) before flagging. Re-verify with corrected logic shows 13/13 PASS.

## See Also

- SKILL.md pitfalls #8, #9, #10, #11 (added in this session)
- `references/phase-4cr4-evidence-template.md` (older pattern, still valid)
