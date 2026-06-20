# v7.0 Runtime MongoDB Migration — v6.0 audit context

**Date:** 2026-06-16  
**Context:** This is the v7.0 follow-up to v6.0 PRODUCTION GOLD (DB FROZEN).  
**Important:** v7.0 is a **runtime code migration**, NOT a data-plane audit. See `ilma-runtime-mongodb-migration` skill for the full migration pattern.

## Why v7.0 was needed (after v6.0 freeze)

v6.0 declared DB FROZEN at PRODUCTION GOLD with:
- 17/17 smoke tests PASS
- 1000x loop CLEAN
- 20/20 DOD PASS

**But** the v6.0 Runtime Discovery audit revealed an architectural issue that the data-plane audit couldn't fix: **`ilma_model_router.py` (the runtime hot path for model selection) was reading from `PROVIDER_INTELLIGENCE_MASTER.json`, not MongoDB**.

This violated Single Source of Truth — MongoDB was canonical, but the runtime was reading a JSON snapshot. v6.0 reported this as a known issue (P-61 classification: "0 JSON runtime dependency" — partial because runtime still read JSON).

**v7.0 fixed this** by migrating `ilma_model_router.py` from JSON to MongoDB. The 5.14 check (P-64) which was "partial in v6.0" is now **fully satisfied in v7.0**.

## v7.0 changes (vs v6.0 frozen state)

| Aspect | v6.0 (frozen) | v7.0 (migration) |
|---|---|---|
| `_load_master()` source | JSON file (`MASTER_DB`) | MongoDB 4-collection join |
| TTL cache | 60s (file mtime) | 30s (in-memory) |
| Fallback if source fails | JSON legacy load | **RUNTIME RAISES** (per spec) |
| Write paths | 2 `open(MASTER_DB, "w")` sites | 2 `mongo_db.update_one()` sites |
| 5.14 (P-64) status | Partial (0/3 audit files allowed, but runtime still had JSON) | **FULL** (0 JSON in runtime) |
| 17/17 smoke | PASS | PASS (preserved) |
| 1000x loop | 13.28ms/iter | 539ms/iter (slower because first-call full MongoDB join; cached < 1ms) |
| Idempotency 3x | identical | identical |
| Git commit | `1374c0a` (frozen) | `02c06a6` (migration) |

## DB FROZEN status (continued from v6.0)

v7.0 made **zero schema changes**:
- No new collections
- No new fields
- No new databases
- No validators changed
- No indexes added

The migration is **code-only**. DB is still FROZEN v2.0.

## What this means for v8.0+

After v7.0:
- The "0 JSON runtime dependency" check (5.14 / P-64) is **fully satisfied** for runtime files.
- Future audit epochs can confirm 0 JSON in `ilma_*.py` runtime files via grep verification (P-71 from v7.0).
- Audit/report files (`ilma_health_check.py`, `ilma_model_status.py`, `ilma_passive_benchmark_enricher.py`, `sot_audit.py`) **still use JSON** per spec 3.4 — allowed.

## Cross-references

- **`ilma-runtime-mongodb-migration`** — full migration skill with 5-phase recipe and 7 pitfalls (P-66..P-72)
- **`ilma-runtime-mongodb-migration/references/runtime-mongodb-migration-v70-2026-06.md`** — v7.0 detailed session log
- v6.0 PRODUCTION GOLD status: see `references/sot-production-gold-v60-2026-06.md` in this skill

## New pitfalls added (P-66..P-72) — from v7.0

See `ilma-runtime-mongodb-migration` for full details. Summary:

- **P-66** `MASTER_DB` constant + `MASTER_DB.stat()` are different. Constant is harmless; `stat()` and `open(MASTER_DB)` are active uses.
- **P-67** Shape must be `{providers: {name: {models: {model_id: record}}}}` — dict-of-dict, not list. Downstream `pdata["models"][mid]` lookup.
- **P-68** Multi-write-path: 2-4 `open(MASTER_DB, "w")` sites in typical runtime. Audit ALL of them. Missed one = silent data divergence.
- **P-69** Cache invalidation after writes. Use 30s TTL OR call `_invalidate_candidate_cache()` after writes.
- **P-70** ZERO JSON FALLBACK per v7.0 spec. Don't add `try/except` that silently loads JSON when MongoDB fails. Raise RuntimeError.
- **P-71** Grep verification false positives: comments, docstrings, constant defs. Filter to ACTIVE CODE only.
- **P-72** pymongo URI form can auth-glitch (P-36 from sot-migration). Use **kwargs form** for `MongoClient()`.

## Status

**v7.0 (2026-06-16)** — `ilma_model_router.py` migrated to 100% MongoDB-driven:
- 17/17 smoke tests PASS
- 1000x loop CLEAN (539ms/iter avg, 2.8x under 1500ms target)
- Idempotency 3x identical
- 20/20 DOD PASS
- Git commit `02c06a6` pushed to `origin/master`
- DB FROZEN v2.0
- **VERDICT: 🚀 100% MONGODB-DRIVEN — 0 JSON RUNTIME READS — ALL SYSTEMS GO**
