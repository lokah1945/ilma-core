# ILMA Phase 22: Integrated Test Runner Reference
**Date:** 2026-05-09

## Path
`/root/.hermes/profiles/ilma/scripts/ilma_integrated_test_runner.py`

## Purpose
Runs all 6 test groups in one command, produces JSON report at `logs/phase22_integrated_test_report.json`.

## Test Groups

| Group | Source | Command | Expected |
|-------|--------|---------|----------|
| frozen_baseline | test_projects/phase20_425file_codebase/ | `pytest -v -q` | 423 tests |
| model_router | ILMA root | `python3 test_ilma_model_router.py` | 21 tests |
| judge_system | ILMA root | `python3 scripts/test_ilma_judge_system.py` | 8 tests |
| import_smoke | ILMA root | Import 10 modules | 10 pass |
| compile_check | ILMA root | `python3 -m compileall -q ...` | 500 files |
| workflow_semantic | ILMA root | `python3 ilma_workflow_ecc.py --task ...` | 1 pass |

## Output Format

```json
{
  "timestamp": "2026-05-09T...",
  "total_groups": 6,
  "groups_passed": 6,
  "groups_failed": 0,
  "total_tests": 963,
  "tests_passed": 963,
  "tests_failed": 0,
  "runtime_seconds": 23.68,
  "overall_status": "PASS",
  "groups": [...]
}
```

## Usage

```bash
cd /root/.hermes/profiles/ilma
python3 scripts/ilma_integrated_test_runner.py
```

## Import Smoke Modules (CORRECTED)

```python
imports = [
    "ilma_workflow_ecc",
    "ilma_orchestrator",
    "ilma_model_router",
    "ilma_judge_system",
    "ilma_evidence_validator",
    "ilma_knowledge_ingestion",
    "ilma_adversarial_qa",
    "ilma_metrics_monitoring",
    "ilma_capability_registry",
    "ilma_complete_system",
]
```

**CRITICAL:** Do NOT include `ilma_memory_layer` or `ilma_meta_cognition` — they don't exist as modules in ILMA root. Use existing modules only.

## Phase 22D Results

```
Groups: 6 passed, 0 failed out of 6
Tests: 963 passed, 0 failed out of 963
Runtime: 27.81s
```

## Common Issues

### Issue: Import smoke fails with ModuleNotFoundError

**Cause:** Including modules that don't exist in ILMA root.

**Fix:** Check actual module list with:
```bash
ls /root/.hermes/profiles/ilma/ilma_*.py
```

Only use modules that actually exist.

### Issue: Integrated test reports 5/6 groups pass

**Cause:** One group failed (usually import_smoke or frozen_baseline).

**Fix:** Run the failed group manually to see error:
```bash
cd /root/.hermes/profiles/ilma
python3 -c "import <module_name>"
```

### Issue: Cannot import ilma_workflow_ecc from ILMA root

**Cause:** `ilma_workflow_ecc.py` exists but module import fails due to path issues.

**Fix:** The module IS importable when run from correct directory. Test import directly:
```bash
cd /root/.hermes/profiles/ilma
python3 -c "import ilma_workflow_ecc; print('OK')"
```

## Phase 22M Regression Check List

When running regression check after Phase:
1. ✅ Integrated test suite exists
2. ✅ Integrated test suite passes (6/6 groups, 963/963)
3. ✅ File count >= 500 (scanner verified)
4. ✅ Compile pass (exit code 0)
5. ✅ Registry recalculated (VERIFIED, STRONGLY_SUPPORTED, PARTIAL counts)
6. ✅ Manifest/dependency valid
7. ✅ Evidence IDs unique
8. ✅ Security review pass
9. ✅ Mutation spot check pass
10. ✅ No secret leak
11. ✅ No false 1000-file claim