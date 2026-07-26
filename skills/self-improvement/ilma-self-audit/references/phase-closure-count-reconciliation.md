# Phase Closure Count Reconciliation Reference

**Created:** 2026-05-09
**Lesson:** Phase 20R forensic truth audit

---

## The Problem

Phase 20CLOSE violated phase closure reporting by:
1. Counting external directories as ILMA files
2. Running only new tests, not the phase's full test suite
3. Including post-phase work (AYDA integration at 14:43) as Phase 20 achievement (Phase 20 ended at 13:11)

---

## External Directories to EXCLUDE

| Directory | Reason |
|----------|--------|
| `.openclaw/` | OpenClaw/AYDA workspace (different agent) |
| `.cache/`, `cache/` | Python/UV package cache |
| `backup/`, `backups/`, `.backup/` | Backup directories |
| `test_projects/` | Generated test codebases |
| `.git/` | Git repository |

---

## Correct Count Pattern

```python
import os

EXTERNAL_DIRS = {'.openclaw', '.cache', 'cache', 'backup', 'backups', 
                '.backup', '.git', 'node_modules', 'test_projects'}

def count_true_ilma_files(base_path):
    """Count purposeful ILMA Python files, excluding external dirs."""
    count = 0
    for root, dirs, files in os.walk(base_path):
        # Prune external directories
        dirs[:] = [d for d in dirs if d not in EXTERNAL_DIRS and not d.startswith('.')]
        
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                try:
                    size = os.path.getsize(path)
                    if size > 100:  # Purposeful, not stub
                        count += 1
                except:
                    pass
    return count
```

---

## Phase 20R True Counts (2026-05-09)

| Source | Count |
|--------|-------|
| scripts/ | 365 |
| fabric/ | 50 |
| skills/ | 50 |
| capabilities/ | 9 |
| ilma_core/ | 3 |
| ilma_*.py (root) | 19 |
| **ILMA Python files** | **496** |
| test_projects/ | 1,362 (generated) |
| **Total** | **1,858** |

Phase 20 target: 425 → **TARGET MET (496 > 425)** ✅

---

## Authoritative Phase Reports

| Phase | Report | Date |
|-------|--------|------|
| Phase 20 | `ILMA_PHASE20_425FILE_EXECUTION_GATE_REPORT_2026-05-09.md` | 13:11 UTC |
| Phase 20CLOSE | `ILMA_PHASE20CLOSE_CLOSURE_REPORT_2026-05-09.md` (corrected) | 15:50 UTC |

**Rule:** Read authoritative phase report BEFORE writing closure report.

---

## Evidence IDs

| ID | Description |
|----|-------------|
| `ILMA-EVID-20260509-P20R-TRUTH-001` | True ILMA files: 496 |
| `ILMA-EVID-20260509-P20R-TEST-001` | Phase 20 tests: 496 |
| `ILMA-EVID-20260509-P20R-AYDA-001` | AYDA integration: post-Phase 20 |
| `ILMA-EVID-20260509-P20R-VIOLATION-001` | Violations identified and corrected |