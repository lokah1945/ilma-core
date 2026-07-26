---
name: ilma-kanban-integration
description: ILMA Kanban Multi-Agent Integration — Hermes v0.13.0 Kanban plugin for parallel sub-agent task coordination with hallucination recovery, heartbeat, zombie detection, and retry budgets. SSS Tier. Auto-trigger for multi-agent parallel tasks, task coordination, team-based workflows. Uses ILMA's 163 FREE models for all workers (minimax, nvidia, openrouter, blackbox).
trigger_conditions:
  - "parallel task"
  - "multi-agent"
  - "task coordination"
  - "kanban"
  - "worker pool"
  - "task board"
  - "parallel execution"
  - "sub-agent team"
  - "dispatch multiple"
  - "batch subagent"
category: autonomous
created: 2026-05-09
updated: 2026-05-24
hermes_version: v0.13.0
source: hermes-agent/plugins/kanban/
---

# ILMA Kanban Integration — Hermes v0.13.0 Multi-Agent Board

## Overview

Hermes v0.13.0 ships a durable multi-agent Kanban board with:
- **Heartbeat** — agents report alive status
- **Reclaim** — abandoned tasks auto-reassigned
- **Zombie Detection** — stalled workers detected and replaced
- **Retry Budgets** — failed tasks retry with backoff
- **Hallucination Gate** — outputs validated before completion

ILMA uses this for parallel sub-agent coordination.

## FREE Model Routing (163 FREE models)

All kanban workers use ONLY ILMA's 163 FREE models — zero cost:

| Provider | FREE Models | Best For |
|----------|-------------|----------|
| nvidia | 131 | Reasoning, coding, heavy tasks |
| minimax | 6 | Fast general tasks |
| openrouter | 25 | Free reasoning (o3-mini-high:free) |
| blackbox | 1 | Multimodal fallback |

**Default model:** `nvidia/DeepSeek-R1` (best free reasoning model)
**Fast model:** `minimax/minimax-m2.7` (fast general tasks)

### Model Selection by Task Type

```python
from ilma_kanban_integration import ILMAKanban

kanban = ILMAKanban()

# Auto-select FREE model for task body
model = kanban.get_worker_model_for_task("Write a research paper about AI")
# → nvidia/DeepSeek-R1

model = kanban.get_worker_model_for_task("Debug this API endpoint")
# → nvidia/Qwen2.5-Coder-32B

model = kanban.get_worker_model_for_task("Quick translation task")
# → minimax/minimax-m2.7
```

### Task Type → Best FREE Model

| Task Type | Best FREE Model | Provider |
|-----------|-----------------|----------|
| reasoning_xhigh | DeepSeek-R1 | nvidia |
| heavy_coding | Qwen2.5-Coder-32B | nvidia |
| medium_coding | Qwen2.5-Coder-32B | nvidia |
| research | DeepSeek-R1 | nvidia |
| general | DeepSeek-R1 | nvidia |
| fast_tasks | minimax-m2.7 | minimax |
| vision | gpt-4o-mini:free | openrouter |
| writing | minimax-m2.7 | minimax |

## Architecture

```
ILMA (Master)
  └── Spawns Kanban Board via hermes cron or direct plugin
       ├── Worker 1: Task A (nvidia/DeepSeek-R1 — FREE)
       ├── Worker 2: Task B (nvidia/Qwen2.5-Coder-32B — FREE)
       ├── Worker 3: Task C (minimax/minimax-m2.7 — FREE)
       └── Worker 4: Task D (openrouter/o3-mini-high:free — FREE)

Result: ALL workers use FREE models — 0 cost
```

## Usage

```python
from ilma_kanban_integration import ILMAKanban
from ilma_kanban_free_model_optimizer import get_kanban_stats, get_fallback_chain

kanban = ILMAKanban()

# Create task with auto FREE model routing
task = kanban.create(
    title="Research task",
    body="Analyze this research paper...",
    assignee="researcher"
)
# Worker gets best FREE model auto-selected from body

# Fan-out: N parallel workers, each with FREE model
parent, children = kanban.fan_out(
    tasks=["Task A", "Task B", "Task C"],
    body_prefix="Research: ",  # Each worker gets body → FREE model
    assignee="researcher"
)

# Get FREE model stats
stats = kanban.get_kanban_free_model_stats()
# → {total_free_models: 163, by_provider: {...}, default_model: "nvidia/DeepSeek-R1"}

# Fallback chain for a task type
chain = get_fallback_chain("heavy_coding")
# → ["nvidia/Qwen2.5-Coder-32B", "minimax/minimax-m2.7", ...]
```

## Free Model Optimizer

`ilma_kanban_free_model_optimizer.py` provides:
- `get_best_free_for_task(task_type)` → best free model per type
- `get_model_for_task_body(body)` → infer type from text → best free model
- `get_fallback_chain(task_type)` → ordered fallback list
- `get_kanban_stats()` → statistics for all free models
- `sync_worker_model_env()` → sync free models + set HERMES_MODEL env

## CLI Commands

```bash
# Create kanban board (Hermes cron integration)
hermes cron create \
  --name "ilma-kanban-board" \
  --prompt "Run ILMA kanban worker loop" \
  --schedule "continuous" \
  --plugin kanban

# Check kanban status
hermes kanban status

# List active tasks
hermes kanban tasks list

# Dispatch workers (with FREE model routing via ILMA)
hermes kanban dispatch --max 5

# View worker logs
hermes kanban log <task_id>
```

# Get task output
hermes kanban tasks get <task_id>

# Cancel task
hermes kanban tasks cancel <task_id>

# Retry failed task
hermes kanban tasks retry <task_id>
```

## ILMA Integration Pattern

### Step 1: Parse Task into Sub-Tasks

When ILMA receives complex task, decompose into kanban cards:

```python
# Example: 1000-file codebase task → split into 10 batches of 100 files
tasks = []
for i in range(10):
    tasks.append({
        "id": f"batch_{i}",
        "description": f"Process files {i*100} to {(i+1)*100}",
        "priority": "high",
        "retry_budget": 3,
        "timeout": 600
    })
```

### Step 2: Dispatch to Kanban Board

```bash
# Method A: Via hermes cron with kanban plugin
hermes cron create \
  --name "ilma-codebase-build" \
  --prompt "Execute batch processing for ILMA Phase 13D" \
  --schedule "once" \
  --plugin kanban

# Method B: Via delegate_task with kanban mode
# Use delegate_task with max_concurrent parameter
```

### Step 3: Monitor with Heartbeat

Workers report heartbeat every 30s. ILMA monitors via:

```bash
hermes kanban workers list
hermes kanban workers get <worker_id>
```

### Step 4: Zombie Detection & Recovery

If worker misses 3 heartbeats:
1. Task marked as `abandoned`
2. Zombie detection fires → task reclaimed
3. New worker dispatched automatically

### Step 5: Hallucination Gate

Before task marked `done`, gate validates:
- Output matches expected format
- Evidence files created
- No obvious hallucination (fake paths, wrong logic)

## Hallucination Recovery Pattern

```python
def validate_task_output(task_id: str) -> bool:
    """Hallucination gate — validates task output before completion"""
    output = hermes_kanban_task_get(task_id)
    
    checks = [
        check_evidence_files_exist(output),
        check_output_format_valid(output),
        check_no_fake_paths(output),
        check_logic_consistency(output)
    ]
    
    if all(checks):
        return True  # Task complete
    else:
        # Hallucination detected — retry or flag
        hermes_kanban_tasks_retry(task_id)
        return False
```

## Retry Budget Logic

- Default: 3 retries
- Backoff: exponential (30s, 60s, 120s)
- After 3 failures: task marked `failed`, alert sent
- ILMA gets notification via cron delivery

## ILMA Master Orchestrator Integration

ILMA's `ilma-master-orchestrator` skill wraps kanban:

```python
# ILMA orchestrator pattern
async def orchestrate_parallel(tasks: list, max_workers: int = 3):
    """ILMA wraps Hermes kanban for parallel execution"""
    
    # 1. Create kanban board
    board = hermes_kanban_create(name="ilma-master", workers=max_workers)
    
    # 2. Add tasks
    for task in tasks:
        hermes_kanban_add(board, task)
    
    # 3. Monitor heartbeats
    while not hermes_kanban_all_done(board):
        status = hermes_kanban_status(board)
        ilma.report_progress(status)
        
        if status.zombies > 0:
            ilma.log(f"Zombie detected: {status.zombies} workers replaced")
        
        sleep(30)
    
    # 4. Collect results
    return hermes_kanban_results(board)
```

## Verification Commands

```bash
# Verify kanban plugin installed
hermes plugins list | grep kanban

# Check kanban config
cat ~/.hermes/config.yaml | grep -A5 kanban

# Test kanban health
hermes kanban health

# Run diagnostic
hermes doctor --component kanban
```

## Pitfalls

1. **Don't over-parallelize** — Max 3-5 workers for ILMA's scale
2. **Heartbeat timeout** — Ensure workers report within 30s intervals
3. **Hallucination gate** — Always validate before marking done
4. **Zombie replacement** — Give replacement workers full context
5. **Cron vs direct** — Use cron for persistent boards, direct for one-shot

## Related Skills

- `ilma-master-orchestrator` — ILMA's orchestrator that wraps kanban
- `ilma-autonomous-loops` — Background task loops
- `ilma-auto-recovery` — Error recovery patterns
- `subagent-driven-development` — When to use subagents vs kanban

## Status

✅ INTEGRATED (2026-05-09) — Hermes v0.13.0 Kanban plugin