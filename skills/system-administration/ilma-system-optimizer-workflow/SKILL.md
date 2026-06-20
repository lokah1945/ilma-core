---
name: ilma-system-optimizer-workflow
description: System optimization workflow - detect and replace fake/stub modules with production-ready code. SSS Tier 3.
tags:
  - system-optimization
  - stub-detection
  - fabric-modules
triggers:
  - "optimize system"
  - "fix fake modules"
  - "replace stubs"
  - "system audit"
---

# ILMA System Optimizer Workflow

## Problem Statement

When auditing a system (like ILMA), many files may appear to exist but are actually **fake/stub implementations** OR **unused duplicate modules** that waste space and cause benchmarks to overcount.

**TWO DISTINCT PROBLEMS:**

### Problem A: Fake/Stub Files
Files with minimal code (e.g., 6-20 lines) that are never used.
```python
# Example: 6-line stub
"""ILMA Worker 1 - Additional worker component."""
class Worker1:
    def __init__(self):
        self.id = "worker_1"
```

### Problem B: Duplicate/Unused Modules
Files that have real code but are NOT used by the system runtime. These were often copied from source systems (like AYDA) but never integrated.

**Example:** 20 `fabric_module_*.py` files existed in ILMA but:
- They were ~100 lines each (not stubs)
- They were NOT imported or used anywhere in ILMA runtime
- They duplicated functionality already in other files
- **Correct action: DELETE entirely, not replace**

---

## Solution Pattern

### Decision Tree: Replace vs Delete

```
Is the module being imported/used in runtime?
├── YES → Is it a stub (<20 lines, no real functionality)?
│   ├── YES → Replace with production implementation
│   └── NO → Keep as-is, verify it's production-ready
└── NO → Is it a duplicate of another file?
    ├── YES → DELETE (save space, reduce confusion)
    └── NO → Is it potentially useful?
        ├── YES → Keep with note about non-usage
        └── NO → DELETE
```

### Step 1: Detect Unused/Duplicate Files
```bash
# Find files NOT imported anywhere
cd /root/.hermes/profiles/ilma
grep -r "import.*fabric_module" . --include="*.py" | grep -v ".home" | wc -l

# Find potential duplicates (same size, similar names)
find . -name "ilma_*.py" -exec basename {} \; | sort | uniq -d

# Count all root ilma_*.py files
ls -la ilma_*.py | wc -l
```

### Step 2: Check Runtime Usage
```bash
# Is fabric_module actually used?
grep -r "fabric_module" . --include="*.py" | grep -v "home" | grep -v "__pycache__"

# Is scripts/ilma_*.py used?
grep -r "scripts/ilma_knowledge" ilma_*.py 2>/dev/null
```

### Step 3: Decision Making

**For FABRIC PLACEHOLDERS (not used in runtime):**
```bash
cd /root/.hermes/profiles/ilma/fabric/workers
rm -v fabric_module_*.py
```

**For ROOT DUPLICATES (duplicated in scripts/):**
```bash
cd /root/.hermes/profiles/ilma
# Keep canonical version in root, delete from scripts/
rm -v scripts/ilma_knowledge_graph.py scripts/ilma_learning_engine.py
```

### Step 4: Verify System Still Works
```bash
cd /root/.hermes/profiles/ilma
python3 ilma_complete_system.py 2>&1 | grep -E "FUSION|SCORE|Success"
```

Expected: FUSION SCORE 100.0% (system still works after cleanup)

---

## ILMA v3.0 Optimization Case Study

### Before Optimization
| Category | Count |
|----------|-------|
| Root ilma_*.py | 17 |
| Scripts | 278+ |
| Fabric modules | 20 placeholder |
| Cron duplicates | 15+ |

### Actions Taken
1. **DELETED** 20 fabric_module_*.py (not used in runtime)
2. **DELETED** 5 root duplicates (ilma_system_fusion, ilma_unified_system, ilma_orchestrator, ilma_router, ilma_capability_orchestrator)
3. **DELETED** 38+ scripts duplicates (cron, auto, self, vector, analytics, cloud)
4. **KEPT** all production-ready files with unique functionality

### After Optimization
| Category | Count |
|----------|-------|
| Root ilma_*.py | 12 (AYDA canonical) |
| Scripts | 240 (unique utilities) |
| Fabric modules | 9 (real workers) |
| Cron scripts | 7 (minimal set) |

### Result
- ✅ **65+ files removed**
- ✅ **FUSION SCORE: 100.0%** (system still fully functional)
- ✅ **No functionality lost**
- ✅ **No duplicates remaining**

---

## Anti-Patterns

❌ **Don't delete everything "unused"** - Some files are unused but may be needed
❌ **Don't assume "real code" means "used"** - Files can have 100+ lines but never be imported
❌ **Don't delete before verifying** - Always check if module is actually used in runtime
❌ **Don't replace with more code** - Sometimes DELETE is better than REPLACE

## Verification Commands

```bash
# Verify system still works after cleanup
python3 ilma_complete_system.py

# Count files after cleanup
find . -name "ilma_*.py" -not -path "./.home/*" | wc -l
find ./scripts -name "ilma_*.py" | wc -l

# Check for remaining duplicates
find . -name "ilma_*.py" -exec basename {} \; | sort | uniq -d
```

## Outcome

After applying this pattern to ILMA v3.0:
- Removed 65+ duplicate/unused files
- System still functions at 100% FUSION SCORE
- Cleaner architecture (12 canonical + 240 utilities)
- No functionality lost

## Related Skills

- `ilma-self-improve` - Continuous improvement
- `ilma-performance-optimizer` - Performance optimization
- `ilma-evolution` - System evolution patterns



## Related Skills

- `ilma-self-improve` - Continuous improvement
- `ilma-performance-optimizer` - Performance optimization
- `ilma-evolution` - System evolution patterns
