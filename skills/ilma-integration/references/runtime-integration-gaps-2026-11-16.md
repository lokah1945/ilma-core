# Runtime Integration Gaps (Session 2026-11-16)

## Summary
Two major integration points are **boot-time only** — not used during actual task execution.

---

## 1. External Skills Bridge → NOT auto-invoked at runtime

### What Works (Boot)
- `ilma.py` loads bridge at startup (line 294-306)
- `extend_capability_registry_with_external()` registers 3,378 capabilities in-memory
- `ilma_runtime_wiring.py` wires module in LAYER_2_EXECUTION

### What Doesn't Work (Runtime)
| Function | Where It Should Be Called |
|----------|---------------------------|
| `find_external_skills_for_task()` | `route_task()` after skill detection (~line 470) |
| `load_external_skill_content()` | When external capability selected as fallback |
| `external_skill:<id>` tool execution | No handler exists for this primary_tool |

### Current Flow
```
Boot: load bridge → extend registry (3,378 caps) ✅
     ↓
Task: route_task() → capability registry → is_capable() ✅ (sees external caps)
     ↓
     → get_fallback() → returns None (no fallback_tools populated) ❌
     → skill_router (Hermes only) → NO external skill auto-detection ❌
     → workflow executes WITHOUT external skills ❌
```

### Required to Make Automatic (4 changes)
1. In `route_task()`: call `find_external_skills_for_task()` and merge into `skill_matches`
2. In `get_fallback()`: populate `fallback_tools` with `external_skill:<id>` for external caps
3. Add tool handler: `external_skill:<id>` → call `load_external_skill_content()` + execute skill
4. Risk gating: critical-risk external skills need approval (already tracked via `needs_approval()`)

### Risk
- 3,378 capabilities registered but unused — memory overhead (~50MB) for zero runtime value
- Critical-risk skills (1,494) registered as `PROVISIONAL` — no auto-approval gate in workflow
- No persistence — re-registered every boot (slow startup: +150ms)

---

## 2. Parallel Coding Agent (ilma_claudecode_agent) → NOT wired into DELEGATE phase

### What Works
- `ilma_claudecode_agent.py` CLI works standalone (3 models in parallel: NVIDIA → OpenRouter → Blackbox)
- `CodingWorkerAdapter.use_claudecode = True` default enabled
- `_call_model()` in adapter uses parallel agent when invoked directly

### What Doesn't Work (Runtime)
| Component | Used in Workflow? |
|-----------|-------------------|
| `ilma_claudecode_agent.execute_parallel()` | ❌ Only in `CodingWorkerAdapter._call_model()` |
| `CodingWorkerAdapter` | ❌ Not wired into `_phase_delegate()` |
| `SubAgentRouter` | ✅ Used directly in `_phase_delegate()` (single model) |

### Gap Location
`ilma_workflow_ecc.py` lines 973-982 (`_phase_delegate`):
```python
from ilma_subagent_router import get_router, close_router
router = get_router()
subagent_result = router.route_and_execute(...)  # Single model, NO parallel
```

### Required to Make Automatic (2 changes)
1. In `_phase_delegate()`: Replace `SubAgentRouter` call with `CodingWorkerAdapter` when task is coding-related
2. Add task type detection: If `task_category` in `("coding", "heavy_coding", "medium_coding")`, use parallel agent

### Risk
- Free models only: Parallel agent uses NVIDIA/OpenRouter/Blackbox free tiers — respects `allow_paid=False`
- Health tracking bypassed: `execute_parallel()` doesn't use `SubAgentRouter`'s circuit breaker / health tracking
- Kanban fan-out still uses SubAgentRouter: The fan-out path (lines 923-955) also bypasses parallel agent

---

## Evidence IDs
- `ILMA-EVID-20261116-EXT-SKILLS-AUTO-001` — External skills bridge loaded at boot but not auto-invoked
- `ILMA-EVID-20261116-CLAUDECODE-AUTO-001` — Parallel coding agent exists but not wired into DELEGATE phase
- `ILMA-EVID-20261116-SKILL-ID-FIX-001` — Fixed skill ID extraction: `path.split('/')[-2]` instead of `[-1]`

---

## Related Files
- `ilma_external_skills_bridge.py` — Bridge implementation (FIXED: line 122)
- `ilma_claudecode_agent.py` — Parallel coding agent (Phase 71)
- `ilma_coding_worker_adapter.py` — Coding worker with `use_claudecode=True`
- `ilma_workflow_ecc.py` — `_phase_delegate()` uses SubAgentRouter directly
- `ilma.py` — `route_task()` boot integration only