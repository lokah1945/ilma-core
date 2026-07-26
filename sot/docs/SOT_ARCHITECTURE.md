# ILMA SOT — Architecture & Operations (2026-06-20)

Single source of truth for the ILMA model pipeline. Mirrors the working notes kept
during the 2026-06-19/20 audit + rebuild. MongoDB db `credentials` @
**172.16.103.253:27017** (`quantumtraffic` / `authSource=admin` / `directConnection`).
Canonical connection: `ilma_mongo_connection.py`. (Host is NOT 172.16.102.11 — that
refuses :27017.)

## 3-tier flow

```
api_key.json ─▶ llm_providers (T1, FROZEN credentials) ─▶ providers (T2, catalog)
                                                          ─▶ models (T3, FINAL, ready-to-use)
                       └▶ downstream: model_intelligence / _benchmark / _capabilities /
                                      _enrichment / _lifecycle_events / _alias
```

- **T1 `llm_providers` — FROZEN, admin-only.** 9-field credential store; required
  `provider`, `account_email`, `api_key` (+ `key_status`, `key_purpose`). One doc per
  (provider, account); multi-key by design (openrouter ×2 = inference + provisioning).
  Real keys SOT = `/root/credential/api_key.json`. DB-level `$jsonSchema` validator
  (validationAction=error) rejects malformed writes. Schema/validator:
  `sot/schemas/llm_providers.schema.json`, `sot/validators/validate_llm_providers.py`.
- **T2 `providers`** — catalog: base_url, auth_format, free_tier, status, **`force_free`**.
- **T3 `models`** — DYNAMIC, auto-built; carries the FINAL `is_free_final` / `billing_class`
  / `free_reason` and links to scoring. This is what runtime reads.

## Auto-sync (models is dynamic)

- Engine `sot/sync/sot_auto_sync.py`: targets = ACTIVE llm_providers ∩ have a sync
  endpoint. Per provider: upsert current `/v1/models` + **HARD-DELETE vanished**
  (`db_ids − live_ids`) across models + downstream. Safety: never prune on empty/failed
  fetch; refuses >50% catalog delete in one pass (`PRUNE_MAX_FRACTION`, override
  `--force-prune`). Fingerprint + model-list hash minimize churn.
- Triggers: (1) **real-time** `sot/sync/sot_sync_daemon.py` — change stream on
  llm_providers (rs0; pre-images for delete events), resume tokens + reconnect + debounce
  (`ilma-sot-sync-daemon.service`); (2) **6h** `ilma-sot-sync.timer` → `--full`.
- State in `sot_sync_state`. Units versioned in `sot/sync/systemd/`. Uses `/usr/bin/python3`.
- Add a provider to llm_providers → auto-synced, no code change.

## Enrichment & scoring (model_intelligence = scoring SOT)

- `sot/enrichment/sot_enrich_models.py` iterates models(active): blends AA + passive
  benchmark + id-pattern classification → `composite_score`(0-100) + `score_tier`
  (S/A/B/C/D) via `sot_ops.compute_score` + `capabilities_detail` (router vocab) +
  `specialization` + required `provenance`. 100% coverage.
- AA layer `sot/enrichment/sot_aa_ingest.py`: Artificial Analysis API (key from
  **`search_providers`**), slug→model_id match, writes aa_*_index to model_benchmark
  (~544 matched). compute_score is AA-weighted when present, else capped heuristic.
- Router `ILMAUnifiedRouter` (`ilma_model_router.py`): MASTER record carries `score` +
  `capabilities_detail`; `_get_intelligence_score` (priority-0b) and capability matcher
  use the real signal (was collapsing to 0.5 → ranked by provider-trust).

## Free / paid — FINAL in models, trap-safe (Bos policy)

Decision computed ONCE at sync/enrich time by `sot/enrichment/sot_billing_classify.py`
and stored on each models doc (`is_free_final`/`billing_class`/`free_reason`). Runtime
`_is_strictly_free` is a one-line read (~0ms) — delegated work (sub-agents, parallel,
kanban) picks the best free model cheaply. **When not explicitly free → PAID.**

1. `force_free` hardcode (`providers.force_free=True`) → FREE, bypasses everything.
   Set on **web-verified all-free** providers + admin-forced: wrapper-nvidia (NVIDIA NIM),
   groq (every model, 14.4k req/day free), cerebras (1M tok/day free), ollama; and minimax
   (paid plan, admin-forced free). Add via
   `db.providers.updateOne({provider},{$set:{force_free:true}})`.
2. paid-keyword (pro/premium/turbo/max/…) → PAID.
3. MIXED providers (openrouter/blackbox/opencode) are trap-prone (price reads $0 while
   billing) → FREE only via explicit `:free` (openrouter) or `:free`/`-free`
   (blackbox/opencode, e.g. `minimax-m3-free`) suffix; else PAID.
4. Direct providers → FREE only via force_free (rule 1) or CONFIRMED per-model $0 pricing.
   The provider-level `is_free`/`free_tier` flag is **NOT trusted** — provider_sync stamps
   it per-provider, so it falsely freed all of pay-per-token Together AI (237) and Nous
   (229), which have no per-model pricing. No reliable evidence → PAID.

**Verified billing (web 2026-06):** all-free = NVIDIA NIM, Groq, Cerebras, Ollama Cloud.
PAID/pay-per-token = Together ($25 trial only), Nous (aggregator, mostly paid), OpenAI,
xAI, Alibaba, aimlapi, BytePlus, Bytez, Google. MIXED-by-suffix = OpenRouter, Blackbox,
OpenCode. `_FREE_API_PROVIDERS` (router health-optimism) must include all force_free
providers or their unprobed models get health-blocked.

Result after correction: 172 free / 1867 paid (was 637/1402 — Together & Nous demoted to
paid; groq/cerebras kept free via force_free). Active free pool = 169. Two concepts:
**best-free** (default `allow_paid=False`) / **best-paid** (`get_best_model(task, allow_paid=True)`).
Hard capability filter for vision/audio/video (`HARD_CAPABILITY_TASKS`) — niche tasks get
a specialist or gracefully fall back. `_FREE_API_PROVIDERS` must list `wrapper-nvidia`
(not stale `nvidia`) so its 121 models aren't health-blocked.

## nvidia → wrapper-nvidia

3 NVIDIA NIM keys consolidated behind local proxy `http://127.0.0.1:9100`
(`/root/wrapper/nvidia`, `nvidia-wrapper.service`, keys in its `.env`). llm_providers
holds ONE `wrapper-nvidia` doc (dummy `api_key=wrapper-local-key`); provider renamed
across all tiers (model_id unchanged). Runtime: base_url from T2, api_key from T1.

## Bugs fixed (2026-06-19/20, verified)

- T1 restored after an ad-hoc agent wiped it (renamed provider→name, dropped
  api_key/account_email). Scheduled jobs are read-only on T1; restore script in
  `/root/backups/sot-restore-20260619/scripts/`.
- `reconcile._provider_has_recent_sync`: refreshed_at stored as ISO string → `$gte:date`
  matched 0 → recent-sync safety net dead. Fixed with date+string `$or`. Also normalized
  all models date fields string→BSON date.
- `reconcile_cascade_out_stale`: added 50% mass-disable safety cap.
- `sot_end_to_end_audit.py`: orphan delete now opt-in `--apply`; audit_trail never
  auto-deleted; audit_trail orphans are informational (append-only ledger), not a defect.
- `provider_sync.py`: duplicate dict key `{$ne,$ne}` → `{$nin:[None,""]}`; free_tier from
  T2; honors T2 auth_format.
- `sot_materialize`: catalog from T2, api_key_count from real T1 sibling count,
  multi-account keys accumulated.
- `sot_ops.generate_evidence_id`: seed counter from DB max (was exhausting 1000-retry
  loop and blocking syncs).
- `ilma_model_router._load_master_from_mongodb`: `intel["score_tier"]` KeyError when a
  model has no intel doc → crashed the whole MASTER build. Use computed tier fallback.
- `acquire_job_lock`: dedup by idempotency_key check-before-insert.

## Operations

```
# sync
python3 sot/sync/sot_auto_sync.py --full|--changed|--provider X|--status|--dry-run
# enrich + score
python3 sot/enrichment/sot_enrich_models.py --full|--only-missing|--provider X|--stats
python3 sot/enrichment/sot_aa_ingest.py            # refresh AA benchmarks
python3 sot/enrichment/sot_billing_classify.py --full|--provider X|--stats
# verify
python3 sot/validators/sot_end_to_end_audit.py     # full e2e audit (ZERO DEFECTS target)
# services
systemctl status ilma-sot-sync-daemon.service      # real-time change-stream watcher
systemctl list-timers ilma-sot-sync.timer          # 6h full sweep
```
