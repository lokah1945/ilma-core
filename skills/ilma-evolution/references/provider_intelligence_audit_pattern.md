# Provider Intelligence Deep Rebuild — Lessons Learned

## Session Context
- Date: 2026-05-11
- Task: MODEL_PROVIDER_INTELLIGENCE_DEEP_REBUILD
- ILMA v3.26

## Key Discoveries

### 1. Artificial Analysis Data Exists (Was Underutilized)
- Location: `home/.cache/ayda/benchmark_research/artificial_analysis_llms_models_raw.json`
- 20 records from `https://artificialanalysis.ai/api/v2/data/llms/models`
- Fetched 2026-05-01 (age: 9 days)
- **Previously classified as DRY_RUN_BENCHMARKED — WRONG**
- **Reclassified as PASSIVE_PROVIDER_BENCHMARKED** — third-party benchmark with real scores
- Attribution required per AA terms

### 2. Source Classification Was Wrong
Before rebuild:
- All 22 DRY_RUN_BENCHMARKED
- All specialization scores INFERRED

After rebuild:
- PASSIVE_PROVIDER_BENCHMARKED: 20 (AA real scores)
- DRY_RUN_BENCHMARKED: 22 (pipeline only)
- NO_BENCHMARK: 1116
- LIVE_RUNTIME_BENCHMARKED: 0
- INFERRED: 0 (AA provides real scores)

### 3. OpenRouter Source Classification
- `PROVIDER_INTELLIGENCE_MASTER.json` generated via `dynamic_catalog_scoring`
- Source type: OPENROUTER_API (not benchmark quality)
- Contains: model metadata, pricing, context lengths, availability
- NOT: quality benchmark scores

### 4. Provider Trust Scores Matter
- 15 providers with trust scores (nvidia=1.0, openrouter=0.9, minimax=0.85, etc.)
- `_select_best_provider()` handles 63 models available via multiple providers
- When same model available on multiple providers: select highest trust among free providers

### 5. Benchmark Router Patches Required
When patching router for evidence-aware scoring, two bugs encountered:
1. `bm_score * bm_confidence` fails when bm_score is None → fix with `bm_score_value = bm_score if bm_score is not None else 0.0`
2. `"DRY_RUN_BENCHMARKED" if bm_score > 0` fails with None → fix by using `bm_evidence` variable from lookup

## Provenance Files Found

| File | Classification | Purpose |
|------|---------------|---------|
| `home/.cache/ayda/benchmark_research/artificial_analysis_llms_models_raw.json` | ACTIVE_SOURCE | 20 AA benchmark records |
| `ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json` | ACTIVE_DATABASE | 1158 models, 16 providers |
| `ilma_model_router_data/benchmark_database.json` | ACTIVE_DATABASE | 42 benchmark records (merged) |
| `.deprecated/ilma_benchmark_scores.json` | DEPRECATED | 22 DRY_RUN records |
| `models_dev_cache.json` | CACHE | Provider cache (1.8MB) |
| `.env` | API_KEY_STORAGE | 29 API keys (don't print) |

## Count Reconciliation

| Metric | Value | Source |
|--------|-------|--------|
| Raw model IDs (provider DB) | 1158 | Provider DB |
| Free in provider DB | 266 | Raw count |
| Usable free (spec_db) | **239** | After filtering |
| Bos ~300 estimate | — | Likely aliases (4319) + rough estimate |
| Provider variants | 63 | Same model via multiple providers |

## Router Scoring Formula (Evidence-Aware)

```
final_subagent_route_score =
  0.24 * specialization_score
+ 0.18 * passive_benchmark_score (× evidence_weight)
+ 0.14 * provider_trust_score
+ 0.12 * availability_score
+ 0.10 * context_fit_score
+ 0.08 * cost_score
+ 0.06 * latency_score
+ 0.05 * evidence_confidence_score
+ 0.03 * fallback_strength_score
- paid_penalty_if_free_only
```

Evidence weights:
- PASSIVE_PROVIDER_BENCHMARKED: 1.0
- DRY_RUN_BENCHMARKED: 0.3
- NO_BENCHMARK: 0.0

## Key Patterns for Future Audits

### Source Discovery Pattern
When auditing provider/model databases:
1. Search for cache files (`home/.cache/`, `models_dev_cache.json`)
2. Check for benchmark research directories
3. Validate source type — metadata ≠ benchmark quality
4. Check evidence level before claiming quality

### Evidence Level Classification Pattern
1. If third-party benchmark with real scores → PASSIVE_PROVIDER_BENCHMARKED
2. If pipeline ran without live calls → DRY_RUN_PIPELINE_VERIFIED
3. If provider metadata only → PROVIDER_DOC_BASED or LIVE_METADATA_REFRESHED
4. If heuristic → HEURISTIC_ESTIMATED
5. If no source → UNVERIFIED or NO_BENCHMARK

### Never Overclaim
- Don't say "live benchmark" for passive third-party data
- Don't say "measured" for DRY_RUN pipeline
- Don't say "~300 free" — use 239 or 266
- Don't omit attribution when required
- Don't claim INFERRED when trusted source exists

## Files Modified

- `ilma_model_router.py`: Evidence-aware benchmark scoring, fixed None handling
- `ilma_model_router_data/benchmark_database.json`: Merged AA + .deprecated, proper schema
- `ilma_evidence_ledger.json`: +5 new records (60 total)
- `capability_registry.json`: Updated 4 capabilities

## Tests Passed

- 233 project tests
- `ilma.py validate` 6/6
- `ilma.py doctor` 9/9
- Production smoke EXIT 0
- 7 mutation tests
- 8 sub-agent route traces