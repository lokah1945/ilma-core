# sys.path Shadowing — Orphaned Module Detection (2026-05-15)

## What Happened

`ilma_complete_system.py` imported from root-level modules:
```python
from ilma_capability_registry import CapabilityRegistry, CapabilityCategory
from ilma_confidence_router import ConfidenceAwareRouter
```

These worked fine when `ilma_complete_system.py` was tested standalone. But when other parts of the system ran and added `scripts/` to `sys.path` (because `scripts/` was cwd), Python found the `scripts/` versions FIRST:

| File | Root Version | scripts/ Version |
|------|-------------|-----------------|
| `ilma_capability_registry.py` | Has `CapabilityCategory` | Missing `CapabilityCategory` |
| `ilma_confidence_router.py` | Has `ConfidenceAwareRouter` | Missing `ConfidenceAwareRouter` |

**Result:** `ilma_complete_system.py` imports broke when `scripts/` was in `sys.path`.

## Detection Method

```bash
# Find all files importing a module
grep -r "from ilma_complete_system import" --include="*.py" .

# Exclude the module itself
grep -v "ilma_complete_system.py:" ...

# Count: if only test files import it → ORPHANED
```

## Prevention Rules

1. **Never create duplicate files** — if a file exists at root, never create another with the same name in `scripts/`
2. **Canonical location per file** — each module has ONE canonical location
3. **Verify before import** — test that a module imports correctly from the expected path
4. **Check sys.path** — be aware that cwd prepend creates shadowing risk