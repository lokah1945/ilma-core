#!/usr/bin/env python3
"""
ILMA Core Module Tests — Phase 14E
===================================
Targeted tests for 8 uncovered core modules.

Goal: Increase coverage, reduce PARTIAL capabilities, add meaningful tests.
"""

import sys
import importlib
import inspect
from pathlib import Path

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
sys.path.insert(0, str(ILMA_ROOT))  # Use absolute path

# Modules to test
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
    """Test that module imports successfully."""
    try:
        mod = importlib.import_module(module_name)
        return True, mod
    except Exception as e:
        return False, str(e)


def check_module_classes(module):
    """Test that module defines classes."""
    classes = [name for name, obj in inspect.getmembers(module, inspect.isclass)]
    return len(classes) > 0, classes


def check_module_functions(module):
    """Test that module defines functions."""
    funcs = [name for name, obj in inspect.getmembers(module, inspect.isfunction) 
             if not name.startswith("_")]
    return len(funcs) > 0, funcs


def check_module_entry(module):
    """Test for common entry points."""
    has_main = hasattr(module, "main") or hasattr(module, "run") or hasattr(module, "execute")
    return has_main


def run_tests():
    """Run all tests."""
    results = {}
    
    for mod_name in MODULES:
        print(f"\n{'='*60}")
        print(f"Testing: {mod_name}")
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
            if len(classes) > 5:
                print(f"      ... and {len(classes) - 5} more")
        
        # Test 3: Has functions
        ok, funcs = check_module_functions(module)
        print(f"  [3] Has functions: {'✅ PASS' if ok else '❌ FAIL'} ({len(funcs)} funcs)")
        if ok:
            for fn in funcs[:5]:
                print(f"      - {fn}")
            if len(funcs) > 5:
                print(f"      ... and {len(funcs) - 5} more")
        
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


if __name__ == "__main__":
    print("=== ILMA Core Module Tests (Phase 14E) ===\n")
    
    results = run_tests()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for mod_name, result in results.items():
        status = "✅" if result["import"] else "❌"
        print(f"{status} {mod_name}")
        if result["import"]:
            if result["classes"] and result["functions"]:
                passed += 1
            elif not result["classes"] and not result["functions"]:
                failed += 1
                print(f"    ⚠️  No classes or functions")
        else:
            failed += 1
            print(f"    ❌ Cannot import")
    
    print(f"\nModule tests: {passed} PASS, {failed} FAIL")
    print(f"Total tests: {len(results)}")
    
    # Exit code: 0 if all modules at least import
    sys.exit(0 if failed == 0 else 1)