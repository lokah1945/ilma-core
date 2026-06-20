# Multi-Purpose Provider Trap (Openrouter + Future Generics)

**Date:** 2026-06-19
**Source:** Bos explicit warning during SOT pipeline audit #2

## The Trap

Beberapa LLM provider punya DUA (atau lebih) jenis API key yang serve
**permukaan berbeda** — bukan key cadangan kapasitas. Openrouter adalah
kasus konkret:

| Key type | Endpoint surface | Use case |
|---|---|---|
| `key_purpose='inference'` | `/api/v1/chat/completions`, embedding, completion | Panggil model |
| `key_purpose='provisioning'` | `/api/v1/models`, `/api/v1/keys` | List/manage |

**Akibat pakai key yang salah:**
- Inference key dipake untuk `/v1/models` → **401 Unauthorized**
- Provisioning key dipake untuk chat → response data model bagus, tapi
  organization's data analytics quota terhitung sebagai "management ops"
  dan rate-limited terpisah

## Field Schema

`llm_providers.key_purpose` enum (di schema ramping setelah Bos's 2026-06-19
simplification):
```
['inference', 'provisioning', 'primary', 'secondary', 'experimental', 'backup']
```

Default `get_api_key(pname)` pilih `purpose='provisioning'` karena listing
endpoint butuh provisioning-key. Panggil `get_api_key('openrouter',
'inference')` explicit saat runtime invoke model.

## Tier 2 Downstream Flag

`providers.multi_purpose` distinct dari `multi_account`. Keduanya bisa
True simultan:

| Concept | Mean | Example |
|---|---|---|
| `multi_account=True` | Multiple sibling keys for **capacity paralel** | nvidia ×3 (`primary`, `secondary`, `experimental`) |
| `multi_purpose=True` | Multiple sibling keys for **different surfaces** | openrouter ×2 (inference + provisioning) |
| Both True | Both | openrouter sits here |

Pipeline `sync_providers_from_llm_providers.py` set kedua field + `key_purposes`
(sorted list) di Tier 2 doc.

## Openrouter Real Case (verified 2026-06-19)

```
llm_providers/openrouter:
  account_email=smahud@gmail.com/call        key_purpose=inference
  account_email=smahud@gmail.com/management  key_purpose=provisioning

provider_sync.get_api_key('openrouter', purpose='provisioning')
  → sk-or-v1-...0dc8   (untuk listing /v1/models)  ✓ 341 models fetched

provider_sync.get_api_key('openrouter', purpose='inference')
  → sk-or-v1-...a594   (untuk chat)               ← beda key!

providers/openrouter (Tier 2 consolidation):
  multi_account: True
  multi_purpose: True
  key_purposes: ['inference', 'provisioning']
```

## Pitfalls

- **P-PURPOSE-1**: JANGAN `find_one()` key tanpa filter `key_purpose` —
  akan nondeterministic untuk multi-purpose provider. Pakai purpose-aware
  lookup.
- **P-PURPOSE-2**: Kalau `key_purpose=''` atau null di dokumen SOT,
  `get_api_key` fallback ke first VALID/UNVERIFIED key — yang mungkin saja
  inference key. Pipeline listing akan GAGAL. **Selalu** set `key_purpose`
  untuk provider yang punya multi-purpose.
- **P-PURPOSE-3**: Jangan pernah reuse inference key untuk management API
  di openrouter. Anti-pattern optimal: environment variables berbeda per
  surface di runtime, e.g. `OPENROUTER_INFERENCE_KEY` vs
  `OPENROUTER_PROVISIONING_KEY`. Pipeline listing pakai management-key-only.
- **P-PURPOSE-4**: Test credential sebelum pakai. Setelah fix url
  (`api.felo.ai` → `openapi.felo.ai`), bisa saja SOT key valid tapi
  endpoint mengembalikan HTTP 500 (felo 2026-06-19). Pipeline harus log
  dan skip gracefully.
- **P-PURPOSE-5**: Pattern `get_api_key(pname, purpose)` bukan `get_api_key(pname)`
  random pick. Untuk non-multi-purpose provider, default `provisioning` masih OK
  (semua key serve all surfaces); untuk openrouter-like, WAJIB specify purpose.

## Future Generics

Provider lain yang berpotensi multi-purpose di masa depan:
- Operator-style providers (OpenAI admin keys vs project keys)
- Cloud-hosted providers yang punya separate billing/quota keys
- Enterprise SSO providers dengan IAM role keys

**Cara handle generically**:
1. Pipeline `get_api_key(pname, purpose)` selalu purpose-aware
2. Tier 2 doc propagate `multi_purpose=True` flag untuk cross-reference
3. Schema llm_providers allow `key_purpose` enum extensible (helper not strict)

## Verification Recipe

```bash
# Cek apakah multi-purpose: di Tier 2 `providers` collection
python3 -c "
import pymongo
c = pymongo.MongoClient(host='172.16.103.253', port=27017, username='quantumtraffic', password='***REDACTED-SEE-.env***')
db = c['credentials']
for d in db['providers'].find({'multi_purpose': True}, {'_id':0, 'provider':1, '_multi_purpose':1, 'key_purposes':1}):
    print(d)
"

# Verify openrouter specifically uses provisioning key for sync:
python3 -c "
import sys
sys.path.insert(0, '/root/.hermes/profiles/ilma/sot/discovery')
import provider_sync
key = provider_sync.get_api_key('openrouter', purpose='provisioning')
print(f'provisioning key: {key[:18]}...')
# Then run sync via reconcile_from_llm_providers --apply to confirm 341+ models fetched
"
```
