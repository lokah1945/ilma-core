# SOT Architecture — 3-Tier Cascade & Slim llm_providers Migration

**Date:** 2026-06-19
**Session:** Bos audit #2 follow-up (post Audit #1)

## Prinsip Pipeline (Bos, NON-NEGOTIABLE)

`llm_providers` adalah SOT **dinamis & fleksibel**. Admin atau Bos boleh menambah/menghapus record kapan saja. Setiap perubahan **WAJIB auto-propagate** ke downstream melalui 3-Tier cascade.

```
TIER 1: llm_providers  (FROZEN credentials, multi-key paralel by design)
TIER 2: providers  (consolidated general, 1 record/provider)
TIER 3: model_intelligence, model_benchmark, model_audit_trail
TIER 4: models  (final, derived)
```

## Schema Slim Migration

**Before:** llm_providers.schema.json punya 23 field incl. config blobs: base_url, endpoints, payload_format, free_tier, description, auth_format, dll. Menciptakan residence dengan providers Tier 2.

**After (8 fields):**
- provider (FK) — required
- account_email — required
- api_key — required, minLength 5
- key_status (enum: VALID/INVALID/QUOTA_EXCEEDED/SERVER_ERROR/TIMEOUT/UNVERIFIED)
- key_purpose (opsional)
- account_status (opsional)
- added (string ISO)
- added_by (string)

## Migration Recipe

```bash
# 1. Backup full collection
python3 -c "
import json, pymongo
c = pymongo.MongoClient(...)
db = c['credentials']
docs = list(db['llm_providers'].find({}))
with open('/root/upload/<audit>/backups/llm_providers_pre_slim_<date>.json', 'w') as f:
    json.dump(docs, f, default=str, indent=2)
"

# 2. Update MongoDB validator -> action: warn (don't reject existing docs)
#    Use collMod with new validator, validationAction=warn

# 3. Apply schema ramping: write new llm_providers.schema.json (8 fields)

# 4. Drop config fields from existing docs
python3 -c "
import pymongo, json
c = pymongo.MongoClient(...)
db = c['credentials']
schema = json.load(open('/path/new_llm_providers.schema.json'))
allowed = set(schema['properties'].keys())
to_drop = set()
for d in db['llm_providers'].find({}):
    to_drop |= set(d.keys()) - allowed
to_drop.discard('_id')
db['llm_providers'].update_many({}, {'\$unset': {f: '' for f in to_drop}})
"
```

## Aggregate Rule (FIX 2026-06-19)

Karena `status` per-doc sudah hilang di schema ramping, pipeline reconcile HARUS pakai aggregate rule:

```python
def _aggregate_provider_live(siblings):
    for s in siblings:
        if s.get("key_status") in {"VALID", "UNVERIFIED"} and s.get("api_key"):
            return True
    return False
```

**Anti-pola**: JANGAN `lp.get("status")` per-doc — field `status` tidak ada lagi.

## Recent-Sync Safety Net

Verifikasi byteplus 2026-06-19: key_status=TIMEOUT tapi 48 model fetched sukses. Cascade_out_stale akan mark disabled — false negative.

Safety net: bypass disable rule jika ada model di Tier 4 dengan refreshed_at <24 jam.

```python
def _provider_has_recent_sync(db, pname, hours=24):
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return db["models"].count_documents({
        "provider": pname, "refreshed_at": {"$gte": cutoff}, "is_active": True
    }) > 0
```

## CURATED_ONLY_PREFIXES (FIX 2026-06-19)

`providers` punya 17 curated-only provider yang TIDAK ada di `llm_providers`.
Berasal dari credential store terpisah (infra_providers, search_providers, system_credentials).
Cascade_out blindly mark -> curated musnah.

Whitelist prefix:
```python
CURATED_ONLY_PREFIXES = ("system", "search_", "messaging", "browser_", "infra_",
                          "crypto_", "gmail_", "puter", "you", "tavily",
                          "serper", "github", "telegram", "cloudflare",
                          "nicehash", "binance", "tokocrypto", "qwen_bridge",
                          "useai_bridge", "artificial_analysis")
```

Nama match prefix -> TIDAK cascade-out. Nama lain boleh mark deprecated.

## Cascade-In Failure Diagnosis

| Symptom | Root cause | Action |
|---|---|---|
| URLError No address associated with hostname | URL placeholder, domain tidak real | Skip (log). NOT pipeline bug |
| URLError Connection refused | Local service tidak running | Skip. Restart manual |
| HTTP 401 Unauthorized | API key invalid | Drop key dari SOT |
| HTTP 500 Internal Server Error | Provider-side issue | Skip. Bos decide keep/drop |
| 0 models returned | URL benar tapi endpoint empty | Skip atau fix URL config |

**Velvet rule**: 1 provider gagal fetch TIDAK crash pipeline. Per-provider fail-safe.

## provider_status family removal

Bos 2026-06-19 minta hapus `provider_status` dari models (residence dengan SOT). Migration:
1. models.schema.json -> remove provider_status & provider_status_source
2. $unset di existing docs MongoDB
3. get_provider_meta() di provider_sync.py -> return aggregate_status saja
4. cascade_out_stale -> tidak set provider_status

## Orphan Patcher Fields Removal

Models punya 27 patcher fields non-schema: _sot_*, normalized_*, is_sot_for, model_identity_rule, provider_generation_rule, account_email, source, deactivated_at, dll. Cleanup $unset semua fields not-in-schema.

## Verify

```bash
# Idempotency
python3 sot/reconcile/reconcile_from_llm_providers.py  # zero work
python3 sot/reconcile/sync_providers_from_llm_providers.py  # zero work
```
