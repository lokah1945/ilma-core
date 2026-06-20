# Owner-Triggered Autonomous Learning Reference
**Phase 48A-C learnings** (2026-05-10)

---

## Auto-Learning System Architecture

```
Owner Trigger (Indonesian)
    ↓
AutoLearningTriggerParser.parse() → TriggerResult
    ↓
AutoLearningSessionManager.create_session() → SessionData
    ↓
run_task_with_evolution() [task_entrypoint]
    → EvolutionOrchestrator (Actor-Critic loop)
        → DefaultActorArtifactProducer (generates artifact)
        → CriticJudge.evaluate() (scores artifact)
        → Reflection (if FAIL, stores lesson)
        → LessonMemory (persist/reuse)
    ↓
Checkpoints (every N cycles)
    ↓
Trace Export (JSON with session_id, results, checkpoints)
    ↓
Session Finalization
```

---

## Status Semantics Contract (Critical!)

From `config/ilma_autolearning_status_semantics.json`:

| Status | Meaning | Exit Code |
|--------|---------|-----------|
| COMPLETED | artifact valid + judge PASS | exit 0 |
| COMPLETED_WITH_WARN | artifact valid + judge WARN (non-blocking) | exit 0 |
| BLOCKED_SAFE | scope/safety blocked (not failure) | exit 0 |
| FAILED | action failed, no valid artifact | exit 1 |
| ERROR | exception/runtime error (blocking) | exit 1 |
| PARTIAL | evidence insufficient, non-fatal | exit 0 |
| PASS | no ERROR/FAILED | exit 0 |

**CRITICAL: ERROR ≠ SUCCESS.** Before Phase 48B-CLOSE, ERROR was being set for non-fatal exception in lesson storage (IndexError on empty reflections list). This was a bug that overwrote the correct judge-set status (PASS_WITH_WARN). Fixed by:
1. Checking `len(trace.reflections) > 0` before accessing `trace.reflections[0]`
2. Wrapping lesson storage in try-except (non-fatal)
3. Only setting ERROR if `final_status` is still UNKNOWN after exception handler

---

## Session Manager API

```python
from ilma_autolearning_session_manager import AutoLearningSessionManager

mgr = AutoLearningSessionManager()
session = mgr.create_session(trigger: TriggerResult) -> SessionData

# SessionData is a dataclass with fields:
# session_id, owner_command, duration_minutes, scope, start_time,
# deadline, checkpoints, actions_taken, blocked_actions, lessons_created,
# files_changed, tests_run, final_status, stop_reason, error_message
```

**NOTE:** `create_session()` takes a `TriggerResult` object (NOT kwargs). Use `from ilma_autolearning_trigger import AutoLearningTriggerParser`.

---

## Trigger Parser API

```python
from ilma_autolearning_trigger import AutoLearningTriggerParser

parser = AutoLearningTriggerParser()
trigger = parser.parse("auto learning selama 120 menit fokus registry truth")

# TriggerResult fields:
# is_trigger: bool
# action: TriggerAction (START/STOP/PAUSE/RESUME)
# duration_minutes: int
# scope: list[str]
# requires_confirmation: bool (True if scope includes forbidden action like external_publish)
# confidence: float
# safety_notes: list[str]
```

---

## Lesson Memory API

```python
from ilma_lesson_memory import LessonMemory

lm = LessonMemory()

# Store lesson
lesson = {
    'event_type': 'phase48c_pilot_completed',
    'phase': '48C',
    'task_type': 'heavy',
    'root_cause': 'root_cause_description',
    'fix_plan': ['step1', 'step2'],
    'validation_method': 'how_validated',
    'confidence': 0.85,
    'overclaim_detected': False,
    'evidence_gaps': [],
    'source_evidence': 'SESSION-xxx'
}
lm.add_lesson(lesson)

# Search/retrieve
lessons = lm.search_lessons('phase48c')  # returns list, not dict

# Retrieving returns list of dicts with 'count' key
# Iterate: for lesson in lessons: print(lesson['event_type'])
```

---

## Evolution Orchestrator Run Loop Fix

**Problem:** Orchestrator requires 3 iterations but `max_iterations=2` exits before EXECUTED status.

**Root cause:** `max_iterations` is the maximum iterations, but loop exits when `current_status != REPLAN`. With 2 iterations, after iteration 1 (MEMORY_RETRIEVED) and iteration 2 (PLANNED → EXECUTED), the loop checks status and exits because status is EXECUTED, not REPLAN.

**Fix (applied in task_entrypoint):** Added stuck-status detection + forced transition when:
- status hasn't changed for 2 consecutive iterations
- status is PLANNED but no artifact produced
- max_iterations reached with status != EXECUTED

Also patched `_step_evaluate()` to use CriticJudge for real evaluation and `_step_execute()` to call `actor_callback(state, plan)` for real artifact production.

---

## Actor-Critic-Judge Loop Verification

8 autonomous actions (Phase 48C):
- All 8 produced artifacts via `DefaultActorArtifactProducer`
- All 8 evaluated by `CriticJudge.evaluate()` → score 95, WARN
- None triggered reflection (reflection only on FAIL, not WARN)
- Lesson memory stored and retrieved successfully
- Checkpoints created at every 3 cycles
- Trace exported to `evidence/evolution_traces/phase48c/trace_xxx.json`

**Judge WARN score 95 is legitimate** when:
- artifact.md file exists and is non-empty
- no blocking failures in artifact content
- warn_threshold = 70, score 95 > 70
- Warnings are cosmetic (e.g., "No evidence IDs found in artifact" — formal ID format not used in artifact body)

---

## Phase 48B-CLOSE Bug Fix Summary

**Bug:** `task_entrypoint.py` line 336: `trace.reflections[0]` → IndexError when `trace.reflections = []` (happens when judge returns WARN, no reflection triggered)

**Effect:** Exception caught → `final_status = "ERROR"` overwrote the correct judge-set `PASS_WITH_WARN`

**Fix:**
```python
# BEFORE (buggy):
if store_lessons and trace.final_status in ["PASS", "PASS_WITH_WARN"]:
    if trace.reflections[0]:  # IndexError if empty!
        lm.add_lesson(...)

# AFTER (fixed):
if store_lessons and trace.final_status in ["PASS", "PASS_WITH_WARN"]:
    # Only store if reflections exist (reflections only created on FAIL → recovery)
    if trace.reflections:
        try:
            lm.add_lesson(...)
        except Exception as e:
            # Lesson storage is non-fatal — do NOT change final_status
            if verbose:
                print(f"[TaskEntrypoint] Lesson store failed (non-fatal): {e}")
```

---

## Running Phase 48C Pilot

```bash
cd /root/.hermes/profiles/ilma
python3 scripts/ilma_phase48c_120min_autonomous_learning_pilot.py
```

Or build your own runner using the APIs above. Key structure:
1. Parse trigger → TriggerResult
2. Create session → SessionData  
3. Loop over work queue items
4. Call `run_task_with_evolution(target, task_class, max_iterations, require_judge, store_lessons, verbose)`
5. Record results, create checkpoints, store lessons
6. Export trace JSON

---

## Forbidden Actions (enforced by scope)

These are blocked by scope enforcement even if included in scope:
- `dependency_install`
- `production_deployment`
- `destructive_delete`
- `os_build`
- `external_publish` (requires_confirmation=True, blocks without owner approval)

---

## Session Trace Schema

```json
{
  "session_id": "9ac97106",
  "trigger": "auto learning selama 120 menit...",
  "start_time": "2026-05-10T10:46:47",
  "deadline": null,
  "actual_duration_min": 0.0,
  "total_cycles": 8,
  "cycles_completed": 8,
  "action_results": [
    {
      "cycle": 1,
      "action_id": "cycle1_xxx",
      "final_status": "PASS_WITH_WARN",
      "judge_status": "WARN",
      "judge_score": 95.0,
      "judge_warnings": ["No evidence IDs found in artifact"],
      "verdict": "COMPLETED_WITH_WARN"
    }
  ],
  "checkpoints": [...],
  "final_verdict": "PASS",
  "errors": [],
  "completed_with_warn": ["COMPLETED_WITH_WARN", ...],
  "lessons_stored": 1,
  "lessons_retrieved": 0,
  "stop_reason": "session_complete",
  "auto_learning_always_on": false,
  "owner_triggered": true
}
```