# Phase 3.5: Self-Audit Pattern — Registry Truth Repair
**Source:** ILMA Phase 3.5 (2026-06-03)
**Trigger:** Bos directive: "MASTER PROMPT — CAPABILITY EVOLUTION TO SSS+++"
**Outcome:** 8/8 gates passed, Phase 4 unlocked

## What Was Audited

41 capabilities in `capability_registry.json`, all claiming VERIFIED status.

## Core Audit Pattern Applied

### Step 0: Freeze State
Before any changes, capture pre-audit state:
```python
import json, hashlib
from datetime import datetime

snapshot = {
    'timestamp': datetime.utcnow().isoformat() + 'Z',
    'hash': hashlib.sha256(open(registry_path).read().encode()).hexdigest(),
    'capabilities': {name: data.get('status') for name, data in registry['capabilities'].items()},
}
with open('ILMA_STATE_SNAPSHOT.json', 'w') as f:
    json.dump(snapshot, f, indent=2)
```

### Step 1: File Existence Check (not just path strings)
"File exists" means `os.path.exists()` returns True for ALL parts of compound paths.

```python
import os

def classify(name, data):
    impl = data.get('implementation_path', '').strip()
    evidence = data.get('evidence_type', '')
    
    if not impl:
        return 'PLACEHOLDER'
    
    if ' + ' in impl:
        parts = [p.strip() for p in impl.split(' + ')]
        if not all(os.path.exists(p) for p in parts):
            return 'BROKEN_REFERENCE'
        return 'VERIFIED_RUNTIME' if evidence in ('MEASURED_AA', 'BEHAVIORAL_TEST', 'E2E_TEST') else 'IMPORT_ONLY'
    
    if not os.path.exists(impl):
        return 'BROKEN_REFERENCE'
    
    return 'VERIFIED_RUNTIME' if evidence in ('MEASURED_AA', 'BEHAVIORAL_TEST', 'E2E_TEST') else 'IMPORT_ONLY'
```

### Step 2: Evidence Type Check (SOURCE_PLACEHOLDER rule)
SOURCE_PLACEHOLDER = PROVISIONAL maximum, never VERIFIED. It means "we plan to measure," not "we measured."

```python
def status_from_evidence(evidence_type):
    if evidence_type in ('MEASURED_AA', 'BEHAVIORAL_TEST', 'E2E_TEST'):
        return 'VERIFIED'
    elif evidence_type == 'SOURCE_PLACEHOLDER':
        return 'PROVISIONAL'
    else:
        return 'UNKNOWN'
```

### Step 3: 8-Gate Check Before Advancing
```
G1: Autonomous mutation paused (snapshot exists, no changes during test)
G2: Root cause found (file paths, line numbers, config keys in report)
G3: Fallback works (code exists AND integrated into request path — not just exists)
G4: Registry corrected (truth_classification field on all entries)
G5: No false VERIFIED (all PLACEHOLDER downgraded from VERIFIED)
G6: SOURCE_PLACEHOLDER not evidence (rule applied to all 41 caps)
G7: Smoke test deterministic (Run1 == Run2, repeated 2x)
G8: Rollback plan exists (snapshot file present and valid)
```

### Step 4: Dead Code Detection
Check if critical code (circuit breakers, fallback handlers) is actually called in the request path:

```bash
# Check if mark_failure is called from outside ilma_model_router.py
grep -rn "mark_failure\|mark_success" /root/.hermes/profiles/ilma/ \
  --include="*.py" | grep -v "ilma_model_router.py"
# If nothing returned → dead code, circuit breaker cannot trip
```

## Key Findings

### Finding: "Manufactured VERIFIED" Pattern
All 41 capabilities claimed VERIFIED. Reality:
- 6 VERIFIED_RUNTIME (file exists + MEASURED_AA or BEHAVIORAL_TEST)
- 20 IMPORT_ONLY (file exists but only SOURCE_PLACEHOLDER evidence)
- 5 BROKEN_REFERENCE (implementation file missing)
- 10 PLACEHOLDER (empty implementation_path)
- 0 VERIFIED_RUNTIME if SOURCE_PLACEHOLDER counted as evidence

**Root cause:** SOURCE_PLACEHOLDER was treated as proof of capability. implementation_path was never cross-checked against filesystem.

### Finding: Dead Code Circuit Breaker
`mark_failure()` exists in `ilma_model_router.py` but is NEVER called from the gateway request path. The circuit breaker is dead code — it passes import tests but cannot function at runtime.

### Finding: Smoke Test Determinism Verified
Smoke test runs twice on frozen state: Run1 = 18/41 pass, Run2 = 18/41 pass. 100% consistent.

## Deliverables Produced

| File | Purpose |
|------|---------|
| `ILMA_STATE_SNAPSHOT_BEFORE_PHASE_3_5.json` | Pre-change rollback point |
| `ILMA_RUNTIME_TIMEOUT_ROOT_CAUSE_REPORT.md` | 187s timeout RCA |
| `ILMA_REGISTRY_TRUTH_REPAIR_REPORT.md` | Full repair summary |
| `ILMA_CAPABILITY_REGISTRY_CORRECTED.json` | Corrected registry |
| `ILMA_BROKEN_REFERENCES_LIST.md` | 5 broken capabilities |
| `ILMA_PLACEHOLDER_CAPABILITIES_LIST.md` | 10 unimplemented |
| `ILMA_PHASE_3_5_SCORECARD.csv` | All 41 before/after |
| `ILMA_PHASE_3_5_GATE_CHECK.md` | 8/8 gates passed |
| `ILMA_PHASE_3_5_DETERMINISM_REPORT.md` | Smoke test consistency |
| `ILMA_PROVIDER_ROUTING_PATCH.md` | 4 routing patches |

## Audit Rule Summary (For Future Sessions)

1. **Never trust a registry claiming 100% VERIFIED** — cross-check against filesystem
2. **SOURCE_PLACEHOLDER = PROVISIONAL/IMPORT_ONLY max** — not evidence of capability
3. **Empty implementation_path = PLACEHOLDER** — no implementation exists
4. **Compound paths need ALL parts** — "fileA + fileB" broken if either missing
5. **Code existence ≠ code integration** — verify both import AND call path
6. **Dead code is worse than no code** — gives false confidence
7. **8-gate check before next phase** — catches most problems before propagation
8. **Smoke test must be deterministic** — flaky tests mask real failures