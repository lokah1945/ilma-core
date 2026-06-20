# ArtificialAnalysis.ai Scraping Investigation
**Date:** 2026-05-24
**Status:** INVESTIGATED — SPA/Next.js, NO REST API, requires Playwright

## Key Findings

### 1. API Key Exists But No REST Endpoints
- Key: `aa_JDMmpZiIGJKPXZvQxoqAQGTWsroVoBcC` (in `/root/credential/api_key.json`)
- All endpoints return HTTP 404:

```
❌ /api/v1/benchmarks        → 404
❌ /api/v1/models            → 404
❌ /api/v1/scores            → 404
❌ /api/v1/chat/completions  → 404
❌ /api/v1/llm-models        → 404
❌ /api/v1/leaderboard       → 404
❌ /models.json (public)     → 404
❌ /api/info                 → 404
```

### 2. Site is a JavaScript SPA (Next.js)
- HTML page is 7-8MB (mostly JS/CSS, minimal SSR content)
- `__NEXT_DATA__` script tag NOT present (client-side hydration only)
- `window.__NUXT__` NOT present
- `data-` attributes: 363 found but no embedded JSON
- urllib/requests only sees the JS shell, NOT the actual model data
- **Must use Playwright** (browser automation) to access rendered content

### 3. Page Structure (from browser_snapshot)
- Main: `https://artificialanalysis.ai/models` — model comparison/leaderboard
  - Shows: Intelligence Index, Coding Index, Agentic Index (v4.0)
  - 523 models total, tabs: Open Weights/Proprietary, Reasoning/Non-Reasoning
  - 10 evaluations: GDPval-AA, τ²-Bench, Terminal-Bench, SciCode, AA-LCR,
    AA-Omniscience, IFBench, Humanity's Last Exam, GPQA Diamond, CritPt
- Model detail: `https://artificialanalysis.ai/models/{model-slug}` (e.g., `gpt-5-4`)
  - Shows: Intelligence (#rank/score), Speed, Input/Output Price, Verbosity,
    Technical specs (reasoning, modality, knowledge cutoff, context window)

### 4. Existing Data in MASTER
- 284 models already have `benchmark_profile.source = "benchmark_aa"`
- Fields: `ai_index` (0-100), `coding_index`, `math_index` (nullable)
- Confidence: "high" (from local_benchmark evidence type)
- Evidence includes both `local_benchmark` (ai_index source) and `catalog_score`

### 5. Slug Normalization
- MASTER model_id: `gpt-5-4` (hyphenated, no spaces)
- AA URL slug: `gpt-5-4` → `https://artificialanalysis.ai/models/gpt-5-4`
- Need to normalize model_ids to URL-safe slugs for scraping

## Proposed Scraping Architecture

```
STEP 4: sync_artificialanalysis()  [NEW in ilma_model_db_manager.py]

1. Load existing benchmark_aa_cache.json (TTL check: 24h)
2. Load MASTER → extract all model_ids needing AA data
   (skip if already has benchmark_aa + recent cache < 24h)
3. Use Playwright browser (ilma_browser_engine.py):
   a. Navigate to https://artificialanalysis.ai/models
   b. browser_snapshot() → get list of model slugs
   c. For each model needing update:
      - Navigate to /models/{slug}
      - browser_snapshot() → extract metrics
      - Parse: ai_index, coding_index, agentic_index, speed, latency,
        input_price, output_price, context_window, reasoning flag
   d. Save to benchmark_aa_cache.json
4. enrich() step merges benchmark_aa_cache → MASTER benchmark_profile

Cache file: ilma_model_router_data/benchmark_aa_cache.json
  {
    "gpt-5-4": {
      "ai_index": 57,
      "coding_index": 57.3,
      "agentic_index": null,
      "speed_tps": 87.2,
      "latency_s": null,
      "input_price_per_m": 2.50,
      "output_price_per_m": 15.00,
      "context_window": 1048576,
      "reasoning": true,
      "rank_intelligence": 5,
      "scraped_at": "2026-05-24T..."
    },
    ...
  }
```

## Scoring Normalization

```
AA scores (0-100) → MASTER benchmark_profile (0-1):

  benchmark_profile.overall_score    = ai_index / 100
  benchmark_profile.quality_score    = ai_index / 100  (AA intelligence = quality)
  benchmark_profile.coding_score     = coding_index / 100
  benchmark_profile.reasoning_score  = agentic_index / 100  (if available)

Confidence:
  has_rank + has_index  → "high"
  has_index only        → "medium"
  estimated only        → "low"
```

## Verification Commands

```bash
# Count AA-enriched models in MASTER
python3 -c "
import json
m = json.load(open('ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json'))
aa = sum(1 for p in m['providers'].values() for x in p['models'].values() if x.get('benchmark_profile',{}).get('source')=='benchmark_aa')
print(f'benchmark_aa models: {aa} / {sum(len(p[\"models\"]) for p in m[\"providers\"].values())}')
"

# Test AA page accessibility via browser
python3 -c "
from scripts.ilma_browser_engine import SyncBrowserEngine
b = SyncBrowserEngine()
b.navigate('https://artificialanalysis.ai/models/gpt-5-4')
snap = b.snapshot()
print('AI Index:', [l for l in snap.split('\n') if '57' in l][:3])
"
```