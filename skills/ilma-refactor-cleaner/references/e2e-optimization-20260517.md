# ILMA End-to-End Optimization Pattern — Session 2026-05-17

## What happened

Comprehensive optimization of ILMA v3.24 core files. The session produced a repeatable 10-task pattern that can be applied to future optimization passes.

## The 10-Task Sequence

| # | Task | Focus |
|---|------|-------|
| 1 | Audit scripts/ folder | `find` + `grep` to identify which files are actually imported/referenced vs orphaned |
| 2 | Optimize ilma.py | Remove duplicate inline imports, fix name collision (`route_task as model_route_task`) |
| 3 | Optimize ilma_capability_registry.py | Verify all registered capabilities are actually callable |
| 4 | Optimize ilma_workflow_ecc.py | Verify 8-step pipeline imports are clean at top level |
| 5 | Optimize ilma_orchestrator.py | Find and remove inline duplicate imports |
| 6 | Optimize ilma_health_manager.py + ilma_subagent_router.py | Same pattern |
| 7 | Optimize ilma_model_router.py | Verify DB integration; check for intentional lazy imports (leave those) |
| 8 | Optimize ilma_core/__init__.py | Same pattern |
| 9 | Remove duplicate/obsolete scripts | Move confirmed duplicates to `.deprecated/`, verify canonical version exists |
| 10 | Run end-to-end integration test | `--status`, `--route`, import smoke tests, runtime wiring check |

## Key Discovery: Inline Import Deduplication Pattern

### What we found
Many functions in ILMA had `import X` statements inside the function body, even though `X` was already imported at the top of the file. This is:
- Redundant (import is cached by Python, but still adds lookup overhead)
- Confusing (creates doubt about what is actually needed)
- A sign of copy-paste or evolving code

### The fix
1. `grep -n '^\s*import ' FILE` or `grep -n '^\s*from ' FILE` — find ALL import lines in file
2. Cross-reference with top-level import block
3. Remove inline import if module already imported at top
4. If inline import is the ONLY place the module appears, keep it (or move to top — that's a style choice)

### Exceptions (do NOT remove)
- **Intentional lazy imports** — used to avoid circular deps or heavy initialization at module load time
- **Conditional imports** — `try: ... except: from fallback_module import ...` pattern
- **Runtime-branched imports** — import changes based on config/environment at runtime

### How to distinguish
```python
# BAD — remove inline, keep only top-level
def cmd_benchmark(args):
    import time   # ← already imported at top of file
    ...

# GOOD — keep, it's the only usage of shutil in that file
def _backup_file(self, path):
    import shutil
    shutil.copy2(path, backup_path)  # Only used here, but could still move to top
```

## Critical Fix: route_task Name Collision

### Problem
```
ilma.py defines: route_task(message: str, prefer_free: bool, response: str, execute: bool)
ilma_model_router.route_task(task_type: str, max_fallbacks: int, capability_context: dict)
```

`ilma.py`'s `route_task()` called `ilma_model_router.route_task()` internally, but since the local definition shadowed the import, calling `route_task(...)` inside the function caused infinite recursion → `TypeError`.

### Solution (3-step)
```python
# Step 1 — alias at top level
from ilma_model_router import route_task as model_route_task

# Step 2 — update internal calls to use the alias
result = model_route_task(task_type, capability_context=capability_context)

# Step 3 — verify
python3 -m py_compile ilma.py
python3 ilma.py --route coding
```

### Alternative approaches considered
- Rename local function — **rejected** because external callers depend on `route_task()`
- Use `from x import route_task` inline inside function — **rejected** because it's the same as having a top-level import but hidden

## Duplicate File Handling Pattern

### Identification
```bash
# Find files with same name in scripts/ vs root
for f in scripts/ilma_*.py; do
  base=$(basename "$f")
  if [ -f "../$base" ]; then
    echo "DUPLICATE: $base"
  fi
done
```

### Verification before archiving
1. Confirm root version is canonical (larger, more complete, has `__main__` block, imported by other files)
2. Confirm scripts/ version is truly redundant (no unique code)
3. Confirm tests reference root version, not scripts/ version
4. Move to `.deprecated/` (not delete — preserves history)
5. Verify compile still passes

### In this session
6 duplicates moved: `ilma_confidence_router.py`, `ilma_super_coding_command_center.py`, `ilma_workflow_ecc.py`, `ilma_adversarial_qa.py`, `ilma_judge_system.py`, plus a timestamped `ilma_capability_registry_scripts_*.py`.

## Git Sync Pattern

ILMA profile dir is NOT a git repo. The canonical repo is at `/tmp/ilma-core-update/` which syncs to `github.com/lokah1945/ilma-core.git`.

After modifying ILMA core files:
```bash
# In ilma profile:
cp ilma.py /tmp/ilma-core-update/
# In ilma-core-update repo:
git add ilma.py
git commit -m "message"
git push origin master  # NOT main
```

## Test Results (2026-05-17)
```
ilma --status:                ✅ PASS
ilma --route coding:         ✅ PASS
ilma --route research:       ✅ PASS
workflow_ecc import:         ✅ PASS
capability_registry (35):    ✅ PASS
health_manager:              ✅ PASS
ilma_core (10/10):            ✅ PASS
ilma_runtime_wiring:         ✅ PASS (27/27 modules)
```