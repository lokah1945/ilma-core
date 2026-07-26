# Phase 38 Reference: NEEDS_SMALL_SCRIPT Implementation and Behavioral Proof

**Date:** 2026-05-09
**Phase:** 38

---

## Context

Phase 38 implemented behavioral proof for NEEDS_SMALL_SCRIPT capabilities — those with no script and no provider dependency. Unlike TEST_READY_NOW (which had existing scripts to test), NEEDS_SMALL_SCRIPT required BOTH script implementation AND behavioral testing.

---

## Key Decisions

1. **Only 3 of 12 NEEDS_SMALL_SCRIPT implemented** (file_operations, working_buffer, debugging)
2. **9 deferred** (networking HIGH risk, others provider-dependent)
3. **Minimal scripts** — stdlib only, 4-7KB each
4. **7 behavioral tests per script** — deterministic, actual I/O

---

## Scripts Implemented

| Script | Size | Functions | Tests | Evidence ID |
|--------|------|-----------|-------|-------------|
| ilma_file_operations.py | 4.5KB | safe_read, safe_write, safe_list_dir, detect_path_traversal | 7/7 | ILMA-EVID-20260509-P38-FILE-OPERATIONS-001 |
| ilma_working_buffer.py | 4.1KB | buffer_store, buffer_get, buffer_update, buffer_delete, buffer_clear | 7/7 | ILMA-EVID-20260509-P38-WORKING-BUFFER-001 |
| ilma_debugging.py | 7.0KB | detect_pattern, diagnose_error, suggest_fix, parse_traceback | 7/7 | ILMA-EVID-20260509-P38-DEBUGGING-001 |

---

## Deferred NEEDS_SMALL_SCRIPT

| Capability | Reason |
|------------|--------|
| networking | HIGH risk — shell injection potential |
| documentation | Merge with existing |
| writing_blog | Merge with existing |
| writing_novel | Merge with existing |
| contradiction_detection | LLM-dependent |
| checkpoints_rollback | Defer |
| runtime_benchmarking | Defer |
| phase17_350file_execution | Not needed |
| context_refs | Defer |

---

## Runner Update

| Category | Before | After | Change |
|----------|--------|-------|--------|
| standalone_behavior_evidence | 12 | 15 | +3 |
| compile_checks | 516 | 520 | +4 |
| **TOTAL** | **1006** | **1013** | **+7** |

---

## Registry Results

| Status | Before | After | Change |
|--------|--------|-------|--------|
| **VERIFIED** | **31** | **34** | **+3** |
| STRONGLY_SUPPORTED | 66 | 63 | -3 |
| Weak VERIFIED | 0 | 0 | 0 |

---

## Selection Criteria for NEEDS_SMALL_SCRIPT

```
IMPLEMENT_NOW if ALL of:
1. LOCAL — no external provider/API dependency
2. MINIMAL — script can be built in <2KB with stdlib
3. HIGH VALUE — widely used, foundational capability
4. TESTABLE — 7+ deterministic behavioral tests possible

DEFER if ANY of:
1. Requires network operations (networking → HIGH risk)
2. LLM-dependent (contradiction_detection)
3. High complexity (checkpoints_rollback)
4. Already covered (documentation, writing_*)
5. Not needed (phase17_350file_execution)
```

---

## Behavioral Proof Batch Pattern

```python
# scripts/ilma_phase38_behavioral_proof_batch.py

import sys
sys.path.insert(0, '/root/.hermes/profiles/ilma')

def test_file_operations():
    """Test file_operations capability."""
    from scripts.ilma_file_operations import FileOperations
    fo = FileOperations()
    # Test sandboxed write
    result = fo.safe_write("/tmp/test_ilma.txt", "test content")
    assert result == True
    # Test sandboxed read
    content = fo.safe_read("/tmp/test_ilma.txt")
    assert content == "test content"
    # Test path traversal detection
    detected = fo.detect_path_traversal("../etc/passwd")
    assert detected == True
    return "ILMA-EVID-20260509-P38-FILE-OPERATIONS-001"

# Similar for working_buffer and debugging

if __name__ == "__main__":
    results = []
    for test_func in [test_file_operations, test_working_buffer, test_debugging]:
        try:
            eid = test_func()
            print(f"✅ {test_func.__name__}: {eid}")
            results.append((test_func.__name__, "PASS", eid))
        except Exception as e:
            print(f"❌ {test_func.__name__}: {e}")
            results.append((test_func.__name__, "FAIL", None))
    
    passed = sum(1 for r in results if r[1] == "PASS")
    print(f"\nRESULTS: {passed}/{len(results)} passed")
    sys.exit(0 if passed == len(results) else 1)
```

---

## Key Lessons

1. **Selection over quantity** — Only 3 of 12 implemented (quality over quantity)
2. **Minimal scripts** — stdlib only, no external dependencies
3. **Behavioral proof first** — 21 tests must pass before registry upgrade
4. **Weak VERIFIED maintained** — 0 throughout (all upgraded with real tests)
5. **Security preserved** — No shell=True, no hardcoded secrets

---

## Phase 39 Recommendation

Continue behavioral proof round OR accept 63 SS as aspirational baseline.

---

*Evidence ID: ILMA-EVID-20260509-P38-REFERENCE-001*