---
name: ilma-gemini-integration
description: |
  ILMA Gemini Multi-Agent Architecture Integration — Complete implementation of Gemini's
  Actor-Critic, Reflexion, MAE, Trajectory Evolution, RCR Pattern, and Long-Term Memory.
  Source: /root/konsep/gemini/ (arsitektur_orkestrasi_multiagen.md, partner_agent.md)
triggers:
  - "gemini"
  - "actor critic"
  - "reflexion loop"
  - "multi-agent evolve"
  - "rcr pattern"
  - "reflect critique refine"
  - "trajectory evolution"
  - "partner agent"
  - "deepseek critic"
  - "prometheus judge"
  - "se-agent"
category: agent-patterns
author: ILMA
version: 1.0.0
created: 2026-05-10
integrated_from:
  - /root/konsep/gemini/arsitektur_orkestrasi_multiagen.md
  - /root/konsep/gemini/partner_agent.md
evidence_id: ILMA-EVID-20260510-GEMINI-INTEGRATION-001
verified: true
---

# ILMA Gemini Integration Skill

## Overview

This skill provides complete implementation of Gemini's multi-agent architecture patterns, integrated into ILMA's runtime.

## Core Components

### 1. Actor-Critic Core (`ilma_actor_critic_core.py`)

Asymmetric triad: Actor (ILMA) / Critic (DeepSeek) / Judge (Prometheus-2)

```python
from ilma_actor_critic_core import ActorCriticCore

core = ActorCriticCore(max_rounds=5, judge_threshold=4.0)
session = core.run_debate("Build REST API", "Must validate input", verbose=True)
```

### 2. Reflexion Loop (`ilma_reflexion_loop.py`)

Self-correction cycle: Judge finds error → ILMA fixes

```python
from ilma_reflexion_loop import ReflexionLoop

reflexion = ReflexionLoop(max_revisions=5, judge_threshold=4.0)
session = reflexion.run_full_reflexion("Build endpoint", "Must handle errors", verbose=True)
```

### 3. MAE Triplet (`ilma_mae_triplet.py`)

Multi-Agent Evolve: Proposer → Solver → Judge

```python
from ilma_mae_triplet import MAETriplet

mae = MAETriplet(max_cycles=10, difficulty_threshold=0.5)
session = mae.run_full_evolution("Build authentication", verbose=True)
```

### 4. Trajectory Evolution (`ilma_trajectory_evolution.py`)

SE-Agent: Revision / Recombination / Refinement

```python
from ilma_trajectory_evolution import TrajectoryEvolution

engine = TrajectoryEvolution()
traj = engine.create_trajectory("Task", [
    {"action": "Step 1", "reasoning": "Because...", "is_failure": False},
])
result = engine.revise(traj.trajectory_id, failure_node_index=1)
```

### 5. RCR Pattern (`ilma_rcr_pattern.py`)

Reflect-Critique-Refine adversarial debate

```python
from ilma_rcr_pattern import RCRPattern

rcr = RCRPattern(max_turns=5)
session = rcr.run_full_debate("Build function", "Must handle nulls", verbose=True)
```

### 6. Long-Term Memory (`ilma_long_term_memory.py`)

Lesson extraction and retrieval (SQLite FTS5)

```python
from ilma_long_term_memory import LongTermMemory

memory = LongTermMemory()
lesson = memory.extract_lesson("api_design", "REST endpoint", "Missing validation", "Added Pydantic")
result = memory.retrieve("REST validation")
```

### 7. Unified Integration (`ilma_gemini_integration.py`)

Single entry point for all components

```python
from ilma_gemini_integration import GeminiIntegrationCore

core = GeminiIntegrationCore()
core.run_actor_critic(task, criteria)
core.run_reflexion(task, criteria)
core.run_rcr_debate(task, target)
core.store_lesson(category, pattern, problem, solution)
core.retrieve_lessons(query)
```

### 8. Partner Wrappers (`ilma_partner_wrappers.py`)

Prometheus-2 (Judge) and DeepSeek (Critic) interfaces

```python
from ilma_partner_wrappers import PrometheusJudgeWrapper, DeepSeekCriticWrapper

judge = PrometheusJudgeWrapper()
critic = DeepSeekCriticWrapper()

score, feedback = judge.evaluate(response, criteria)
flaws, feedback = critic.critique(actor_output, task)
```

## Temperature Asymmetry

Per Gemini architecture:

| Role | Temperature | Purpose |
|------|-------------|---------|
| Actor (ILMA) | 0.4-0.7 | Creative, flexible |
| Critic (DeepSeek) | 0.0-0.1 | Deterministic, analytical |
| Judge (Prometheus-2) | 0.0 | Strict rubric evaluation |

## Key Principles

1. **Actor-Critic**: ILMA = Actor, Partner = Critic/Judge. Temperature asymmetry is critical.
2. **Reflexion**: Judge forces ILMA to fix wrong approach → extract lesson
3. **MAE**: Proposer → Solver → Judge closes loop without human
4. **SE-Agent**: Revision fixes failure node, Recombination cross-breeds, Refinement removes redundancies
5. **RCR**: Critic's goal is NOT to give correct answer, but to find flaws
6. **Memory**: Every Judge forcing fix → extract lesson for future

## Files

| File | Lines | Purpose |
|------|-------|---------|
| ilma_actor_critic_core.py | ~716 | Asymmetric triad orchestration |
| ilma_reflexion_loop.py | ~460 | Self-correction cycle |
| ilma_mae_triplet.py | ~430 | Multi-Agent Evolve |
| ilma_trajectory_evolution.py | ~380 | SE-Agent evolution |
| ilma_rcr_pattern.py | ~310 | Reflect-Critique-Refine |
| ilma_long_term_memory.py | ~360 | Lesson storage/retrieval |
| ilma_gemini_integration.py | ~350 | Unified entry point |
| ilma_partner_wrappers.py | ~390 | Partner agent interfaces |

**Total: ~3,396 lines of production Python**

## Integration Status

- All modules compile ✓
- All imports functional ✓
- All demos pass ✓
- Skills created ✓
- Documentation complete ✓
- Evidence ID: ILMA-EVID-20260510-GEMINI-INTEGRATION-001

## Usage Examples

### Full Workflow with Memory Integration

```python
from ilma_gemini_integration import GeminiIntegrationCore
from ilma_long_term_memory import MemoryIntegratedSession

core = GeminiIntegrationCore()
memory_session = MemoryIntegratedSession(core.memory)

# Run Actor-Critic with automatic lesson extraction
session = core.run_actor_critic("Build API", "Must validate", verbose=False)
memory_session.extract_from_actor_critic(session.to_dict())

# Retrieve lessons for similar future tasks
lessons = core.retrieve_lessons("API validation")
for lesson in lessons.lessons:
    print(f"Learned: {lesson.solution}")
```

### RCR Debate for Critical Decisions

```python
core = GeminiIntegrationCore()

# Adversarial debate for high-stakes task
session = core.run_rcr_debate(
    "Design database schema",
    "Must handle 1M rows, support full-text search",
    verbose=True
)

if session.resolved:
    print("Debate resolved — approach is sound")
else:
    print(f"Debate exhausted — {len(session.turns[-1].flaws_found)} remaining issues")
```

## Not Implemented (Requires External APIs)

- Live Prometheus-2 API calls (requires API endpoint + key)
- Live DeepSeek-R1 API calls (requires API endpoint + key)
- ChromaDB/Mem0 vector storage (using SQLite FTS5 fallback)

## See Also

- `ilma-evolution` — ILMA's evolution patterns
- `ilma-multi-agent` — ILMA's multi-agent patterns
- `ilma-auto-evolution-engine` — ILMA's self-improvement engine