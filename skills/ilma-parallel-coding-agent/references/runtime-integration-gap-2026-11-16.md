# Runtime Integration Gap (Session 2026-11-16)

## Summary
The parallel coding agent (`ilma_claudecode_agent.py`) exists and works via CLI, but is **NOT wired into the main DELEGATE phase** of ILMA's workflow.

---

## Current State

| Component | Status |
|-----------|--------|
| `ilma_claudecode_agent.py` CLI | ✅ Works standalone |
| `CodingWorkerAdapter.use_claudecode = True` | ✅ Default enabled |
| `ilma_coding_worker_adapter._call_model()` | ✅ Uses parallel agent when invoked directly |
| `_phase_delegate()` in `ilma_workflow_ecc.py` | ❌ Uses `SubAgentRouter` directly (single model) |

---

## Gap Location

`ilma_workflow_ecc.py` lines 973-982 (`_phase_delegate`):
```python
from ilma_subagent_router import get_router, close_router
router = get_router()
subagent_result = router.route_and_execute(...)  # Single model, NO parallel
```

The parallel agent is ONLY used when `CodingWorkerAdapter._call_model()` is invoked directly (e.g., in `scripts/run_phase_4c_l1_retry.py`), NOT in the main workflow.

---

## Required to Make Automatic (2 Changes)

1. **In `_phase_delegate()`**: Replace `SubAgentRouter` call with `CodingWorkerAdapter` when task is coding-related
2. **Add task type detection**: If `task_category` in `("coding", "heavy_coding", "medium_coding")`, use parallel agent

---

## Risk Assessment

- **Free models only**: Parallel agent uses NVIDIA/OpenRouter/Blackbox free tiers — respects `allow_paid=False`
- **Health tracking bypassed**: `execute_parallel()` doesn't use `SubAgentRouter`'s circuit breaker / health tracking
- **Kanban fan-out still uses SubAgentRouter**: The fan-out path (lines 923-955) also bypasses parallel agent

---

## Evidence IDs
- `ILMA-EVID-20261116-CLAUDECODE-AUTO-001` — Parallel coding agent exists but not wired into DELEGATE phase

---

## Related Files
- `ilma_claudecode_agent.py` — Parallel coding agent (Phase 71)
- `ilma_coding_worker_adapter.py` — Coding worker with `use_claudecode=True`
- `ilma_workflow_ecc.py` — `_phase_delegate()` uses SubAgentRouter directly