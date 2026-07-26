# Real-Time Canary Pattern Reference

**Created:** 2026-05-10
**Phase:** Phase 48H, 49I, 50
**Status:** PROVEN (5-min ×3, 30-min ×1)

---

## Overview

Real-time canary = execute a bounded task for N minutes measuring actual wall-clock via `time.monotonic()`. The canary proves:
1. ILMA can sustain autonomous operation for N minutes
2. All agent body components work together under real-time pressure
3. Trace, checkpoint, heartbeat systems function correctly
4. No memory leaks, no runaway loops, no always-on behavior

---

## Wall-Clock Measurement (CRITICAL)

Always use `time.monotonic()` for wall-clock measurement. NEVER use `time.time()` (can jump backward on NTP sync).

```python
import time

wall_clock_start = time.monotonic()
# ... run task ...
wall_clock_end = time.monotonic()
wall_clock_seconds = wall_clock_end - wall_clock_start

if wall_clock_seconds < REQUIRED_DURATION:
    print(f"❌ FAILED: {wall_clock_seconds:.2f}s < {REQUIRED_DURATION}s")
    sys.exit(1)
else:
    print(f"✅ PASSED: {wall_clock_seconds:.2f}s >= {REQUIRED_DURATION}s")
```

---

## Can Run Modes

### Full Real-Time (actual wall-clock):

```bash
cd /root/.hermes/profiles/ilma
python3 scripts/ilma_phaseXX_realtime_Nmin_canary.py
# Block for N minutes, exit code 0 = success
```

### Background (non-blocking):

```bash
cd /root/.hermes/profiles/ilma
# Start in background
python3 scripts/ilma_phaseXX_realtime_Nmin_canary.py > /tmp/canary_output.txt 2>&1

# Poll for progress
cat /tmp/canary_output.txt

# Poll for completion
# Process exits when wall-clock >= REQUIRED_DURATION
```

When using background=true + notify_on_complete=true:
```
terminal(background=true, notify_on_complete=true)
→ poll(session_id, action="poll") to check status
→ process exits when complete
```

### Accelerated (development/testing only — CANNOT claim canary passed):

Modify `MIN_DURATION_SECONDS` in script to 60-300 for quick integration check. This does NOT prove real-time capability.

---

## Canary Runner Template

```python
#!/usr/bin/env python3
"""
ILMA Phase XX: Real-Time N-Minute Canary Runner
"""
import time
import sys
import json
import os

MIN_DURATION_SECONDS = N * 60  # N minutes
HEARTBEAT_INTERVAL = 60  # seconds
CHECKPOINT_INTERVAL = 600  # 10 minutes
MIN_CYCLES = 3
REQUIRED_GATES = ["wall_clock", "exit_code", "heartbeats", "checkpoints", "cycles"]

class CanaryRunner:
    def __init__(self):
        self.wall_clock_start = time.monotonic()
        self.heartbeats = []
        self.checkpoints = []
        self.cycles = []
        self.gates_passed = {}
        
    def run(self):
        # 1. Load components
        self._load_components()
        
        # 2. Safety check
        if not self._safety_check():
            return self._fail("safety", "Safety check failed")
        
        # 3. Run cycles
        while True:
            elapsed = time.monotonic() - self.wall_clock_start
            cycle_data = self._run_cycle()
            self.cycles.append(cycle_data)
            
            # Heartbeat
            self._heartbeat(elapsed)
            
            # Checkpoint
            if len(self.checkpoints) < 3 and elapsed >= len(self.checkpoints) * CHECKPOINT_INTERVAL:
                self._checkpoint(elapsed)
            
            # Exit if minimum duration met
            if elapsed >= MIN_DURATION_SECONDS:
                break
        
        return self._evaluate_gates()
    
    def _load_components(self):
        """Load runtime router, tool/skill selector, lesson memory, judge."""
        # CRITICAL BUG: RoutingDecision is namedtuple, NOT dict
        # Use getattr(rd, 'field') not rd.get('field')
        pass
    
    def _run_cycle(self):
        """Run one optimization cycle: router → selector → retrieval → artifact → judge."""
        pass
    
    def _safety_check(self):
        """Verify no forbidden scope in run."""
        return True
    
    def _heartbeat(self, elapsed):
        """Log heartbeat every 60s."""
        self.heartbeats.append(elapsed)
        minutes = elapsed / 60
        print(f"💓 [{elapsed:.0f}s] HB#{len(self.heartbeats)}")
    
    def _checkpoint(self, elapsed):
        """Write checkpoint every 10 minutes."""
        cp = {
            "timestamp": elapsed,
            "cycle": len(self.cycles),
            "reuse_count": sum(1 for c in self.cycles if c.get("reuse_incremented"))
        }
        self.checkpoints.append(cp)
        path = f"evidence/evolution_traces/phaseXX/checkpoint_{len(self.checkpoints)}_{int(elapsed)}s.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(cp, f)
        print(f"💾 Checkpoint #{len(self.checkpoints)} @ {elapsed:.0f}s")
    
    def _evaluate_gates(self):
        """Evaluate all gates, export trace, return exit code."""
        elapsed = time.monotonic() - self.wall_clock_start
        self.gates_passed = {
            "wall_clock": elapsed >= MIN_DURATION_SECONDS,
            "heartbeats": len(self.heartbeats) >= MIN_CYCLES,
            "checkpoints": len(self.checkpoints) >= 2,
            "cycles": len(self.cycles) >= MIN_CYCLES,
            "no_error": True
        }
        
        trace = {
            "wall_clock_seconds": elapsed,
            "exit_code": 0 if all(self.gates_passed.values()) else 1,
            "cycles": self.cycles,
            "heartbeats": self.heartbeats,
            "checkpoints": self.checkpoints,
            "gates_passed": self.gates_passed
        }
        
        path = "evidence/evolution_traces/phaseXX/final_trace.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(trace, f, indent=2)
        
        if all(self.gates_passed.values()):
            print(f"✅ ALL GATES PASSED — canary SUCCESS ({elapsed:.2f}s)")
            return 0
        else:
            print(f"❌ GATES FAILED: {self.gates_passed}")
            return 1
```

---

## Critical Integration Bugs (MUST AVOID)

### Bug 1: RoutingDecision Namedtuple

`RuntimeRouter().route()` returns `RoutingDecision` (namedtuple). Cannot use `.get()`.

```python
# ❌ WRONG
rd = router.route(task)
task_class = rd.get("task_class")  # AttributeError!

# ✅ CORRECT
rd = router.route(task)
task_class = rd.task_class.value if hasattr(rd.task_class, 'value') else str(rd.task_class)
workflow_type = getattr(rd, 'workflow', getattr(rd, 'workflow_type', 'unknown'))
```

### Bug 2: TaskClass Enum → String

`_map_task_class_to_policy_key()` receives `TaskClass.AUDIT` enum, not string.

```python
# ❌ WRONG
tc_lower = task_class.lower() if isinstance(task_class, str) else task_class.value.lower()

# ✅ CORRECT
if hasattr(task_class, 'value'):
    tc_lower = task_class.value.lower()
else:
    tc_lower = str(task_class).lower()
```

### Bug 3: LessonMemory.count_lessons() Missing

```python
# ❌ WRONG
count = self.lesson_memory.count_lessons()  # AttributeError!

# ✅ CORRECT
count = len(self.lesson_memory._read_all()) if hasattr(self.lesson_memory, '_read_all') else 0
```

### Bug 4: TargetedLessonRetrieval Import

```python
# ❌ WRONG
from ilma_enhanced_lesson_retrieval import EnhancedLessonRetrieval

# ✅ CORRECT
from ilma_enhanced_lesson_retrieval import TargetedLessonRetrieval

# Also: __init__() takes 0 args, not (lesson_memory,)
retrieval = TargetedLessonRetrieval()  # No constructor args
```

### Bug 5: TargetedLessonRetrieval.search() Missing

```python
# ❌ WRONG
results = retrieval.search(query, limit=3)  # AttributeError!

# ✅ CORRECT
results = retrieval.search_with_targeting(
    task_class=task_class,
    workflow_type=workflow_type,
    forbidden_scope=False,
    previous_failures=[],
    limit=3
)
```

---

## Lesson Query Mapping (PERSISTENT GAP)

Lesson storage uses `task_type` field (e.g., "heavy", "writing", "code", "safe", "audit") but queries built from workflow_type (e.g., "audit_workflow", "internal_audit") don't match.

**Impact:** Query returns 0 lessons even when 106 lessons exist.

**Mitigation:** Build targeted queries from task context, not workflow_type:
```python
# Instead of querying by workflow_type
query = workflow_type  # → returns 0

# Query by related task_type keywords
query = "audit evidence registry claim"  # → returns lessons
```

See also: `references/phase50-session-log.md` for Phase 50 session details.

---

## Proven Canaries

| Phase | Duration | Wall-Clock | Cycles | Heartbeats | Checkpoints | Result |
|-------|----------|------------|--------|------------|-------------|--------|
| Phase 48H | 5 min | 300.00s | 151 | 5 | 1 | ✅ PASS |
| Phase 49I | 5 min | 300.00s | 12 | 12 | 12 | ✅ PASS |
| Phase 50 | 30 min | 1800.03s | 8 | 29 | 3 | ✅ PASS |

**Next target:** Phase 51 — 300 minutes (5 hours).

---

## Claim Rules

After real-time canary:
- CAN claim: "Real-time N-minute canary passed (X.XXs wall-clock)"
- CAN claim: "Agent body integration working end-to-end"
- CANNOT claim: real-time longer than actual run
- CANNOT claim: production autonomous agent
- CANNOT claim: SSS+++ achieved
- CANNOT claim: always-on auto-learning

See `config/ilma_claim_boundary.json` for current claim boundary.