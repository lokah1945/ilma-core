# ILMA Critical Patching Flow

## When to Use

When modifying critical files: router, core system, provider integration, or any file that could break ILMA's runtime if patched incorrectly.

## The Flow

1. **BACKUP FIRST** — Always backup before structural changes
   ```bash
   mkdir -p backups/ilma_codex_primary_backup_$(date +%Y%m%d_%H%M%S)
   cp -r scripts/ilma_codex_router.py scripts/ilma_codex_stdio.py scripts/ilma_codex_oauth.py backups/
   ```

2. **READ BEFORE PATCH** — Read current state, check for `name 'model' is not defined` errors, verify line numbers

3. **SMOKE TEST IMMEDIATELY** — After any patch, run a quick smoke test:
   ```python
   from scripts.ilma_codex_router import ILMACodexRouter
   router = ILMACodexRouter()
   ok, resp = router.send('Say: HELLO', chain='general')
   print(f'ok={ok}, resp={resp}')
   ```

4. **RUN FULL TEST SUITE** — Don't declare success until 21/21 tests pass:
   ```bash
   python3 -m pytest tests/test_phase56_ilma_cli.py -v --tb=line
   ```

5. **UPDATE SKILLS** — If patch succeeded and revealed new knowledge, patch the relevant skill

6. **RESTORE FROM BACKUP** — If patch breaks things:
   ```bash
   cp backups/ilma_codex_primary_backup_YYYYMMDD_HHMMSS/scripts/ilma_codex_router.py scripts/
   ```

## Lessons Learned (2026-05-11)

- `_start_session()` does NOT receive `model` as parameter — uses `self._current_model`
- `start_thread()` called with `self._current_model` not bare `model` variable
- Backup before EVERY structural change to router
- Test suite timeout must be 180-240s for Codex CLI tasks
- Sub-agent routing (`ilma_model_registry.py`) is SEPARATE from Codex routing (`ilma_codex_router.py`)