# Phase 62: Bootstrap Name-Mismatch — ILMA v3.9 SSS+++ Consolidation

**Date:** 2026-05-17 | **Phase:** 62 | **Area:** infra

---

## The Bug

Bootstrap reported `health_mgr` as FAIL but the component was actually fine:

```
✅ smart_router
❌ health_mgr      ← WRONG (reported as fail)
✅ fallback_engine ✓
✅ dag_engine ✓
```

When called directly: `factory.get_health_manager()` → `HealthManager` (healthy, 15 models tracked).

## Root Cause

In `ilma_core/__init__.py`, `bootstrap()` and `status()` used this component list:

```python
components = [
    'smart_router', 'health_mgr', 'fallback_engine', ...
]
```

Then constructed method names via f-string:
```python
factory_method = getattr(self._factory, f'get_{name}', None)
```

For `'health_mgr'` → `getattr(factory, 'get_health_mgr', None)` → `None` (method doesn't exist!)

Actual method: `get_health_manager()` — no `get_health_mgr` method exists.

**Result:** `None` is not callable → `results[name] = False` → reported as FAIL.

But `get_health_manager()` itself works perfectly — it's just not being checked because the name string doesn't match.

## Why It's a Silent Failure

- No `AttributeError` raised — `getattr(..., None)` explicitly returns `None` when not found
- The check `factory_method() is not None` never executes when `factory_method is None`
- `None is not None` → `False` → reported as failed
- The actual component loads fine on first access via other code paths

## The Fix

```python
# WRONG
'health_mgr'    # → get_health_mgr() → None → FAIL

# CORRECT  
'health_manager'  # → get_health_manager() → HealthManager → OK
```

Applied in two places in `ilma_core/__init__.py`:
- `bootstrap()` component list (line ~491)
- `status()` component list (line ~435)

## Why It Wasn't Caught Sooner

- The component itself worked fine — direct `get_health_manager()` calls always returned healthy objects
- Only the bootstrap/status verification was wrong
- No test called `getattr(factory, f'get_{name}')` specifically and noticed it returned None
- The fix required reading the bootstrap loop source to understand the f-string method name construction

## Detection Method

When a component shows FAIL in bootstrap but works when called directly, check:
```bash
grep -n "get_health_mgr\|get_health_manager" ilma_core/__init__.py
```

Always compare: the string in the component list vs the actual method name.

## Prevention Pattern

**Rule:** When maintaining a component registry that maps strings to factory methods via f-strings:
1. Use the exact method name (not an abbreviation) in the registry
2. OR generate the registry programmatically from actual method names
3. Add a bootstrap self-check: verify `getattr(factory, f'get_{name}')` is not None before calling it
4. For any FAIL result where the component is known to work, immediately check for name mismatches

---

## Files Modified

`/root/.hermes/profiles/ilma/ilma_core/__init__.py`
- Line ~435 (status method): `'health_mgr'` → `'health_manager'`
- Line ~491 (bootstrap method): `'health_mgr'` → `'health_manager'`

## Related

- `ilma-self-improvement/SKILL.md` — Phase 62 pattern entry
- `ilma-evolution/references/phase62-bootstrap-name-mismatch.md` — full case study