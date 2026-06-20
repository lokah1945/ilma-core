# MongoDB SOT 4-Collection TDD — Migration Design Template (2026-06-09)

**Source:** Phase 1 design session 2026-06-09 23:30 WIB. TDD authored for migration from `PROVIDER_INTELLIGENCE_MASTER.json` (4.4 MB, 2,465 models, 25 providers) to MongoDB native SOT at `mongodb://quantumtraffic:<pw>@172.16.103.253:27017/credentials`.

**Status:** TDD complete (14 files, 5,277 lines, ~190 KB). Phase 1.5 (schema setup) awaiting Bos approval. No code written, no collections created, no migrations executed.

**Master directory:** `/root/shared-memory/ilma/design/` — all 14 files referenced in `00-tdd-index.md`.

---

## 1. Bos-Mandated 4-Collection Design (DECISION-202/203)

**REJECTED alternatives:**
- ❌ Single collection (everything in one doc) — Bos: "Saya TIDAK menyetujui... Saya tidak ingin metadata model, benchmark, intelligence score, dan runtime health bercampur dalam satu dokumen besar. Saya ingin separation of concerns."
- ❌ 5+1 collection (`models` + `model_benchmarks` + `provider_intelligence` + `runtime_health` + 2 audit) — too many

**APPROVED 4 collections:**

| Collection | Role | Update cadence | Owner | Unique key | Size est. |
|------------|------|----------------|-------|------------|----------:|
| `llm_providers` | Credential registry | Manual (rare) | master_chief | `(provider, account_email)` | ~70 KB |
| `models` | Stable metadata | Cron 6h | ILMA discovery | `(provider, model_id)` | ~9.5 MB |
| `model_intelligence` | Benchmark + score + capability | Cron 24h | ILMA enrichment | `(provider, model_id)` | ~6.75 MB |
| `runtime_health` | Transient metrics + circuit breaker | Per call (TTL 7d) | ILMA health mgr | `(provider, model_id)` | ~3.1 MB |

**Separation of concerns rules:**
- **Credential layer** (llm_providers) ≠ **Model layer** (models, model_intelligence, runtime_health)
- **Stable** (models) ≠ **Enrichment** (model_intelligence) ≠ **Transient** (runtime_health)
- **Multi-account** (nvidia=3, openrouter=2 key_types) → ONE model doc per `(provider, model_id)`. Multi-account handled at credential layer, NOT model layer.

---

## 2. Mandatory TDD Structure (8 sections per Bos directive)

For each collection TDD, MUST include:

1. **Schema** — full field list with type, required/optional, rationale
2. **Indexes** — all indexes with name, keys, options (unique/TTL), per-index rationale
3. **Sample document** — realistic example with all common fields populated
4. **Query patterns** — 5-8 patterns with index used + latency target
5. **Estimated size** — per-doc bytes × count = total; index overhead

Plus 7 mandatory FLOW documents:
1. **Data lifecycle** — per-collection state machine, cross-collection invariants
2. **Migration flow** — Phase 0-6 with sub-steps
3. **Runtime query flow** — cold start, hot path, write-through, periodic refresh
4. **Materialized cache flow** — hourly batch regenerate MASTER.json from DB
5. **Rollback flow** — 4 levels (in-flight / per-doc / per-cron / per-phase / full DB)
6. **Failure recovery flow** — 5 categories (conn/read/write/runtime/materialize) + 5 degraded modes
7. **Master field mapping** — exhaustive 71-field MASTER.json → 4 collections table

---

## 3. Hourly Batch Materialize Cache (DECISION-209)

**Bos chose hourly batch over every-change refresh.** Reasons: stability, easy rollback, easy audit.

```
cron: 0 * * * * (hourly)
  ↓
materialize_cache.py
  ↓
1. Read db.models.find({is_active: True})
2. Read db.model_intelligence.find({is_recommended: True})
3. Read db.providers.find() for metadata
4. Build nested JSON (same shape as old MASTER.json format)
5. Validate (min 100 models, all providers have models)
6. Backup current MASTER.json to backups/PROVIDER_INTELLIGENCE_MASTER_<ts>.json
7. Atomic write: tmp.replace(MASTER_PATH) — never partial write
8. Git commit (optional, --no-git to skip)
  ↓
PROVIDER_INTELLIGENCE_MASTER.json (regenerated, read-only)
```

**Atomic write is mandatory:**
```python
TMP_PATH = MASTER_PATH.with_suffix(".tmp")
TMP_PATH.write_text(content)
TMP_PATH.replace(MASTER_PATH)  # atomic at filesystem level
```

**Auto-rollback on gate failure (integrated with existing `ilma_safe_build_and_push.sh`):**
- Validate via `ilma_sot_integrity.py --gate` (already exists from Phase 73)
- Exit 0 = push proceeds
- Exit 1 = auto-rollback to last known-good backup, push skipped
- Exit 2 = NO VALID BACKUP, manual intervention required

---

## 4. Two-Layer Schema Validation (DECISION-210)

**Defense in depth:** MongoDB native `$jsonSchema` + Python `jsonschema`.

**Layer 1: MongoDB native** (per collection, set at creation or via `collMod`):
```python
db.command({
  "collMod": "models",
  "validator": {
    "$jsonSchema": {
      "bsonType": "object",
      "required": ["provider", "model_id", "is_active", "is_free", "status", "discovered_at", "discovered_via"],
      "properties": {
        "provider": { "bsonType": "string", "minLength": 1, "maxLength": 100 },
        "model_id": { "bsonType": "string", "minLength": 1, "maxLength": 200 },
        "is_active": { "bsonType": "bool" },
        "is_free": { "bsonType": "bool" },
        "status": { "enum": ["active", "deprecated", "quota_exceeded", "disabled", "experimental"] },
        "discovered_via": { "enum": ["openrouter_models_list", "provider_direct", "/v1/models", "manual", "heuristic_derived"] },
        "context_window": { "bsonType": ["int", "null"], "minimum": 0, "maximum": 10000000 }
      }
    }
  },
  "validationLevel": "moderate",  # existing docs not checked
  "validationAction": "warn"      # Phase 1.5 transitional
})
```

**Layer 2: Python `jsonschema`** (in adapter layer, before each write):
- Runs before DB write
- More detailed than MongoDB native (range checks, format checks, cross-collection rules)
- Logs validation failures for audit

**Phase 1.5 → Phase 2 transition:** start with `validationAction: "warn"`, switch to `"error"` after Phase 2 migration verified.

---

## 5. AA Benchmark Mapping Design Only (DECISION-208)

**Bos mandate:** design mapping without fetching. Schema-ready, no actual AA data yet.

**AA API field → `model_intelligence.benchmarks.artificial_analysis.*`:**

| AA API field | Target field | Notes |
|--------------|--------------|-------|
| `artificial_analysis_intelligence_index` | `intelligence_index` | 0-100 scale |
| `artificial_analysis_coding_index` | `coding_index` | |
| `artificial_analysis_math_index` | `math_index` | |
| `mmlu_pro`, `gpqa`, `livecodebench` | same field name | |
| `output_speed_tps` | `score.breakdown.raw_speed_tps` | (performance metric, NOT in benchmarks dict) |
| `latency_first_chunk_sec` | `score.breakdown.raw_latency_first_chunk` | |
| `price_per_m_input` | `pricing.input_per_m` | (pricing, NOT in benchmarks) |
| `price_per_m_output` | `pricing.output_per_m` | |
| `context_window` | (NOT in `model_intelligence` — already in `models.context_window`) | Avoid duplication |

**Benchmarks dict keyed by source name** (multi-source merge):
```json
"benchmarks": {
  "artificial_analysis": {
    "intelligence_index": 60.2, "coding_index": 59.1, "math_index": null,
    "mmlu_pro": null, "gpqa": null, "livecodebench": null,
    "evidence_type": "LIVE_RUNTIME", "fetched_at": ISODate("...")
  },
  "openrouter": { "context_length": 128000, "evidence_type": "PROXY", "fetched_at": ISODate("...") },
  "passive": { "calls_total": 0, "evidence_type": "PASSIVE", "fetched_at": ISODate("...") }
}
```

---

## 6. Cron Audit (DECISION-207) — Audit Only, No Fix

**3 of 4 cron jobs broken. Common root cause:** `no_agent=true` jobs with `prompt` field + relative `script` path both cause failures.

| Job ID | Schedule | Last Run | Status | Fix |
|--------|----------|----------|--------|-----|
| `bf9ad9925449` | `0 0,12 * * *` | 2026-06-05 12:00:31 | 🔴 SCRIPT NOT FOUND | Remove `prompt`, use absolute `script` path |
| `77a171f68d82` | `*/15 * * * *` | 2026-05-23 20:00:33 | 🔴 BLOCKED scanner | Same fix |
| `a115de75d3ef` | `0 * * * *` | 2026-06-04 13:21:40 | 🟡 FAILED last | Investigate daemon log |
| `2e8463c3e57f` | `0 9 * * *` | 2026-06-05 06:00:27 | ✅ OK | – |

**Fix effort:** ~1 hour total (1 line per job — change `prompt` to empty + use absolute `script` path).

**Risk:** LOW.

**Audit report:** `/root/shared-memory/ilma/design/01-cron-reliability-audit.md` (217 lines, full per-job root cause, impact, fix effort, risk).

---

## 7. Phase Plan (Per Bos, 6 Phases)

| Phase | Work | Duration | Bos approval needed |
|-------|------|---------:|-------------------|
| 0 | Observation | DONE 2026-06-09 | – |
| 1 | TDD | DONE 2026-06-09 | – |
| **1.5** | **Schema setup (validators + indexes + TTL)** | **0.5-1 day** | **NEEDED NOW** |
| 2 | Populate from MASTER.json (2,465 models) | 1-2 days | auto-approve after 1.5 |
| 3 | Refactor 4 writers (manager, router, enricher, health mgr) | 2-3 days | check-in |
| 4 | Runtime integration (DB + MASTER.json dual) | 1 day | auto-approve |
| 5 | Deprecate MASTER.json (after 1+ month stable) | TBD | needed |
| 6 | Cleanup (api_key.json → vault) | 1 day | needed |

**Total coding:** 1-2 weeks. **Total to MASTER.json deprecation:** 1.5-2 months.

---

## 8. 4-Phase Rollback Strategy

| Level | Time | Trigger | Action |
|-------|-----:|---------|--------|
| Level 0: don't write | 0s | preventive | Skip write |
| Level 1: per-doc | <5s | bad doc detected | `replace_one` with original |
| Level 2: per-cron batch | <30s | cron polluted | `update_many` or `delete_many` by `enriched_by` tag |
| Level 3: per-phase | <5min | migration failed | revert git + re-run previous phase |
| Level 4: full DB restore | 5-15min | disaster | `mongorestore` from `mongodump` |

**MANDATORY before any migration:**
```bash
mongodump --host 172.16.103.253 --db credentials \
          --out /root/backup/mongo_<DATE>_pre_<PHASE>
```

**MANDATORY tag all migration docs:** `enriched_by = "ILMA_<PHASE>_<VERSION>"` for selective rollback.

---

## 9. Failure Recovery (5 Categories)

| Category | Recovery strategy |
|----------|-------------------|
| Connection (MongoDB down) | 3x retry with exponential backoff (1s, 2s, 4s) → cache fallback → alert |
| Read (doc not found, validation fail, slow query) | Skip + log + continue; use cache for hot path |
| Write (validator reject, E11000 dup, disk full) | E11000 expected (idempotent); validator reject = log + skip; disk full = alert |
| Runtime (timeout, 401/403/429/5xx, content filter) | Record in runtime_health; if 3+ consecutive → open circuit breaker |
| Materialize (0 docs, backup fail, git fail, gate fail) | Abort + alert; auto-rollback to last backup on gate fail |

**5 degraded modes (graceful degradation):**
- Mode 1: Full DB (everything works)
- Mode 2: DB slow but available (cache priority, periodic refresh paused)
- Mode 3: DB unavailable, cache available (in-memory + write buffer)
- Mode 4: DB unavailable, no cache (fall back to MASTER.json if Phase 4)
- Mode 5: Everything down (hard fail with clear error)

---

## 10. Cross-Collection Invariants

1. `models[provider=X]` exists → `llm_providers` must have at least one doc with `provider=X`
2. `model_intelligence[(provider, model_id)]` exists → `models[(provider, model_id)]` must exist
3. `runtime_health` exists → `models.is_active=true` (TTL auto-cleanup if not)
4. `model_intelligence.score.composite` is DETERMINISTIC (same inputs → same output)
5. `models.price_*_per_m` ≈ `model_intelligence.pricing.*` (acceptable lag: 24h, one enrichment cycle)

---

## 11. Key Decision Points Pending Bos (from this TDD)

1. **MASTER.json in git or gitignore?** 105 MB/day growth concern
2. **TTL strictness:** 7 days default
3. **Validation:** `validationLevel: "strict"` vs `"moderate"`
4. **Cron fix timing:** Phase 1.5 or Phase 3?
5. **URL drift scope:** Fix all 11/25 broken or scope?
6. **AA fetch scope:** All 2,465 or top 100 by tier?
7. **Schema versioning:** `version` field or git tag?
8. **Backwards compat:** Keep `model_health_state.json` for 1 week after Phase 3?

---

## 12. TDD File Index (full session output)

| File | Lines | Topic |
|------|------:|-------|
| `00-tdd-index.md` | 156 | Index, decision tracker, unresolved items |
| `01-cron-reliability-audit.md` | 217 | DECISION-207 audit |
| `02-decisions-201-211-applied.md` | 181 | Decisions summary |
| `03-llm-providers-collection.md` | 294 | `llm_providers` TDD |
| `04-models-collection.md` | 428 | `models` TDD |
| `05-model-intelligence-collection.md` | 533 | `model_intelligence` TDD + AA mapping |
| `06-runtime-health-collection.md` | 458 | `runtime_health` TDD + circuit breaker |
| `07-data-lifecycle.md` | 272 | Lifecycle, invariants |
| `08-migration-flow.md` | 410 | Phase 0-6 detail |
| `09-runtime-query-flow.md` | 401 | Cold start, hot path, write-through |
| `10-materialized-cache-flow.md` | 495 | Hourly batch materialize |
| `11-rollback-flow.md` | 373 | 4-level rollback |
| `12-failure-recovery-flow.md` | 489 | 5 failure categories, 5 degraded modes |
| `13-master-field-mapping.md` | 570 | Exhaustive MASTER.json → 4 collections |

**Total:** 5,277 lines, ~190 KB. All in `/root/shared-memory/ilma/design/`.

---

## 13. Pattern for Future SOT/Architecture Migrations

When Bos asks for ANY architecture migration in the future, follow this exact pattern:

1. **Phase 0: Observation only** — list existing system, NO design yet
2. **Phase 1: 9-priority audit (per Bos mandate)** — dependencies, data flow, existing engines, code health, risk, before any design
3. **Phase 1.5: TDD only** — schemas, indexes, lifecycle, migration flow, runtime flow, cache flow, rollback, failure recovery
4. **Bos approval** — CONDITIONAL before any implementation
5. **Phase 2: Populate** — one-time data migration
6. **Phase 3: Refactor writers** — preserve logic, swap I/O
7. **Phase 4: Runtime integration** — dual mode (old + new)
8. **Phase 5: Deprecate old** — after 1+ month stable
9. **Phase 6: Cleanup** — remove old artifacts

**CRITICAL: Bos will reject designs that violate separation of concerns.** Never propose single-collection designs for multi-domain data. Always separate by:
- Layer (credential vs model vs runtime)
- Update cadence (stable vs enrichment vs transient)
- Owner (master_chief vs ILMA)
