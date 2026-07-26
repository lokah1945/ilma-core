---
name: ilma-goals-ralph-loop
description: Hermes /goal command — first-class multi-turn goal tracking across sessions with milestone locking, progress persistence, and ralph loop patterns. SSS Tier. Upgrade from ilma-goal-tracker.
version: 2.0.0
category: workflow
platforms:
  - linux
  - macos
metadata:
  hermes:
    tags: [goals, ralph, tracking, milestones, loop]
    category: workflow
    requires:
      - goals database
      - milestone tracking
---

# ILMA Goals & Ralph Loop — First-Class Goal Tracking

## Overview

Hermes Goals is a first-class goal tracking system that persists across sessions. Unlike ad-hoc task tracking, Goals has explicit milestone locking, cross-session persistence, and natural-language status updates.

```
Goal: "Build a REST API for the inventory management system"
  ├─ Milestone 1: Design database schema [DONE]
  ├─ Milestone 2: Implement CRUD endpoints [IN PROGRESS]
  ├─ Milestone 3: Add authentication [TODO]
  └─ Milestone 4: Write tests and documentation [TODO]
```

---

## Core Concepts

### Goal
A high-level objective with:
- **Title** — what you want to achieve
- **Description** — context and requirements
- **Milestones** — discrete steps toward the goal
- **Status** — triaged, in_progress, blocked, completed, archived
- **Created/Updated** — timestamps
- **Priority** — optional (helps with triage)

### Milestone
A discrete step within a goal:
- **Title** — what needs to be done
- **Status** — locked (waiting on previous), ready (can start), in_progress, completed
- **Notes** — context, blockers, decisions
- **Locked milestones** — can't be worked on until previous milestone completes

### Ralph Loop
The `goal` subcommand for agents (inspired by Ralph from Dexter):

```
goal → plans → executes → tests → revises → goal
```

The goal subsystem keeps the agent focused on the overall objective while allowing iteration within each milestone.

---

## CLI Commands

### Creating Goals

```bash
# Create goal with inline milestones
hermes goal create "Build REST API" \
  --milestones "Design schema" "Implement endpoints" "Add auth" "Write tests"

# Create goal with description
hermes goal create "Migrate database to PostgreSQL" \
  --description "Move from SQLite to PostgreSQL for production" \
  --milestones "Dump SQLite data" "Set up PostgreSQL" "Migrate schema" "Verify data"

# Create goal with priority
hermes goal create "Critical bug fix" \
  --priority high \
  --milestones "Reproduce bug" "Find root cause" "Implement fix" "Verify"
```

### Listing Goals

```bash
hermes goal list                    # List all goals
hermes goal list --status in_progress  # Filter by status
hermes goal list --priority high     # Filter by priority
hermes goal list --assigned ilma    # Filter by assignee
```

### Goal Details

```bash
hermes goal show <goal-id>           # Show goal with milestones
hermes goal status <goal-id>        # Quick status summary
hermes goal progress <goal-id>      # Show completion percentage
```

### Updating Goals

```bash
# Complete a milestone
hermes goal complete <goal-id> --milestone 2

# Update goal status
hermes goal update <goal-id> --status blocked --reason "Waiting on API spec"

# Add milestone
hermes goal add-milestone <goal-id> "Add rate limiting"

# Reorder milestones
hermes goal reorder <goal-id> --milestone 3 --to 2

# Add note to milestone
hermes goal note <goal-id> --milestone 2 "Need to use connection pooling"
```

### Deleting & Archiving

```bash
hermes goal archive <goal-id>        # Archive (not delete)
hermes goal delete <goal-id>        # Hard delete (irreversible)
hermes goal restore <goal-id>       # Restore from archive
```

### Goal Templates

```bash
hermes goal templates               # List available templates
hermes goal create --template api  # Create from template
```

---

## Ralph Loop Integration

The `/goal` slash command activates the Ralph Loop in messaging:

```
/goal <goal-id>     # Activate goal tracking
```

When active, ILMA:
1. Reads the goal and current milestone
2. Plans work for this session
3. Executes work
4. Tests/reviews results
5. Updates milestone status
6. Reports progress

### Session Workflow with /goal

```
1. User: "/goal build-api"
2. ILMA: "Active goal: Build REST API (Milestone 2: Implement CRUD endpoints)
   Ready to work on this milestone. What's next?"
3. User: "Create the user endpoint"
4. ILMA:
   - Creates user endpoint
   - Tests it
   - Updates milestone notes
5. User: "Done for today"
6. ILMA: "Milestone 2 progress saved. See you next session."
```

### Cross-Session Memory

Goals persist in database. Each session:
- Loads current goal state
- Shows last completed milestone
- Reminds of active milestone
- Tracks time spent per milestone

---

## Goal Status Flow

```
triage → in_progress → blocked → in_progress → completed
                ↓          ↓
              triage    archived
```

**Transitions:**
- `triage` → `in_progress`: When work begins
- `in_progress` → `blocked`: When hitting a blocker
- `blocked` → `in_progress`: When blocker resolved
- `in_progress` → `completed`: When all milestones done
- Any → `archived`: When goal is no longer relevant

---

## Milestone Locking

Milestones are locked until previous milestone completes:

```
Milestone 1 [completed]     → Milestone 2 [ready]     → Milestone 3 [locked]
                                  ↓
                             Milestone 2 [in_progress]  → Milestone 3 [ready]
```

This prevents working on out-of-order tasks and ensures prerequisites are complete.

---

## Auto-Trigger Patterns

### Goal Creation Trigger
When user describes a complex multi-step objective:
```
"Build a complete web application with user auth, dashboard, and API"
"I need to migrate our entire infrastructure to Kubernetes"
"Create a machine learning pipeline from data ingestion to model serving"
```
→ Suggest: `hermes goal create "..." --milestones "..."`

### Milestone Update Trigger
When completing a significant chunk of work:
```
"Auth module is done"
"Database schema is finalized"
"API documentation is complete"
```
→ Ask: "Should I mark milestone N as completed?"

### Goal Review Trigger
On session start:
- Check for active goals
- Report current milestone
- Ask if continuing or switching

---

## Integration with Kanban

Goals and Kanban work together:

```
Goal (high-level objective)
  ↓ splits into
Milestones (discrete steps)
  ↓ each becomes
Kanban Task (actionable work unit)
```

| Aspect | Goals | Kanban |
|--------|-------|--------|
| Scope | High-level, multi-session | Discrete, atomic tasks |
| Duration | Days to months | Minutes to days |
| Tracking | Milestones and notes | Status columns |
| Assignment | Usually one person | Can be multi-agent |
| Persistence | Long-term | Task lifetime |

**Best practice:** Create a Goal for a project, then break each milestone into Kanban tasks.

---

## ILMA Goal Tracking Pattern

```python
# ilma_goal_tracker.py
class GoalTracker:
    def __init__(self, db_path: str = "~/.hermes/goals.db"):
        self.db = sqlite3.connect(Path(db_path).expanduser())
    
    async def create_goal(self, title: str, milestones: list, priority: str = "medium"):
        """Create goal with milestones."""
        goal_id = self._insert_goal(title, priority)
        for i, milestone in enumerate(milestones):
            self._insert_milestone(goal_id, i+1, milestone)
        return goal_id
    
    async def activate_goal(self, goal_id: int):
        """Activate goal for current session."""
        # Load goal, show current state
        goal = self.get_goal(goal_id)
        current = self.get_current_milestone(goal_id)
        return f"Active: {goal.title}\nMilestone {current.num}: {current.title}"
    
    async def complete_milestone(self, goal_id: int, milestone_num: int):
        """Mark milestone as completed, unlock next."""
        self._update_milestone(goal_id, milestone_num, "completed")
        next_num = milestone_num + 1
        if self._milestone_exists(goal_id, next_num):
            self._update_milestone(goal_id, next_num, "ready")
        # Check if all done → mark goal complete
```

---

## Auto-Trigger

Load this skill when:
- User mentions `/goal` or "goal" in slash command context
- User describes a complex multi-step objective
- User wants to "track progress", "set milestones", "plan long-term work"
- On session start: check for active goals

---

*Hermes v0.13.0 — Goals & Ralph Loop feature*
*Integrated into ILMA v3.3*