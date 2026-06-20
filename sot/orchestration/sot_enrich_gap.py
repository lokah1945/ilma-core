#!/usr/bin/env python3
"""
sot_enrich_gap.py — Fill enrichment gap with smart defaults
============================================================
For models without enrichment entries, write default enrichment
based on model_id heuristics (avoids API calls, idempotent).
"""
import re
from datetime import datetime, timezone
from pymongo import UpdateOne
from orchestration.sot_ops import (
    get_db, models_coll, audit_coll,
)

# Heuristic capability inference from model_id
def infer_caps(mid: str) -> dict:
    mid_l = mid.lower()
    caps = []
    cats = []

    # Modality
    if any(k in mid_l for k in ["vision", "vl", "image", "video"]):
        caps.append("vision")
        cats.append("multimodal")
    if "audio" in mid_l or "tts" in mid_l or "asr" in mid_l or "whisper" in mid_l:
        caps.append("audio")
        cats.append("multimodal")
    if "embed" in mid_l:
        caps.append("embedding")
        cats.append("embedding")
    if "rerank" in mid_l:
        caps.append("rerank")
        cats.append("ranking")

    # Reasoning
    if any(k in mid_l for k in ["reason", "think", "r1", "o1", "o3", "o4"]):
        caps.append("reasoning")
        cats.append("reasoning")

    # Code
    if any(k in mid_l for k in ["coder", "code", "deepseek-coder", "starcoder"]):
        caps.append("code")
        cats.append("coding")

    # Default
    if not caps:
        caps = ["text"]
        cats = ["general"]
    if "general" not in cats:
        cats.append("general")

    # Context window inference
    ctx = 8192  # default
    if "32k" in mid_l or "32k-" in mid_l:
        ctx = 32768
    elif "128k" in mid_l or "128k-" in mid_l or "200k" in mid_l or "1m" in mid_l or "1-m" in mid_l:
        ctx = 131072 if "1m" not in mid_l and "1-m" not in mid_l else 1048576
    elif "16k" in mid_l:
        ctx = 16384
    elif "gpt-5" in mid_l or "claude-opus" in mid_l or "claude-sonnet-4" in mid_l:
        ctx = 200000
    elif "claude" in mid_l:
        ctx = 200000
    elif "gemini" in mid_l and "pro" in mid_l:
        ctx = 2000000
    elif "llama-3" in mid_l or "llama-4" in mid_l:
        ctx = 131072
    elif "qwen" in mid_l and "2.5" in mid_l:
        ctx = 131072
    elif "mistral" in mid_l or "mixtral" in mid_l:
        ctx = 32768

    # Tools support
    supports_tools = "vision" not in caps and "embedding" not in caps and "rerank" not in caps and "audio" not in caps

    return {
        "capabilities": caps,
        "categories": cats,
        "context_window": ctx,
        "supports_tools": supports_tools,
        "supports_vision": "vision" in caps,
        "is_reasoning": "reasoning" in caps,
        "is_code": "code" in caps,
    }


def main():
    db = get_db()
    models = db["models"]
    enrich = db["model_enrichment"]

    # Find models without enrichment
    pipeline = [
        {"$lookup": {
            "from": "model_enrichment",
            "let": {"p": "$provider", "m": "$model_id"},
            "pipeline": [{"$match": {"$expr": {"$and": [
                {"$eq": ["$provider", "$$p"]},
                {"$eq": ["$model_id", "$$m"]}
            ]}}}],
            "as": "enrich"
        }},
        {"$match": {"enrich": {"$size": 0}}},
        {"$project": {"provider": 1, "model_id": 1, "status": 1, "is_active": 1}},
    ]
    no_enrich = list(models.aggregate(pipeline))
    print(f"Models without enrichment: {len(no_enrich)}")

    # Bulk infer and write
    added = 0
    bulk_ops = []
    now = datetime.now(timezone.utc).isoformat()
    for m in no_enrich:
        prov = m["provider"]
        mid = m["model_id"]
        inferred = infer_caps(mid)
        doc = {
            "provider": prov,
            "model_id": mid,
            "context_window": inferred["context_window"],
            "capabilities": inferred["capabilities"],
            "categories": inferred["categories"],
            "supports_tools": inferred["supports_tools"],
            "supports_vision": inferred["supports_vision"],
            "is_reasoning": inferred["is_reasoning"],
            "is_code": inferred["is_code"],
            "enrichment_source": "heuristic_gap_fill",
            "is_active": m.get("is_active", True),
            "status": m.get("status", "active"),
            "tier": "C" if m.get("is_active", True) else "Z",
            "updated_at": now,
        }
        bulk_ops.append(UpdateOne(
            {"provider": prov, "model_id": mid},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        ))
        if len(bulk_ops) >= 500:
            enrich.bulk_write(bulk_ops, ordered=False)
            added += len(bulk_ops)
            bulk_ops = []

    if bulk_ops:
        enrich.bulk_write(bulk_ops, ordered=False)
        added += len(bulk_ops)

    print(f"Added enrichment: {added}")
    print(f"Total enrichment: {enrich.count_documents({})}")

    # Also update model_capabilities from new enrichment
    cap_ops = []
    cap_count = 0
    for doc in enrich.find({"enrichment_source": "heuristic_gap_fill"}):
        cap_ops.append(UpdateOne(
            {"provider": doc["provider"], "model_id": doc["model_id"]},
            {"$set": {
                "provider": doc["provider"],
                "model_id": doc["model_id"],
                "capabilities": doc["capabilities"],
                "categories": doc["categories"],
                "updated_at": now,
            }},
            upsert=True,
        ))
        if len(cap_ops) >= 500:
            db["model_capabilities"].bulk_write(cap_ops, ordered=False)
            cap_count += len(cap_ops)
            cap_ops = []
    if cap_ops:
        db["model_capabilities"].bulk_write(cap_ops, ordered=False)
        cap_count += len(cap_ops)
    print(f"Updated capabilities: {cap_count}")

    audit_coll().insert_one({
        "event": "sot_enrich_gap_fill",
        "evidence_id": f"ILMA-EVID-{datetime.now(timezone.utc).strftime('%Y%m%d')}-GAPFILL-{int(datetime.now(timezone.utc).timestamp()) % 100000:05d}",
        "provider": "*",
        "model_id": "*",
        "event_type": "enrichment_gap_fill",
        "actor": "sot_enrich_gap",
        "source_collection": "model_enrichment",
        "event_at": datetime.now(timezone.utc),
        "added": added,
        "capabilities_updated": cap_count,
        "timestamp": now,
    })


if __name__ == "__main__":
    main()
