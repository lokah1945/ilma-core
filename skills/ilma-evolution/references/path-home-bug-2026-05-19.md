# Path.home() Returns Wrong Value in ILMA Runtime

**Date:** 2026-05-19
**Severity:** CRITICAL — causes all Path-based file lookups to fail silently
**Component:** ILMA runtime environment

## Problem

Inside ILMA's Python runtime (running as a Hermes subagent or forked process), `Path.home()` returns:

```
/root/.hermes/profiles/ilma/home
```

**Expected:**
```
/root/.hermes
```

This causes any code using `Path.home() / ".hermes" / "something"` to resolve to the wrong path:
- `/root/.hermes/profiles/ilma/home/.hermes/...` (does NOT exist)
- Instead of `/root/.hermes/...` (correct)

## Affected Code Patterns

```python
# WRONG in ILMA runtime:
Path.home() / ".hermes" / "skills"
Path.home() / ".hermes" / "kanban.db"
Path.home() / ".hermes" / "hermes-agent" / "skills"

# CORRECT:
HERMES_ROOT = Path("/root/.hermes")  # Always use absolute path
HERMES_ROOT / "skills"
HERMES_ROOT / "kanban.db"
HERMES_ROOT / "hermes-agent" / "skills"
```

## Symptoms

- Hermes skills not found (scanner returns 0 or wrong count)
- Kanban DB not found
- hermes-agent skills not scanned
- Silent failure — no error, just empty results

## Detection

```python
from pathlib import Path
assert Path.home() == Path("/root/.hermes"), f"Path.home() wrong: {Path.home()}"
```

## Fix Applied

All affected files now use `HERMES_ROOT = Path("/root/.hermes")` as a module-level constant instead of `Path.home()`.

**Files fixed:**
- `ilma_hermes_skills_router.py`
- `ilma_kanban_integration.py`

## Lesson

Never assume `Path.home()` returns a known value in a subagent/runtime context. Always use absolute paths for system-level resources in ILMA. This applies to:
- `/root/.hermes/` paths
- `/root/.config/` paths
- Any host-level filesystem paths
