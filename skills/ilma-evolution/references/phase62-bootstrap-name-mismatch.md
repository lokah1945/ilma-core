# Phase 62: Bootstrap Name-Mismatch Bug — ILMA v3.9 Consolidation

**Date:** 2026-05-17
**Phase:** 62
**Area:** infra (consolidation, bootstrap)

---

## The Bug

During ILMA v3.9 SSS+++ consolidation, bootstrap reported `health_mgr` as FAIL:
```
✅ smart_router
❌ health_mgr
✅ fallback_engine
...
```

But when `get_health_manager()` was called directly after bootstrap, it returned a healthy `HealthManager` object. The component loaded fine — only the bootstrap check was wrong.

## Root Cause

The `bootstrap()` method had this component list:
```python
components = [
    'smart_router', 'health_mgr', 'fallback_engine', ...
]
```

And this check:
```python
for name in components:
    factory_method = getattr(self._factory, f'get_{name}', None)
    results[name] = factory_method() is not None
```

When `name = 'health_mgr'`, the lookup was `get_health_mgr` (underscore, no 'manager'). But the actual factory method is `get_health_manager()`.

Result: `getattr(factory, 'get_health_mgr', None)` returns `None` → bootstrap reports FAIL even though `get_health_manager()` works perfectly.

**Contrast:** `fallback_engine` matches `get_fallback_engine()` exactly → OK. Same for `dag_engine`, `smart_router`.

## The Fix

```python
# WRONG (in bootstrap component list)
'health_mgr'

# CORRECT
'health_manager'
```

Also applied the same fix to `status()` method which used the same incorrect list.

## Why It Wasn't Caught Earlier

- Direct calls to `get_health_manager()` always worked (the underlying component was fine)
- The bootstrap loop just silently got `None` for the factory method and marked it FAIL
- No exception was raised — just a `getattr(..., None)` returning None
- The init order print showed `health_mgr` because the dictionary key was `'health_mgr'` (that's correct — internal key names don't have to match method names)
- But the bootstrap check was comparing the wrong name string against method names

## The Pattern: Name-Mismatch Silent Failure

When you have a registry/list of component names and you construct method names via f-string, the string must match the actual method name exactly. A mismatch produces `None` rather than an exception, so it's a silent failure — the component is reported as failed when it actually loaded fine.

**Prevention:** Every time you add a new component to a bootstrap/status list, verify:
1. The string in the list exactly matches the method name after `get_`
2. Or better: generate the list from the method names themselves, not from a hardcoded list

## ILMA Self-Audit Pattern Triggered

This was found during the consolidation validation process — not from an error message. The trace showed:
```
[TRACE] No get_health_mgr method found
```

This required going back to the source code to find the mismatch. A cleaner prevention would be a bootstrap self-check that verifies every factory method in the list actually exists before calling it.

---

## Files Modified

- `/root/.hermes/profiles/ilma/ilma_core/__init__.py` — lines 435, 491: `'health_mgr'` → `'health_manager'`

## See Also

- `references/phase-56-production-entrypoint.md` — production entry point verification patterns
- `references/phase60-orphaned-module-detection.md` — module resolution patterns
- `ilma-self-improvement/references/phase-56-execute-repair-now-pattern.md` — audit→patch→test→report cycle