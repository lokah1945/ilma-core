# 2026-06-01: Autonomous Runtime Integration
**Commit:** 0280f9c — "AUTONOMOUS LOOP + KANBAN INTEGRATION"

## What Changed

Prior to this update, ILMA was **reactive** — waited for explicit commands. Components existed but weren't wired into task execution pipeline:

| Komponen | Before | After |
|----------|--------|-------|
| `ILMAKanban` | Only during `--status` | Auto-wired for MEDIUM/COMPLEX tasks in `run_capability_workflow()` |
| `SubAgentRouter` | Not used in task execution | Used in `_phase_delegate()` with `allow_paid=False` |
| `AutonomousLoopEngine` | Only via cron daemon | In-process trigger in `run_capability_workflow()` |
| DELEGATE phase | Did not exist | Added to all build/fix/audit workflows |

## New Execution Flow

```
USER TASK → ilma.py → analyze_4w1h() ──── complexity detection
     ├─ MEDIUM/COMPLEX → ILMAKanban.auto_wire() → create task + START comment
     ├─ run_capability_workflow()
     │    └─ execute_phase(DELEGATE) → _phase_delegate()
     │         ├─ targets > 1 + complexity MEDIUM/COMPLEX → ILMAKanban.fan_out()
     │         │    └─ SubAgentRouter.route_and_execute(allow_paid=False)
     │         ├─ single target → SubAgentRouter.route_and_execute(allow_paid=False)
     │         └─ fallback → direct ILMABridgeRouter
     ├─ AutonomousLoopEngine (in-process)
     │    └─ COMPLEX: full loop_engine.run_cycle()
     │    └─ MEDIUM: lightweight event recording
     └─ ILMAKanban.close() → complete() or block()
```

## DELEGATE Phase

Added to workflow_ecc.py at ~line 804:

```python
def _phase_delegate(task: str, state: ECCIntegrationState) -> dict:
    targets = _extract_targets(state)
    complexity = state.complexity
    use_fan_out = len(targets) > 1 and complexity in ("MEDIUM", "COMPLEX")
    if use_fan_out:
        parent_id, child_ids = kanban.fan_out(targets=targets, ...)
        for target in targets:
            subagent_result = SubAgentRouter.route_and_execute(
                message=target_instruction, task_type_or_desc=task_type,
                thinking="off", allow_paid=False, stateless=True,
            )
    else:
        result = SubAgentRouter.route_and_execute(..., allow_paid=False)
        # Fallback: if all subagents fail → direct ILMABridgeRouter
```

Workflows with DELEGATE: simple_build, medium_build, complex_build, audit.

## FREE_MODEL_ONLY Policy

All subagent calls: `allow_paid=False` by default.
- Routes to free-tier: NVIDIA NIM, MiniMax, OpenRouter free
- Health-aware circuit breaker: 3 consecutive failures → excluded
- Paid only if Bos explicitly says "bayar" or "paid"

## Files Modified

- `ilma_workflow_ecc.py` — `_phase_delegate()` + DELEGATE phase wiring
- `ilma.py` — `run_capability_workflow()` with kanban + autonomous loop integration

## Key Lesson

**Components existing ≠ runtime wired.** ILMA had all parts (kanban, subagent router, autonomous loop engine) but they only ran during diagnostics/cron, not during actual task execution. The gap: `ilma.py` was calling `route_task()` directly without going through workflow decomposition. Fix: wire DELEGATE phase + in-process autonomous trigger into `run_capability_workflow()`.
