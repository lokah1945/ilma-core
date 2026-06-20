#!/usr/bin/env python3
"""
sot_add_normalized.py — Add normalized_model field to all models
================================================================
Per Master Rule v2.0 §7: normalized_model is for analysis only,
DO NOT replace original model_id. Just compute and store.
"""
import re
from datetime import datetime, timezone
from pymongo import UpdateOne
from orchestration.sot_ops import get_db, audit_coll


def normalize(mid: str) -> str:
    """Normalize model_id for analysis (rule §7)."""
    if not mid:
        return mid
    n = mid
    # Strip :free, :beta, :preview, :paid suffixes
    n = re.sub(r":(free|beta|preview|paid|thinking)$", "", n)
    # Strip -free, -beta, -preview, -paid suffixes
    n = re.sub(r"-(free|beta|preview|paid|thinking)$", "", n)
    # Strip date versions (e.g., -2024-08-01)
    n = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", n)
    # Strip latest/latest-tag
    n = re.sub(r"~", "", n)
    # Lowercase for comparison
    n = n.lower()
    return n


def main():
    db = get_db()
    models = db["models"]
    cur = models.find({}, {"_id": 1, "model_id": 1})
    bulk = []
    updated = 0
    now = datetime.now(timezone.utc).isoformat()
    for doc in cur:
        mid = doc.get("model_id", "")
        norm = normalize(mid)
        bulk.append(UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {"normalized_model": norm, "original_model_id": mid, "normalized_at": now}}
        ))
        if len(bulk) >= 1000:
            models.bulk_write(bulk, ordered=False)
            updated += len(bulk)
            bulk = []
    if bulk:
        models.bulk_write(bulk, ordered=False)
        updated += len(bulk)

    # Also update model_alias
    aliases_added = 0
    for doc in models.find({"$expr": {"$ne": ["$model_id", "$normalized_model"]}}):
        prov = doc["provider"]
        mid = doc["model_id"]
        norm = doc["normalized_model"]
        try:
            db["model_alias"].update_one(
                {"alias": f"{prov}/{norm}"},
                {"$set": {
                    "alias": f"{prov}/{norm}",
                    "canonical_provider": prov,
                    "canonical_model_id": mid,
                    "alias_source": "normalized_model_v2",
                    "updated_at": now,
                }},
                upsert=True
            )
            aliases_added += 1
        except Exception:
            pass

    # Stats
    total = models.count_documents({})
    has_norm = models.count_documents({"normalized_model": {"$exists": True}})
    diff = models.count_documents({"$expr": {"$ne": ["$model_id", "$normalized_model"]}})

    print(f"Updated: {updated}")
    print(f"Total models: {total}, with normalized_model: {has_norm}")
    print(f"Different (model_id != normalized_model): {diff}")
    print(f"Aliases added: {aliases_added}")

    audit_coll().insert_one({
        "event": "sot_normalize_models",
        "evidence_id": f"ILMA-EVID-{datetime.now(timezone.utc).strftime('%Y%m%d')}-NORM-{int(datetime.now(timezone.utc).timestamp()) % 100000:05d}",
        "provider": "*",
        "model_id": "*",
        "event_type": "model_normalize",
        "actor": "sot_add_normalized",
        "source_collection": "models",
        "event_at": datetime.now(timezone.utc),
        "updated": updated,
        "total": total,
        "different": diff,
        "aliases": aliases_added,
        "timestamp": now,
    })


if __name__ == "__main__":
    main()
