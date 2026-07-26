# Benchmark Database Reference (2026-05-15)

## Files

| File | Path | Entries | Purpose |
|------|------|---------|---------|
| benchmark_database.json | ilma_model_router_data/ | 648 total | All benchmark scores |
| free_model_rankings.json | ilma_model_router_data/ | 294 free models | Ranked free models |
| free_model_allowlist.json | ilma_model_router_data/ | 435 free IDs | Allowlist for routing |
| model_ids | SQLite data/ilma_dashboard.db | 1,284 total | Canonical registry |

## Merge Priority (lowest to highest)

1. `free_model_rankings` (294) — lowest priority, PROXY_ESTIMATED
2. `benchmark_records` proxy entries (548) — PROXY_BENCHMARKED
3. `model_scores` (308) — higher priority, DRY_RUN/PASSIVE/LIVE
4. `benchmark_records` real entries (41) — highest priority

## Nested Scores Fix

Proxy entries in `benchmark_records` use nested `scores` dict:
```json
{
  "canonical_model_id": "nvidia/DeepSeek-R1",
  "scores": {
    "coding_weighted": 0.910,
    "overall": 0.886,
    "reasoning_weighted": 0.920
  },
  "evidence_level": "PROXY_BENCHMARKED"
}
```

Direct entries use flat structure:
```json
{
  "canonical_model_id": "openai/gpt-4o",
  "coding_weighted": 0.890,
  "overall": 0.875
}
```

Correct extraction:
```python
scores_nested = rec.get('scores', rec)
score = scores_nested.get('coding_weighted', scores_nested.get('overall', 0.0))
```

## Top 10 Free Models (by composite_score)

| Rank | Model | Provider | Coding | Overall | Tags |
|------|-------|----------|--------|---------|------|
| 1 | nvidia/DeepSeek-R1 | nvidia | 0.910 | 0.886 | [coding, reasoning, vision] |
| 2 | meta/llama-3.1-405b-instruct | nvidia | ? | 0.846 | [coding, reasoning, vision] |
| 3 | nvidia/llama-3.1-nemotron-ultra-253b-v1 | nvidia | ? | 0.846 | [reasoning] |
| 4 | meta/codellama-70b | nvidia | 0.860 | ? | [coding] |
| 5 | google/gemini-2.0-flash | google | ? | 0.830 | [vision, general] |
| 6 | qwen/qwen3-235b-a22b | nvidia | ? | 0.820 | [reasoning] |
| 7 | google/gemini-1.5-flash | google | ? | 0.815 | [vision] |
| 8 | nvidia/nemotron-3-nano-omni-30b-a3b-reasoning | nvidia | ? | 0.700 | [reasoning] |
| 9 | meta/llama-3.1-8b-instruct | nvidia | ? | 0.740 | [general] |
| 10 | mistral/mistral-large-3 | nvidia | ? | 0.710 | [reasoning] |

## Evidence Level Distribution

```
LIVE_RUNTIME_BENCHMARKED:                    13
PASSIVE_PROVIDER_BENCHMARKED_NORMALIZED:     17
PASSIVE_PROVIDER_BENCHMARKED:                18
DRY_RUN_BENCHMARKED:                         43
PROXY_BENCHMARKED (from free_model_rankings): 548
PROXY_ESTIMATED:                              9
---
Total:                                       648
```

## Verification Commands

```bash
# Check benchmark entry
python3 -c "
import json
with open('/root/.hermes/profiles/ilma/ilma_model_router_data/benchmark_database.json') as f:
    db = json.load(f)
rec = db.get('benchmark_records', {}).get('nvidia/DeepSeek-R1') or db.get('model_scores', {}).get('nvidia/DeepSeek-R1')
print(json.dumps(rec, indent=2))
"

# Check rankings entry
python3 -c "
import json
with open('/root/.hermes/profiles/ilma/ilma_model_router_data/free_model_rankings.json') as f:
    rankings = json.load(f)
rec = next((m for m in rankings if m.get('model_id') == 'nvidia/DeepSeek-R1'), None)
print(json.dumps(rec, indent=2))
"

# Quick benchmark score check for any model
python3 -c "
import sys; sys.path.insert(0, '/root/.hermes/profiles/ilma')
from ilma_model_router import get_best_model
for task in ['coding', 'reasoning', 'general']:
    r = get_best_model(task, prefer_free=True)
    print(f'{task}: {r[\"model_id\"]} bm={r.get(\"benchmark_score\",0):.3f}')
"
```

## Known Issues

1. Many entries from `free_model_rankings` lack `coding_weighted` — only `composite_score` available. Use composite_score as fallback.
2. `model_scores` entries often have `None` for individual dimensions — merge logic must handle None gracefully.
3. Provider prefix normalization: `nvidia/DeepSeek-R1` vs `nvidia--DeepSeek-R1` — must normalize dashes to slashes.