# ILMA Phase Audit Pattern: Self-Report Fallacy & Actual Source Verification
**Skill class:** ilma-evolution
**Created:** 2026-06-03
**Session:** 20260603_220126
**References:** `references/phase1-audit-self-report-failure.md`, `references/phase3-baseline-smoke-test-discovery.md`

---

## Pattern: Evidence-Gated Capability Audit

### The Problem

Phase 1 audit claimed:
- 37 capabilities, 32 verified, 5 provisional
- Missing modules: `ilma_free_webfetch`, `ilma_web_search`
- 284 skills

Actual `capability_registry.json` shows:
- **41 capabilities**, **0 provisional**, **all VERIFIED** (uppercase + lowercase mixed)
- `web_fetch` and `web_search` do NOT exist as capability IDs in registry
- Phase 1 audit was generated from assumed/self-reported data, not actual inspection

Result: The Phase 1 audit document became a false positive source that propagated incorrect data through all subsequent phases.

### The Root Cause

**"Self-Report Fallacy"** — trusting the system's own claims about itself without external verification. ILMA's own audit documents, when generated from assumed data rather than source inspection, become manufactured evidence that looks real but is not.

### The Defense

**Always verify capability claims against primary source:**
```python
# Correct procedure — NEVER skip this
import json
with open('/root/.hermes/profiles/ilma/capability_registry.json') as f:
    registry = json.load(f)

# The capabilities key is a DICT, not a list
caps = registry['capabilities']

# Count actual statuses
statuses = {}
for cap_id, cap_data in caps.items():
    status = cap_data.get('status', 'UNKNOWN')
    statuses[status] = statuses.get(status, 0) + 1

print(f"Total: {len(caps)}, Statuses: {statuses}")

# Verify implementation paths exist
import os
for cap_id, cap_data in caps.items():
    impl_path = cap_data.get('implementation_path', '')
    if impl_path:
        # Handle comma-separated paths (take first)
        primary = impl_path.split(',')[0].strip()
        if primary and not os.path.exists(primary):
            print(f"MISSING: {cap_id} → {primary}")
```

### Why This Matters for SSS+++ Claims

Any capability without a passing import test is NOT even in the running for SSS+++. The hierarchy:

| Level | Test | Pass Threshold |
|-------|------|---------------|
| 1 | Import smoke test | Can even load? |
| 2 | Function test | Can it do its job? |
| 3 | Benchmark suite | 50+ test cases pass? |
| 4 | Adversarial test | Edge cases handled? |
| 5 | Safety test | Refuses dangerous requests? |
| 6 | SSS+++ | All 36 criteria pass |

Most ILMA capabilities (23/41 = 56%) haven't passed Level 1.

### Correct Phase Sequence

```
Phase 0: Governance (LOCK)
Phase 1: Audit from PRIMARY SOURCE (actual JSON parsing)
Phase 2: Benchmark plan + harness spec + rubrics (PLAN)
Phase 3: Baseline evaluation (ACTUAL SMOKE TEST)
Phase 4: Upgrade architecture (DESIGN)
Phase 5: Controlled evolution (EXECUTE)
Phase 6: SSS+++ certification (CERTIFY)
```

**Never skip Phase 3 smoke test with "baseline already known." The smoke test reveals truth.**

---

## Related Reference Files

| File | Lesson |
|------|--------|
| `references/phase1-audit-self-report-failure.md` | Phase 1 audit generated false claims. Root cause: self-report fallacy. Correct procedure uses direct JSON parsing. |
| `references/phase3-baseline-smoke-test-discovery.md` | Actual smoke test revealed 56% of "VERIFIED" capabilities have broken paths. VERIFIED badge = manufactured not measured. Correct order of testing levels. |
| `scripts/ilma_phase3_smoke_test.py` | Executable smoke test script — always run before Phase 4 |