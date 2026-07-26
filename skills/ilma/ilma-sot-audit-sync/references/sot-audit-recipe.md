# SOT Audit Recipe — Working Python Snippets

Verified 2026-07-24. Run from `/root/.hermes/profiles/ilma`.

## 1. Connect local (no-auth) + cloud (SOT-URI)

```python
import pymongo

# LOCAL — NO AUTH (mongod terbuka)
L = pymongo.MongoClient("127.0.0.1", 27017, serverSelectionTimeoutMS=5000)
L.admin.command("ping")  # OK

# CLOUD — ambil URI dari SOT, JANGAN dari .env
doc = L["credentials"]["infra_providers"].find_one({"provider": "mongodb-cloud"})
uri = doc["accounts"]["bos"]["api_token"]   # mongodb://quantumtraffic:***@172.16.103.253:27017/...?authSource=admin&replicaSet=rs0
C = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8000)
C.admin.command("ping")  # OK
```

## 2. Hitung provider aktif (T1)

```python
coll = L["credentials"]["llm_providers"]
print("total:", coll.count_documents({}))
print("is_active=True:", coll.count_documents({"is_active": True}))   # PAKAI INI, BUKAN status
print("is_active=False:", coll.count_documents({"is_active": False}))
# status field = None untuk semua doc → jangan dipakai
```

## 3. Tier-by-tier drift comparison

```python
T1 = ["llm_providers","infra_providers","system_credentials"]
T2 = ["providers","models","model_intelligence","model_capabilities","model_enrichment","model_benchmark","model_alias"]
T3 = ["sot_jobs","sot_sync_state","model_audit_trail","model_lifecycle_events",
      "provider_lifecycle_events","sot_backups","sot_schema_registry","_meta","sessions","crypto_exchanges","search_providers","messaging"]

def ids(coll): return set(d["_id"] for d in coll.find({},{"_id":1}))

for tier, cols in [("T1",T1),("T2",T2),("T3",T3)]:
    print(f"\n### {tier}")
    for col in cols:
        lc, cc = L["credentials"][col], C["credentials"][col]
        li, ci = ids(lc), ids(cc)
        flag = ""
        if len(li) != len(ci): flag += " COUNT-DIFF"
        if li - ci: flag += f" +{len(li-ci)}_only_local"
        if ci - li: flag += f" +{len(ci-li)}_only_cloud"
        print(f"  {col:22} L={len(li):6} C={len(ci):6}{flag}")
```

## 4. Field-level diff (exclude volatile) pada doc common

```python
SKIP = {"_id","_sync_source","_sync_generation","_sync_timestamp","_sync_dirty",
        "verified_at","restored_at","added","updated_at","last_sync",
        "billing_classified_at","refreshed_at","discovered_at","_sot_last_sync"}
def norm(v): return v.isoformat() if hasattr(v,"isoformat") else v

coll = "llm_providers"
lm = {d["_id"]:d for d in L["credentials"][coll].find({})}
cm = {d["_id"]:d for d in C["credentials"][coll].find({})}
diffs = 0
for k in set(lm) & set(cm):
    a, b = lm[k], cm[k]
    for f in set(a) | set(b):
        if f in SKIP: continue
        if norm(a.get(f)) != norm(b.get(f)):
            diffs += 1
            if diffs <= 10:
                print(f"  {a.get('provider')}/{a.get('account_email')} f={f}: L={a.get(f)!r} C={b.get(f)!r}")
print(f"TOTAL field diffs (common): {diffs}")
```

## 5. Sync daemon fix patch (already applied to scripts/ilma_two_way_sync.py)

### `_get_local_client()` — no-auth probe first
```python
def _get_local_client():
    try:
        _c = MongoClient(host=LOCAL_HOST, port=LOCAL_PORT, directConnection=True, serverSelectionTimeoutMS=4000)
        _c.admin.command("ping")
        return _c
    except Exception:
        pass
    return MongoClient(host=LOCAL_HOST, port=LOCAL_PORT, username=LOCAL_USER,
                       password=LOCAL_PASS, authSource=LOCAL_AUTH_DB,
                       directConnection=True, serverSelectionTimeoutMS=5000)
```

### `_resolve_remote_from_sot()` — no-auth probe for local SOT lookup
```python
# ganti blok connect local (awalnya selalu auth) jadi:
c = None
try:
    c = pymongo.MongoClient("127.0.0.1", 27017, directConnection=True, serverSelectionTimeoutMS=4000)
    c.admin.command("ping")
except Exception:
    local_user = env.get("ILMA_MONGO_LOCAL_USER") or env.get("ILMA_MONGO_USER") or "ilma_sync"
    local_pass = env.get("ILMA_MONGO_LOCAL_PASS") or env.get("ILMA_MONGO_PASS")
    try:
        c = pymongo.MongoClient("127.0.0.1", 27017, username=local_user, password=local_pass,
                                authSource="admin", directConnection=True, serverSelectionTimeoutMS=4000)
        c.admin.command("ping")
    except Exception as _ce:
        import sys as _sys; print(f"[SOT] local probe failed: {_ce}", file=_sys.stderr); return None
```

## 6. Recovery commands
```bash
# restart daemon
systemctl --user restart ilma-sync-daemon.service
systemctl --user is-active ilma-sync-daemon.service   # -> active

# reconcile (lambat ~7min, jalankan background)
python3 scripts/ilma_two_way_sync.py --reconcile --db credentials QuantumTrafficDB

# tail log
tail -f run/ilma-sync-daemon.log
```
