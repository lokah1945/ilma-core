---
name: ilma-hermes-integration
description: ILMA Hermes Integration — Kanban board, 788 Hermes+ILMA skills via Skills Router v2.0 (execution engine), Canon8 pipeline v2.0, singleton pattern, E2E verified.
last_updated: 2026-05-22
---
```

## ✅ Hermes Skills Router v2.0 — FULL PIPELINE INTEGRATION (2026-05-22)

**Total: 788 skills** (168 Hermes + 620 ILMA) across **34 categories** with **137 trigger patterns**.

All 81 official Hermes optional skills installed and integrated as an execution engine into ILMA's default pipeline. See `references/hermes-skills-router-v2-integration.md` for full session details.

## References

- `references/hermes-skills-integration-2026-05-22.md` — 81 skills installation + router extension + pipeline integration (all 8 E2E passed)
- `references/hermes-skills-router-v2-integration.md` — v2.0 upgrade: execution engine, singleton, orchestrator handlers, Canon8 v2.0 pipeline (commit 2dce8c8)
- `references/path-home-bug-2026-05-19.md` — Path.home() workaround details
## Umbrella: Hermes Agent Integration for ILMA

Integrates ILMA with Hermes Agent v0.13.0 ecosystem: Kanban board management and Hermes Skills Router v2.0 execution engine (788 skills across 34 categories).

**v2.0 Execution Engine** (upgraded 2026-05-22):
- `get_skills_router()` singleton — no re-init on each call
- `execute_skill()` — actual skill execution via hermes_cli / direct import / fallback
- `learn_from_result()` — success rate tracking per skill
- Confidence threshold: >=0.90 auto-execute in Workflow ECC Step 1.5
- Canon8 v2.0 pipeline: 5-step with SKILL_DETECT step

## Components

### 1. Hermes Skills Router (`ilma_hermes_skills_router.py`)

Auto-detects and triggers Hermes skills based on task context. Scans three sources:
- `~/.hermes/skills/` — bundled Felo + Hermes skills (~11 skills)
- `~/.hermes/hermes-agent/skills/` — 75 skills, 24 categories
- `~/.hermes/hermes-agent/optional-skills/` — 79 skills (all validated present)

**Total: 788 skills** (168 Hermes + 620 ILMA) across **34 categories** with **137 trigger patterns**.

#### Routing Logic (Priority Order)
1. **ILMA_SKILL_TRIGGERS** — explicit `ilma-*` patterns (confidence 0.95)
2. **TASK_TO_SKILL_PATTERNS** — keyword → category/skill mapping (confidence 0.80)
3. **context-based** — task_type, domain from workflow (confidence 0.85-0.95)

#### Pattern Format
Supports both `category` and `category/skill` formats:
- `devops` → all skills in devops category
- `research/arxiv` → look up `research` category, override to `arxiv` skill

#### Key Patterns
```
kanban workflow parallel task delegation → claude-code (autonomous-ai-agents)
yuanbao group member info → yuanbao
ilma self-improve autonomous loop → ilma-autonomous-loops
kubernetes debug pod crash fix → devops
research paper writing machine learning → arxiv
playwright stealth browser automation → devops (via playwright pattern)
plan feature implementation roadmap milestone → plan
github pull request code review → github
```

#### Hermes Skill Categories (HERMES_SKILL_CATEGORIES)
- apple, autonomous-ai-agents, creative, data-science, devops, diagramming, dogfood, domain
- email, feeds, gaming, gifs, github, inference-sh, leisure, mcp, media, mlops, note-taking
- productivity, red-teaming, research, smart-home, social-media, software-development, yuanbao

### 2. Hermes Kanban Integration (`ilma_kanban_integration.py`)

Wrapper for `hermes kanban` CLI (Hermes v0.13.0+):

#### Capabilities
- **Task CRUD**: create, show, list, complete, block, reclaim, reassign
- **Heartbeat monitoring**: detects zombie tasks
- **Fan-out**: parallel task delegation
- **Sequential pipeline**: stage-based execution
- **Hallucination gate**: pre-execution task validation
- **Retry budget tracking**: budget management per task

#### Hermes Kanban CLI Reference
```bash
hermes kanban create "<title>" [--assignee <name>] [--priority <1-5>] [--parent <id>]
hermes kanban list
hermes kanban show <task_id>
hermes kanban complete <task_id>
hermes kanban block <task_id>
hermes kanban reclaim <task_id>
hermes kanban stats
```

### 3. ILMA.py Boot Components

Added to boot sequence:
- **component #11**: `kanban` — Hermes Kanban integration
- **component #12**: `hermes_skills` — Hermes Skills Router

Integration points:
- `route_task()` → auto-detects skills via `HermesSkillsRouter`
- `run_capability_workflow()` → also auto-detects skills
- `cmd_route()` → displays detected skills + handles workflow/direct output formats

## ⚠️ CRITICAL: Path.home() Bug in ILMA Runtime

**Problem:** Inside ILMA's Python runtime, `Path.home()` returns:
```
/root/.hermes/profiles/ilma/home  ❌ WRONG
```
**Expected:**
```
/root/.hermes  ✅ CORRECT
```

**Impact:** All `Path.home() / ".hermes" / "something"` resolves to non-existent path.

**Fix:** Always use absolute path constant:
```python
HERMES_ROOT = Path("/root/.hermes")  # NOT Path.home()
```

**Affected files:**
- `ilma_hermes_skills_router.py`
- `ilma_kanban_integration.py`

## References

- `references/path-home-bug-2026-05-19.md` — Path.home() workaround details
- `references/hermes-skills-integration-2026-05-19.md` — Full session notes, integration details, auto-detection examples

## Related Skills

- `ilma-evolution` — ILMA self-improvement system
- `devops/kanban-orchestrator` — Hermes Kanban orchestrator
- `devops/kanban-worker` — Hermes Kanban worker