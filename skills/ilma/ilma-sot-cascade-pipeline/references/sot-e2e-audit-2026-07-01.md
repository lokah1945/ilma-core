# SOT E2E Audit — 2026-07-01

## Session Summary

Full T1→T2→T3 pipeline integrity audit of `credentials` DB (local `127.0.0.1:27017`, no-auth).

## Document Counts

| Tier | Collection | Count |
|------|-----------|-------|
| T1 | llm_providers | 26 |
| T2 | providers | 35 |
| T3 | models | 1241 |

## Critical Findings

### C1: T2 aggregate_status — 100% Dead
- 0/35 providers have `aggregate_status` set
- 11/35 have `_status_cascaded_v3=True` (LLM providers only)
- 20/35 have `is_active=null` (non-LLM curated providers)
- Root: `provider_sync.py` only sets `aggregate_status` on NEW providers; never backfills existing

### C2: T1→T2 Orphan — 7 Providers Missing
aimlapi, alibaba, bytez, cerebras, minimax, ollama, together

### C3: T2 Key Status vs T1 Mismatch (5 providers zombie)
| T2 Provider | T2 status | T2 is_active | T1 key_status |
|---|---|---|---|
| blackbox | INVALID | true | INVALID |
| groq | INVALID | true | INVALID |
| byteplus | INVALID | true | TIMEOUT |
| felo | INVALID | true | SERVER_ERROR |
| bluesminds | INVALID | true | INVALID |

### C4: T3 active_with_disabled_at — 688 Contradictions (55%)
`is_active=True` + `disabled_at` exists. Deactivation scripts set timestamp but don't flip flag.

### C5: T3 llm_provider_ref Missing — 215 Models (17.3%)
No reverse traceability to T1 credential source.

## Data Quality Detail

### T1 key_status distribution
- VALID: 10 (openai, openrouter, wrapper-nvidia, nvidia, edge, cloudflare_ai, antigravity, xai via MULTI_ACCOUNT_DEFAULT_VALID, minimax, aimlapi)
- UNVERIFIED: 7 (nous, ollama, sumopod, tinyfish, together, xai, z.ai)
- INVALID: 9 (alibaba, blackbox, bluesminds, bytez, cerebras, groq)
- TIMEOUT/SERVER_ERROR: 2 (aisure, byteplus, felo)

### T3 models distribution
- is_active=True: 1090, is_active=False: 151
- billing_class=None: 1094, billing_class=free: 147, billing_class=paid: 0
- is_free=True: 315, is_free=False: 926
- is_free_final=100% None (intentionally $unset by sot_billing_classify.py 2026-06-22)
- billing_classified_at: 1241/1241 exist (classify HAS run)
- free_reason: 1241/1241 exist

### Active models per provider
| Provider | Active Models |
|----------|--------------|
| openrouter | 338 |
| nous | 264 |
| antigravity | 147 |
| wrapper-nvidia | 121 |
| openai | 120 |
| byteplus | 48 |
| opencode | 20 |
| groq | 17 |
| xai | 9 |
| nvidia | 5 |
| edge | 1 |

### discovered_via
- provider_direct: 937
- sot_reconcile: 151
- ilma_phase_73_sync: 147
- sot_gap_enrichment: 6

## Reconcile Script Results (dry-run 2026-07-01)

```
sot providers:        26
Models providers:     13
Orphan in models:     []

[cascade_in]
  needs_sync: 8 items (aimlapi, minimax, ollama, +5 more)

[cascade_out_stale]
  disabled_providers: []

[enum_discovered_via]
  invalid_discovered_via_documents: 153

[data_integrity]
  active_with_disabled_at: 688
```

## Billing Classify Stats (dry-run 2026-07-01)

```
total: 1241
is_free=True: 315
is_free=False: 926
unclassified: 0
active_free: 312
```

Full classify dry-run:
- free: 315
- paid: 926
- Reasons: mixed_no_free_suffix=376, free_bypass:t1=291, no_per_model_price_evidence=407, mixed_free_suffix=24, paid_keyword=143

## T2 Full Status Dump

See `/tmp/sot_audit2.py` output for all 35 T2 providers with their status/is_active/aggregate_status/t1_source_key values.

Key anomalies:
- google: status=deprecated, is_active=true → should be is_active=false
- 20 non-LLM providers: is_active=null (puter, you, tavily, serper, github, cloudflare, nicehash, binance, tokocrypto, telegram, browser_sessions, gmail_sessions, system, z.ai, nvidia, edge, cloudflare_ai, antigravity, artificial_analysis, sumopod subset)

## Fix Scripts Location

- Reconcile: `python3 sot/reconcile/reconcile_from_llm_providers.py --apply`
- T1→T2 sync: `python3 sot/reconcile/sync_providers_from_llm_providers.py --apply`
- Billing classify: `python3 sot/enrichment/sot_billing_classify.py --full`
- Key validator: `python3 sot/validators/ilma_validate_keys.py --all`

## Priority Recommendations

### P1 Immediate
1a. `reconcile_from_llm_providers.py --apply` → fixes C3 (5 zombie providers)
1b. Backfill `aggregate_status` → fixes C1
1c. `db.models.updateMany({is_active:True, disabled_at:{$exists:True}}, {$set:{is_active:False}})` → fixes C4

### P2 Short Term
2a. Reconcile 7 orphan T1→T2 providers
2b. Backfill 215 models without llm_provider_ref
2c. Update SOT_ARCHITECTURE.md — remove is_free_final references

### P3 Medium Term
3a. Cron: periodic `sot_billing_classify --full`
3b. Guard: is_active ↔ disabled_at consistency in sot_sync_daemon
3c. Guard: T1 key_status → T2 is_active cascade after each validate_keys run
3d. Unify T2 status fields (status/is_active/aggregate_status/_status_cascaded_v3 → 1 canonical field)

## Pipeline Health Scorecard

| Tier | Total | Healthy | Degraded | Dead | Health % |
|------|-------|---------|----------|------|----------|
| T1 | 26 | 10 VALID | 7 UNVERIFIED | 9 INVALID | 38% |
| T2 | 35 | 11 | 0 | 24 (cascade dead) | 31% |
| T3 | 1241 | 315 free+active | 688 contradiction | 151 inactive | 25% |
