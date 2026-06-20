# attic/ — quarantined dead code (2026-06-20 audit)

Modules here have **zero importers** and are not in `ilma_runtime_wiring.py`,
`ilma_orphan_wiring.py`, or the capability registry. They were duplicated/alternate
implementations that the canonical path does not use. Kept (not deleted) for reference.

- `ilma_system.py` — alternate entrypoint/router+client+scheduler stack; superseded by
  `ilma_orchestrator.py` (canonical) + the systemd gateway. Referenced a non-existent
  `scripts/ilma_benchmark_autoloop.py`.
- `ilma_unified_model_router.py` — old JSON-file-based `UnifiedModelRouter` (v3.0),
  superseded by the live MongoDB-driven `ilma_model_router.ILMAUnifiedRouter`.
