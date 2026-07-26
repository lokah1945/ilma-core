---
name: ilma-hermes-knowledge-ingestion
description: "ILMA v5.0 Hermes Core Knowledge Ingestion Engine — Perplexity-Style Research. Periodically checks Hermes documentation (hermes-agent.nousresearch.com) for new features, translates docs into executable ILMA skills at runtime. Auto-generates SKILL.md + implementation code. SSS-OMEGA Tier."
triggers:
  - hermes-knowledge
  - documentation-ingestion
  - perplexity-style
  - research
  - feature-extraction
  - runtime-skill-generation
version: 5.0.0
tier: SSS-OMEGA
last_updated: 2026-05-07 19:00
---

# ILMA v5.0 — HERMES CORE KNOWLEDGE INGESTION

## Overview

**Tier:** SSS-OMEGA  
**Version:** 5.0.0  
**Status:** OPERATIONAL

## Concept

Perplexity-Style Research: Instead of ILMA searching the web, ILMA **ingests official documentation** and translates it into executable capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│          HERMES KNOWLEDGE INGESTION ENGINE — PERPLEXITY STYLE               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  HERMES DOCS (hermes-agent.nousresearch.com/docs/)                          │
│       │                                                                       │
│       │  Every 6 hours (configurable)                                         │
│       │                                                                       │
│       ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              DOCUMENTATION PARSER (HermesDocParser)                    │   │
│  │                                                                      │   │
│  │   Parses:                                                            │   │
│  │   ├── Markdown (headings, code blocks, lists)                        │   │
│  │   ├── HTML (BeautifulSoup extraction)                               │   │
│  │   ├── API endpoints (GET/POST patterns)                             │   │
│  │   └── Code examples (language detection)                             │   │
│  │                                                                      │   │
│  │   Output: FeatureDoc objects with:                                   │   │
│  │   ├── name, category, description                                   │   │
│  │   ├── code_examples, api_endpoints                                 │   │
│  │   └── related_features, prerequisites                               │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              SKILL GENERATOR (SkillGenerator)                         │   │
│  │                                                                      │   │
│  │   Input: FeatureDoc                                                  │   │
│  │   Output: LearnedSkill with:                                        │   │
│  │   ├── SKILL.md (metadata, triggers, documentation)                   │   │
│  │   ├── [skill_name].py (implementation code)                        │   │
│  │   └── test_skill.py (validation)                                     │   │
│  │                                                                      │   │
│  │   Implementation templates by category:                             │   │
│  │   ├── tool_integration → ToolIntegration class                     │   │
│  │   ├── memory_system → MemoryStore/retrieve/delete                  │   │
│  │   ├── orchestration → TaskOrchestrator with semaphore              │   │
│  │   ├── security → Auth/encryption patterns                          │   │
│  │   ├── networking → HTTP client patterns                             │   │
│  │   ├── autonomy → Self-improvement loops                            │   │
│  │   ├── multi_agent → Agent delegation                               │   │
│  │   ├── workflow → Pipeline execution                                │   │
│  │   └── monitoring → Metrics collection                              │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              SKILL REGISTRY (Auto-Discovery)                            │   │
│  │                                                                      │   │
│  │   skills/hermes-ingested/                                            │   │
│  │   ├── hermes-tool-registry/SKILL.md + .py + test.py                 │   │
│  │   ├── hermes-memory-system/SKILL.md + .py + test.py                  │   │
│  │   ├── hermes-task-orchestration/SKILL.md + .py + test.py            │   │
│  │   └── ... (one directory per feature)                               │   │
│  │                                                                      │   │
│  │   ILMA loads these at runtime via normal skill discovery            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Feature Categories

| Category | Keywords | Generated Skill Pattern |
|----------|----------|-------------------------|
| TOOL_INTEGRATION | tool, plugin, extension | ToolIntegration class |
| MEMORY_SYSTEM | memory, storage, persistence | Store/retrieve/delete |
| ORCHESTRATION | orchestrat, routing, dispatch | TaskOrchestrator |
| SECURITY | security, auth, encryption | Auth patterns |
| NETWORKING | http, api, webhook | HTTP client |
| AUTONOMY | autonomous, self-improve | Self-improvement loop |
| MULTI_AGENT | multi-agent, delegation | Agent council |
| WORKFLOW | workflow, pipeline, chain | Pipeline executor |
| MONITORING | monitoring, metrics | Metrics collector |

## Ingestion Cycle

```
1. CHECK UPDATES (ETag/Last-Modified comparison)
        │
        ▼
2. FETCH DOCS (features, architecture, api-reference)
        │
        ▼
3. PARSE FEATURES (Markdown → FeatureDoc)
        │
        ▼
4. EXTRACT (name, description, code examples, API endpoints)
        │
        ▼
5. GENERATE SKILLS (FeatureDoc → SKILL.md + .py + test.py)
        │
        ▼
6. TEST (validate generated skill can be imported)
        │
        ▼
7. STORE (skills/hermes-ingested/[feature]/)
        │
        ▼
8. LOG (memory/hermes_ingestion/ingestion_log.json)
```

## Genesis Daemon Integration

```python
# In Genesis Daemon background tasks:
from ilma_hermes_knowledge_ingestion import HermesIngestionBackgroundTask

ingestion_task = HermesIngestionBackgroundTask(daemon=genesis_daemon)
await ingestion_task.start()  # Runs every 6 hours

# Manual trigger:
result = await ingestion_task.trigger_ingestion()
print(f"Generated {result.skills_generated} new skills")
```

## State File Paths

| File | Purpose |
|------|---------|
| `memory/hermes_ingestion/features_index.json` | All documented features |
| `memory/hermes_ingestion/learned_skills.json` | Generated skills registry |
| `memory/hermes_ingestion/docs_cache/*.txt` | Cached documentation |
| `memory/hermes_ingestion/ingestion_log.json` | Ingestion history |
| `memory/hermes_ingestion/etag.txt` | Last ETag for update detection |

## Files

- /root/.hermes/profiles/ilma/scripts/ilma_hermes_knowledge_ingestion.py (1,657 lines)

## Hermes Documentation Endpoints

| Endpoint | Content |
|----------|---------|
| `/docs/user-guide/features/overview` | Feature overview |
| `/docs/architecture` | System architecture |
| `/docs/api-reference` | API reference |

---

**ILMA v5.0 — LEARNING FROM HERMES, TRANSCENDING HERMES**