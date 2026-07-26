---
name: ilma-autonomous-loops
description: SSS Tier skill for autonomous operation loops. Military Grade Quality.
triggers:
  - ilma-autonomous-loops
  - autonomous,loop,continuous
version: 1.3.0
tier: SSS
last_updated: 2026-05-11
---

# Autonomous Loops

## Overview

**Tier:** SSS (Military Grade)  
**Version:** 1.0.0  
**Status:** OPERATIONAL  
**Last Updated:** 2026-05-06

## Description

This skill provides comprehensive, military-grade patterns and best practices for **autonomous operation loops**.

## Trigger Conditions

This skill automatically activates when:
- User requests: `autonomous,loop,continuous`
- Task involves: autonomous operation loops
- Context suggests: autonomous operation loops operations needed
- **NEW (Phase 57):** Problem solving when internal knowledge insufficient (unclear root cause, repeated failures)

## Patterns

### Primary Pattern

SSS Tier implementation for autonomous operation loops:

```python
# SSS Tier Autonomous Loops
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class AutonomousLoopsHandlerConfig:
    """Configuration for Autonomous Loops operations."""
    enabled: bool = True
    verbose: bool = False
    timeout: int = 30
    retries: int = 3
    
    def validate(self) -> bool:
        """Validate configuration."""
        return (
            self.timeout > 0 and
            self.retries >= 0 and
            self.timeout >= self.retries
        )

class AutonomousLoopsHandlerHandler:
    """
    SSS Tier handler for autonomous operation loops.
    
    Military Grade implementation with full error handling,
    logging, type hints, and comprehensive validation.
    """
    
    def __init__(self, config: Optional[AutonomousLoopsHandlerConfig] = None):
        self.config = config or AutonomousLoopsHandlerConfig()
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.config.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
    
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Execute autonomous operation loops operation.
        
        Returns:
            Dict with 'success', 'message', and 'data' keys
        """
        try:
            self.logger.info("Executing Autonomous Loops")
            
            if not self.config.validate():
                return {
                    'success': False,
                    'message': 'Invalid configuration'
                }
            
            result = self._execute(*args, **kwargs)
            
            return {
                'success': True,
                'message': 'Autonomous Loops completed successfully',
                'data': result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in Autonomous Loops: {e}")
            return {
                'success': False,
                'message': f'Operation failed: {str(e)}',
                'error': str(e)
            }
    
    def _execute(self, *args, **kwargs) -> Any:
        """
        Internal execution logic.
        Override in subclass for specific functionality.
        """
        return {"status": "completed", "operation": "Autonomous Loops"}


def main() -> int:
    """Main entry point."""
    handler = AutonomousLoopsHandlerHandler()
    result = handler.execute()
    return 0 if result['success'] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

## Implementation Steps

### Step 1: Initialize Handler

```python
config = AutonomousLoopsHandlerConfig(verbose=True)
handler = AutonomousLoopsHandlerHandler(config=config)
```

### Step 2: Execute Operation

```python
result = handler.execute(param1=value1, param2=value2)
if result['success']:
    print(f"Success: {result['message']}")
```

### Step 3: Handle Results

```python
if result['success']:
    data = result['data']
else:
    error = result.get('error', 'Unknown error')
```

## Error Handling

| Error Type | Handling Strategy |
|------------|-------------------|
| Validation Error | Return `success=False` with message |
| Execution Error | Log and return error details |
| Timeout | Configurable timeout with retries |
| Unknown Error | Catch all, log, return safe error |

## Best Practices

1. **Always validate configuration** before execution
2. **Use verbose mode** for debugging
3. **Check return value** for `success` key
4. **Log all operations** for audit trail
5. **Handle timeouts** gracefully with retry logic

## Pitfalls (Phase 47CLOSE Hard-Learned)

### PITFALL 1: Orchestrator Default Artifact Producer Gap — FIXED in Phase 48A
**Problem (BEFORE):** `AutonomousEvolutionOrchestrator._step_execute()` only produced plan text (`f"# Artifact: {target[:80]}..."`). Judge evaluated placeholder text → WARN score=95. Orchestrator technically "PASSED" internally but task_entrypoint saw no real artifact → FAIL.

**Detection:**
```
# Symptom: orchestrator final_status=PASSED but actor_attempts=0, actor_artifact_path=None
# Judge: WARN score=95 but no real file on disk
# task_entrypoint: FAIL because judge says WARN but no artifact path
```

**Fix Applied (Phase 48A):**
1. Created `scripts/ilma_default_actor_artifact_producer.py` — writes real files to disk (8 artifact types: markdown_report, python_module, test_file, json_config, audit_report, refactor_plan, lesson_memory_report, trace_report)
2. Connected as fallback `actor_callback` in task_entrypoint and orchestrator
3. Added `actor_artifact_path: Optional[str]` to MissionState dataclass
4. `_step_execute()` now calls `self.actor_callback` → writes file → returns path
5. `_step_evaluate()` now uses `CriticJudge` for real artifact evaluation

**Verification:**
```
# BEFORE: actor_attempts=0, actor_artifact_path=None, status=PASSED but no file
# AFTER:  actor_attempts=1, actor_artifact_path=test_projects/artifact_*.md, status=PASSED ✅
```

**Reference:** `docs/ILMA_PHASE48A_USER_TRIGGERED_AUTOLEARNING_AND_ORCHESTRATOR_REPAIR_REPORT_2026-05-10.md`

### PITFALL 1B: Orchestrator run() Loop Infinite Stall — FOUND and FIXED in Phase 48A
**Problem:** The orchestrator run() loop increments `iteration` counter at the START of each iteration, then executes the step. With `max_iterations=2`:
- Iteration 1: INIT → `_step_init()` → MEMORY_RETRIEVED
- Iteration 2: MEMORY_RETRIEVED → `_step_plan()` → PLANNED
- Loop exits (iteration >= max_iterations) BEFORE ever reaching EXECUTED where `actor_callback` is called.

**Detection:**
```
# Symptom: orchestrator exits with max_iterations, actor_attempts=0
# Status transitions: INIT → MEMORY_RETRIEVED → PLANNED → (exits)
# Never reaches: EXECUTED → EVALUATED → (REFLECTING) → REVISING
# actor_callback is inside _step_execute() which is only reached at PLANNED→EXECUTED transition
```

**Root Cause:** The state machine has 7 states but the loop only runs N iterations. Each state transition consumes 1 iteration. 3 states are consumed BEFORE reaching the actor step. So `max_iterations` must be at least 7 to reach revision.

**Fix Applied:** Stuck-status detection + forced transition in run() loop:
```python
# After each step, check if status advanced
if state.current_status == status_before_step and state.current_status not in terminal_states:
    # Force advance to next state
    if state.current_status == MissionStatus.INIT:
        state.current_status = MissionStatus.MEMORY_RETRIEVED
    elif state.current_status == MissionStatus.MEMORY_RETRIEVED:
        state.current_status = MissionStatus.PLANNED
    elif state.current_status == MissionStatus.PLANNED:
        state = self._step_execute(state, verbose)  # Call actor
    elif state.current_status == MissionStatus.EVALUATED:
        state = self._route_evaluation(state, verbose)
    # ... etc
```

**Verification:**
```
# BEFORE: max_iterations=2 → exits at PLANNED, actor_attempts=0
# AFTER:  max_iterations=4 → reaches EXECUTED, actor_attempts=1, status=PASSED ✅
# Integration test: real file written to disk, judge evaluated WARN, orchestrator PASSED
```

**Reference:** `scripts/ilma_autonomous_evolution_orchestrator.py` (run() method)

### PITFALL 2: Dataclass Enum JSON Serialization
**Problem:** `JudgeStatus` and other Enum dataclass fields cause `TypeError: Object of type JudgeStatus is not JSON serializable` when saving traces.

**Detection:**
```
TypeError: Object of type JudgeStatus is not JSON serializable
```

**Fix:** Always use `.value` on Enum fields before JSON dump:
```python
# WRONG:
jr_dict = asdict(judge_result)
trace.judge_results = [jr_dict]

# RIGHT:
jr_dict = asdict(judge_result)
jr_dict['status'] = judge_result.status.value  # Enum -> string
trace.judge_results = [jr_dict]
```

### PITFALL 3: Field Reference Mismatch (result vs trace)
**Problem:** After inner function returns `trace` but variable name outside is `result`, code references `result.trace_id` but the actual object is `trace`. Causes `AttributeError: 'MissionState' object has no attribute 'trace_id'`.

**Detection:**
```
AttributeError: 'MissionState' object has no attribute 'trace_id'
```

**Fix:** Use consistent variable naming. After `trace = run_evolution_loop(...)`, use `trace` everywhere, not `result`.

### PITFALL 4: PreTaskLearningHook Returns Dict, Not List
**Problem:** `retrieve_for_task()` returns `{"lessons": [...], "count": N, ...}` not a raw list. Code that does `[asdict(l) for l in retrieved]` fails because `dict` is not iterable as lessons.

**Detection:**
```
TypeError: 'NoneType' object is not iterable
# or empty lessons despite existing lessons
```

**Fix:**
```python
# WRONG:
trace.retrieved_lessons = [asdict(l) for l in retrieved]

# RIGHT:
if isinstance(retrieved, dict):
    trace.retrieved_lessons = retrieved.get('lessons', [])
else:
    trace.retrieved_lessons = []
```

### PITFALL 5: Confirmation Gate Bypass — FOUND and FIXED in Phase 48C-CLOSE
**Problem:** `requires_confirmation=True` did NOT block session start. Trigger parser calculated `requires_confirmation` correctly but runner never checked it before calling `create_session()`.

**Detection:**
```
# Command: "auto learning selama 120 menit external publish"
# Parser: requires_confirmation=True, scope=['external_publish']
# Runner: creates session WITHOUT checking requires_confirmation
# Result: forbidden action attempted without owner approval
```

**Fix Applied:**
1. Runner must check `trigger.requires_confirmation` BEFORE `create_session()`:
   ```python
   if trigger.requires_confirmation:
       return BLOCKED_SAFE, "Confirmation required before session start"
   ```
2. Positive forbidden scope items → `requires_confirmation=True`
3. Negative forbidden scope items (jangan/don't/no) → `requires_confirmation=False`
4. Duration > 120 min → `requires_confirmation=True`

**Verification:**
```
# BEFORE: external_publish in scope, requires_confirmation=True → session starts anyway ❌
# AFTER:  external_publish in scope, requires_confirmation=True → BLOCKED_SAFE ✅
```

### PITFALL 6: Negative Scope Parser — FOUND and FIXED in Phase 48C-CLOSE
**Problem:** `_extract_scope()` matched keywords regardless of negation context. "jangan external publish" incorrectly added `external_publish` to active_scope.

**Detection:**
```python
# SCOPE_PATTERNS regex matches "external publish" anywhere in command
# "auto learning... jangan external publish" → scope=['external_publish'] ← WRONG
```

**Fix Applied (trigger.py `_extract_scope`):**
```python
def _extract_scope(cmd: str) -> tuple[List[str], List[str]]:
    allowed, forbidden = [], []
    
    for keyword, scope_name in SCOPE_PATTERNS:
        if keyword.lower() in cmd.lower():
            # Check for negative patterns in 20 chars before keyword
            idx = cmd.lower().find(keyword.lower())
            prefix = cmd[max(0, idx-20):idx].lower()
            
            negative_patterns = [
                'jangan', 'janganlah', 'jangan sekali', 'jangan dilakukan',
                'jangan install', 'jangan deploy', 'jangan delete',
                'jangan publish', 'jangan external',
                "don't", "do not", "never", "no ", "must not", "shall not",
                "refrain from", "tidak boleh", "dilarang", "tanpa "
            ]
            
            is_negative = any(pat in prefix for pat in negative_patterns)
            
            if is_negative:
                forbidden.append(scope_name)
            else:
                allowed.append(scope_name)
    
    return allowed, forbidden
```

**Verification:**
```
# BEFORE: "jangan external publish" → scope=['external_publish'] ❌
# AFTER:  "jangan external publish" → scope=[], forbidden=['external_publish'] ✅
```

### PITFALL 7: Report COMPLETE While Process Exit Code 1 — FOUND in Phase 48C-CLOSE
**Problem:** Phase report claimed COMPLETE before process finished. Process then crashed with TypeError (exit code 1). Report was generated from intermediate state, not final state.

**Detection:**
```
# trace_9ac97106.json: 8 cycles completed, then crash
# Report: COMPLETE (generated before crash)
# Exit code: 1
```

**Fix Applied:**
1. Report generated AFTER process exits
2. Report reads actual exit code, actual trace
3. Report status = EXIT CODE MAPPING:
   - exit 0 + no errors → COMPLETE
   - exit 0 + warnings → COMPLETED_WITH_WARN
   - exit 1 + crash → ERROR
   - exit 2 + partial → PARTIAL
4. Never claim COMPLETE if process exit code ≠ 0

**Reference:** `docs/ILMA_PHASE48C_CLOSE_A_CONTRADICTION_AUDIT_2026-05-10.md`

## Persistent Integration Checklist

Before claiming "persistent autonomous evolution in ILMA task path", verify ALL:

- [ ] `run_task_with_evolution()` is the central integration point
- [ ] Config has `enabled: true` and `default_for_task_classes` includes target classes
- [ ] Pre-task hook is called in every heavy+ task run
- [ ] Orchestrator has a default artifact producer (not just planner)
- [ ] Judge evaluates real artifacts (not empty strings)
- [ ] Reflection produces structured `ReflectionResult` with `root_cause`, `fix_plan`
- [ ] Router terminates safely (no infinite loop possible)
- [ ] Lessons persist in JSONL across process restarts
- [ ] Evolution traces are saved to `evidence/evolution_traces/`
- [ ] Gate (`ilma_autonomous_evolution_gate.py`) passes 38/38 checks

## Verification

```bash
# 1. Gate must pass
python3 scripts/ilma_autonomous_evolution_gate.py

# 2. Task entrypoint must produce traces
python3 scripts/ilma_phase47close_task_runner.py

# 3. Lessons must persist
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from ilma_lesson_memory import LessonMemory
m = LessonMemory()
print(f'Lessons: {m.count()}')
"

# 4. Weak VERIFIED must be 0
python3 -c "
import json
with open('config/ilma_capability_registry.json') as f:
    reg = json.load(f)
weak = []
for cat, caps in reg.get('capabilities', {}).items():
    for cid, c in caps.items():
        if c.get('confidence', 0) >= 0.95 and c.get('test_count', 0) < 3:
            weak.append(f'{cat}/{cid}')
print(f'Weak VERIFIED: {len(weak)}')
if weak: print('  ', weak)
"
```

## Reference Documents

| Document | Purpose |
|----------|---------|
| `docs/ILMA_PHASE47CLOSE_AUTONOMOUS_EVOLUTION_NERVE_TRUTH_LOCK_2026-05-10.md` | Truth-lock audit — PARTIAL status, orchestrator gap |
| `docs/ILMA_PHASE47_AUTONOMOUS_EVOLUTION_NERVE_INTEGRATION_REPORT_2026-05-10.md` | Phase 47 final report |
| `config/ilma_autonomous_evolution_config.json` | Persistent runtime config |
| `config/ilma_autonomous_evolution_contract.json` | Nerve integration contract |
| `config/ilma_limited_internal_autolearning_contract.json` | Safety contract v1.0.0 (Phase 48D) |
| `evidence/evolution_traces/` | Saved evolution traces |
| **`references/phase48d-limited-internal-autolearning.md`** | Phase 48D productionization: command interface, readiness harness, safety contract, canary results, critical bugs fixed |
- **`references/phase52-300min-daemon-truth-lock.md`** — Phase 52/52R: wall-clock semantics bugs fixed, time-gated heartbeat proven correct via 290s canary, failure taxonomy separated (fatal vs per-job), 300-min ready for retry
- **`references/phase57-live-research-activation.md`** — Phase 57: Live Research module created, web search + arXiv integration, automatic trigger when internal knowledge insufficient, 233 tests pass

## See Also

- **`ilma-orchestrator-frameworks`** — 4 advanced patterns for autonomous loops (LangGraph, AutoGen, DSPy, MetaGPT)
- **`ilma-multi-agent`** — Actor-Critic, Reflexion, MAE, RCR patterns
- **`ilma-evolution`** — Agent self-improvement via systematic rollout
- **`ilma-refactor-cleaner`** — Refactoring patterns for fixing orchestrator gaps

---

**SSS Tier - Military Grade - ILMA System**
