# SOT Split-Brain Dedup & Final Verify Script

Reusable script untuk menyelesaikan drift sisa setelah reconcile gagal karena
cross-side duplicates (same `provider+model_id`, different `_id` → E11000).

## Usage
```bash
python3 - <<'PY'
# paste block di bawah
PY
```

## Script (run dari /root/.hermes/profiles/ilma)
```python
import pymongo
from bson import ObjectId

# 1) Connect local (NO-AUTH) + cloud (SOT URI)
c = pymongo.MongoClient(host="127.0.0.1", port=27017, serverSelectionTimeoutMS=5000)
doc = c["credentials"]["infra_providers"].find_one({"provider": "mongodb-cloud"})
uri = doc["accounts"]["bos"]["api_token"]
rc = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8000)
L = c["credentials"]; C = rc["credentials"]

def ids(col): return set(d["_id"] for d in col.find({}, {"_id": 1}))

# 2) T2 model collections: drop cloud cross-dups, push local-only
for col in ["models", "model_intelligence", "model_capabilities", "model_enrichment"]:
    li = ids(L[col]); ci = ids(C[col])
    cloud_only = ci - li
    if cloud_only:
        r = C[col].delete_many({"_id": {"$in": list(cloud_only)}})
        print(f"{col}: dropped {r.deleted_count} cloud dups")
    li2 = ids(L[col]); ci2 = ids(C[col])
    for i in (li2 - ci2):
        d = L[col].find_one({"_id": i})
        C[col].replace_one({"_id": i}, d, upsert=True)
    a = ids(L[col]); b = ids(C[col])
    print(f"  {col}: L={len(a)} C={len(b)} {'OK' if a == b else 'drift=' + str(len(a ^ b))}")

# 3) infra_providers: dedup by provider (keep local newer)
for p in L.infra_providers.distinct("provider"):
    lo = L.infra_providers.find_one({"provider": p})
    co = C.infra_providers.find_one({"provider": p})
    if co and lo["_id"] != co["_id"]:
        C.infra_providers.delete_one({"_id": co["_id"]})
        C.infra_providers.replace_one({"_id": lo["_id"]}, lo, upsert=True)
        print(f"infra_providers: synced {p}")

# 4) model_benchmark (volatile cache): drop cloud stale by (provider,model_id), push local
lkeys = set((d["provider"], d["model_id"]) for d in L.model_benchmark.find({}, {"provider": 1, "model_id": 1}))
cdrop = [d["_id"] for d in C.model_benchmark.find({}, {"provider": 1, "model_id": 1, "_id": 1})
         if (d["provider"], d["model_id"]) in lkeys and d["_id"] not in ids(L.model_benchmark)]
if cdrop:
    C.model_benchmark.delete_many({"_id": {"$in": [ObjectId(x) if not isinstance(x, ObjectId) else x for x in cdrop]}})
li = ids(L.model_benchmark); ci = ids(C.model_benchmark)
for i in (li - ci):
    d = L.model_benchmark.find_one({"_id": i})
    C.model_benchmark.replace_one({"_id": i}, d, upsert=True)
print(f"model_benchmark: L={len(li)} C={len(ids(C.model_benchmark))}")

# 5) model_lifecycle_events: pull cloud-only to local (initial states valid)
ci = ids(C.model_lifecycle_events); li = ids(L.model_lifecycle_events)
for i in (ci - li):
    d = C.model_lifecycle_events.find_one({"_id": i})
    L.model_lifecycle_events.replace_one({"_id": i}, d, upsert=True)
print(f"model_lifecycle_events: pulled {len(ci - li)}")

# 6) FINAL VERIFY
print("\n=== FINAL ===")
for col in ["llm_providers","infra_providers","providers","models","model_intelligence",
            "model_capabilities","model_enrichment","model_benchmark","model_alias",
            "model_audit_trail","model_lifecycle_events","provider_lifecycle_events",
            "sot_backups","sot_schema_registry","_meta","crypto_exchanges","search_providers","messaging"]:
    a = ids(L[col]); b = ids(C[col])
    flag = "OK" if a == b else f"drift={len(a ^ b)}"
    print(f"  {col:22} L={len(a):6} C={len(b):6} {flag}")
rc.close()
```

## Pitfalls
- `delete_one({"_id": "string"})` → 0 deleted. Cast: `ObjectId("string")`.
- `replace_one` replacement harus dict — `find_one` returns dict, OK.
- `model_benchmark` kecil (3-10 docs) — jangan panic jika count aneh setelah reconcile.
- `antigravity/wrapper` di `llm_providers` akan REJECTED oleh cloud validator (api_key='***',
  minLength:5) — expected, biarkan.
- `sot_sync_state`/`sot_jobs` beda _id = NORMAL (daemon-private per-side state).
