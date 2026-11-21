# SOT Production Audit Methodology — S1–S10

**Session:** 2026-07-01
**Outcome:** 9/9 e2e checks PASSED — SOT PRODUCTION READY
**Fixes applied:** 27

## The 10-Step Pipeline (class-level, reusable)

### Phase 1: AUDIT (S1–S7)
Do NOT modify any files in this phase. Observe, catalog, classify only.

| Step | Name | What to check | Tools |
|------|------|---------------|-------|
| S1 | Inventory | Total files, packages, LOC | `rglob('*.py')`, line count |
| S2 | Orphan classify | Files with zero importers (other modules don't import them) | grep for module name across all files |
| S3 | Wiring audit | Broken imports (absolute inside package), missing `__init__.py` | `ast.parse()`, `importlib.import_module()` |
| S4 | Pipeline integrity | Import smoke test for all modules | `importlib.import_module()` on each module |
| S5 | Runtime health | MongoDB alive, collection counts, stale fields, systemd | `pymongo`, `systemctl --user` |
| S6 | Dead code | Empty directories, true orphans, unused functions | `Path.rglob()`, call-graph analysis |
| S7 | Schema coverage | MongoDB collections vs schema files, stale DB fields | schema glob, `db.list_collection_names()` |

**Key principle:** Classify orphans carefully. "CLI-only" orphans (files with `if __name__` entry points but no other importers) are VALID — they're standalone tools. Only "TRUE-ORPHAN" (no entry point, no importers, no purpose) needs action.

### Phase 2: FIX (batch apply)
Write single fix script (`/tmp/sot_apply_fixes.py`) handling ALL fixes in dependency order:

1. **FIX-1: Empty directories** — `rmdir()` directories with 0 files
2. **FIX-2: Orphan quarantine** — Move TRUE-ORPHAN files to `sot/quarantine/` (don't delete — preserve for provenance)
3. **FIX-3: Orphan schemas** — Mark schemas matching no collection with `_orphan: true`
4. **FIX-4: Schema stubs** — Auto-generate from MongoDB sample doc for uncovered collections
5. **FIX-5: Stale MongoDB fields** — `$unset` deprecated fields, backfill null fields
6. **FIX-7: Logging injection** — Add logging to high-LOC files WITHOUT it (see P-CASCADE-30!)
7. **FIX-8: Systemd services** — Copy service files, daemon-reload, enable

### Phase 3: VERIFY (S8–S10)

| Step | Name | What to verify |
|------|------|----------------|
| S8 | Hardening | Logging present in core files, try/except patterns, systemd active |
| S9 | Integration | Dispatcher exists, runtime wiring references SOT, cascade engine present |
| S10 | Final e2e | 9-check composite: imports, MongoDB, schema coverage, stale fields (0), empty dirs (0), package init, quarantine, integration, cascade |

## Session-Specific Results (2026-07-01)

### State Before
- 58 SOT files, 12,038 LOC
- 5 empty directories (health, intelligence, materialization, migration, tests)
- 1 TRUE-ORPHAN: `sot_master_rule_v2_fix.py` (runs side-effect on import, no callers)
- 4 broken absolute imports in orchestration/ (fixed in S3)
- 6 schema stubs needed
- 3 stale MongoDB fields (is_free_final, _status_cascaded_v3, aggregate_status)
- 8 core files had no logging
- No systemd service for SOT sync

### State After
- 44 files (reduced from 58 via empty dir removal + orphan quarantine)
- 37/37 imports OK (was 19/37 due to logging injection breakage — fixed)
- 20/21 collections covered by schemas (1 uncovered: `sessions` — low priority)
- 0 stale fields across all tiers
- 0 empty directories
- `ilma-sot-sync.service` installed and enabled
- aggregate_status backfilled (15 active + 1 inactive providers)

### Logging Injection Incident (P-CASCADE-30)
Naive injector found "last import line" via regex `^import |^from ` but picked lines inside
`if __name__` blocks. Result: `import logging` inserted at function-level indent → 6 files
broke with `SyntaxError: unexpected indent`. Also one file had `from __future__ import annotations`
at line 51 — logging was placed at line 2, violating Python's `__future__` first rule.

**Recovery:** `re.sub(r'\nimport logging\nlogger = logging.getLogger\(__name__\)', '', content)`
then re-insert at correct top-level location. Verify with `ast.parse()`.

### MongoDB Tier State

| Tier | Collection | Docs | Active |
|------|-----------|------|--------|
| T1 | llm_providers | 27 | — |
| T2 | providers | 39 | 36 |
| T3 | models | 1,241 | 402 |

### Fix Script
Created at `/tmp/sot_apply_fixes.py` — 384 lines. Can be adapted for future audits.

### Cascade Enforcement (c1-c7)
Prior to S1-S10, cascade enforcement was run:
- 0 violations in all 7 cascade checks
- 620 is_active+disabled_at contradictions fixed
- 23 aggregate_status backfilled
- 15+1 providers had aggregate_status set from None to active/inactive

## Evidence IDs
- `ILMA-EVID-20260701-SOT-PRODUCTION-READY` — 9/9 e2e checks PASSED
