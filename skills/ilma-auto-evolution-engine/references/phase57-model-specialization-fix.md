# Phase 57: Model Specialization DB Key Mismatch Fix
**Date:** 2026-05-11
**Version:** ILMA v3.26

---

## What Happened

During MASTER_TARGET_SELF_OPTIMIZATION_V5 execution, validation revealed 16/16 task categories in the model specialization database reported their primary models as "NOT IN models database" — even though those models were clearly accessible via the router.

## Root Cause

Model ID format mismatch:
- Router (`get_best_model()`) returns: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
- Provider DB internal key: `01-ai/yi-large` (nvidia provider only prefixes with provider when key doesn't already have slash)
- spec_db was keyed using: `f"{prov_name}/{model_id}"` format which doesn't match what router returns

## Fix Applied

```python
# Build models dict using model_id as-is (what router returns)
for prov_name, prov_data in providers_info.items():
    for model_id, model_info in prov_models.items():
        new_models[model_id] = {...}  # NOT f"{prov_name}/{model_id}"

# Build task_models via router query
primary = get_best_model(route_to)
new_task_models[cat] = {
    "primary_model": primary.get('model_id'),  # Router's returned ID
    ...
}
```

Result: 16/16 primary models now verified in database, 0 model reference issues.

## Also Fixed

1. **Evidence ledger schema migration**: 42 records, new required fields (evidence_id, claim, evidence_type, source_path, command_or_test, result, timestamp, status, caveat), NARA/NAILA/ZARA sanitized to DEPRECATED_AGENTS
2. **Free model allowlist**: 19 provider-level entries → 1088 full model IDs

## Validation: 7/7 PASS

- model_specialization_db ✅
- capability_registry ✅
- evidence_ledger ✅
- free_model_only ✅
- 16_task_routing ✅
- deprecated_cleanup ✅
- production_smoke ✅

## Key Pattern

When verifying a database against routing output, build the verification DB by querying the router — never assume internal key formats align without testing.

## Next
PHASE 58: Live benchmark runner to upgrade evidence_level from PROVIDER_DOC_BASED to LIVE_BENCHMARKED.