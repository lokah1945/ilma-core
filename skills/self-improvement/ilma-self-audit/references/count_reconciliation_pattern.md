# Count Reconciliation Pattern

**Lesson from PROVIDER_MODEL_DATABASE_AND_BENCHMARK_USAGE_AUDIT (2026-05-11)**

## The Problem

Bos said "around 1000 model IDs, about 300 should be free/usable." ILMA found:
- Provider DB: 1158 raw models, 266 free raw
- spec_db: 1088 models, 239 free usable

The discrepancy (239 vs ~300) must be explained honestly, not assumed correct.

## The Reconciliation Table Template

```python
def count_reconciliation():
    """
    Always build this table when counts don't match prior claims.
    """
    metrics = {
        'total_raw_model_ids': 0,       # Provider DB
        'total_canonical_unique': 0,    # Provider DB or spec_db
        'total_aliases': 0,              # canonical_model_index keys - models
        'total_providers': 0,
        'total_free_raw_provider_db': 0,
        'total_free_usable_spec_db': 0,  # AFTER filtering
        'total_paid_raw': 0,
        'bos_estimate': None,            # e.g. "~300 free"
        'actual_usable': 0,
        'gap_explanation': ''
    }
    return metrics
```

## Why Counts Differ

| Source | Count | Why |
|--------|-------|-----|
| Provider DB raw free | 266 | Count of billing=free in PROVIDER_INTELLIGENCE_MASTER |
| spec_db usable free | 239 | Filtered during spec_db construction via get_best_model() |
| Bos ~300 estimate | ~300 | Likely includes aliases (4319 in cmi) or is approximate |

**The 27-model gap (266 - 239):** spec_db construction filtered models that didn't pass routing threshold.

**The ~300 likely includes:**
- 4319 aliases in canonical_model_index.json
- Provider-level allowlist entries (16 providers as entries)
- Approximate estimate without exact count

## Rules

1. **Never accept prior claims without verification.** Bos's ~300 is a guess, not a verified count.
2. **Document which database you're counting from.** Provider DB vs spec_db give different numbers.
3. **Explain the gap.** If your count differs from prior claims, explain why.
4. **Usable free ≠ Raw free.** spec_db filters to 239, provider DB has 266 raw.
5. **Aliases are not models.** 4319 aliases ≠ 1158 models. Don't conflate them.

## The Audit Pattern

```python
# Step 1: Discover all model-related files
model_files = discover_files([
    'provider', 'model', 'router', 'benchmark',
    'specialization', 'allowlist', 'free', 'paid',
    'openrouter', 'nvidia', 'minimax', 'cloud'
])

# Step 2: Load each and count
provider_db = load_json('ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json')
spec_db = load_json('model_specialization_database.json')
cmi = load_json('ilma_model_router_data/canonical_model_index.json')
allowlist = load_json('ilma_model_router_data/free_model_allowlist.json')
bench_db = load_json('ilma_model_router_data/benchmark_database.json')

# Step 3: Build reconciliation table
table = {
    'provider_db_raw': count_provider_db_models(provider_db),
    'spec_db_filtered': count_spec_db_models(spec_db),
    'aliases': cmi['key_count'] - cmi['model_count'],
    'free_provider_raw': count_free_in_provider_db(provider_db),
    'free_spec_db_usable': count_usable_free_in_spec_db(spec_db),
}
```

## When Count Reconciliation Applies

- When user mentions a model count estimate (~300 free, ~1000 models)
- When two databases give different counts for same metric
- When spec_db and provider DB have different model counts
- Before claiming "X free models" in any report or phase closure

## Key Numbers (2026-05-11)

| Database | Total | Free | Paid |
|----------|-------|------|------|
| Provider DB (PROVIDER_INTELLIGENCE_MASTER) | 1158 | 266 | 892 |
| spec_db (model_specialization_database) | 1088 | 239 | 849 |
| benchmark_database | 22 | — | — |
| canonical_model_index | 5477 keys | — | — |
| aliases (cmi) | 4319 | — | — |