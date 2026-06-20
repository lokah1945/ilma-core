---
name: ilma-goal-tracker
description: ILMA Goal Tracker — Hermes v0.13.0 /goal Ralph Loop integration. First-class goal tracking across turns. Lock agent onto target, persistent context across conversations, milestone tracking, and goal health monitoring. SSS Tier. Auto-trigger for any task requiring multi-turn goal persistence.
trigger_conditions:
  - "long-term goal"
  - "multi-turn goal"
  - "persistent objective"
  - "goal tracking"
  - "keep on track"
  - "stay on task"
  - "target"
  - "objective"
  - "milestone"
category: autonomous
created: 2026-05-09
hermes_version: v0.13.0
source: hermes-agent /goal primitive
---

# ILMA Goal Tracker — Ralph Loop Integration

## Overview

Hermes v0.13.0 introduces `/goal` as a first-class primitive (Ralph Loop). ILMA integrates this into its DNA for multi-turn goal persistence.

**Ralph Loop concept:** Agent stays locked on target across turns, with memory of why and what.

## CLI Commands

```bash
# Set a goal (Ralph loop)
hermes goal set "Complete Phase 13D services decomposition"

/goal Complete Phase 13D services decomposition

# List active goals
hermes goal list

# Get goal status
hermes goal status <goal_id>

# Update goal progress
hermes goal update <goal_id> --progress 75 --milestone "services split into 3 domains"

# Complete goal
hermes goal complete <goal_id>

# Cancel goal
hermes goal cancel <goal_id>

# Goal history
hermes goal history
```

## ILMA DNA Integration

### DNA Rule

```
When: Any task with >2 phases or >1 session expected
Action: Use /goal to set Ralph loop
Pattern: goal set → milestone track → evidence capture → complete
```

### Goal Lifecycle in ILMA

```
1. TASK RECEIVED
   ↓
2. [goal set "TASK_NAME"] — Create Ralph loop
   ↓
3. Execute task in phases
   ↓
4. [goal update --progress X --milestone "Y"] — After each phase
   ↓
5. Evidence capture — Save milestone to evidence ledger
   ↓
6. [goal complete] — When task done
   ↓
7. Auto-evolution: Session report → DNA update
```

## Goal Definition Format

```yaml
Goal: "Complete ILMA Phase 13D services decomposition"
Criteria:
  - services/ reduced from 36 files to ≤20
  - All imports verified
  - Tests still pass
  - Documentation updated
Milestones:
  - M1: Identify domain boundaries
  - M2: Split services into subdirectories
  - M3: Update all import paths
  - M4: Run regression tests
  - M5: Update documentation
Expected Duration: 3-5 sessions
Priority: HIGH
```

## Milestone Tracking

```python
# ILMA milestone pattern
def track_milestone(goal_id: str, milestone: str, evidence: list):
    """Track milestone with evidence"""
    
    # 1. Update goal progress
    hermes_goal_update(goal_id, milestone=milestone)
    
    # 2. Capture evidence
    for e in evidence:
        add_to_evidence_ledger(
            event=f"milestone_{milestone}",
            goal_id=goal_id,
            evidence=e,
            timestamp=now()
        )
    
    # 3. Log to session
    log(f"🎯 Milestone: {milestone}")
    log(f"   Evidence: {evidence}")

# Example usage
track_milestone(
    goal_id="phase-13d-001",
    milestone="M3: services split into 3 domains",
    evidence=[
        "services/api/ created with 5 files",
        "services/data/ created with 4 files",
        "services/core/ created with 8 files"
    ]
)
```

## Goal Health Monitoring

```python
def check_goal_health(goal_id: str) -> dict:
    """Monitor goal health — detect drift, stall, or abandonment"""
    
    status = hermes_goal_status(goal_id)
    
    health = {
        "progress": status.progress,
        "days_active": status.days,
        "last_update": status.last_milestone,
        "confidence": assess_progress_validity(status)
    }
    
    if health["days_active"] > 7 and health["progress"] < 10:
        return {"status": "STALLED", "action": "flag for review"}
    
    if health["days_active"] > 14 and health["progress"] < 25:
        return {"status": "ABANDONED", "action": "suggest cancel or revamp"}
    
    return {"status": "HEALTHY", "action": "continue"}
```

## Cross-Session Goal Persistence

The Ralph loop persists across sessions:

```bash
# Session 1
/hermes goal set "Complete Phase 13D services decomposition"
# → Goal ID: phase-13d-001 created

# Session 2 (next day)
hermes goal status phase-13d-001
# → Progress: 40%, Last milestone: M2 (domain analysis done)

# Session 3
hermes goal list
# → Shows all active goals with health status
```

## ILMA Goal Template

For every complex task, ILMA creates:

```markdown
## Goal: [TASK_NAME]
- **Created:** [DATE]
- **Goal ID:** [ID]
- **Criteria:** [SUCCESS_CRITERIA]
- **Milestones:** [M1, M2, M3, ...]

### M1: [Milestone]
- Status: done|active|pending
- Evidence: [files/proofs]
- Date: [when completed]

### M2: [Milestone]
- Status: ...
```

## Integration with Other Skills

- `ilma-abstract-goal-translator` — Translates abstract goals to concrete tasks
- `ilma-autonomous-loops` — Background tracking
- `ilma-auto-evolution-engine` — Post-goal debrief
- `ilma-master-orchestrator` — Multi-agent goal coordination
- `ilma-kanban-integration` — Parallel task execution under goal

## Verification

```bash
# Check goal system health
hermes goal health

# Verify goal persistence
hermes goal list

# Test goal CLI
hermes goal set "test goal" && hermes goal list && hermes goal cancel "test goal"
```

## Pitfalls

1. **Goal creep** — Don't add milestones after starting
2. **Stale goals** — Review goals older than 7 days weekly
3. **Lost goal ID** — Always store goal ID in memory
4. **No evidence** — Each milestone needs proof
5. **Parallel goal conflicts** — Max 3 active goals simultaneously

## Status

✅ INTEGRATED (2026-05-09) — Hermes v0.13.0 /goal Ralph Loop