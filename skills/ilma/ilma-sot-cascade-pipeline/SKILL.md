---
name: ilma-sot-cascade-pipeline
description: "SOT-driven cascade pipelines for MongoDB: when `llm_providers` is single source of truth and downstream must follow dynamically. Covers 5-step reconcile llm_providers→models (cascade-in/out-orphan/out-stale/enum-normalize/integrity), sibling-aggregation for key_status, recent-sync safety net, 4-report deliverable pattern, idempotency requirement, fail-safe per-item, anti-pattern WORKING_PROVIDERS hardcode, slim llm_providers (8-field credential-only), Tier 1→Tier 2 provider consolidation w/ CURATED_ONLY_PREFIXES. Verified 2026-06-19 #2: models 972→1954, 27 orphan patcher fields scrubbed, provider_status dropped, llm_providers ramped 23→8 fields."
triggers:
  - "audit sot pipeline"
  - "cascade pipeline llm_providers"
  - "reconcile models from llm_providers"
  - "sot-driven cascade"
  - "cascade delete downstream collection"
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
  - Bisa overlap: openrouter punya multi_account=True AND multi_purpose=True.

  **Schema enum** `llm_providers.key_purpose`:
  ```
  ['inference', 'provisioning', 'primary', 'secondary', 'experimental', 'backup']
  ```
  `default purpose='provisioning'` di `get_api_key()` karena listing endpoint
  butuh provisioning key. Panggil `get_api_key('openrouter', 'inference')`
  explicit saat runtime invoke model.

  Field `multi_purpose` di `providers.schema.json` (Tier 2) — bisa `True` saat
  siblings punya `key_purpose` berbeda. Update schema providers untuk include
  field ini.

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

**2026-06-19 (Audit #1)** — `sot/reconcile/reconcile_from_llm_providers.py`:
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
