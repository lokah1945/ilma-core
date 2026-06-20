---
name: ilma-orchestrator-frameworks
description: |
  ILMA Orchestrator Frameworks — 4 advanced multi-agent orchestration patterns:
  LangGraph (state machine), AutoGen (real-world execution), DSPy (metric self-improvement),
  MetaGPT (SOP corporate simulation), plus Universal orchestrator with auto-selection.
triggers:
  - build orchestrator
  - multi-agent debate
  - self-improvement loop
  - autonomous evolution
  - actor-critic framework
  - reflexion loop
  - state machine orchestration
  - corporate SOP simulation
  - metric-based evaluation
  - code execution feedback
---

# ILMA Orchestrator Frameworks

## Overview

ILMA implements 4 advanced multi-agent orchestration patterns based on the architecture document:
"Arsitektur Orkestrasi Multi-Agen untuk Evolusi Otonom".

Each framework provides a different approach to autonomous Agent-Critic debate.

## Frameworks

### 1. LangGraph Orchestrator (`ilma_langgraph_orchestrator.py`)
State machine with conditional edges — deterministic routing based on Judge verdict.

**Key Features:**
- `GraphState`: Global state passed through graph
- `ActorNode`: Hermes produces solution (temperature 0.4-0.7)
- `JudgeNode`: Evaluates against criteria (temperature 0.0-0.1)
- `ConditionalEdge`: Routes based on verdict — FAIL → Actor, PASS → END

**When to use:** Logical pass/fail criteria, deterministic evaluation

### 2. AutoGen Executor (`ilma_autogen_executor.py`)
Real-world execution with stack trace feedback — "reality" as Judge.

**Key Features:**
- `UserProxyAgent`: Executes code, returns stack traces
- `ExecutionResult`: Success/error/execution_time/return_code
- `AutogenSession`: Tracks attempts and feedback
- TeachableAgent pattern: Stores lessons when failures resolved

**When to use:** Code execution, testing, stack trace evaluation

### 3. DSPy Self-Improver (`ilma_dspy_self_improver.py`)
Metric-based self-improvement — Judge = Python functions, not conversation.

**Key Features:**
- `MetricFunctions`: 5 metric types (correctness, style, efficiency, safety, completeness)
- `Teleprompter`: Analyzes failures, mutates prompts
- Prompt evolution: Like compiling weights, but for instructions

**When to use:** Prompt optimization, template evolution

### 4. MetaGPT Orchestrator (`ilma_metagpt_orchestrator.py`)
Corporate SOP simulation — hierarchical roles with strict stage transitions.

**Key Features:**
- `SOPStage`: REQUIREMENTS → ARCHITECTURE → IMPLEMENTATION → TESTING → REVIEW → COMPLETE
- `AgentRole`: ENGINEER, QA_ENGINEER, ARCHITECT, REVIEWER
- `Artifact`: Intermediate work products
- Rejection loop: QA reject → Engineer revises → QA retests

**When to use:** Complex multi-role, end-to-end deliverables

### 5. Universal Orchestrator (`ilma_universal_orchestrator.py`)
Auto-selection and unified entry point for all 4 frameworks.

**Selection Logic:**
- `langgraph`: Logical validation, deterministic pass/fail
- `autogen`: Code execution, testing, stack traces
- `dspy`: Prompt optimization, template evolution
- `metagpt`: Complex multi-role, SOP-driven
- `gemini`: Actor-Critic debate, temperature asymmetry

## Usage

```python
from ilma_universal_orchestrator import UniversalOrchestrator, OrchestratorType

# Auto-select
universal = UniversalOrchestrator()
result = universal.run_auto("Build function", "Validate input", verbose=True)

# Explicit selection
result = universal.run(OrchestratorType.LANGGRAPH, task, criteria, verbose=True)

# Direct orchestrator
from ilma_langgraph_orchestrator import LangGraphOrchestrator
orch = LangGraphOrchestrator(max_rounds=5, pass_threshold=4.0)
session = orch.create_session(task, criteria)
result = orch.run(session.session_id, verbose=True)
```

## Temperature Configuration

Critical for debate effectiveness:

| Role | Temperature | Purpose |
|------|------------|---------|
| Actor (Hermes) | 0.4 - 0.7 | Creative flexibility |
| Judge (Critic) | 0.0 - 0.1 | Deterministic, unforgiving |

## Memory Integration

All orchestrators accept `memory_integration` parameter for persistent learning:

```python
from ilma_long_term_memory import LongTermMemory

memory = LongTermMemory()
orch = LangGraphOrchestrator(memory_integration=memory)
```

When failure is resolved, lesson is stored. Before next task, lessons are pulled.

## Testing

```bash
pytest tests/test_ilma_orchestrators.py -v
# 40/40 PASS
```

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `ilma_langgraph_orchestrator.py` | 688 | State machine orchestrator |
| `ilma_autogen_executor.py` | 579 | Real-world execution |
| `ilma_dspy_self_improver.py` | 700 | Metric self-improvement |
| `ilma_metagpt_orchestrator.py` | 750 | SOP corporate simulation |
| `ilma_universal_orchestrator.py` | 428 | Unified entry point |
| `tests/test_ilma_orchestrators.py` | 550 | 40 unit tests |
| **TOTAL** | **3,695** | **All frameworks** |

## Quick Reference

See `references/orchestrator-selection.md` for:
- When to use which framework (quick table)
- Temperature asymmetry table
- RCR pattern rule
- Metric types and thresholds
- SOP stage flow
- Teleprompter mutation types

- `ILMA-EVID-20260510-ORCHESTRATOR-001` — 4 frameworks + universal, all compile/import/functional
- `ILMA-EVID-20260510-ORCHESTRATOR-002` — 40/40 tests pass

## Related Skills

- **`ilma-multi-agent`** — SSS Tier skill for Actor-Critic, Reflexion, MAE, SE-Agent, RCR patterns
- `ilma-gemini-integration` — Unified entry point for all 6 Gemini patterns
- `ilma-auto-evolution-engine` — Automated evolution cycles
- `ilma-autonomous-loops` — SSS Tier for continuous operation loops