#!/usr/bin/env python3
"""
purge_to_live_only.py — Bos command 2026-06-18
=================================================
End goal: SOT `models` collection hanya berisi model siap-pakai
dari provider yang punya api_key valid (live-verified).

WORKING providers (live /v1/models endpoint returns 200):
  nvidia (3 keys), minimax, openrouter (2 keys), xai, bluesminds, groq, together

Steps:
  1. Backup current state
  2. Purge non-WORKING providers from models + 5 downstream collections
  3. Sync live /v1/models for WORKING providers → insert new models
  4. Verify end-to-end (only valid models remain)
"""
import json
import pymongo
from datetime import datetime, timezone
from pymongo import MongoClient

MONGO_HOST = "127.0.0.1"
MONGO_PORT = 27017
MONGO_USER = "quantumtraffic"
MONGO_PASS = (__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), ""))

# WORKING = verified live
WORKING_PROVIDERS = {"nvidia", "minimax", "openrouter", "xai", "bluesminds", "groq", "together"}

# Collections to purge (models + downstream)
# ⛔ Bos 2026-06-18: llm_providers is FROZEN — DO NOT purge (Bos mandate)
MODELS_COLL = ["models", "model_intelligence", "model_benchmark",
               "model_capabilities", "model_enrichment", "model_lifecycle_events"]
EXTRA_COLL = ["model_alias", "provider_lifecycle_events"]  # llm_providers EXCLUDED (FROZEN)

BACKUP_DIR = "/root/.hermes/profiles/ilma/sot_backups/pre_live_only_purge_20260618"

def get_client():
    return MongoClient(
        host=MONGO_HOST, port=MONGO_PORT,
        username=MONGO_USER, password=MONGO_PASS,
        serverSelectionTimeoutMS=15000,
    )

def backup():
    """Backup all current state to disk."""
    import os
    os.makedirs(f"{BACKUP_DIR}/dump/credentials", exist_ok=True)
    db = get_client()["credentials"]
    for c in db.list_collection_names():
        if c.startswith("_"):
            continue
        if c in ("sot_backups",):
            continue
        docs = list(db[c].find({}))
        with open(f"{BACKUP_DIR}/dump/credentials/{c}.json", "w") as f:
            json.dump(docs, f, default=str)
    print(f"  📦 Backup saved to {BACKUP_DIR}/dump/credentials/")

def purge_non_working(dry_run=True):
    """Remove all docs where provider NOT in WORKING_PROVIDERS from models + 5 downstream + model_alias + provider_lifecycle_events.

    ⛔ Bos 2026-06-18: llm_providers is FROZEN — skipped.
    """
    db = get_client()["credentials"]
    summary = {}
    for cname in MODELS_COLL + EXTRA_COLL:
        coll = db[cname]
        if cname == "models":
            query = {"provider": {"$nin": list(WORKING_PROVIDERS)}}
        elif cname == "model_alias":
            query = {"$or": [
                {"canonical_provider": {"$nin": list(WORKING_PROVIDERS) + [None]}},
                {"alias": {"$regex": "^(openai|alibaba|aimlapi|nous|byteplus|blackbox|google|cerebras|opencode|felo|bytez|tinyfish|sumopod|ollama|aisure)/", "$options": "i"}},
            ]}
        elif cname == "provider_lifecycle_events":
            # Keep only WORKING llm_providers
            query = {"provider": {"$nin": list(WORKING_PROVIDERS)}}
        else:
            query = {"$or": [
                {"provider": {"$nin": list(WORKING_PROVIDERS)}},
                {"subprovider": {"$nin": list(WORKING_PROVIDERS) + [None]}},
                {"model_id": {"$regex": "^(openai|alibaba|aimlapi|nous|byteplus|blackbox|google|cerebras|opencode|felo|bytez|tinyfish|sumopod|ollama|aisure)/", "$options": "i"}},
            ]}
        matched = coll.count_documents(query)
        if not dry_run and matched > 0:
            result = coll.delete_many(query)
            deleted = result.deleted_count
        else:
            deleted = 0
        summary[cname] = {"matched": matched, "deleted": deleted}
    return summary

def insert_live_models(dry_run=True):
    """Insert live /v1/models response into SOT models collection."""
    import urllib.request, urllib.error, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"

    with open("/tmp/llm_providers_dump.json") as f:
        providers = json.load(f)
    with open("/tmp/live_models.json") as f:
        live = json.load(f)

    db = get_client()["credentials"]
    coll = db["models"]
    inserted = 0
    skipped = 0

    # Map provider → first account_email (for now)
    provider_account = {}
    for p in providers:
        if p["provider"] not in provider_account:
            provider_account[p["provider"]] = p["account_email"]

    for prov, model_ids in live.items():
        if prov not in WORKING_PROVIDERS:
            continue
        account = provider_account.get(prov, "owner")
        for mid in model_ids:
            # Check if exists
            existing = coll.find_one({"provider": prov, "model_id": mid})
            if existing:
                skipped += 1
                continue
            if dry_run:
                continue
            doc = {
                "provider": prov,
                "model_id": mid,
                "model_name": mid,
                "account_email": account,
                "is_active": True,
                "is_free": False,  # unknown — default False (safer for routing)
                "free_tier": False,
                "status": "active",
                "source": "live_models_purge_20260618",
                "discovered_via": "live_purge_20260618",  # enum-valid (audit M5)
                # FIX 2026-06-19: store BSON datetimes, not ISO strings, so date-range
                # queries / freshness guards work natively (audit M2).
                "discovered_at": datetime.now(timezone.utc),
                "refreshed_at": datetime.now(timezone.utc),
            }
            coll.insert_one(doc)
            inserted += 1
    return {"inserted": inserted, "skipped_existing": skipped}

def verify():
    """End-to-end verify: only WORKING providers in SOT models + counts."""
    db = get_client()["credentials"]
    coll = db["models"]
    pipeline = [{"$group": {"_id": "$provider", "count": {"$sum": 1}}}]
    print("="*70)
    print("FINAL STATE: SOT models collection")
    print("="*70)
    by_prov = {}
    for d in coll.aggregate(pipeline):
        by_prov[d["_id"]] = d["count"]
        print(f"  {d['_id']:15s} | {d['count']:5d} models")
    print()
    print(f"  KEEP providers: {sorted(set(by_prov.keys()) & WORKING_PROVIDERS)}")
    leak = set(by_prov.keys()) - WORKING_PROVIDERS
    if leak:
        print(f"  ❌ LEAK (non-WORKING in DB): {leak}")
    else:
        print(f"  ✅ ZERO LEAK — only WORKING providers in SOT models")
    return by_prov


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry-run"
    print(f"Mode: {mode}")
    print()
    if mode == "backup":
        print("Step 1: Backup")
        backup()
    elif mode == "purge":
        print("Step 1: Backup")
        backup()
        print("Step 2: Purge non-WORKING providers")
        s = purge_non_working(dry_run=False)
        for c, v in s.items():
            print(f"  {c:25s} | matched={v['matched']:5d} deleted={v['deleted']:5d}")
        print("Step 3: Verify")
        verify()
    elif mode == "sync":
        print("Step 1: Insert live /v1/models into SOT")
        s = insert_live_models(dry_run=False)
        print(f"  Inserted: {s['inserted']}, Skipped (existing): {s['skipped_existing']}")
        print("Step 2: Verify")
        verify()
    elif mode == "all":
        print("Step 1: Backup")
        backup()
        print("\nStep 2: Purge non-WORKING providers")
        s = purge_non_working(dry_run=False)
        for c, v in s.items():
            print(f"  {c:25s} | matched={v['matched']:5d} deleted={v['deleted']:5d}")
        print("\nStep 3: Insert live /v1/models into SOT")
        s = insert_live_models(dry_run=False)
        print(f"  Inserted: {s['inserted']}, Skipped (existing): {s['skipped_existing']}")
        print("\nStep 4: Final verify")
        verify()
    else:  # dry-run
        print("DRY-RUN: would purge these:")
        s = purge_non_working(dry_run=True)
        for c, v in s.items():
            print(f"  {c:25s} | would_delete={v['matched']}")
        print()
        print("DRY-RUN: would insert these live models:")
        s = insert_live_models(dry_run=True)
        print(f"  Would insert: {s['inserted']}, Would skip: {s['skipped_existing']}")
        print()
        print("DRY-RUN current state:")
        verify()
