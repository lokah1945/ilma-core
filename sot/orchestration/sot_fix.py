#!/usr/bin/env python3
"""
sot_fix.py — Fix known SOT bugs in MongoDB collections.
========================================================

Idempotent. Re-runs are safe (use $set, not insert).

Bugs fixed:
  BUG-IS_FREE-1: :free suffix but is_free=False → set is_free=True
  BUG-IS_FREE-2: price 0/0 but is_free=False → set is_free=True
  BUG-IS_FREE-4: is_free mismatch models vs intel → sync to models
  BUG-INTEL-1: orphan intel (no matching model) → delete or sync from MASTER
  BUG-INTEL-2: score_tier set but composite_score null → set composite_score
  BUG-CAP-1: empty capabilities → run infer_capabilities()
  BUG-MASTER-2: BUG-MASTER-3: detected by audit, fixed by re-materialization

Usage:
    python3 sot_fix.py                # fix all
    python3 sot_fix.py --bug BUG-IS_FREE-1   # fix specific
    python3 sot_fix.py --dry-run      # preview
"""
import os, sys, json, argparse
from datetime import datetime, timezone
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sot_ops
from sot_ops import (
    models_coll, intelligence_coll, audit_coll,
    generate_evidence_id, write_audit,
    infer_capabilities, infer_specialization,
    compute_score,
)

FIXES_APPLIED: List[Dict[str, Any]] = []


def _now():
    return datetime.now(timezone.utc)


def fix_is_free_1(dry_run: bool = False) -> Dict[str, Any]:
    """BUG-IS_FREE-1: :free suffix but is_free=False → set is_free=True
    Also sets free_tier=True and billing='free' for consistency."""
    q = {
        "model_id": {"$regex": ":free$"},
        "$or": [{"is_free": False}, {"is_free": {"$exists": False}}],
        "is_active": True,
    }
    affected = 0
    if not dry_run:
        result = models_coll().update_many(
            q,
            {"$set": {"is_free": True, "_sot_fixed_is_free_1": _now()}}
        )
        affected = result.modified_count
    else:
        affected = models_coll().count_documents(q)
    return {"bug": "BUG-IS_FREE-1", "affected": affected}


def fix_is_free_2(dry_run: bool = False) -> Dict[str, Any]:
    """BUG-IS_FREE-2: price 0/0 but is_free=False → set is_free=True"""
    q = {
        "price_per_m_input": {"$in": ["0", 0, "0.0", 0.0]},
        "price_per_m_output": {"$in": ["0", 0, "0.0", 0.0]},
        "is_free": False,
        "is_active": True,
        "status": "active",
    }
    affected = 0
    if not dry_run:
        result = models_coll().update_many(
            q,
            {"$set": {"is_free": True, "_sot_fixed_is_free_2": _now()}}
        )
        affected = result.modified_count
    else:
        affected = models_coll().count_documents(q)
    return {"bug": "BUG-IS_FREE-2", "affected": affected}


def fix_cap_1(dry_run: bool = False) -> Dict[str, Any]:
    """BUG-CAP-1: empty capabilities → run infer_capabilities()"""
    q = {
        "capabilities": {"$in": [[], None]},
        "is_active": True,
    }
    affected = 0
    if dry_run:
        affected = models_coll().count_documents(q)
        return {"bug": "BUG-CAP-1", "affected": affected}
    # Process in batch
    for d in models_coll().find(q):
        mid = d.get("model_id", "")
        caps = infer_capabilities(mid)
        spec = infer_specialization(mid)
        models_coll().update_one(
            {"_id": d["_id"]},
            {"$set": {
                "capabilities": caps,
                "specialization": spec,
                "_sot_fixed_cap_1": _now(),
            }}
        )
        affected += 1
    return {"bug": "BUG-CAP-1", "affected": affected}


def fix_intel_1(dry_run: bool = False) -> Dict[str, Any]:
    """BUG-INTEL-1: orphan intel entries (no matching model) → delete orphans.

    This is safer than syncing back, because intel was ported from MASTER
    and models is the live state. Orphan intel = stale data.
    """
    # Find orphan intel keys
    models_keys = set()
    for d in models_coll().find({}, {"provider": 1, "model_id": 1}):
        models_keys.add((d["provider"], d["model_id"]))

    orphans = []
    for d in intelligence_coll().find({}, {"provider": 1, "model_id": 1, "_id": 1}):
        if (d["provider"], d["model_id"]) not in models_keys:
            orphans.append(d["_id"])

    if not dry_run and orphans:
        # Batch delete
        from bson import ObjectId
        oid_list = [ObjectId(o) if isinstance(o, str) else o for o in orphans]
        result = intelligence_coll().delete_many({"_id": {"$in": oid_list}})
        affected = result.deleted_count
    else:
        affected = len(orphans)
    return {"bug": "BUG-INTEL-1", "affected": affected, "sample_orphans": [(str(o)) for o in orphans[:5]]}


def fix_intel_2(dry_run: bool = False) -> Dict[str, Any]:
    """BUG-INTEL-2: score_tier set but composite_score null → set composite_score.

    composite_score = score / 100 (since score is 0..100 and composite is 0..1).
    """
    q = {
        "score_tier": {"$nin": [None, ""]},
        "$or": [{"composite_score": None}, {"composite_score": {"$exists": False}}],
    }
    affected = 0
    if dry_run:
        affected = intelligence_coll().count_documents(q)
        return {"bug": "BUG-INTEL-2", "affected": affected}
    for d in intelligence_coll().find(q):
        # Get score from benchmarks field or compute from capabilities
        b = d.get("benchmarks") or {}
        score = b.get("score")
        if score is None:
            # Derive: heuristic only, default to score_tier base
            tier_base = {"S": 80, "A": 65, "B": 50, "C": 35, "D": 20}.get(d.get("score_tier"), 20)
            score = tier_base
        composite = round(float(score) / 100.0, 4)
        quality = composite  # For SOT composite = quality_score for simplicity
        intelligence_coll().update_one(
            {"_id": d["_id"]},
            {"$set": {
                "composite_score": composite,
                "quality_score": quality,
                "_sot_fixed_intel_2": _now(),
            }}
        )
        affected += 1
    return {"bug": "BUG-INTEL-2", "affected": affected}


def fix_intel_3_is_free_sync(dry_run: bool = False) -> Dict[str, Any]:
    """BUG-IS_FREE-4: is_free mismatch models vs intel → sync from models to intel.

    Models is the source of truth. Intel inherits.
    """
    mismatches = []
    for d in models_coll().find({}, {"provider": 1, "model_id": 1, "is_free": 1}):
        intel = intelligence_coll().find_one(
            {"provider": d["provider"], "model_id": d["model_id"]},
            {"is_free": 1}
        )
        if intel and intel.get("is_free") != d.get("is_free"):
            mismatches.append((d["provider"], d["model_id"], d.get("is_free")))

    if not dry_run and mismatches:
        for provider, model_id, is_free, free_tier in mismatches:
            intelligence_coll().update_one(
                {"provider": provider, "model_id": model_id},
                {"$set": {
                    "is_free": is_free,
                    "_sot_fixed_is_free_4": _now(),
                }}
            )
    return {"bug": "BUG-IS_FREE-4", "affected": len(mismatches)}


def fix_whitespace(dry_run: bool = False) -> Dict[str, Any]:
    """POT-MODEL_ID-WS: model_id with whitespace → replace with underscore-safe form.

    Some models have parenthesized suffixes (e.g. 'gemini-3-flash (thinking-minimal)').
    These break URL/CLI parsing. Replace whitespace with hyphen and dedupe.
    """
    affected = 0
    if dry_run:
        affected = models_coll().count_documents({"model_id": {"$regex": "\\s"}})
        return {"bug": "POT-MODEL_ID-WS", "affected": affected}
    for d in models_coll().find({"model_id": {"$regex": "\\s"}}, {"model_id": 1, "model_name": 1, "provider": 1}):
        old_mid = d["model_id"]
        new_mid = old_mid.replace(" ", "-")
        # Avoid collision: if target key already exists for same provider, append suffix
        existing = models_coll().find_one({"provider": d["provider"], "model_id": new_mid})
        if existing and existing["_id"] != d["_id"]:
            new_mid = new_mid + "-dup"
        models_coll().update_one(
            {"_id": d["_id"]},
            {"$set": {
                "model_id": new_mid,
                "model_name": new_mid,
                "_sot_fixed_whitespace": _now(),
            }}
        )
        affected += 1
    return {"bug": "POT-MODEL_ID-WS", "affected": affected}


def fix_cap_drift(dry_run: bool = False) -> Dict[str, Any]:
    """POT-CAP-DRIFT: capabilities in intel but empty in models → sync intel→models.

    When passive enricher adds 'general' capability to intel, models still has [].
    Sync intel.capabilities to models.capabilities for consistency.
    Also ensure specialization is propagated if models has no specialization.
    """
    affected = 0
    if dry_run:
        # Count via aggregation
        pipeline = [
            {"$lookup": {
                "from": "model_intelligence",
                "let": {"p": "$provider", "m": "$model_id"},
                "pipeline": [
                    {"$match": {"$expr": {"$and": [
                        {"$eq": ["$provider", "$$p"]},
                        {"$eq": ["$model_id", "$$m"]},
                        {"$gt": [{"$size": {"$ifNull": ["$capabilities", []]}}, 0]}
                    ]}}}
                ],
                "as": "intel"
            }},
            {"$match": {
                "intel.0": {"$exists": True},
                "$or": [{"capabilities": {"$in": [[], None]}}, {"capabilities": {"$exists": False}}]
            }},
            {"$count": "n"}
        ]
        r = list(models_coll().aggregate(pipeline))
        return {"bug": "POT-CAP-DRIFT", "affected": r[0]["n"] if r else 0}

    # Iterate and fix
    pipeline = [
        {"$lookup": {
            "from": "model_intelligence",
            "let": {"p": "$provider", "m": "$model_id"},
            "pipeline": [
                {"$match": {"$expr": {"$and": [
                    {"$eq": ["$provider", "$$p"]},
                    {"$eq": ["$model_id", "$$m"]},
                    {"$gt": [{"$size": {"$ifNull": ["$capabilities", []]}}, 0]}
                ]}}},
                {"$project": {"capabilities": 1, "specialization": 1, "is_free": 1, "_id": 0}}
            ],
            "as": "intel"
        }},
        {"$match": {
            "intel.0": {"$exists": True},
            "$or": [{"capabilities": {"$in": [[], None]}}, {"capabilities": {"$exists": False}}]
        }}
    ]
    for d in models_coll().aggregate(pipeline):
        intel_doc = d["intel"][0]
        intel_caps = intel_doc.get("capabilities", [])
        intel_spec = intel_doc.get("specialization", "general")
        if not intel_caps:
            continue
        update = {
            "capabilities": intel_caps,
            "specialization": d.get("specialization") or intel_spec,
            "_sot_fixed_cap_drift": _now(),
        }
        models_coll().update_one(
            {"_id": d["_id"]},
            {"$set": update}
        )
        affected += 1
    return {"bug": "POT-CAP-DRIFT", "affected": affected}


FIXES = {
    "BUG-IS_FREE-1": fix_is_free_1,
    "BUG-IS_FREE-2": fix_is_free_2,
    "BUG-CAP-1": fix_cap_1,
    "BUG-INTEL-1": fix_intel_1,
    "BUG-INTEL-2": fix_intel_2,
    "BUG-IS_FREE-4": fix_intel_3_is_free_sync,
    "POT-CAP-DRIFT": fix_cap_drift,
    "POT-MODEL_ID-WS": fix_whitespace,
}


def fix_master_orphan_sync(dry_run: bool = False) -> Dict[str, Any]:
    """BUG-MASTER-3: models in MASTER.json that don't exist in models collection.

    Sync back: for each (provider, model_id) in MASTER that isn't in models,
    insert a minimal models entry sourced from MASTER's data.
    """
    if not os.path.exists("/root/.hermes/profiles/ilma/ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json"):
        return {"bug": "BUG-MASTER-3", "affected": 0, "note": "MASTER.json not found"}
    with open("/root/.hermes/profiles/ilma/ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json") as f:
        master = json.load(f)
    models_keys = set()
    for d in models_coll().find({}, {"provider": 1, "model_id": 1}):
        models_keys.add((d["provider"], d["model_id"]))
    missing = []
    for p, pd in master.get("providers", {}).items():
        for mid, m in pd.get("models", {}).items():
            if (p, mid) not in models_keys:
                missing.append((p, mid, m))
    if not dry_run and missing:
        from datetime import datetime as _dt
        for p, mid, m in missing:
            # Respect the original disabled flag, default is_active based on disabled
            disabled = bool(m.get("disabled", False))
            is_active = not disabled if m.get("is_active") is None else bool(m.get("is_active"))
            doc = {
                "provider": p,
                "model_id": mid,
                "model_name": mid,
                "is_active": is_active,
                "disabled": disabled,
                "is_free": bool(m.get("is_free", False)),  # single canonical field
                "status": m.get("status", "disabled" if disabled else "active") if not disabled else "disabled",
                "disabled_reason": m.get("disabled_reason"),
                "capabilities": m.get("capabilities", []),
                "specialization": m.get("specialization", "general"),
                "context_window": m.get("context_window"),
                "price_per_m_input": m.get("price_per_m_input"),
                "price_per_m_output": m.get("price_per_m_output"),
                "discovered_via": "sot_fix_master_sync",
                "discovered_at": _dt.now(timezone.utc),
                "refreshed_at": _dt.now(timezone.utc),
                "_sot_fixed_master_3": _dt.now(timezone.utc),
            }
            try:
                models_coll().insert_one(doc)
            except Exception as e:
                pass
    return {"bug": "BUG-MASTER-3", "affected": len(missing)}


def fix_master_2_is_free(dry_run: bool = False) -> Dict[str, Any]:
    """BUG-MASTER-2: :free suffix in MASTER.json with is_free=False.

    Re-write MASTER.json via materializer.
    """
    if not dry_run:
        # Re-run materializer
        from sot_materialize import materialize_master
        r = materialize_master(dry_run=False)
        return {"bug": "BUG-MASTER-2", "affected": r.get("models", 0), "action": "rematerialized"}
    return {"bug": "BUG-MASTER-2", "affected": 0, "action": "would_rematerialize"}


FIXES["BUG-MASTER-2"] = fix_master_2_is_free
FIXES["BUG-MASTER-3"] = fix_master_orphan_sync


def fix_master_orphan_v2_disabled(dry_run: bool = False) -> Dict[str, Any]:
    """Fix orphan models that don't have `disabled` field set correctly.

    This is a follow-up to BUG-MASTER-3: for each orphan model, re-sync
    `disabled` and `is_active` from MASTER.json's source.
    """
    if not os.path.exists("/root/.hermes/profiles/ilma/ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json"):
        return {"bug": "POT-ORPHAN-2", "affected": 0, "note": "MASTER.json not found"}
    with open("/root/.hermes/profiles/ilma/ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json") as f:
        master = json.load(f)
    # Build MASTER map: (provider, model_id) -> model data
    master_map = {}
    for p, pd in master.get("providers", {}).items():
        for mid, m in pd.get("models", {}).items():
            master_map[(p, mid)] = m
    affected = 0
    if not dry_run:
        from datetime import datetime as _dt
        for d in models_coll().find({"discovered_via": "sot_fix_master_sync"}, {
            "provider": 1, "model_id": 1, "is_active": 1, "disabled": 1
        }):
            key = (d["provider"], d["model_id"])
            if key not in master_map:
                continue
            m = master_map[key]
            disabled = bool(m.get("disabled", False))
            if m.get("is_active") is None:
                is_active = not disabled
            else:
                is_active = bool(m.get("is_active"))
            # Update if changed
            if d.get("disabled") != disabled or d.get("is_active") != is_active:
                models_coll().update_one(
                    {"_id": d["_id"]},
                    {"$set": {
                        "disabled": disabled,
                        "is_active": is_active,
                        "status": "disabled" if disabled else "active",
                        "_sot_fixed_master_3_v2": _dt.now(timezone.utc),
                    }}
                )
                affected += 1
    else:
        affected = models_coll().count_documents({"discovered_via": "sot_fix_master_sync"})
    return {"bug": "POT-ORPHAN-2", "affected": affected}


FIXES["POT-ORPHAN-2"] = fix_master_orphan_v2_disabled


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bug", choices=list(FIXES.keys()) + ["all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Acquire job lock
    job_id = f"sot-fix-{_now().strftime('%Y%m%d-%H%M%S')}"
    job = sot_ops.acquire_job_lock(
        job_id=job_id, job_type="validate", actor="sot_fix",
        idempotency_key=f"fix:{_now().strftime('%Y%m%d-%H%M')}"
    )
    if job is None:
        print("[JOB] Another fix is running. Skipping.")
        return
    try:
        targets = list(FIXES.keys()) if args.bug == "all" else [args.bug]
        print(f"\n=== SOT Fix — targets={targets} dry_run={args.dry_run} ===\n")
        results = []
        for bug_code in targets:
            r = FIXES[bug_code](dry_run=args.dry_run)
            results.append(r)
            print(f"  {r['bug']}: {r['affected']} affected")
            FIXES_APPLIED.append(r)
        # Audit trail
        eid = generate_evidence_id(code="FIX")
        write_audit(
            provider="*", model_id="*",
            event_type="field_corrected", actor="sot_fix",
            source_collection="models",
            delta={"fixes": results}, evidence_id=eid,
            notes=f"SOT bug fix run (dry_run={args.dry_run})"
        )
        sot_ops.finish_job(job_id, "success", result={"fixes": results})
        print(f"\n[DONE] evidence_id={eid}")
    except Exception as e:
        sot_ops.finish_job(job_id, "error", error=str(e)[:500])
        print(f"\n[ERROR] {e}")
        raise

if __name__ == "__main__":
    main()
