# Phase 1 Audit — Evidence-Gated Capability Verification Pattern
**Source:** ILMA Phase 1 Capability Inventory Audit (2026-06-03)
**Session:** lokah2150 / ILMA profile

---

## Context

ILMA performed a systematic audit of 37 capabilities and 284 skills. The audit revealed systemic patterns where claimed capabilities are not independently verified. This reference captures the methodology and findings for future evolution cycles.

---

## Core Finding: Capability Claims ≠ Verified Capabilities

Every ILMA capability registry had self-reported status. None had been tested independently.

**The problem:**
- 32 capabilities claimed `verified`
- 5 capabilities claimed `provisional`
- 0 capabilities had test suites
- 0 capabilities had benchmark results

**The consequence:**
- Module existence ≠ capability verified
- Skill directory existence ≠ capability working
- Self-report status = unverified claim

**The rule:**
> Every claimed capability must be tested with actual execution before status can be validated. A capability that has never been run cannot be called VERIFIED, PROVISIONAL, or EMERGING — it is UNTESTED.

---

## Audit Methodology

### Step 1: Import Test

For each capability, attempt to import the primary module:

```python
import traceback
modules = [
    ("ilma_capability_registry", "/root/.hermes/profiles/ilma/ilma_capability_registry.py"),
    ("ilma_orchestrator", "/root/.hermes/profiles/ilma/ilma_orchestrator.py"),
    ("ilma_model_router", "/root/.hermes/profiles/ilma/ilma_model_router.py"),
    # etc.
]
for name, path in modules:
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        print(f"✅ {name}")
    except Exception as e:
        print(f"❌ {name}: {type(e).__name__}: {e}")
```

**Findings from Phase 1:**
```
❌ ilma_free_webfetch — module missing (capability: web_fetch)
❌ ilma_web_search — module missing (capability: web_search)
✅ ilma_capability_registry — loaded successfully
✅ ilma_orchestrator — loaded successfully
✅ ilma_model_router — loaded successfully
```

### Step 2: Capability Registry Scan

```python
import json
with open('/root/.hermes/profiles/ilma/capability_registry.json') as f:
    reg = json.load(f)
capabilities = reg.get('capabilities', {})
print(f"Total capabilities: {len(capabilities)}")
for cap_id, info in capabilities.items():
    print(f"  {cap_id}: {info.get('status','?')} | tool={info.get('primary_tool','?')}")
```

**Phase 1 results:**
```
Total capabilities: 37
Verified: 32
Provisional: 5
Critical risk: 1 (system_administration)
High risk: 10
Module missing: 2 (web_fetch, web_search)
```

### Step 3: Skill Inventory Count

```python
import os
skills_dir = '/root/.hermes/profiles/ilma/skills'
skill_dirs = [d for d in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, d))]
skill_files = []
for d in skill_dirs:
    path = os.path.join(skills_dir, d)
    files = [f for f in os.listdir(path) if f.endswith('.md')]
    skill_files.extend(files)
print(f"Total skill directories: {len(skill_dirs)}")
print(f"Total skill files: {len(skill_files)}")
```

**Phase 1 results:**
```
Total skill directories: 284
Total skill files: 284+
```

### Step 4: Model/Provider Routing Test

Test the model router to ensure routing works and fallback chains exist:

```python
import sys
sys.path.insert(0, '/root/.hermes/profiles/ilma')
from ilma_model_router import ModelRouter

router = ModelRouter()
# Test routing for a simple task
result = router.get_best_model(task_description="test routing", budget="free")
print(f"Router result: {result}")
```

**Phase 1 findings:**
- MiniMax-M2.7 model configured but returning malformed responses (`response.content invalid (not a non-empty list)`)
- Session `20260603_202433_40d8b163` failed repeatedly
- Fallback to `deepseek-v4-pro` (nvidia) triggered — routing still functional
- Root cause: provider `minimax` has 0 entries in PROVIDER_INTELLIGENCE_MASTER.json

### Step 5: Confidence Router Calibration Test

Test whether confidence estimation works:

```python
from ilma_capability_registry import CapabilityRegistry
registry = CapabilityRegistry()

# Test confidence estimation
result = registry.estimate_task_confidence(task_description="write a report")
print(f"Confidence: {result}")
```

**Phase 1 findings:**
- `estimate_task_confidence()` returned `confidence=0` for all inputs
- No calibration data loaded
- No benchmark to verify accuracy
- Critical: routing decisions have no confidence backbone

### Step 6: Safety/Risk Assessment

For capabilities marked `high` or `critical` risk, verify guardrails exist:

```python
# system_administration capability — critical risk
cap = capabilities.get('system_administration', {})
primary_tool = cap.get('primary_tool')
print(f"Primary tool: {primary_tool}")
# Check if destructive command guard exists
# (answer: it does not)
```

---

## Key Patterns Found

### Pattern A: Module Missing but Capability Claimed VERIFIED

`web_fetch` capability:
- primary_tool: `ilma_free_webfetch`
- Registry status: `verified`
- Actual: module file does not exist on disk

**Resolution:** Either locate the actual implementation, create a shim, or downgrade to DEPRECATED.

### Pattern B: Model Failure Cascading

When `minimax-m2.7` fails:
1. Session starts with default model from config
2. Model returns malformed response
3. Fallback doesn't trigger cleanly
4. Session fails with `Invalid API response after 3 retries`

**Resolution:** Pre-flight check should test model connectivity before session starts. Fallback chain must be verified independently.

### Pattern C: Confidence Router Returns 0

`estimate_task_confidence()` is supposed to guide routing. When it returns 0 for everything, routing is blind.

**Resolution:** Calibrate against known tasks. Build a small golden dataset of (task, expected_confidence, actual_confidence) tuples. Measure accuracy and adjust thresholds.

### Pattern D: PROVISIONAL Capabilities Without Test Suites

5 capabilities marked `provisional` since 2026-05-10 with no test suite:
- planning
- longform_writing
- creative_generation
- heavy_coding
- capability_discovery

**Rule:** PROVISIONAL capabilities need minimum 20 test cases across varied inputs before evaluation.

---

## Evidence Requirements Per Capability

For any capability to be considered VERIFIED, the following must exist:

1. **Test case file** — at minimum 10 test cases per capability
2. **Execution log** — actual run results, not just code existence
3. **Metrics** — success_rate, latency_p50, error_types
4. **Limitation document** — known failure modes
5. **Fallback verification** — what happens when primary tool fails
6. **Date + environment** — when tested, on what hardware/OS

Without these, status should be `UNTESTED`, not VERIFIED.

---

## SSS+++ Tier Requirements Summary

A capability earns SSS+++ only if:

| Criterion | Requirement |
|-----------|-------------|
| Reliability | ≥99% success on normal cases, ≥95% on edge cases |
| Safety | No harmful/illegal operations, clear error reports |
| Evidence | test_case + execution + log + metrics + artifact + date + env + limitations |
| Robustness | Handles ambiguous input, can ask for clarification, can fallback |
| Security | No secret leakage, timeout/retry/rate-limit on all external calls |
| Auditability | Trace: input → reasoning → action → tool → result → validation → conclusion |
| Performance | Latency, cost, resource usage all measured |
| Generalization | Tested across variations, adversarial tests, regression tests |

---

## Phase 1 Output Files

| File | Purpose |
|------|---------|
| `ILMA_CAPABILITY_EVOLUTION_GOVERNANCE.md` | Scope, limits, evidence requirements, rollback policy |
| `ILMA_CAPABILITY_INVENTORY_AUDIT.md` | Per-capability audit record |
| `ILMA_CAPABILITY_MATRIX.yaml` | Structured capability data |
| `ILMA_RISK_REGISTER.md` | Risk tracking and mitigation plan |

---

## Lessons for Future Evolution Cycles

1. **Never trust registry status alone** — always test independently
2. **Module existence is necessary but not sufficient** — must import and call methods
3. **Model/provider failures cascade** — test routing chain before session starts
4. **Confidence router is foundational** — if it returns 0, routing is blind
5. **PROVISIONAL without tests = UNVERIFIED** — test or downgrade
6. **Safety-critical capabilities need guardrails** — system_administration needs destructuve command blocks
7. **Phase 0 (governance) must be complete before Phase 1** — governance defines standards
8. **Report findings honestly** — "UNTESTED" is more valuable than "VERIFIED" when unproven

---

*Last updated: 2026-06-03*
*Next: Phase 2 requires benchmark harness construction*