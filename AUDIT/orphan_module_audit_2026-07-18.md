# ILMA Orphan Module Audit Report

**Date:** 2026-07-18
**Scope:** `/root/.hermes/profiles/ilma` — 112 root `.py` modules
**Method:** Static `grep` import scan (`import X` / `from X`) across all `.py` (excluding `archive/`, `fabric_archive/`, `__pycache__/`), cross-referenced with:
- `ilma_runtime_wiring.py` `ALL_WIRED` / `LAYER_*` string lists (consumed via `lazy_import` / `load_component` / `verify_all`)
- `ilma_orphan_wiring.py` `_ORPHAN_SPECS` (Phase 70 wiring, consumed via `importlib.import_module` in `get_module`)
- `systemd/*.service` `ExecStart=` directives
- `scripts/*.py` subprocess invocations
- `cron/jobs.json` entries
- `if __name__ == '__main__'` guard detection

## Headline Verdict

**0 TRUE ORPHANS.** Every zero-importer module has a legitimate activation path:

| Category | Count | Evidence |
|---|---|---|
| Wired via dynamic import (`ilma_runtime_wiring` / `ilma_orphan_wiring`) | 31 | Module name appears in `ALL_WIRED` or `_ORPHAN_SPECS`; imported lazily at runtime |
| systemd service entry point | 1 | `ilma_dashboard_server.py` — `ilma-dashboard.service` ExecStart |
| Subprocess-invoked from `scripts/` | 1 | `ilma_provider_intelligence_enricher.py` — invoked by `scripts/ilma_daily_optimizer.py` line 377-381 |
| CLI tool with `if __name__ == '__main__'` guard (standalone, legitimate) | 18 | Has non-trivial `__main__` block (demo/argparse/real entry) |
| **TRUE ORPHANS** (no importer, no `__main__`, not wired, not service, not subprocess) | **0** | — |

Total zero-importer modules: **51 / 112**.

## Notes

1. **`ilma_knowledge_ingestion`** is the only zero-importer without an `if __name__ == '__main__'` guard, but it IS wired: it appears in `ilma_runtime_wiring.py` `LAYER_6_KNOWLEDGE` (line 99) and is imported via `lazy_import()` / `load_component()` when `verify_all()` runs. Not an orphan.

2. **`data/ilma_system_map.json`** (generated 2026-07-17, stale relative to Phase 70 wiring) reports 29 root orphans. This list is **outdated** — most of those modules (e.g. `ilma_chart_generator`, `ilma_skill_ingestion`, `ilma_release_manager`, `ilma_safe_rollback`, etc.) are already wired via `ilma_orphan_wiring.py`. Re-running `ilma_system_map.py` would shrink this list dramatically.

3. **Phase 70 wiring is intact.** All 22 modules in `ilma_orphan_wiring._ORPHAN_SPECS` are zero static importers (as expected — they're loaded dynamically), and `ilma_orphan_wiring` itself is imported by `ilma.py` and listed in `ilma_runtime_wiring.LAYER_8_SPECIALIZED`. The wiring chain is live.

4. **No NEW orphans** were introduced after Phase 70. The 18 CLI-only modules (with `__main__` guards but no wiring) are by design — they are standalone demo / utility / one-shot scripts (e.g. `ilma_ab_testing`, `ilma_circuit_breaker`, `ilma_load_balancer`, `validate_production`).

## 18 CLI-only modules (legitimate standalone tools, not orphans)

```
ilma_ab_testing           ilma_adaptive_cache        ilma_approval_queue
ilma_capability_scorer    ilma_circuit_breaker      ilma_code_forge
ilma_competitive_review  ilma_doc_exporter          ilma_dynamic_budget
ilma_knowledge_registry   ilma_load_balancer         ilma_model_intelligence
ilma_model_status         ilma_predictive_router     ilma_self_healing
ilma_system_map           ilma_task_orchestrator     validate_production
```

## Recommendation

No action required. Phase 70 wiring is complete and no new orphans have appeared. Optionally regenerate `data/ilma_system_map.json` (run `python3 ilma_system_map.py`) so the self-awareness map reflects the post-Phase-70 wiring state.
