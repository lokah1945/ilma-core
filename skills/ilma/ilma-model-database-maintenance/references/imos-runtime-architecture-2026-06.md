# IMOS — ILMA Model Operating System Runtime Architecture (2026-06-09)

**Source:** Phase 1.6 design session 2026-06-09 23:30 WIB. Conceptual design for "How ILMA picks the best model in <10ms" — independent of SOT schema.

**Full doc:** `/root/shared-memory/ilma/reports/2026-06-09-model-operating-system.md` (833 lines, 29.6 KB).

**Status:** Bos approval pending. No implementation. This is the **runtime layer** that sits ON TOP of the 4-collection SOT from the 4-collection TDD reference.

---

## 1. Core Principle — Build-Time vs Runtime Separation

**The defining insight:** Scoring 10,000 models × 12 task types per request = 120,000 calculations = 120 seconds. **Not acceptable.**

**IMOS answer:** Compute composite scores **once at build time** (24h cycle), persist as **precomputed index in memory**. Runtime only does **hashmap lookup + filter + sort** — sub-10ms total.

```
Build-time (24h, async):
  SOT → extract (model, capability, tier, price, trust) →
  score per (model, task_type) →
  bucket to S/A/B/C/D tier →
  build precomputed hashmap [(task_type, constraints) → sorted list] →
  persist to disk for cold start

Runtime (per request):
  task_desc → classify → constraint decomp → hashmap lookup →
  health filter → tier ceiling → sort → return top 1

NO DB query, NO benchmark at runtime. Just memory access.
```

---

## 2. 12 Fixed Task Taxonomy (D-IMOS-002)

**Each task_type has a weight vector (sums to 1.0).** Default keyword classifier (already in `ilma_model_router.py:705: classify_task`).

| Task type | cap | intel | ctx | trust | fresh | Tier ceiling |
|-----------|----:|------:|----:|------:|------:|-------------|
| `heavy_coding` | 0.35 | 0.30 | 0.10 | 0.15 | 0.10 | A+ |
| `medium_coding` | 0.30 | 0.25 | 0.15 | 0.15 | 0.15 | B+ |
| `reasoning_xhigh` | 0.30 | 0.35 | 0.10 | 0.15 | 0.10 | A+ |
| `research` | 0.25 | 0.30 | 0.15 | 0.15 | 0.15 | B+ |
| `security_review` | 0.35 | 0.30 | 0.10 | 0.15 | 0.10 | A+ |
| `vision` | 0.40 | 0.20 | 0.15 | 0.15 | 0.10 | B+ |
| `writing` | 0.30 | 0.25 | 0.15 | 0.15 | 0.15 | C+ |
| `creative` | 0.30 | 0.25 | 0.15 | 0.15 | 0.15 | C+ |
| `planning` | 0.30 | 0.30 | 0.10 | 0.15 | 0.10 | B+ |
| `long_context` | 0.25 | 0.25 | 0.25 | 0.15 | 0.10 | C+ |
| `fast_tasks` | 0.20 | 0.20 | 0.10 | 0.20 | 0.30 | D+ |
| `general` | 0.25 | 0.25 | 0.15 | 0.20 | 0.15 | C+ |

**5 dimensions (per D-IMOS-003):** capability, intelligence, context, trust, freshness.

**Tier bucket (D-IMOS-004):** composite >= 0.85 → S, >= 0.70 → A, >= 0.55 → B, >= 0.40 → C, else D.

---

## 3. Runtime Hot Path (Sub-10ms Target)

For N models (scales to 100K):

| Step | Complexity | At N=10,000 | Notes |
|------|-----------|------------:|-------|
| Task classification | O(1) hash | <0.5ms | Keyword match in precomputed map |
| Constraint decomp | O(1) parse | <0.1ms | Build constraints_key string |
| Candidate pool lookup | O(1) hashmap get | <1ms | Pre-indexed by (task, constraints) |
| Health filter | O(K), K≤200 | <1ms | In-memory set: drop circuit_open |
| Tier ceiling | O(K) | <0.5ms | Filter: composite >= threshold |
| Rank sort | O(K log K) | <1ms | K≤200 stable sort |
| **Total** | **O(K log K)** | **<5ms** | ✅ Sub-10ms target met |

**Memory:** 1.1 MB for 10,000 models × 12 tasks. Trivial heap.

**At N=100,000:** K≤2,000, sort 2ms, total <10ms. Still under target.

---

## 4. Key Design Decisions (10 Total)

| D-# | Decision | Pitfall if violated |
|----|----------|---------------------|
| 001 | Build-time scoring, not runtime | Runtime becomes 100+ seconds at scale |
| 002 | 12 task types, fixed taxonomy | More = config bloat, less = granularity loss |
| 003 | 5-dim composite (cap/intel/ctx/trust/fresh) | Single-dim scoring loses nuance |
| 004 | Tier bucket + ceiling per task | No tier = no quality gate |
| 005 | Free-first, paid as fallback | Always-paid = cost waste |
| 006 | Health affects ranking, not selection | Hard-exclude on degrade = no good model if all bad |
| 007 | Provider trust SEPARATE from quality | Trust=1 + bad model > Trust=0.3 + good model |
| 008 | Family-aware fallback (gpt-4o → gpt-4o-mini → gpt-3.5) | Cross-family jump loses behavior consistency |
| 009 | ZERO DB query at runtime | DB hit = +5-20ms (defeats sub-10ms target) |
| 010 | Subagent bias via weight multiplication | Bias=separate ranking = double bookkeeping |

---

## 5. Free vs Paid Strategy (D-IMOS-005)

**Default flow:**
1. Try free pool first
2. If free pool empty / all circuit-open / tier ceiling unmet → fall to paid
3. If both fail → emergency fallback (TDD-12 degraded mode)

**Opt-outs:**
- `allow_paid=False` strict — return None if free fails
- `use_paid=True` explicit — skip free, use paid
- `cost_budget=$X` — use paid only if budget allows

**Implicit triggers (free → paid without explicit opt):**
- Required context > max free context (e.g. > 32k)
- Required tier > max free tier (e.g. heavy_coding needs A+)

---

## 6. Subagent Bias (D-IMOS-010)

**Subagents tune task weights, not scoring algorithm.**

| Subagent | Bias | Effect |
|----------|------|--------|
| `coder` | capability × 1.5, trust × 1.2 | Prefer trusted code-specialized models |
| `researcher` | research × 1.5, context × 1.3 | Prefer long-context models |
| `vision_specialist` | vision × 2.0 | Strongly prefer vision-capable |
| `writer` | writing × 1.5, trust × 1.1 | Style + reliability |
| `security_auditor` | security_review × 1.5 | Quality matters |
| `planner` | planning × 1.5 | Reasoning priority |
| `default` | no bias | General selection |

**Implementation:** Multiply task_type weights by subagent bias. Re-compute composite in-memory for ≤200 candidates. Time: <5ms.

---

## 7. Family Fallback Chain (D-IMOS-008)

**Same family first, then cross-family.**

Example for gpt-4o down:
```
gpt-4o (down) → gpt-4o-mini → gpt-4-turbo → gpt-3.5-turbo (all OpenAI)
              ↓ if all OpenAI down
claude-3-5-sonnet → claude-3-haiku
              ↓ if all down
gemini-2.0-flash → gemini-1.5-pro
```

**Family extraction rule:** from `model_id`, strip version/quantization suffix.
- `openai/gpt-4o-2024-08-06` → `gpt-4o`
- `anthropic/claude-3-5-sonnet-20241022` → `claude-3-5-sonnet`
- `meta-llama/llama-3.1-70b-instruct` → `llama-3.1`

**Pitfall:** If family extraction fails, default family=model_id, log warning.

---

## 8. Re-ranking Strategy (When NOT 24h)

**Default cadence:** 24h cron.

**Triggers for hot patch (mid-cycle):**
- `models` insert (new model) → re-score + add to precomputed
- `model_intelligence.score` change → patch score
- `runtime_health` health_status change → drop from pool or penalty
- User feedback "model X bad" → temporary 0.5x penalty for X
- Provider trust change → re-score trust dimension

**Coalesce:** batch updates in 5-min windows. Avoid thrashing.

**Incremental:** only re-score changed models, append to existing (don't full rebuild).

---

## 9. Catalog Generation (Build-time, Optional)

**`/catalog` command** (Bos or subagent) returns browsable list:

```json
{
  "provider": "openrouter",
  "model_id": "openai/gpt-4o",
  "display_name": "GPT-4o",
  "family": "gpt-4o",
  "tier": "A",
  "is_free": false,
  "context_window": 128000,
  "input_modalities": ["text", "image"],
  "output_modalities": ["text"],
  "price_input_per_m": 5.0,
  "price_output_per_m": 15.0,
  "trust_score": 0.95,
  "score_per_task": {
    "heavy_coding": 0.85,
    "medium_coding": 0.78,
    "reasoning_xhigh": 0.88,
    ...
  }
}
```

**Generated by:** `materialize_catalog.py` (build-time, similar to materialize_cache).
**Persisted to:** `catalog.json` (human-readable, git-tracked).

---

## 10. Scaling Math — N=10,000 Models Stress Test

**Setup:** 500 providers × 20 models each.

**Cold start (one-time per Hermes boot):**
- Load SOT: ~200ms
- Build precomputed (one-time, async): ~5,000ms
- Memory: 1.1 MB

**Hot path (`medium_coding` task, default constraints):**
- Candidate pool: 150 (15% of 10,000)
- Health filter: 145 (5 had circuit_open)
- Tier ceiling (B+): 90
- Sort: <1ms
- **Total: ~3ms** ✅

**Subagent bias:** re-compute 200 scores in-memory: <5ms. **Total: ~8ms** ✅

**Verdict:** Sub-10ms target achievable up to 100K models.

---

## 11. Risks (10 Identified, 3 MEDIUM, 7 LOW)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Score staleness 24h | MEDIUM | Trigger on insert/update, hot patch |
| Tier ceiling misconfig | MEDIUM | Tuned defaults, override, alert when 0 pass |
| Task classification false positive | MEDIUM | Default to `general`, allow override |
| Health vs score conflict | LOW | Expand pool if all down |
| Trust over-penalize new provider | LOW | Trust floor 0.3, exploration mode |
| Family extraction fails | LOW | Default family=model_id, log |
| Memory at 100K models | LOW | Compress 16-bit, lazy build, limit guard |
| Subagent bias inverts good ranking | LOW | A/B test 10% default vs biased |
| Cold start 200ms | LOW | Background load, MASTER.json fallback |
| Re-rank too frequent | MEDIUM | Threshold 5% change, coalesce 5min |

---

## 12. Relation to Existing ILMA Code

IMOS is **formalization + completion** of existing logic in `ilma_model_router.py` (2792 lines, Phase 73). Key functions that IMOS formalizes:

| Function | Line | IMOS role |
|----------|-----:|-----------|
| `TASK_WEIGHTS` | 381 | D-IMOS-003 weights |
| `TASK_KEYWORDS` | 423 | D-IMOS-002 taxonomy |
| `classify_task` | 705 | Task classification |
| `_get_intelligence_score` | 759 | intelligence dimension |
| `_get_capability_match_score` | (later) | capability dimension |
| `_get_context_fit_score` | (later) | context dimension |
| `_get_provider_trust_score` | (later) | trust dimension |
| `_get_freshness_bonus` | (later) | freshness dimension |
| `_precompute_scores_for_task_type` | 1152 | D-IMOS-001 build-time |
| `_build_candidate_pool` | (later) | Runtime filter |
| `_is_healthy` | (later) | D-IMOS-006 health filter |
| `_emergency_fallback` | (last) | TDD-12 fallback |

**IMOS = existing logic + scaling design for 10K models + 12 task types + subagent bias + family fallback.**

---

## 13. When to Use This Pattern (IMOS Design)

**Apply IMOS design to ANY system that:**
1. Has many providers (10+) offering many models (100+)
2. Needs to pick one in real-time (<10ms)
3. Has benchmarks/scores that change slowly (24h acceptable)
4. Serves heterogeneous tasks (different types need different weights)
5. Has free/paid tiers to manage

**Examples:**
- LLM routing (current)
- Image generation model selection (DALL-E vs SD vs Midjourney)
- Embedding model selection
- TTS/STT model selection
- Any multi-provider/multi-model selection

**Don't apply if:**
- Single model, single provider (overkill)
- Real-time benchmark needed (use build-time pattern, not IMOS)
- All models are equivalent (just pick random)

---

## 14. Implementation Checklist (When Bos Approves)

Phase 1.6 implementation order:

1. Build-time scoring engine (`build_precomputed.py`)
2. Precomputed index builder (serialize to disk)
3. In-memory hashmap loader (cold start)
4. Task classifier (port from `ilma_model_router.py`)
5. Tier ceiling filter
6. Health filter (read from `runtime_health` cache)
7. Family fallback chain
8. Subagent bias multiplier
9. Catalog generation (`materialize_catalog.py`)
10. Stress test with 10K mock models
11. Replace `ilma_model_router.get_best_model` with IMOS
12. Keep old router as fallback (1 week)
13. A/B test 10% IMOS vs 90% old

**Estimated:** 1-2 hari coding + 1 hari stress test + 1 minggu A/B.
