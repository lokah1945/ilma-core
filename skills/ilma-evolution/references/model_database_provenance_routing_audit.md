# ILMA Model Database Provenance & Runtime Routing Audit

## Session: 2026-05-11 — Phase: MODEL_DATABASE_PROVENANCE_AND_RUNTIME_ROUTING_AUDIT

Full report: `docs/ILMA_MODEL_DATABASE_PROVENANCE_AND_ROUTING_AUDIT_REPORT_2026-05-11.md`

---

## Summary

Systematic audit of ILMA's model/provider databases, benchmark data validity, specialization score provenance, and runtime sub-agent routing behavior.

**Key findings:**
- Provider DB: 1158 models, 16 providers, 4 days old, LIVE_PROVIDER_API source
- Benchmark: **0 LIVE_BENCHMARKED**, 22 DRY_RUN_BENCHMARKED, 1136 NO_BENCHMARK
- Specialization: **3264 INFERRED scores** (all UNVERIFIED — not from live measurement)
- Provider multiplicity: 63 canonical models available via multiple providers
- Sub-agents: FREE_ONLY enforced, main model isolated

---

## Critical Evidence Levels (for claims)

| Evidence Level | Count | Usage Rule |
|----------------|-------|------------|
| LIVE_BENCHMARKED | **0** | NEVER claim — does not exist |
| DRY_RUN_BENCHMARKED | 22 | Say "DRY_RUN_BENCHMARKED" — not "live" or "benchmarked quality" |
| INFERRED | 3264 | Say "INFERRED" — not "measured" or "verified" |

**Router penalty for INFERRED:** `missing_evidence_penalty=0.05`, `inferred_score_penalty=0.02`

---

## Provider Trust Scores

Used by `_select_best_provider()` when same canonical model available via multiple providers:

| Provider | Trust | Provider | Trust |
|----------|-------|----------|-------|
| nvidia | 1.0 | google | 0.7 |
| openrouter | 0.9 | openai | 0.7 |
| minimax | 0.85 | anthropic | 0.7 |
| deepseek | 0.8 | blackbox | 0.5 |
| alibaba | 0.75 | | |

---

## Count Reconciliation

| Metric | Value |
|--------|-------|
| Raw model IDs (provider DB) | 1158 |
| Free (provider DB raw) | 266 |
| Usable free (spec_db) | **239** |
| Bos ~300 estimate | Likely aliases (4319) or rough estimate |
| **Never claim ~300** | Use 239 or 266 |

---

## Database Files & Provenance

| File | Source | Age | Trust |
|------|--------|-----|-------|
| `PROVIDER_INTELLIGENCE_MASTER.json` | OpenRouter API | 4 days | HIGH/EMPIRICAL=360, MEDIUM=575 |
| `benchmark_database.json` | .deprecated file | 0 days | DRY_RUN only |
| `model_specialization_database.json` | Inferred from routing | 0 days | ALL INFERRED |
| `canonical_model_index.json` | Auto-generated | 2 days | MEDIUM |

All databases have provenance fields added during this audit.

---

## Mutations Tested (7/7 PASS)

1. Provider availability → fallback works
2. Paid model penalty → gpt-4o, claude, gemini blocked
3. Benchmark sensitivity → score(0.9)=0.71 > score(0.1)=0.59
4. Specialization routing → coding model selected
5. Source trust → nvidia(1.0) > openrouter(0.9) > blackbox(0.5)
6. Alias resolution → multiple formats route correctly
7. Main model isolation → sub-agent does not modify ILMA main model

---

## Provider Multiplicity (63 Models)

When same canonical model available via multiple providers:
1. Filter to FREE only (sub-agent constraint)
2. Score: `candidate_score + (provider_trust * 0.1)`
3. Select highest combined
4. Example: `google/gemma-3-12b-it` via nvidia (free), openrouter (paid), google (paid) → **nvidia wins**

---

## Sub-Agent Route Example

```json
{
  "role": "Coding Sub-Agent",
  "task_category": "coding",
  "provider": "nvidia",
  "model_id": "nvidia/deepseek-ai/deepseek-coder-6.7b-instruct",
  "canonical_model_id": "deepseek-ai/deepseek-coder-6.7b-instruct",
  "free_or_paid": "free",
  "benchmark_score": 0.804,
  "benchmark_evidence": "DRY_RUN_BENCHMARKED",
  "specialization_evidence": "INFERRED",
  "provider_trust": 1.0,
  "source_db": "PROVIDER_INTELLIGENCE_MASTER.json"
}
```

---

## Router Changes (v3.1)

1. Added `PROVIDER_TRUST_SCORES` dict (15 providers)
2. Added `_select_best_provider(candidates)` function
3. Modified `get_best_model()` to group by canonical model and handle multi-provider
4. Added `missing_evidence_penalty=0.05` to spec_db routing policy

---

## Capability Status After Audit

| Capability | Status | Caveat |
|------------|--------|--------|
| provider_model_database | VERIFIED | Fresh, provenance added |
| model_router | VERIFIED | Full integration |
| model_benchmark_runner | PARTIAL | 0 LIVE, 22 DRY_RUN |
| model_specialization_db | PARTIAL | All 3264 INFERRED |

Final: 19 VERIFIED, 4 PARTIAL, 1 UNVERIFIED