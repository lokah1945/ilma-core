---
name: ilma-phase-10-recovery
description: Phase 10R recovery lessons — hard-won insights from 272-test codebase recovery with test triage, file count verification, mutation testing, and honest gap reporting
tags: [phase-10, recovery, mutation-testing, test-fix, evidence-based]
created: 2026-05-08
---

# ILMA Phase 10R Recovery Pattern

## Purpose
Systematic approach for large-scale codebase recovery when test failures, file count discrepancies, and runtime budget constraints complicate phase completion.

## Triggers
- Large phase (200+ files) has test failures
- Batch file generation claims don't match actual output
- Runtime turn budget concerns during long phases
- Need to recover gracefully from inflated claims

## Core Lessons

### Lesson 1: File Count — Unique Count Only
**Problem:** Batch scripts reported "N files written" as running sum. Claimed 255, actual was 151.
**Fix:** Always unique count post-generation:
```python
from pathlib import Path
purposeful = [p for p in Path(target_dir).rglob('*.py')
              if not p.name.startswith('test_') and '__pycache__' not in str(p)]
```
**Prevention:** Verify after each batch with `find target_dir -name "*.py" | wc -l`.

### Lesson 2: Test Failure Triage — Categorize Before Fixing
**Triage Protocol:**
1. Run all tests — get complete failure list first
2. Categorize: **Contract mismatch** → add method to impl | **Implementation bug** → fix impl | **Test data** → fix test | **Import/syntax** → fix imports
3. Group by category, fix by batch

### Lesson 3: Runtime Budget Audit — Verify Before Trusting
```python
import yaml
config = yaml.safe_load(open('config/ilma/config.yaml'))
print(f"agent.max_turns: {config['agent']['max_turns']}")
```
Older session context carries stale assumptions. Always verify current runtime.

### Lesson 4: Test Files Must Be Excluded from Secrets Scans
**Fix:** Add to scan skip list: `['tests/', 'test_projects/', '__pycache__/', 'docs/']`

### Lesson 5: Integration Tests Define the Contract
If integration test calls `mark_healthy()` or `register()` and method is missing → **add the method to implementation**. This is contract fix, not test hack.

### Lesson 6: Batch Generation Silent Failures
**Prevention:** After each batch, compare expected vs actual file count:
```bash
echo "Expected N, got $(find target_dir -name '*.py' -not -path '*/__pycache__/*' | wc -l)"
```

### Lesson 7: Honesty Over Inflation
Report gaps honestly. Gap analysis = actionable intelligence.

### Lesson 8: Phase Completion Checklist
- [ ] All tests pass (full count)
- [ ] Unique file count verified
- [ ] All JSON valid
- [ ] No hardcoded secrets
- [ ] Benchmarks within threshold
- [ ] Kanban updated
- [ ] Evidence IDs registered
- [ ] Regression complete
- [ ] Report what was NOT achieved

## Workflow
```
Audit Runtime → Run All Tests → Triage by Category → Fix by Batch → 
Re-verify → Mutation Testing → Security Review → Performance → 
Specialist Validation → Evidence Registry → Regression → Final Report
```

## Evidence IDs from Phase 10R
P10R-001 through P10R-008 covering test recovery, mutation, security, performance, specialist validation, file count correction, runtime verification, regression.