---
name: ilma-sot-cascade-pipeline
description: "SOT-driven cascade pipelines for MongoDB: when `llm_providers` is single source of truth and downstream must follow dynamically. Covers 5-step reconcile llm_providers→models, 4-phase cascade enforcement engine (zombie kill + missing create + integrity + verify), free_bypass cascade handling, is_active=None backfill, sibling-aggregation for key_status, recent-sync safety net, 4-report deliverable pattern, idempotency requirement, fail-safe per-item, CURATED_ONLY_PREFIXES. Enforcement #3 2026-07-01: aligned=True, 0 violations, 402 active models."
triggers:
  - "audit sot pipeline"
  - "cascade pipeline llm_providers"
  - "reconcile models from llm_providers"
  - "sot-driven cascade"
  - "cascade delete downstream collection"
  - "sot cascade enforcement"
  - "cascade enforcement engine"
  - "enforce cascade integrity"
  - "t1 t2 t3 alignment fix"
  - "fix is_active disabled_at contradiction"
  - "backfill aggregate_status providers"
  - "foreign key migration mongodb"
  - "models collection cleanup"
  - "orphan provider cleanup"
  - "sot_reconcile enum value"
  - "audit mongodb collection findings"
  - "4-report audit deliverable"
  - "claude_report_auditsot_e2e"
  - "pipeline reconcile mongodb"
  - "tier 1 tier 2 providers cascade"
  - "sync_providers_from_llm_providers"
  - "curated_only_prefixes"
  - "slim llm_providers schema"
  - "multi key parallel provider"
  - "key_status aggregate"
  - "byteplus timeout recent sync safety"
  - "provider_status residence hapus"
  - "orphan patcher fields scrub"
  - "openrouter multi-purpose inference vs provisioning"
  - "key_purpose enumeration"
  - "get_api_key purpose parameter"
  - "multi_account vs multi_purpose distinction"
  - "providers.multi_purpose flag"
  - "schema widen recipe"
  - "bson datetime validator normalize"
  - "unique compound index llm_providers"
---

# ILMA SOT Cascade Pipeline (class-level)

## When to use

- Bos says: "audit pipeline llm_providers → models", "SOT cascade",
  "downstream harus mengikuti SOT", "reconcile dari SOT", "turunkan SOT ke models",
  "fk orphan cleanup", "cek apakah models sudah benar"
- A MongoDB collection (e.g. `models`, `model_intelligence`) claims to be a
  derived view of an SOT (e.g. `llm_providers`) but the derivation has gaps:
  - Dangling FK: child has `provider=X` but X isn't in parent
  - Stale FK: child has `provider=X` but parent now says `status=INVALID/disabled`
  - Missing FK: parent has provider `status=active` but child has 0 docs
  - Enum drift: child field values fall outside schema enum
  - Field conflicts: two fields carry duplicative semantic (e.g. `free_tier` + `is_free`)
- You just discovered a `sync_provider()` script that only writes/upserts
  and never cleans up — that's a no-cascade pipeline and needs this skill.

## Principe Bos 2026-06-19 (NON-NEGOTIABLE)

> `llm_providers` adalah SOT **dinamis & fleksibel** dengan struktur tetap.
> Turunan (`models` + downstream) **WAJIB mengikuti secara otomatis** dalam
> **3-Tier cascade**:
>
> ```
>   Tier 1: llm_providers (FROZEN credentials, multi-key paralel by design)
>      │   single source of truth for API keys
>      │   only admin/Bos boleh hapus-tambah record
>      ▼
>   Tier 2: providers (CONSOLIDATED general metadata, 1 record/provider)
>      │   satu dokumen per provider_name — sibling keys di Tier 1 di-rollup jadi
>      │   multi_account=True, key_count=N, act_key_count=M
>      ▼
>   Tier 3: model_intelligence, model_benchmark, model_audit_trail
>      ▼
>   Tier 4: models (final derived product)
> ```
>
> **Konsekuensi langsung:**
> - Duplicate keys di `llm_providers` (mis. `nvidia` ×3, `openrouter` ×2) ADALAH
>   paralel capacity dan CONSOLIDATED di Tier 2 jadi 1 record dengan
>   `multi_account=True, key_count=3, act_key_count=3`. BUKAN duplicate bug.
> - `cascade_in` / `cascade_out` / `enum_normalize` / `data_integrity` line
>   WAJIB jalan di antara tier manapun yang demanded oleh task.
> - Setiap perubahan di Tier 1 harus otomatis propagate ke Tier 2 lalu
>   downstream ke Tier 4.
>
> **Anti-pola (JANGAN):**
> - ❌ JANGAN hardcode `WORKING_PROVIDERS = {...}` di pipeline reconcile.
>   Anti-pola yang menciptakan kode yang kadaluarsa tiap admin/Bos edit SOT.
> - ❌ JANGAN anggap `llm_providers` punya 1 row per provider. Selalu group by
>   `provider` dan aggregate sibling keys.
> - ❌ JANGAN pakai `lp.get("status")` per-doc kalau schema llm_providers
>   sudah ramping (lihat P-CASCADE-12).
> - ✅ Baca SOT setiap kali pipeline jalan — derive state of truth dari SOT.
> - ✅ Cascade-delete orphan (FK yang tidak ada di SOT).
> - ✅ Cascade-mark-stale (provider dengan agregat non-live di SOT → `is_active=False`,
>    `status='disabled'` di child, **keep docs for provenance**).

## The 4-Report Deliverable Pattern

Letakkan semuanya di `/root/upload/claude_report_<audit-slug>/`
(contoh: `claude_report_auditsot_e2e`).

| File | Isi |
|---|---|
| `pipeline_map.md` | Skema kedua collection (parent SOT + child derived) + peta transformasi field-by-field + file/fungsi penggerak pipeline |
| `audit_findings.md` | Semua temuan dikategorikan: **UNTRACKED** (field di child tanpa sumber), **MISSED** (field di parent yang tidak mengalir), **LOGIC_ERROR** (logika pipeline salah). Severity Critical/High/Medium/Low. |
| `fix_log.md` | File yang diubah per-baris (old → new), data yang dikoreksi (count before/after), evidence_id per fix. Tandai items yang BUTUH Bos decision vs yang auto-applied. |
| `verification_result.md` | Hasil pasca-fix (counter-prove), idempotency confirmation (re-run = same state), foreign-key integrity, state DB final. |

**Aturan:** DILARANG buat file baru di luar dir report. Semua perbaikan
kode dilakukan **langsung di file yang sudah ada**. Backup pre-apply
opsional tapi recommended di `backups/pre_<audit>_<date>/`.

**Catatan schema:** Jika enum perlu backward-compat untuk data legacy
yang sudah ada, tambahkan nilai enum baru (mis. `"sot_reconcile"`,
`"live_purge_20260618"`) — BUKAN rename data existing.

## The Pipeline Pattern (5 steps, fail-safe per-item)

Letakkan pipeline di `sot/reconcile/reconcile_from_<sot-name>.py`:

```
def main():
    sot_index = load_sot_providers(db)                     # baca SOT
    models_providers = load_models_providers(db)           # baca derived

    steps ordered:
        cascade_in          # derived missing → sync dari SOT
        cascade_out_orphan  # derived not-in-SOT → DELETE (cascade ke downstream)
        cascade_out_stale   # derived but SOT.status≠active → is_active=False
        enum_normalize      # derived.enum field not in schema → rewrite to known enum
        data_integrity      # resolve field conflicts (e.g. free_tier mirror is_free)

    for each step: try/except ALL, log error, continue
```

### Step 1: cascade_in

For each SOT provider whose aggregate status is `live` (any sibling has
`key_status ∈ {VALID, UNVERIFIED}`) and has 0 docs in derived:
- Invoke `derived_sync_function(pname)`
- If derived has docs → refresh SOT-driven fields on existing docs.

**FIX 2026-06-19**: Setelah `llm_providers` ramping (lihat P-CASCADE-12),
SELALU group by `provider` dan aggregate over siblings. JANGAN per-doc status.

```python
def reconcile_cascade_in(db, sot_index, models_providers, apply):
    needs_sync = []
    siblings_idx = {}
    for d in db["llm_providers"].find({}):
        siblings_idx.setdefault(d["provider"], []).append(d)

    for pname, sibs in siblings_idx.items():
        if not _aggregate_provider_live(sibs):  # see Step 3
            continue
        if pname not in models_providers:
            needs_sync.append({"provider": pname,
                               "sib_count": len(sibs),
                               "act_keys": sum(1 for s in sibs
                                               if s.get("key_status") in {"VALID","UNVERIFIED"})})
    if needs_sync and apply:
        import provider_sync  # late import — needs network/credentials
        for entry in needs_sync:
            try:
                entry["sync_result"] = provider_sync.sync_provider(
                    entry["provider"], dry_run=False)
            except Exception as e:
                entry["sync_error"] = str(e)
    return {"needs_sync": needs_sync, "synced": [...]}
```

**Pitfall:** `cascade_in` butuh HTTP call / credentials.
- Provider dengan URL kosong di `PROVIDER_CONFIGS` akan fail fetch → error `URLError`. Ini artifacts of mis-registration, bukan bug pipeline. Log tapi jangan crash.
- Provider dengan hostname tidak resolving (`api.tinyfish.ai`, `api.sumopod.com`)
  fetch-fail tapi bukan salah pipeline — domain mungkin placeholder.
- Untuk pass pertama (audit murni), pisahkan `cascade_in` apply dari cascade-out/enum/integrity apply. Dry-run cascade_in dulu → Bos decide → apply.

### Pre-step 0: Tier 1 → Tier 2 first (sync_providers_from_llm_providers)

Jika task melibatkan `providers` collection (Tier 2), jalankan pipeline ini
SEBELUM `reconcile_from_llm_providers`. Pipeline Tier 1→Tier 2 punya 5 langkah:

```python
# File: sot/reconcile/sync_providers_from_llm_providers.py
1. load llm_providers, group by provider → siblings_idx
2. for each provider:
   - status = 'active' if any sibling has key_status ∈ {VALID, UNVERIFIED} else 'INVALID'
   - free_tier = act_keys[0].get('free_tier') if any, else fallback
   - key_count = len(siblings)
   - act_key_count = count of VALID/UNVERIFIED siblings
   - multi_account = key_count > 1
   - UPSERT into `providers` (preserve curated fields: endpoints, description, etc.)
3. for each curated-only provider (NOT in llm_providers):
   - DO NOT mark deprecated if name matches CURATED_ONLY_PREFIXES:
     ("system", "search_", "messaging", "browser_", "infra_", "crypto_",
      "gmail_", "puter", "you", "tavily", "serper", "github", "telegram",
      "cloudflare", "nicehash", "binance", "tokocrypto", "qwen_bridge",
      "useai_bridge", "artificial_analysis")
   - These providers live in different credential stores (infra_providers,
     search_providers, system_credentials, etc.) — not llm_providers.
   - Mark deprecated only if name doesn't match prefix (genuine SOT-orphan LLM).
```

Then run Tier 2+ downstream: `reconcile_from_llm_providers.py --apply`.

CLI:
```bash
python3 sot/reconcile/sync_providers_from_llm_providers.py         # dry-run
python3 sot/reconcile/sync_providers_from_llm_providers.py --apply # apply
```

**Why CURATED_ONLY_PREFIXES matters** (verified 2026-06-19): Pada awalnya
akan ada 17 provider di `providers` yang TIDAK ADA di `llm_providers`
(`google`, `puter`, `tavily`, `serper`, `hostable_*`, `*_bridge`, dll).
Kalau cascade-out blindly mark mereka deprecated, curated endpoints catalog
akan musnah. Whitelist_prefix adalah safety net.

### Step 2: cascade_out_orphan

For each derived entry whose key NOT in SOT at all → DELETE with cascade.

```python
def reconcile_cascade_out_orphan(db, sot_index, apply):
    sot_pnames = set(sot_index.keys())
    orphan_pnames = set(db["models"].distinct("provider")) - sot_pnames
    if not apply:
        # dry-run count mode
        return {"orphan_providers": sorted(orphan_pnames),
                "deleted": {"would_delete": N for each downstream collection}}
    # Mark first to preserve provenance, then delete
    audit_marker = {"_sot_cascade_at": datetime.now(timezone.utc),
                    "_sot_cascade_reason": "orphan_provider_not_in_sot"}
    for coll in ["models", "model_intelligence", "model_benchmark", "model_audit_trail"]:
        db[coll].update_many({"provider": {"$in": list(orphan_pnames)}}, {"$set": audit_marker})
        result = db[coll].delete_many({"provider": {"$in": list(orphan_pnames)}})
    return summary
```

**Pitfall:** Sebelum delete, `_sot_cascade_*` field dicatat di audit trail
untuk provenance. JANGAN delete hard — selalu mark first.

### Step 3: cascade_out_stale

For each derived entry whose SOT aggregate status is non-live
(`key_status ∉ {VALID, UNVERIFIED}` untuk SEMUA sibling, DAN tidak ada
synced models baru-baru ini) → mark disabled.

**FIX 2026-06-19**: Setelah `llm_providers` ramping (lihat P-CASCADE-12),
tidak ada `status` per-doc. Aggregate rule:

```python
def _aggregate_provider_live(siblings):
    """Provider is live if ANY sibling has key_status ∈ {VALID, UNVERIFIED}
    AND a non-empty api_key."""
    for s in siblings:
        if s.get("key_status") in {"VALID", "UNVERIFIED"} and s.get("api_key"):
            return True
    return False


def _provider_has_recent_sync(db, pname, hours=24):
    """Safety net: 'recently live' if any model has refreshed_at in window.
    Prevents false-negative disable bila key_status stale (e.g. TIMEOUT) tapi
    pipeline masih sukses (verified byteplus 2026-06-19: key_status=TIMEOUT
    but 48 models fetched OK)."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return db["models"].count_documents({
        "provider": pname, "refreshed_at": {"$gte": cutoff}, "is_active": True
    }) > 0


def reconcile_cascade_out_stale(db, sot_index, apply):
    out = []
    siblings_idx = {}
    for d in db["llm_providers"].find({}):
        siblings_idx.setdefault(d["provider"], []).append(d)

    for pname in sot_index.keys():
        siblings = siblings_idx.get(pname, [])
        live_by_siblings = _aggregate_provider_live(siblings)
        live_by_recent_sync = _provider_has_recent_sync(db, pname)
        if live_by_siblings or live_by_recent_sync:
            continue  # Skip — provider is live by either rule
        n_active = db["models"].count_documents({"provider": pname, "is_active": True})
        if n_active == 0:
            continue
        out.append({"provider": pname, "active_to_disable": n_active,
                    "reason": "no_live_sibling_no_recent_sync"})
        if apply:
            db["models"].update_many(
                {"provider": pname, "is_active": True},
                {"$set": {"is_active": False, "status": "disabled",
                          "deactivation_reason": "no_live_sibling_no_recent_sync",
                          "deactivated_at": datetime.now(timezone.utc)}}
            )
    return {"disabled_providers": out}
```

**Penting:** Kalau `key_status` di SOT adalah `TIMEOUT/SERVER_ERROR/ENDPOINT_WORKS_QUOTA_EXHAUSTED`
tapi model baru baru ini ter-sync sukses, JANGAN disable — pakai recent-sync safety net.

### Step 4: enum_normalization

For each derived entry with field value not in schema enum → rewrite to
a known compatible value (default: `"sot_reconcile"`).

```python
DISCOVERED_VIA_ENUM = {"provider_direct", "openrouter", "sot_fix_master_sync",
                       "sot_fix_v2", "passive", "manual", "live_purge_20260618",
                       "sot_reconcile"}

def reconcile_enum_discovered_via(db, apply):
    bad_query = {"discovered_via": {"$nin": list(DISCOVERED_VIA_ENUM)}}
    bad_count = db["models"].count_documents(bad_query)
    if apply and bad_count > 0:
        r = db["models"].update_many(bad_query, {"$set": {
            "discovered_via": "sot_reconcile",
            "_sot_enum_normalized_at": datetime.now(timezone.utc)
        }})
    return {"invalid_discovered_via_documents": bad_count, "updated": ...}
```

**Penting:** Sebelum fix, tambahkan nilai enum baru ke `*.schema.json`
agar backward-compat existing + new docs. Pipeline ini grade lakukan
rename massal.

### Step 5: data_integrity

Resolve field conflicts. Contoh umum:
- `free_tier` vs `is_free` (semantic duplikat) → mirror `free_tier = is_free`
- `is_active=True` + `disabled_at` ada → set `is_active=False`

```python
def reconcile_integrity(db, apply):
    out = {}
    mismatched = db["models"].count_documents({"$expr": {"$ne": ["$is_free", "$free_tier"]}})
    out["free_tier_mismatched"] = mismatched
    if apply and mismatched > 0:
        for doc in db["models"].find({"$expr": {"$ne": ["$is_free", "$free_tier"]}},
                                       {"provider":1, "model_id":1, "is_free":1, "_id":1}):
            db["models"].update_one({"_id": doc["_id"]},
                                     {"$set": {"free_tier": doc.get("is_free", False),
                                               "_sot_free_tier_synced_at": now()}})
    return out
```

## Idempotency Requirement

Pipeline **WAJIB idempotent**: re-run setelah apply menghasilkan state
identik (zero work needed on re-run).

Verifikasi:
```bash
python3 reconcile_from_<name>.py   # second run: orphan=[], stale=[], enum=0, integrity=0
```

## Fail-Safe per Item

Setiap step dalam `try/except` block. Error satu step = log + continue,
TIDAK abort pipeline. Laporkan errors di summary per-step.

```python
for name, fn in [
    ("cascade_in", lambda: reconcile_cascade_in(...)),
    ("cascade_out_orphan", lambda: reconcile_cascade_out_orphan(...)),
    ...
]:
    try:
        steps[name] = fn()
    except Exception as e:
        steps[name] = {"error": f"{type(e).__name__}: {e}",
                       "traceback": traceback.format_exc(limit=5)}
```

## CLI Surface

```bash
# Cascade Enforcement Engine (4-phase unified: zombie kill + missing create + integrity + verify)
python3 sot/sync/sot_cascade_enforcement.py              # dry-run (default, safe)
python3 sot/sync/sot_cascade_enforcement.py --apply       # execute all 4 phases
python3 sot/sync/sot_cascade_enforcement.py --json        # JSON output for CI

# Default = dry-run (preview only, safe)
python3 reconcile_from_<name>.py

# Apply: actually mutate MongoDB
python3 reconcile_from_<name>.py --apply

# Single provider only
python3 reconcile_from_<name>.py --provider nvidia

# JSON output for CI / pipeline
python3 reconcile_from_<name>.py --json
```

## Pitfalls

- **P-CASCADE-1**: JANGAN hardcode providers list. Baca SOT setiap kali.
- **P-CASCADE-2**: Hapus orphan HANYA setelah marking. Marker field
  (`_sot_cascade_at`, `_sot_cascade_reason`) preserve provenance kalau
  perlu rollback.
- **P-CASCADE-3**: cascade-out-orphan **sweep downstream** juga
  (`model_intelligence`, `model_benchmark`, `model_audit_trail`) — bukan
  hanya `models`. Otherwise FK-orphan di downstream.
- **P-CASCADE-4**: Schema enum harus di-update SEBELUM pipeline apply
  (karena `find_one` / `update_many` refer ke enum valid). Kalau tidak,
  `validation` rules bisa reject update.
- **P-CASCADE-5**: `cascade_in` butuh network call. Pisahkan pass dry-run
  dari pass apply. Jangan bulk-fan-out HTTP di dry-run.
- **P-CASCADE-6**: Self-improvement cron `*/5` atau periodic commit
  bisa **auto-commit patch kita**. Sebelum `git add`, jalankan
  `git log --since="2 hours ago"` untuk lihat apakah patch sudah masuk.
  **Verifikasi**: `git diff <path>` kosong setelah patch? Cek
  `git show HEAD:path/to/file` untuk konfirmasi perubahan ada di HEAD
  (bisa commit oleh self-improvement cycle).
- **P-CASCADE-7**: Distinct values via `db.coll.distinct("provider")`
  lebih reliable dari aggregate untuk query sederhana.
- **P-CASCADE-8**: Backup sebelum apply — letakkan di
  `/root/upload/claude_report_<slug>/backups/pre_<audit>_<date>/` (di
  dalam dir report yang sama, BUKAN di tempat lain).
- **P-CASCADE-9**: Jangan apply `cascade_in` HTTP fetch di pass pertama
  yang dijalankan shortly after audit (sandboxed env bisa rate-limited).
  Pisahkan scheduling: dry-run audit → Bos approve → apply mutated →
  apply HTTP cascade_in terpisah.
- **P-CASCADE-10**: Backup standard: dump 5 koleksi (`llm_providers`,
  `models`, `model_intelligence`, `model_benchmark`, `model_audit_trail`).
  Jangan lupa `model_intelligence` — sering ada orphan FK.
- **P-CASCADE-11**: Field `provider_status` & `provider_status_source` di `models`
  schema **adalah residence dengan SOT** — Bos 2026-06-19 minta dihapus.
  Pipeline reconcile tidak boleh menambahkannya. Schema `models.schema.json`
  JANGAN include field ini. Migrasi: `$unset` di existing docs.
- **P-CASCADE-12**: Schema `llm_providers` ramping (8 field, dari 23): cuma
  credentials-essential (`provider`, `account_email`, `api_key`, `key_status`,
  `key_purpose`, `account_status`, `added`, `added_by`). Migrasi pattern:
  1. Backup full collection ke `llm_providers_pre_slim_<date>.json`
  2. `collMod` validator MongoDB → `validationAction: warn` (jangan reject
     existing docs yang violate schema ramping)
  3. `$unset` semua field config (`base_url`, `endpoints`, `payload_format`,
     `free_tier`, `description`, `auth_format`, dll) — sekarang live di
     `providers` Tier 2
  4. Pipeline `reconcile_*` yang baca `lp.get("status")` per-doc HARUS
     di-update ke `_aggregate_provider_live(siblings)` rule
- **P-CASCADE-13**: `cascade_in` candidates yang fetch-fail tidak selalu bug
  pipeline. Diagnose per-provider URL dulu:
  - URL kosong di `PROVIDER_CONFIGS` → register URL di config dict atau di
    `llm_providers.endpoints.models_list.url`
  - Hostname not resolving → URL placeholder, log dan skip pipeline tidak crash
  - `connect refused` ke localhost → backend service tidak running, log dan skip
  - HTTP 4xx/5xx → key/endpoint invalid, log dan skip
  Jangan treat fetch-fail sebagai fatal — pipeline harus tetap lanjut ke
  provider berikutnya. Per-provider fail-safe.
- **P-CASCADE-14**: Diagnosa `cascade_in` candidates: cek `prov_meta =
  get_provider_meta(pname)` di awal. Kalau `act_key_count=0`, skip cascade_in.
  Hanya invoke `provider_sync.sync_provider()` jika `act_key_count > 0` ATAU
  there's curated `endpoints.models_list.url` di `providers` collection.
- **P-CASCADE-15**: `recent-sync safety net` (P-CASCADE rule `_provider_has_recent_sync`).
  BYPASS disable rule bila ada model synced sukses <24 jam. Mencegah false-negative
  ketika `key_status` stale (verified: byteplus 2026-06-19 key_status=TIMEOUT
  tapi 48 models fetched fine). Default window 24 jam dapat di-tune per task.
- **P-CASCADE-16**: Curated providers (`google`, `puter`, `tavily`, `serper`,
  crypto exchanges seperti `binance/nicehash`, system services seperti
  `cloudflare/telegram/github`, bridges `qwen_bridge/useai_bridge`) **bookeeping**
  di `providers` collection tanpa backing di `llm_providers`. Mereka eksis karena
  credential store terpisah (`infra_providers`, `search_providers`, `system_credentials`).
  Whitelist prefix sebelum `mark deprecated`. Default CURATED_ONLY_PREFIXES ada
  di script `sync_providers_from_llm_providers.py`.
- **P-CASCADE-17 (Openrouter multi-purpose trap — Bos 2026-06-19)**: Beberapa
  provider punya DUA jenis API key yang serve **permukaan berbeda**. Openrouter
  khususnya:
  - `key_purpose='inference'` — untuk panggil model (`/api/v1/chat/completions`)
  - `key_purpose='provisioning'` — untuk listing/management (`/api/v1/models`)
  Memakai key yang salah di endpoint yang salah = auth failure atau data salah.

  Pipeline `provider_sync` WAJIB pilih key by purpose:
  ```python
  # sot/discovery/provider_sync.py
  def get_api_key(provider: str, purpose: str = "provisioning") -> Optional[str]:
      # 1. Try exact match: provider + key_purpose=purpose
      # 2. Fallback: any VALID/UNVERIFIED key (regardless of purpose)
      # 3. Last resort: any api_key
      ...
  ```

  Tier 2 `providers` collection WAJIB flag multi-purpose:
  ```python
  purposes = {s.get("key_purpose") for s in siblings if s.get("key_purpose")}
  providers_doc["multi_purpose"] = len(purposes) > 1   # distinct dari multi_account!
  providers_doc["key_purposes"] = sorted(purposes)
  ```

  **Pitfall distinction**:
  - `multi_account=True` = sibling keys untuk capacity paralel (nvidia ×3)
  - `multi_purpose=True` = sibling keys serve permukaan BERBEDA (openrouter
    inference vs provisioning). DOWNSTREAM consume `key_purposes` aware — never
    panggil `/v1/models` pakai key inference.
  Schema enum
  `llm_providers.key_purpose`:

  ```
  ['inference', 'provisioning', 'primary', 'secondary', 'experimental', 'backup']
  ```
  `default purpose='provisioning'` in `get_api_key()` because listing endpoint
  butuh provisioning key. Panggil `get_api_key('openrouter', 'inference')`
  explicit saat runtime invoke model.

  Field `multi_purpose` in `providers.schema.json` (Tier 2) — bisa `True` saat
  siblings punya `key_purpose` berbeda. Update schema providers untuk include
  field ini.

- **P-CASCADE-18 (BSON datetime validation trap, Bos 2026-06-23)**: When
  validating `llm_providers` (or any collection) against a JSON-schema
  (draft-07), BSON-native `datetime` objects in fields like
  `verified_at` / `restored_at` / `last_valid_evidence` will FAIL schema
  validation because schema declares `type: "string"`. Two fixes — pick
  one to add to the validator:

  - **(A)** Widen schema to allow datetime strings only:
    `type: ["string", "null"]` + `format: date-time` + insert ISO strings
    explicitly (cumbersome insert-side).
  - **(B)** **Normalize at validator boundary** (preferred, REC #4):
    ```python
    def _normalize(doc):
        from datetime import datetime, date
        if isinstance(doc, dict): return {k: _normalize(v) for k,v in doc.items()}
        if isinstance(doc, list): return [_normalize(v) for v in doc]
        if isinstance(doc, (datetime, date)): return doc.isoformat()
        return doc
    norm = _normalize(doc); errors = list(Draft7Validator(schema).iter_errors(norm))
    ```

  Both work. **Do NOT remove `verified_at`/`restored_at`** to make schema
  pass — these are legitimate fields set by probe-once validator (REC #1)
  and restore scripts.

  Always pair schema change + validator update + `sot_schema_registry`
  `fields_count` update. Evidence needed: validator pass count
  (`0/N invalid`) AFTER fix.

- **P-CASCADE-19 (DB alias drift — public reference)**: Some docs and
  older scripts reference DB `ilma_sot`. Authoritative reference is
  the collection `_db_meta.db_alias_map` in DB `credentials` that lists
  `db_canonical=credentials` + alias `ilma_sot→credentials`. Phase any
  multi-collection script with `client['credentials']` default; never
  trust schema file's DB name as literal.

- **P-CASCADE-20 (Unique compound index — pattern)**: Adding
  `unique(provider, account_email)` to `llm_providers` requires:
  1. **Pre-check duplicates** via `Counter` over compound keys. If any
     count > 1, REPAIR intent first (multi-account by design ≠ accidental
     dup; consult Bos).
  2. `create_index([(p,1),(e,1)], name=..., unique=True)` — re-run safe.
  3. Log entry to `model_audit_trail` with
     `event_type='unique_index_added'` + `provider='*'` (system-level).
  4. Re-run any restore scripts idempotency test to verify they don't
      violate the new constraint.

  Verified 2026-06-23 (#REC #5): 23 docs, 23 distinct
  `(provider, account_email)` pairs, zero dup, safe to add. Index name
  convention: `uq_<fields>`.

- **P-CASCADE-21 (aggregate_status never backfilled — verified 2026-07-01)**:
  `provider_sync.py` sets `aggregate_status` only on NEW providers discovered
  during sync. Existing `providers` docs created before the field was added
  (or created by `sync_providers_from_llm_providers.py`) will have
  `aggregate_status=None` forever. This makes T2 cascade-status useless
  for 100% of existing docs.

  **Fix:** After `sync_providers_from_llm_providers.py --apply`, run a
  backfill pass:
  ```python
  for doc in db.providers.find({"aggregate_status": None}):
      # Re-derive from T1 sibling aggregation
      siblings = list(db.llm_providers.find({"provider": doc["provider"]}))
      live = _aggregate_provider_live(siblings)
      status = "active" if live else "disabled"
      db.providers.update_one({"_id": doc["_id"]},
          {"$set": {"aggregate_status": status, "_backfilled_at": now()}})
  ```
  Without this, any router query on `aggregate_status` returns empty/confusing
  results for ALL providers.

- **P-CASCADE-22 (is_active/disabled_at contradiction — verified 2026-07-01)**:
  688 out of 1241 models (55%) have `is_active=True` AND `disabled_at` exists.
  Root cause: deactivation scripts set `disabled_at` timestamp but forget to
  flip `is_active=False`. Any router filtering `is_active=True` will include
  these disabled models as routing candidates.

  **Fix (data_integrity step enhancement):**
  ```python
  # Already in Step 5 but needs explicit coverage:
  contradiction = db.models.count_documents(
      {"is_active": True, "disabled_at": {"$exists": True}})
  if contradiction > 0:
      db.models.update_many(
          {"is_active": True, "disabled_at": {"$exists": True}},
          {"$set": {"is_active": False,
                    "deactivation_reason": "disabled_at_isactive_contradiction_fix",
                    "fixed_at": now()}})
  ```
  Add this as a **required sub-step** in the `data_integrity` step. Also add
  a **guard in `sot_sync_daemon`** to automatically flip `is_active=False`
  whenever `disabled_at` is set on any model.

- **P-CASCADE-23 (T1 key_status → T2 is_active cascade broken — verified 2026-07-01)**:
  5 providers in T2 have `is_active=True` but T1 `key_status ∈ {INVALID, SERVER_ERROR, TIMEOUT}`.
  Specifically: blackbox, groq, byteplus, felo, bluesminds. The `sync_providers_from_llm_providers.py`
  script computes `is_active` from sibling aggregate but **existing T2 docs were never updated**
  after keys went INVALID. The cascade is write-on-create, not write-on-change.

  **Fix:** `sync_providers_from_llm_providers.py` must be run with `--apply`
  AFTER any key validation run that changes `key_status`. The script's sibling
  aggregation logic is correct — the problem is operational: nobody re-runs it
  after key status changes. **Add to cron or run manually after each
  `ilma_validate_keys.py --all` session.**

- **P-CASCADE-24 (is_free_final consolidated away — schema/doc drift, verified 2026-07-01)**:
  `sot_billing_classify.py` (2026-06-22) intentionally `$unset`s `is_free_final`
  and `free_tier`, consolidating into `is_free` as the single canonical billing
  field. Runtime (`ilma_model_router`) correctly reads `is_free`. But
  `SOT_ARCHITECTURE.md` and some skill docs still reference `is_free_final` as
  "the final billing verdict field." This is cosmetic but causes confusion.

  **Fix:** Search all docs/skills for `is_free_final` references and update to
  `is_free (canonical since 2026-06-22, is_free_final unset)`. The field
  `is_free_final` must NOT be re-added — the consolidation was intentional.

- **P-CASCADE-25 (T2 `provider_name` field never existed — verified 2026-07-01)**:
  Some scripts and doc references mention `providers.provider_name` as the
  primary key. In reality, the field is `provider` (string). There is NO
  `provider_name` field in any of the 35 T2 documents. If any code queries
  `provider_name`, it returns 0 results silently.

  **Rule:** Always use `providers.provider` as the join key. If code references
  `provider_name`, patch it to use `provider`.

- **P-CASCADE-26 (free_bypass providers cascade as live — verified 2026-07-01)**:
  Providers with `free_bypass=True` in T1 `llm_providers` MUST be treated as "live" for cascade
  purposes, even when `key_status=INVALID`. Example: `groq` has `key_status=INVALID` +
  `free_bypass=True` → still active (route through xAI proxy, not direct key).

  When building T2 from T1 (fallback path without sync module), the `_build_t2_from_t1` function
  must check:
  ```python
  has_free_bypass = any(s.get("free_bypass") is True for s in siblings)
  if act_keys > 0 or has_free_bypass:
      status = "active"; is_active = True; effective_act_keys = max(act_keys, 1)
  else:
      status = "INVALID"; is_active = False; effective_act_keys = 0
  ```

  Without this, free_bypass providers get `status="INVALID"` + `is_active=False` in T2, and
  the cascade engine marks them as "missing T2" → creates a duplicate INVALID T2 doc.

- **P-CASCADE-27 (T2 is_active=None legacy drift — verified 2026-07-01)**:
  19 out of 39 T2 `providers` docs had `status="active"` but `is_active=None` (not `True`).
  Root cause: these docs were created by `sync_providers_from_llm_providers.py` which sets
  `status` but never explicitly set `is_active=True`. The `is_active` field was added later
  but the sync script's upsert didn't include it for existing docs.

  **Impact:** Any verification or runtime check using `is_active is True` (strict) will miss
  these providers even though they're functionally active. The cascade enforcement engine's
  Phase B ("missing T2" check) won't flag them because `t2_active - t1_live = ∅`, but
  integrity verification scripts using strict `is_active is True` see 5 violations.

  **Fix (backfill):**
  ```python
  db.providers.update_many(
      {'status': 'active', 'is_active': None},
      {'$set': {'is_active': True, '_backfilled_is_active_at': now}})
  db.providers.update_many(
      {'status': {'$ne': 'active'}, 'is_active': None},
      {'$set': {'is_active': False, '_backfilled_is_active_at': now}})
  ```
  Also: `sync_providers_from_llm_providers.py` MUST include `is_active` in its upsert
  document (not just `status`) going forward.

- **P-CASCADE-28 (Cascade enforcement engine — 4-phase unified approach, verified 2026-07-01)**:
  A single engine script `sot_cascade_enforcement.py` handles ALL cascade violations in one pass:

  | Phase | Purpose | Actions |
  |-------|---------|---------|
  | A (Zombie Kill) | T1 inactive → remove downstream | Deactivate T2 zombie, deprecate T2 orphan (curated), deactivate T3 zombie models, deactivate T3 orphan models |
  | B (Missing Create) | T1 active → ensure downstream | Create missing T2 from T1 siblings (with free_bypass), update T2 status, trigger T3 sync |
  | C (Data Integrity) | Fix contradictions + backfill | Fix is_active+disabled_at contradictions, backfill aggregate_status, clean stale fields |
  | D (Verify) | Post-enforcement alignment check | Re-check all violations, report alignment status |

  **Safety guard:** Max 50% of active models can be deactivated in one run (configurable).
  **Dry-run by default.** Use `--apply` to execute mutations.
  **Location:** `sot/sync/sot_cascade_enforcement.py`

  Important: Phase D runs the SAME checks as the enforcement logic. If Phase D reports
  `aligned=True`, the DB is fully consistent. If not, there are violations the engine
  couldn't fix (e.g. missing T3 models for providers without sync endpoints).

- **P-CASCADE-29 (Missing T3 after cascade enforcement is expected — verified 2026-07-01)**:
  After running `sot_cascade_enforcement.py --apply`, Phase D will show `missing_t3_remaining`
  for providers that have no sync endpoint (no way to fetch their model catalog). These are
  not violations — they're providers where:
  - API endpoint unknown or placeholder (cloudflare_ai, minimax, z.ai)
  - Service is wrapper-level not provider-level (aimlapi)
  - API requires paid access only (some mid-tier providers)

  The engine logs these as `skipped_no_sync_endpoint`. They're acceptable as-is; models
  will be populated when credentials/endpoints become available.

## Verification Recipe

Paska-apply, verifikasi:
1. **Idempotency**: `python3 reconcile_from_<name>.py` (default dry-run)
   harus return zero work di semua step.
2. **FK integrity**: `set(db["models"].distinct("provider")) - set(db["llm_providers"].distinct("provider"))` → `{}`
3. **Active vs SOT**: untuk setiap active di `models`, cek
   `llm_providers[provider].status ∈ LIVE_STATUSES`.
4. **Enum compliance**: `db["models"].aggregate([{"$group":{...}}])`
   per field enum → semua value ∈ schema enum.
5. **Conflict resolution**: `is_free` ↔ `free_tier` cross-table
   aggregation → all match.

## Verified status

**2026-06-19 (Audit #1)** —
- 672 anomalies fixed in 1 pass (models 978 → 972)
- 6 orphan-docs removed (google)
- 168 INVALID-provider docs marked disabled (blackbox, bluesminds, groq)
- 212 invalid enum docs normalized
- 323 free_tier match resolved
- 122 disabled_at + is_active conflicts resolved
- Git commit `d4ab9b7` pushed to `lokah1945/ilma-core`

**2026-06-19 (Audit #2 — Tuned Bos pipeline per prinsip 3-Tier)** —
`sot/reconcile/sync_providers_from_llm_providers.py` added + refining
`reconcile_from_llm_providers.py`:
- PROVIDER_CONFIGS missing entries fixed (`tinyfish`, `sumopod`)
- `felo` URL fixed (`api.felo.ai` → `openapi.felo.ai/v1/models`)
- `cascade_in` run applied: 5 providers live-fetched (1056 models added to
  `models`, total 972 → 1954):
  openai 120, nous 269, opencode 20, aimlapi 599 → wait, byteplus? Actually
  openai 120 + nous 269 + opencode 20 + aimlapi 599? — re-check log
  (**CASCADE_IN_RESULT_2026_06_19**: openai=120, nous=269, opencode=20,
  aimlapi=525, byteplus=48 — total 982 added, 972 → 1954)
- 4 providers fetch-fail (gracefully logged, not fatal):
  tinyfish (host not resolve), sumopod (host not resolve), ollama
  (connection refused), felo (HTTP 500 server error)
- `provider_status` & `provider_status_source` fields REMOVED from `models`
  schema and existing docs (P-CASCADE-11)
- Orphan patcher fields scrubbed from 972 `models` docs (`_sot_*`,
  `normalized_*`, `is_sot_for`, `model_identity_rule`,
  `provider_generation_rule`, `account_email`, `source`, dll — 27 fields
  total) → 0 orphan fields remaining
- `llm_providers` schema slimmed from 23-field config blob ke 8-field
  credential store (P-CASCADE-12). Pipeline `reconcile_cascade_out_stale`
  di-rewrite pakai `_aggregate_provider_live()` rule + `_provider_has_recent_sync()`
  safety net (terverifikasi byteplus 2026-06-19: stuck di TIMEOUT but live)
- `sync_providers_from_llm_providers.py` (Tier 1 → Tier 2 pipeline created):
  aggregate 24 sibling-doc llm_providers jadi 21 consolidated
  `providers` record dengan `multi_account`, `key_count`, `act_key_count`,
  `aggregate_status`. CURATED_ONLY_PREFIXES whitelist preservasi 17 provider
  curated-only (system, search, telegram, crypto, bridge, dll).
- Backup disimpan di `/root/upload/claude_report_auditsot_e2e/backups/`:
  - `pre_reconcile_20260619/` — 5 koleksi pre-fix #1
  - `llm_providers_pre_slim_<date>.json` — pre-fix #2

**2026-07-01 (Enforcement #3 — Cascade enforcement engine + full alignment)** —
`sot/sync/sot_cascade_enforcement.py` (4-phase unified engine):
- Phase A: 1 T2 zombie deactivated (opencode), 1 T2 orphan deprecated (google), 68 T3 zombie models deactivated (byteplus 48 + opencode 20)
- Phase B: 5 missing T2 created (aimlapi, groq, minimax, ollama, together) — groq via free_bypass handling
- Phase C: 620 is_active+disabled_at contradictions fixed, 23 aggregate_status backfilled
- Post-apply: 19 T2 `is_active=None` → `True` backfill (legacy schema drift)
- Phase D: **aligned=True** — 0 violations forward + reverse
- Active models: 402/1241 (true count after contradiction fix)
- T2 active providers: 36, T3 active providers: 7

- **P-CASCADE-30 (Logging injection pitfall — verified 2026-07-01)**:
  When adding `import logging` + `logger = logging.getLogger(__name__)` to files that lack
  logging, a naive "find the last `import`/`from` line and insert after it" approach
  **WILL BREAK** files where the last import is inside a function body or `if __name__`
  block. The injected lines get wrong indentation (module-level code inserted at
  function-level indent), causing `SyntaxError: unexpected indent` or
  `SyntaxError: from __future__ imports must occur at the beginning of the file`.

  **Verified failure mode:** A regex-based injector scanned for the last line matching
  `^import |^from ` without checking indent level, injected `import logging` inside
  an `if __name__ == "__main__"` block, broke 6 out of 8 target files. Additionally,
  one file had `from __future__ import annotations` on line 51 — the injector placed
  logging before it, violating Python's `__future__` import-first rule.

  **Correct approach:**
  1. Use `ast.parse()` to find top-level import statements (no indent / no parent scope).
  2. Insert `import logging` + `logger = logging.getLogger(__name__)` after the
     **last top-level import** (one with zero indent, not inside any function/class/main block).
  3. **Explicit check:** If any `from __future__` import exists, the logging import
     MUST come after it — never before. `__future__` imports must be first in file.
  4. Verify with `ast.parse(content)` after write to catch indentation errors immediately.

  **Recovery pattern** if naive injector already broke files:
  ```python
  import re
  content = re.sub(r'\nimport logging\nlogger = logging.getLogger\(__name__\)', '', content)
  # Then re-insert at correct location using AST-aware approach
  ```

- **P-CASCADE-31 (SOT production audit methodology — S1–S10, verified 2026-07-01)**:
  When Bos asks for "SOT deep audit" or "optimize SOT" or "pastikan semua wiring terhubung",
  use this systematic 10-step audit → fix → verify pipeline. Each step produces findings
  that feed into the fix phase. Audit FIRST, fix SECOND, verify THIRD. Never mix phases.

  | Step | Name | Purpose | Key Checks |
  |------|------|---------|------------|
  | S1 | Inventory | Map all files, LOC, packages | `.py` file count, packages, LOC |
  | S2 | Orphan classify | Find files with zero importers | CLI-only (ok) vs TRUE-ORPHAN (fix) |
  | S3 | Wiring audit | Broken imports, missing `__init__.py` | Absolute→relative import fixes, pkg init |
  | S4 | Pipeline integrity | Import smoke test for all modules | `importlib.import_module()` on each |
  | S5 | Runtime health | MongoDB alive, stale fields, systemd | Collection counts, stale field cleanup |
  | S6 | Dead code | Empty dirs, orphan quarantine, overlap | Remove empty dirs, quarantine orphans |
  | S7 | Schema coverage | Collections vs schemas, stale DB fields | Schema stubs for uncovered, clean stale |
  | S8 | Hardening | Logging, try/except, systemd services | Add logging (P-CASCADE-30 safe!), services |
  | S9 | Integration | Dispatcher + runtime wiring + cascade | Verify cross-module wiring is intact |
  | S10 | Final e2e | 9/9 checklist verification | Imports, MongoDB, schema, stale, dirs, pkg, quarantine, integration, cascade |

  **Fix script pattern:** Write a single `/tmp/sot_apply_fixes.py` that handles ALL
  fixes in dependency order (empty dirs → quarantine → schema → stale fields → logging
  → systemd). Run once, verify with S10 e2e check. If logging injection breaks files
  (P-CASCADE-30), fix those first before re-running S10.

  **Session results (2026-07-01):** 27 fixes applied, 5 empty dirs removed,
  1 orphan quarantined, 6 schema stubs created, 3 stale MongoDB fields cleaned
  (is_free_final, _status_cascaded_v3, aggregate_status backfill), 8 files got
  logging, 1 systemd service installed. Final: **9/9 checks PASSED**.

## Cross-references

- `ilma-runtime-mongodb-migration` — sibling skill for MongoDB-driven
  runtime (not cascade)
- `ilma-sot-migration-mongodb` — data-plane SOT migration (one-time)
- `ilma-comprehensive-report-writing` — for multi-part audit reports
- `references/sot-cascade-pipeline-2026-06-19.md` — full session log
  with field-trace tables, audit findings, evidence IDs
- `references/git-self-improvement-cycle.md` — pitfall P-CASCADE-6 in
  detail with the `git check-ignore` / `git log --since` verification flow
- `references/tier-1-tier-2-cascade.md` — **NEW** 3-Tier cascade
  architecture (Tier 1 llm_providers → Tier 2 providers → Tier 3/4 models),
  slim llm_providers migration recipe, aggregate `key_status` rule,
  recent-sync safety net, CURATED_ONLY_PREFIXES whitelist, cascade-in
  failure diagnosis table, provider_status removal migration, orphan
  patcher fields cleanup
- `references/openrouter-multi-purpose-trap.md` — **NEW (Bos 2026-06-19
  warning)** Multi-purpose provider trap (inference vs provisioning keys),
  `key_purpose` enum, `multi_purpose` flag distinct dari `multi_account`,
  `get_api_key(pname, purpose=...)` API usage, verification recipe
- `references/sot-session-2026-06-23-zai-insert.md` — companion to
  REC #1-#6 (probe validator, schema widen P-CASCADE-18, unique index
  P-CASCADE-20, DB alias drift P-CASCADE-19, felo diagnosis REC #6)
- `references/sot-e2e-audit-2026-07-01.md` — Full T1→T2→T3 pipeline
  E2E audit: document counts, C1-C5 critical issues (aggregate_status dead,
  7 T1→T2 orphans, 5 zombie T2 providers, 688 is_active/disabled_at
  contradictions, 215 missing llm_provider_ref), billing classify stats,
  reconcile dry-run results, priority recommendations, health scorecard
- `references/sot-cascade-enforcement-2026-07-01.md` — **NEW** Cascade enforcement
  engine build+apply session: 4-phase engine architecture, dry-run vs apply
  results, free_bypass handling (P-CASCADE-26), is_active=None backfill
  (P-CASCADE-27), before/after state, E2E aligned verification (0 violations)
- `references/sot-production-audit-s1-s10-2026-07-01.md` — **NEW** Full S1–S10
  production audit methodology: 3-phase (audit→fix→verify) pipeline, logging
  injection pitfall detail (P-CASCADE-30), fix script pattern, session results
  (27 fixes, 9/9 final e2e), MongoDB tier state, evidence IDs

## Pointer to operator-side skill

For one-shot operator queries against `llm_providers` (read-only audit,
probe key_status, check DB alias, etc.), use
**`ilma-sot-credential-retrieval`**. This skill is for cascade/reconcile
tasks that mutate downstream collections.
