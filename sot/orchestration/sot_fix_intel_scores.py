#!/usr/bin/env python3
"""
sot_fix_intel_scores.py — Fix intelligence docs with score_tier but no composite_score
=========================================================================================
For each model_intelligence doc with score_tier set but composite_score is null,
compute a heuristic composite_score based on:
- pricing (free models get lower score)
- context_window
- capabilities
- is_active
"""
from datetime import datetime, timezone
from pymongo import UpdateOne
from .sot_ops import get_db, audit_coll


def derive_composite_score(doc: dict) -> float:
    """Derive a heuristic composite score 0-100 from available fields."""
    score = 50.0  # default baseline

    # Active bonus
    if doc.get("is_active", False):
        score += 10

    # Free penalty (no proven cost-to-quality)
    if doc.get("is_free", False):
        score -= 5

    # Disabled penalty
    if doc.get("disabled", False):
        score -= 20

    # Capabilities bonus
    caps = doc.get("capabilities", [])
    if "reasoning" in caps:
        score += 8
    if "code" in caps:
        score += 5
    if "vision" in caps:
        score += 3

    # Context window bonus
    ctx = doc.get("context_window", 0) or 0
    if ctx >= 200000:
        score += 8
    elif ctx >= 128000:
        score += 6
    elif ctx >= 32000:
        score += 3
    elif ctx >= 8192:
        score += 1

    # Quality score from existing data
    qs = doc.get("quality_score", 0) or 0
    if qs > 0:
        score = score * 0.6 + qs * 0.4

    # Description length heuristic (richer metadata = better)
    desc = doc.get("description", "") or ""
    if len(desc) > 200:
        score += 2

    # Trust score
    ts = doc.get("trust_score", 0) or 0
    if ts > 0:
        score = score * 0.7 + ts * 0.3

    # Clamp to 0-100
    score = min(100.0, max(0.0, score))
    return score  # 0-100 scale, normalized to 0-1 by caller


def tier_from_score(score_0_1: float) -> str:
    """Given 0-1 score, return tier."""
    if score_0_1 >= 0.85:
        return "A"
    elif score_0_1 >= 0.70:
        return "B"
    elif score_0_1 >= 0.55:
        return "C"
    elif score_0_1 >= 0.40:
        return "D"
    else:
        return "E"


def main():
    db = get_db()
    intel = db["model_intelligence"]

    # Find docs to fix (composite_score > 1.0 OR score_tier set but no composite_score)
    pipeline = [
        {"$match": {
            "score_tier": {"$exists": True, "$ne": None},
            "$or": [
                {"composite_score": None},
                {"composite_score": {"$exists": False}},
                {"composite_score": {"$gt": 1.0}}
            ]
        }},
    ]
    cur = intel.aggregate(pipeline)
    bulk = []
    fixed = 0
    now = datetime.now(timezone.utc)
    tier_changes = {}
    for doc in cur:
        comp_0_100 = derive_composite_score(doc)
        comp_0_1 = round(comp_0_100 / 100.0, 4)  # normalize to 0-1
        new_tier = tier_from_score(comp_0_1)
        old_tier = doc.get("score_tier")
        if new_tier != old_tier:
            tier_changes[(old_tier, new_tier)] = tier_changes.get((old_tier, new_tier), 0) + 1
        bulk.append(UpdateOne(
            {"_id": doc["_id"]},
            {"$set": {
                "composite_score": comp_0_1,
                "score_tier": new_tier,
                "score_source": "heuristic_derived",
                "score_derived_at": now,
            }}
        ))
        if len(bulk) >= 500:
            intel.bulk_write(bulk, ordered=False)
            fixed += len(bulk)
            bulk = []
    if bulk:
        intel.bulk_write(bulk, ordered=False)
        fixed += len(bulk)

    print(f"Fixed: {fixed} intelligence docs")
    print(f"Tier changes: {tier_changes}")

    # Verify
    remaining = intel.count_documents({
        "score_tier": {"$exists": True, "$ne": None},
        "$or": [
            {"composite_score": None},
            {"composite_score": {"$exists": False}}
        ]
    })
    print(f"Remaining without composite_score: {remaining}")

    audit_coll().insert_one({
        "event": "sot_fix_intel_scores",
        "evidence_id": f"ILMA-EVID-{datetime.now(timezone.utc).strftime('%Y%m%d')}-INTSCO-{int(datetime.now(timezone.utc).timestamp()) % 100000:05d}",
        "provider": "*",
        "model_id": "*",
        "event_type": "model_updated",
        "actor": "sot_fix_intel_scores",
        "source_collection": "model_intelligence",
        "event_at": datetime.now(timezone.utc),
        "fixed": fixed,
        "tier_changes": {f"{k[0]}->{k[1]}": v for k, v in tier_changes.items()},
        "remaining": remaining,
        "timestamp": now.isoformat(),
    })


if __name__ == "__main__":
    main()
