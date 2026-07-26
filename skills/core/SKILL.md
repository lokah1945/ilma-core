---
name: core
description: "ILMA v5 Core Architecture Skills — Foundational components including Abstract Goal Translator, Genesis Daemon, Genetic Evolution, Omega Council, Provider Gateway, Vector Omega, and Hermes Knowledge Ingestion."
triggers:
  - core
  - architecture
  - foundation
  - abstract-goal
  - genesis
  - genetic-evolution
  - omega-council
  - provider-gateway
  - vector-omega
  - hermes-knowledge
category: ilma-core
version: 5.0.0
tier: SSS-OMEGA
last_updated: 2026-05-09
type: category
---

# ILMA v5 Core Architecture Skills

## Overview

This category contains the foundational architecture skills for ILMA v5.0. These are the core systems that power ILMA's autonomous operation, evolution, and multi-agent coordination.

**Tier:** SSS-OMEGA  
**Version:** 5.0.0  
**Status:** OPERATIONAL

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ILMA v5 CORE ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                  │
│  │   ABSTRACT  │────▶│   GENESIS   │────▶│   GENETIC   │                  │
│  │    GOAL     │     │   DAEMON    │     │  EVOLUTION  │                  │
│  │ TRANSLATOR  │     │             │     │             │                  │
│  └─────────────┘     └─────────────┘     └─────────────┘                  │
│         │                   │                   │                           │
│         ▼                   ▼                   ▼                           │
│  ┌─────────────────────────────────────────────────────────┐               │
│  │                    OMEGA COUNCIL                        │               │
│  │         Multi-Agent Coordination & Decision             │               │
│  └─────────────────────────────────────────────────────────┘               │
│         │                   │                   │                           │
│         ▼                   ▼                   ▼                           │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                  │
│  │   HERMES    │     │   VECTOR    │     │  PROVIDER   │                  │
│  │ KNOWLEDGE   │     │   OMEGA     │     │  GATEWAY    │                  │
│  │ INGESTION   │     │             │     │             │                  │
│  └─────────────┘     └─────────────┘     └─────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Included Skills

### 1. ilma-abstract-goal-translator

**Description:** Translates high-level user goals into actionable sub-tasks.

**Key Features:**
- Goal decomposition
- Task prioritization
- Dependency mapping
- Execution planning

**Triggers:** goal, translate, abstract, plan, decompose

### 2. ilma-genesis-daemon

**Description:** Initialization and bootstrap system for ILMA agents.

**Key Features:**
- Agent initialization
- Configuration loading
- Skill loading
- State restoration

**Triggers:** genesis, init, bootstrap, start, initialize

### 3. ilma-genetic-evolution

**Description:** Self-improvement through genetic algorithms and mutation.

**Key Features:**
- Trait evolution
- Mutation strategies
- Fitness evaluation
- Generation management

**Triggers:** evolution, genetic, mutate, evolve, fitness

### 4. ilma-omega-council

**Description:** Multi-agent coordination and decision-making council.

**Key Features:**
- Agent delegation
- Consensus building
- Task distribution
- Result aggregation

**Triggers:** council, multi-agent, coordinate, delegate, consensus

### 5. ilma-provider-gateway

**Description:** Unified interface for external service providers.

**Key Features:**
- Provider abstraction
- Request routing
- Response normalization
- Error handling

**Triggers:** provider, gateway, external, service, route

### 6. ilma-vector-omega

**Description:** Vector storage and semantic search for knowledge retrieval.

**Key Features:**
- Vector embedding
- Semantic search
- Similarity matching
- Knowledge indexing

**Triggers:** vector, embedding, semantic, search, similarity

### 7. ilma-hermes-knowledge-ingestion

**Description:** Perplexity-style documentation ingestion engine.

**Key Features:**
- Documentation parsing
- Skill generation
- Auto-discovery
- Knowledge updating

**Triggers:** knowledge, ingestion, documentation, perplexity, research

## Core Components

### Abstract Goal Translator

```python
from ilma.core import AbstractGoalTranslator

translator = AbstractGoalTranslator()

# High-level goal
goal = "Set up a production-ready Kubernetes cluster"

# Translate to actionable tasks
tasks = translator.translate(goal)
# Returns: [Task("provision infrastructure"), Task("configure networking"), ...]
```

### Genesis Daemon

```python
from ilma.core import GenesisDaemon

daemon = GenesisDaemon()

# Initialize agent
await daemon.initialize(profile="ilma")

# Load skills
await daemon.load_skills()

# Restore state
await daemon.restore_state()
```

### Omega Council

```python
from ilma.core import OmegaCouncil

council = OmegaCouncil()

# Propose decision
proposal = {
    "action": "deploy",
    "target": "production",
    "agents": ["ILMA", "DEPRECATED_AGENT"]
}

# Get consensus
decision = await council.get_consensus(proposal)
# Returns: {"approved": True, "votes": {...}}
```

### Vector Omega

```python
from ilma.core import VectorOmega

vector_db = VectorOmega()

# Store embedding
await vector_db.store("concept_id", embedding, metadata)

# Semantic search
results = await vector_db.search("query text", top_k=10)
```

## Tier System

| Tier | Description | Skills |
|------|-------------|--------|
| SSS-OMEGA | Core infrastructure | genesis, abstract-goal, omega-council |
| SSS | System-level | genetic-evolution, provider-gateway |
| S | Service-level | vector-omega, hermes-knowledge |

## Inter-Skill Communication

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTER-SKILL PROTOCOL                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Goal Request ──────▶ Abstract Goal Translator                  │
│                              │                                  │
│                              ▼                                  │
│                       Genesis Daemon                            │
│                              │                                  │
│                              ▼                                  │
│                    Genetic Evolution                            │
│                              │                                  │
│                              ▼                                  │
│                      Omega Council                              │
│                      /    |    \                                │
│                     ▼     ▼     ▼                               │
│              Hermes   Vector  Provider                          │
│            Knowledge   Omega   Gateway                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration

```yaml
core:
  tier: SSS-OMEGA
  genesis:
    auto_init: true
    load_skills: true
  omega_council:
    consensus_threshold: 0.7
    timeout: 30
  vector_omega:
    dimension: 1536
    backend: pinecone
```

## Related Categories

- `hermes-ingested/` — Hermes memory and tool registry skills
- `security/` — Security hardening patterns

---
Generated by ILMA v5 Skill System
