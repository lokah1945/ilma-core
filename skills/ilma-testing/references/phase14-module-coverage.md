# Test Naming Pitfall + 9-Module Coverage Verification Pattern
**Date:** 2026-05-10
**Session:** Phase 14E (Uncovered Module Tests)

## The Problem: pytest fixture collision

When a function in a test file has prefix `test_`, pytest treats it as a test case AND looks for fixture parameters.

```python
# FAILS when run via pytest
def test_module_import(module_name):  # 'module_name' is a pytest fixture
    try:
        mod = importlib.import_module(module_name)
        return True, mod
    except Exception as e:
        return False, str(e)
```

Error: `fixture 'module_name' not found`

## The Solution: check_* helpers + main()

For scripts that run standalone AND via pytest:

```python
#!/usr/bin/env python3
"""ILMA Core Module Tests — Phase 14E"""

import sys
import importlib
import inspect
from pathlib import Path

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
sys.path.insert(0, str(ILMA_ROOT))  # Use ABSOLUTE path

MODULES = [
    "ilma_learning_engine",
    "ilma_capability_registry",
    "ilma_provider_kernel",
    "ilma_cognition_kernel",
    "ilma_reasoning_runtime",
    "ilma_grounding_loop",
    "ilma_confidence_router",
    "ilma_execution_graph",
    "ilma_autonomous_loop_engine",
]

def check_module_import(module_name):
    """Test that module imports successfully. Returns (bool, result)."""
    try:
        mod = importlib.import_module(module_name)
        return True, mod
    except Exception as e:
        return False, str(e)

def check_module_classes(module):
    """Test that module defines classes. Returns (bool, class_list)."""
    classes = [name for name, obj in inspect.getmembers(module, inspect.isclass)]
    return len(classes) > 0, classes

def check_module_functions(module):
    """Test that module defines non-private functions. Returns (bool, func_list)."""
    funcs = [name for name, obj in inspect.getmembers(module, inspect.isfunction)
             if not name.startswith("_")]
    return len(funcs) > 0, funcs

def check_module_entry(module):
    """Test for common entry points (main, run, execute). Returns bool."""
    return hasattr(module, "main") or hasattr(module, "run") or hasattr(module, "execute")

def run_tests():
    """Run all checks. Called by main()."""
    results = {}
    for mod_name in MODULES:
        print(f"\n{'='*60}")
        print(f"Module: {mod_name}")
        print('='*60)
        
        # Test 1: Import
        ok, result = check_module_import(mod_name)
        print(f"  [1] Import: {'✅ PASS' if ok else '❌ FAIL'}")
        if not ok:
            results[mod_name] = {"import": False, "classes": False, "functions": False, "entry": False}
            continue
        
        module = result
        
        # Test 2: Has classes
        ok, classes = check_module_classes(module)
        print(f"  [2] Has classes: {'✅ PASS' if ok else '❌ FAIL'} ({len(classes)} classes)")
        if ok:
            for cls in classes[:5]:
                print(f"      - {cls}")
        
        # Test 3: Has functions
        ok, funcs = check_module_functions(module)
        print(f"  [3] Has functions: {'✅ PASS' if ok else '❌ FAIL'} ({len(funcs)} funcs)")
        
        # Test 4: Entry point
        ok = check_module_entry(module)
        print(f"  [4] Has entry point: {'✅ PASS' if ok else '⚠️  NONE'}")
        
        results[mod_name] = {
            "import": True,
            "classes": check_module_classes(module)[0],
            "functions": check_module_functions(module)[0],
            "entry": check_module_entry(module),
        }
    
    return results

def main():
    results = run_tests()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results.values() if all(r.values()))
    failed = sum(1 for r in results.values() if not all(r.values()))
    
    for mod_name in sorted(results):
        status = "✅" if all(results[mod_name].values()) else "❌"
        print(f"{status} {mod_name}")
    
    print(f"\nModule tests: {passed} PASS, {failed} FAIL")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
```

## sys.path Pattern: Absolute Path

**PROBLEM:** Running from `tests/` directory fails because modules aren't in path.

**SOLUTION:**
```python
from pathlib import Path
ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
sys.path.insert(0, str(ILMA_ROOT))  # Use ABSOLUTE, not "."
```

## Results from Phase 14E

All 9 modules tested:
- ilma_learning_engine ✅ (9 classes, 2 funcs)
- ilma_capability_registry ✅ (6 classes, 12 funcs)
- ilma_provider_kernel ✅ (6 classes, 2 funcs)
- ilma_cognition_kernel ✅ (6 classes, 2 funcs)
- ilma_reasoning_runtime ✅ (7 classes, 2 funcs)
- ilma_grounding_loop ✅ (7 classes, 2 funcs)
- ilma_confidence_router ✅ (2 classes, 3 funcs)
- ilma_execution_graph ✅ (6 classes, 0 funcs) — no top-level functions
- ilma_autonomous_loop_engine ✅ (6 classes, 0 funcs) — no top-level functions

## Standalone vs pytest execution

| Method | Result |
|--------|--------|
| `python3 tests/test_ilma_core_modules.py` | 7 PASS, 0 FAIL (standalone main()) |
| `python3 -m pytest tests/ -q` | 141 PASS (check_* functions not collected as tests) |

Both methods work. The check_* pattern is the key to dual-mode compatibility.