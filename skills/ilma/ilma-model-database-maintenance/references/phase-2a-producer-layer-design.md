# Phase 2A — Producer Layer Foundation Design
**Date:** 2026-06-10
**Phase:** 2A — Audit + Design (NO CODING mode)
**Source:** `/root/shared-memory/ilma/reports/2026-06-10-phase-2a-producer-layer-design.md`

---

## Quick Reference (Condensed from Full Design)

### Producer Layer Architecture

```
EXTERNAL SOURCES (AA Leaderboard, Provider APIs, Runtime Logs)
         ↓
    BENCHMARK ENGINE → model_benchmarks (per-source benchmark records)
         ↓
    INTELLIGENCE ENGINE → model_intelligence (composite scores, tiers)
         ↓
    AUDIT + DIFF ENGINE → model_audit (immutable event log)
         ↓
    RUNTIME CONSUMERS (ilma_model_router, capability_registry, orchestrator)
```

### 5-Collection Ownership Map

| Collection | Owner | Producer | Refresh Cadence | Stale |
|-----------|-------|----------|-----------------|-------|
| `llm_providers` | SOT_MGMT | credential_sync | Event-driven | Never |
| `providers` | Audit | _meta migration | Event-driven | Never |
| `models` | Discovery | provider_sync | **12h** | **24h** |
| `model_benchmarks` | Benchmark | benchmark_engine | **24h** | **72h** |
| `model_intelligence` | Intelligence | intelligence_engine | **48h** | **7d** |

### Intelligence Scoring (5 Dimensions → composite_score)

```
quality_score  = max(AA_intelligence, AA_coding × 0.85, heuristic) × provider_trust
speed_score    = max(TPS_normalized, latency_inverted) + reliability_factor
cost_score     = is_free ? 1.0 : inverted_normalized(blended_price)
context_score  = log2_normalized(context_window)
free_tier      = is_free ? 1.0 : 0.2

Weights: quality=0.40, cost=0.25, speed=0.15, context=0.12, free=0.08
Tier:    S>=0.85, A>=0.70, B>=0.50, C>=0.30, D<0.30
```

### Benchmark Sources

| Tier | Source | Trust | Refresh |
|------|--------|-------|---------|
| 1 | AA Leaderboard (artificialanalysis.ai) | HIGH 0.90 | Weekly |
| 2 | Live Benchmarks (lm-eval-harness) | HIGH 0.95 | Monthly |
| 3 | Provider API (price/context) | MEDIUM 0.80 | 12h |
| 4 | Runtime Metrics (TPS/latency) | HIGH 0.90 | 24h |

### Implementation Phases

| Phase | Mission | Duration |
|-------|---------|----------|
| 2B | Benchmark Engine → populate model_benchmarks | 16-24h |
| 2C | Intelligence Engine → populate model_intelligence | 12-16h |
| 2D | Audit + Diff + Freshness | 20-28h |
| 3 | Materialization Pipeline (replace MASTER.json) | 16-24h |
| 4 | Validation + Deprecate MASTER.json | 12-16h |

### Key Design Decisions

1. **model_benchmarks = multi-source container** (1 doc per provider+model+source)
2. **model_intelligence = derived aggregate** (1 doc per provider+model)
3. **Separate model_audit collection** (NOT embedded in documents)
4. **AA names → model_id via fuzzy match** (confidence 0.75 vs 0.90 direct)
5. **Fallback: heuristic scoring** when model_benchmarks empty (provenance = HEURISTIC_FALLBACK, confidence 0.30)
6. **MASTER.json stays as fallback** until Phase 3 complete
7. **Audit-first, no-coding for architecture migrations** (Bos rule)

---

## Gap Analysis Summary (from Phase 1.5)

**Overall Readiness: 3.5/9 (39%) — NOT Production Ready**

| Blocker | Impact | Fix |
|---------|--------|-----|
| model_benchmarks EMPTY | No benchmark scores | Phase 2B |
| model_intelligence EMPTY | No composite scores | Phase 2C |
| No audit trail | Cannot explain changes | Phase 2D |
| No freshness mechanism | Data goes stale | Phase 2D |
| Schema mismatch (models) | 5 fields written not in schema | Fix models.schema.json |
| Runtime uses MASTER.json | Legacy coupling | Phase 3 |

---

## Schema Mismatch (models)

`provider_sync.py` writes 18 fields, `models.schema.json` defines 15. Gap:

**Written but NOT in schema:** `_sot_last_sync`, `capabilities`, `price_per_m_input`, `price_per_m_output`, `refreshed_at`, `specialization`

**In schema but NEVER written:** `max_output_tokens`, `modality`, `input_modalities`, `output_modalities`, `deactivation_reason`

→ Must reconcile before Phase 2B production use.

---

## Audit Event Taxonomy (selected)

| Category | Event Type | Trigger |
|---------|-----------|---------|
| MODELS | MODEL_ADDED, MODEL_REMOVED, MODEL_RENAMED, PRICE_CHANGED, CONTEXT_CHANGED | Discovery |
| BENCHMARKS | BENCHMARK_ADDED, BENCHMARK_UPDATED, BENCHMARK_STALE, CONFIDENCE_RECALCULATED | Benchmark Engine |
| INTELLIGENCE | INTELLIGENCE_COMPUTED, INTELLIGENCE_RECALCULATED, SCORE_TIER_CHANGED, FALLBACK_ACTIVATED | Intelligence Engine |
| SYSTEM | PROVIDER_KEY_INVALID, SOT_BACKUP_CREATED, SCHEMA_MIGRATION | System |

---

## Rollback Strategy

| Phase | Rollback Method | Time |
|-------|----------------|------|
| 2B | Delete by benchmark_source | 5 min |
| 2C | Delete all model_intelligence | 2 min |
| 2D | Apply retention early | 10 min |
| 3 | Restore MASTER.json + revert config | 10 min |

---

## Full Document

Full design: `/root/shared-memory/ilma/reports/2026-06-10-phase-2a-producer-layer-design.md` (24KB)