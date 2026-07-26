# Baseline Evaluation: Actual Smoke Test Method
**Created:** 2026-06-03
**Script:** `scripts/ilma_phase3_smoke_test.py`
**Lesson:** Import smoke tests reveal truth about "VERIFIED" capabilities

---

## What the Baseline Revealed

Running actual Python import tests against 41 registered capabilities:

```
Total: 41 capabilities (all marked VERIFIED)
Smoke test pass rate: 18/41 = 43.9%
Failed (broken path): 23/41 = 56.1%

Failure types:
  NO_PATH (empty implementation_path): 10 capabilities
  MODULE_NOT_FOUND: 13 capabilities
```

**Key finding:** More than half of all "VERIFIED" capabilities cannot be imported. The VERIFIED badge is manufactured, not measured.

---

## Smoke Test Script Pattern

```python
#!/usr/bin/env python3
"""
ILMA Baseline Smoke Test
Tests import + basic function for each capability in registry.
"""
import os, sys, json, time
os.chdir('/root/.hermes/profiles/ilma')
sys.path.insert(0, '.')

with open('capability_registry.json') as f:
    registry = json.load(f)
caps = registry['capabilities']

FAILED_IMPORTS = []
RESULTS = []

for cap_id, cap_data in caps.items():
    impl_path = cap_data.get('implementation_path', '')
    result = {'capability_id': cap_id, 'import_success': False, 'error': None}
    
    if not impl_path:
        result['error'] = 'NO_PATH'
        FAILED_IMPORTS.append((cap_id, impl_path))
        RESULTS.append(result)
        continue
    
    module_name = impl_path.replace('/', '.').replace('\\', '.').rstrip('.py')
    
    try:
        __import__(module_name)
        result['import_success'] = True
    except ModuleNotFoundError:
        result['error'] = 'MODULE_NOT_FOUND'
        FAILED_IMPORTS.append((cap_id, impl_path))
    except Exception as e:
        result['error'] = str(e)[:100]
    
    RESULTS.append(result)
```

---

## Evidence Files Produced

| File | Purpose |
|------|---------|
| `ILMA_SMOKE_TEST_RESULTS.json` | Full raw results (21KB) |
| `ILMA_CAPABILITY_SCORECARD.csv` | Tabular for spreadsheet |
| `ILMA_BASELINE_EVALUATION_REPORT.md` | Human-readable summary |

---

## Implications for SSS+++ Claims

Any capability that fails import smoke test CANNOT be SSS+++, SSS, or even B-tier. It can't even pass the minimum bar.

**Hierarchy of testing needed:**
1. **Import smoke test** (what we did) — can it even load?
2. **Function test** — can it do its stated job?
3. **Benchmark suite** — does it pass 50+ test cases?
4. **Adversarial test** — does it handle edge cases?
5. **Safety test** — does it refuse dangerous requests?
6. **SSS+++ certification** — all 36 criteria pass

Only 18/41 capabilities have passed level 1. None have been tested at level 3+.

---

## Correct Order of Operations

```
Phase 0: Governance ✓
Phase 1: Audit (source-first!) ✓ — but audit was wrong, corrected
Phase 2: Benchmark plan ✓ (plan + spec + rubrics)
Phase 3: Baseline evaluation ✓ — smoke test reveals truth
Phase 4: Fix broken references (23 broken → ~18 working)
Phase 5: Upgrade and iterate
Phase 6: SSS+++ certification (only after all prior phases done)
```

**Never claim SSS+++ before Phase 6. Never skip Phase 3 smoke test as "baseline already known."**