# Hermes Skills + Kanban Integration — 2026-05-19

**Session:** Phase-deep-dive Hermes integration
**Outcome:** ILMA now auto-triggers 684+ Hermes skills + Hermes Kanban board

## What was built

### 1. Hermes Skills Router (`ilma_hermes_skills_router.py`)
Auto-detects and triggers Hermes skills based on task context. Scans:
- `~/.hermes/skills/` (bundled Felo + Hermes skills)
- `~/.hermes/hermes-agent/skills/` (75 skills, 24 categories)
- `~/.hermes/hermes-agent/optional-skills/` (72 skills)

**Result:** 159 Hermes skills + 525 ILMA skills = 684 total accessible skills

**Router logic:**
1. Priority 1: ILMA_SKILL_TRIGGERS (explicit `ilma-*` patterns)
2. Priority 2: TASK_TO_SKILL_PATTERNS (keyword → category/skill)
3. Priority 3: context-based (task_type, domain from workflow)
4. Dedup by (skill_name, source), sort by confidence

**Key pattern fix:** Handle `category/skill` format (e.g., `research/arxiv` → look up `research` category then override to `arxiv` skill)

### 2. Hermes Kanban Integration (`ilma_kanban_integration.py`)
Wrapper for `hermes kanban` CLI (Hermes v0.13.0+):
- Task CRUD: create, show, list, complete, block, reclaim, reassign
- Heartbeat monitoring (zombie detection)
- Fan-out (parallel task delegation)
- Sequential pipeline execution
- Hallucination gate (pre-execution task validation)
- Retry budget tracking

### 3. ILMA.py Integration
- Boot: `kanban` (component #11) + `hermes_skills` (component #12)
- `route_task()`: auto-detect skills via `HermesSkillsRouter`
- `run_capability_workflow()`: also auto-detect skills
- `cmd_route()`: display detected skills + handle both workflow/direct output formats

## Critical Bug Fixed

`Path.home()` in ILMA runtime returns `/root/.hermes/profiles/ilma/home` (wrong).
Fix: Use `HERMES_ROOT = Path("/root/.hermes")` constant everywhere.

See: `references/path-home-bug-2026-05-19.md`

## Skills Auto-Detection Examples

| Task | Detected Skill |
|------|----------------|
| "plan feature implementation roadmap" | `plan` |
| "research paper writing machine learning" | `arxiv` |
| "playwright stealth browser automation" | `devops` |
| "github pull request code review" | `github` |
| "kubernetes debug pod crash" | `devops` |
| "ilma self-improve autonomous loop" | `ilma-autonomous-loops` |
| "yuanbao group member info" | `yuanbao` |

## Files Changed

- `ilma_hermes_skills_router.py` — new, 420 lines
- `ilma_kanban_integration.py` — new, 543 lines
- `ilma.py` — patched (boot components, route_task, run_capability_workflow, cmd_route)
- Git commit: `1cd292b`