# Parallel Executor Path Resolution — ILMA Session Log

## The Bug (2026-05-10, Phase 52S)

**Symptom:** `job_capability_map_validation` failed (1 per-job failure per cycle) in the daemon's parallel executor, but passed when run as a standalone Python one-liner.

**Root cause:** Handler function used `from ilma_capability_registry import ...` without setting sys.path. The daemon set `sys.path.insert(0, "scripts")` at startup. This meant Python could only find modules *inside* `scripts/` subdirectory — not the ILMA root where `ilma_capability_registry.py` actually lives.

**Why it was tricky:** The module DOES exist at `/root/.hermes/profiles/ilma/ilma_capability_registry.py`. The import works in isolation (when sys.path naturally includes the working directory). The failure only manifests in the parallel executor's thread pool context where path order matters.

## The Fix

```python
def job_capability_map_validation() -> dict:
    try:
        import sys as _sys
        _sys.path.insert(0, str(ILMA_PROFILE))  # ← explicitly add root path
        from ilma_capability_registry import CapabilityRegistry
        ...
```

**Result:** 368/368 PASS (was 367/1).

## Pattern: sys.path Insertion Order in Parallel Workers

When a process sets `sys.path.insert(0, "subdir")`, it shadows the root directory. Any imports that assume root-level modules must explicitly re-insert the root path *inside* the function, not just at process startup.

**Rule:** Inside job handler functions that live in `scripts/`, if you need to import from ILMA root:
```python
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))  # root = parent of scripts/
```

**Do NOT rely on the outer process having set sys.path correctly** — thread pool workers may have different path states.

## Diagnostic Steps Used

1. Isolated job → passed (root in path naturally)
2. Parallel executor (12 workers) → 1 fail every run
3. Searched for `capability_map_validation` → found handler in `ilma_parallel_worker_executor.py`
4. Checked import line → `from ilma_capability_registry import CapabilityRegistry`
5. Verified module location → `/root/.hermes/profiles/ilma/ilma_capability_registry.py` (root, not scripts/)
6. Checked daemon startup → `sys.path.insert(0, "scripts")` shadows root
7. Applied fix → verified with 368-job parallel run