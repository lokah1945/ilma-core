# ILMA Hermes Integration (2026-05-19)

## New Skill: `ilma-hermes-integration`

Session 2026-05-19 produced a new class-level skill for Hermes Agent integration.

**See:** `ilma-hermes-integration` skill

**Summary:**
- 684 Hermes skills auto-triggered via `HermesSkillsRouter` (ilma_hermes_skills_router.py)
- Hermes Kanban wrapper (ilma_kanban_integration.py)
- Fixed Path.home() bug → HERMES_ROOT=/root/.hermes
- Boot components: kanban (#11), hermes_skills (#12)
- Auto-detected skills in route_task() and run_capability_workflow()

## Bug: Path.home() Returns Wrong Value

Inside ILMA runtime, `Path.home()` → `/root/.hermes/profiles/ilma/home` (wrong).
Always use `HERMES_ROOT = Path("/root/.hermes")` for system paths.

**See:** `ilma-hermes-integration` skill for full details
