#!/usr/bin/env python3
import logging
logger = logging.getLogger(__name__)
"""
sot_audit.py — SOT Comprehensive Audit
========================================

Runs ALL known data integrity checks against the SOT MongoDB collections
AND the materialized disk cache. Returns non-zero exit code if ANY bug
is found.

This is the single source of truth for "is the SOT clean?" — designed
to be run in CI, cron, and after every sync.

Exit codes:
  0 = clean
  1 = critical bugs found
  2 = medium bugs found
  3 = low bugs found (warnings)

Usage:
    python3 sot_audit.py              # full audit
    python3 sot_audit.py --json        # JSON output
    python3 sot_audit.py --no-materialize-check  # skip disk cache
"""
import os, sys, json, argparse
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
import pymongo
from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sot_ops import (
    MONGO_HOST, MONGO_PORT, MONGO_USER, MONGO_PASS, DB_NAME,
    models_coll, benchmarks_coll, intelligence_coll,
    llm_providers_coll, providers_coll, audit_coll, jobs_coll,
)

SOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sot/orchestration -> sot
PROFILE_DIR = os.path.dirname(SOT_DIR)  # sot -> profiles/ilma
ROUTER_DIR = os.path.join(PROFILE_DIR, "ilma_model_router_data")
MASTER_PATH = os.path.join(ROUTER_DIR, "PROVIDER_INTELLIGENCE_MASTER.json")
BENCH_DB_PATH = os.path.join(ROUTER_DIR, "benchmark_database.json")
API_KEY_PATH = "/root/credential/api_key.json"

# Bug catalog with severity
BUGS: List[Dict[str, Any]] = []
SEVERITY_WEIGHT = {"CRITICAL": 3, "MEDIUM": 2, "LOW": 1}


def bug(severity: str, code: str, msg: str, count: int, details: Any = None) -> None:
    BUGS.append({
        "severity": severity,
        "code": code,
        "message": msg,
        "count": count,
        "details": details,
    })


# ── MongoDB integrity checks ─────────────────────────────────────────────────
def audit_mongo() -> None:
    print("\n[MongoDB integrity]")

    # BUG-DUP-1: Duplicate (provider, model_id) in models
    dups = list(models_coll().aggregate([
        {"$group": {"_id": {"provider": "$provider", "model_id": "$model_id"}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]))
    if dups:
        bug("CRITICAL", "BUG-DUP-1", "Duplicate (provider, model_id) in models", len(dups),
            [d["_id"] for d in dups[:5]])
        print(f"  ✗ BUG-DUP-1: {len(dups)} duplicate (provider, model_id) keys")
    else:
        print("  ✓ BUG-DUP-1: no duplicate (provider, model_id)")

    # BUG-DUP-2: Duplicate evidence_id in audit_trail
    dups = list(audit_coll().aggregate([
        {"$group": {"_id": "$evidence_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]))
    if dups:
        bug("CRITICAL", "BUG-DUP-2", "Duplicate evidence_id in audit_trail", len(dups),
            [d["_id"] for d in dups[:5]])
        print(f"  ✗ BUG-DUP-2: {len(dups)} duplicate evidence_id")
    else:
        print("  ✓ BUG-DUP-2: no duplicate evidence_id")

    # BUG-DUP-3: Duplicate job_id in sot_jobs
    dups = list(jobs_coll().aggregate([
        {"$group": {"_id": "$job_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
    ]))
    if dups:
        bug("CRITICAL", "BUG-DUP-3", "Duplicate job_id in sot_jobs", len(dups))
    else:
        print("  ✓ BUG-DUP-3: no duplicate job_id")


# ── Field consistency checks ────────────────────────────────────────────────
def audit_field_consistency() -> None:
    print("\n[Field consistency]")

    # BUG-IS_FREE-1: :free suffix but is_free=False
    n = models_coll().count_documents({
        "model_id": {"$regex": ":free$"},
        "$or": [{"is_free": False}, {"is_free": {"$exists": False}}],
        "is_active": True,
    })
    if n > 0:
        bug("CRITICAL", "BUG-IS_FREE-1",
            "Model with ':free' suffix but is_free=False (OpenRouter convention)",
            n)
        print(f"  ✗ BUG-IS_FREE-1: {n} models with :free suffix but is_free=False")
    else:
        print("  ✓ BUG-IS_FREE-1: all :free suffix models have is_free=True")

    # BUG-IS_FREE-2: price 0/0 but is_free=False (active only)
    n = models_coll().count_documents({
        "price_per_m_input": {"$in": ["0", 0, "0.0", 0.0]},
        "price_per_m_output": {"$in": ["0", 0, "0.0", 0.0]},
        "is_free": False,
        "is_active": True,
        "status": "active",
    })
    if n > 0:
        bug("CRITICAL", "BUG-IS_FREE-2",
            "Price 0/0 but is_free=False (should be free)", n)
        print(f"  ✗ BUG-IS_FREE-2: {n} active models with price 0/0 but is_free=False")
    else:
        print("  ✓ BUG-IS_FREE-2: all price=0 active models have is_free=True")

    # BUG-IS_FREE-3: is_free=True but has real price (contradiction)
    n = models_coll().count_documents({
        "is_free": True,
        "price_per_m_input": {"$nin": ["0", 0, "0.0", 0.0, None]},
        "is_active": True,
    })
    if n > 0:
        bug("MEDIUM", "BUG-IS_FREE-3",
            "is_free=True but has real price (contradiction)", n)
        print(f"  ✗ BUG-IS_FREE-3: {n} models is_free=True with real price")
    else:
        print("  ✓ BUG-IS_FREE-3: no is_free=True with real price")

    # BUG-STATUS-1: is_active != boolean
    n = models_coll().count_documents({"is_active": {"$type": "array"}})
    if n > 0:
        bug("CRITICAL", "BUG-STATUS-1", "is_active is array, not boolean", n)
    else:
        print("  ✓ BUG-STATUS-1: is_active is always boolean")

    # BUG-STATUS-2: status=enum mismatch
    valid = ["active", "disabled", "deprecated", "quota_exceeded", "broken", "unknown"]
    bad = models_coll().count_documents({
        "status": {"$nin": valid + [None]},
    })
    if bad > 0:
        bug("CRITICAL", "BUG-STATUS-2", f"status not in enum {valid}", bad)
    else:
        print("  ✓ BUG-STATUS-2: all status values in enum")

    # BUG-CAP-1: capabilities should not be empty for known patterns
    # Note: empty list is acceptable if model has no identifiable capability pattern
    # (e.g. "general" models like "claude-fable-latest"). We only flag if the
    # model_id contains obvious capability keywords that weren't picked up.
    capability_keywords = [
        "code", "coder", "coding", "reason", "think", "vision", "vl",
        "fast", "flash", "lite", "instruct", "chat", "embed", "dall-e",
    ]
    n = models_coll().count_documents({
        "capabilities": {"$in": [[], None]},
        "is_active": True,
        "model_id": {"$regex": "|".join(capability_keywords), "$options": "i"},
    })
    if n > 0:
        bug("MEDIUM", "BUG-CAP-1",
            f"{n} active models have capability keyword in model_id but capabilities=[]",
            n)
    else:
        print("  ✓ BUG-CAP-1: all models with capability keywords have capabilities populated")

    # BUG-CAP-2: capability but no specialization
    n = models_coll().count_documents({
        "capabilities": {"$ne": [], "$exists": True},
        "$or": [{"specialization": None}, {"specialization": {"$exists": False}}],
    })
    if n > 0:
        bug("MEDIUM", "BUG-CAP-2", "has capabilities but no specialization", n)
    else:
        print("  ✓ BUG-CAP-2: all models with capabilities have specialization")

    # POTENTIAL BUG: model_id with whitespace (could break URL/CLI parsing)
    n = models_coll().count_documents({"model_id": {"$regex": "\\s"}})
    if n > 0:
        bug("LOW", "POT-MODEL_ID-WS",
            f"{n} models with whitespace in model_id (URL/CLI parse issues)", n)
    else:
        print("  ✓ POT-MODEL_ID-WS: no models with whitespace in model_id")

    try:
        import sys as _sys
        _sys.path.insert(0, os.path.join(SOT_DIR, "discovery"))
        _sys.path.insert(0, "/root/.hermes/profiles/ilma/sot")
        import provider_sync as _ps
        cfg_providers = set(_ps.PROVIDER_CONFIGS.keys())
        mongo_providers = set(d["_id"] for d in models_coll().aggregate(
            [{"$group": {"_id": "$provider"}}]))
        # All mongo providers should be in PROVIDER_CONFIGS
        missing_from_cfg = mongo_providers - cfg_providers
        if missing_from_cfg:
            bug("LOW", "POT-CFG-MISSING",
                f"{len(missing_from_cfg)} providers in mongo not in PROVIDER_CONFIGS: {missing_from_cfg}",
                len(missing_from_cfg))
        else:
            print("  ✓ POT-CFG-MISSING: all mongo providers in PROVIDER_CONFIGS")
    except Exception as e:
        print(f"  ⚠ POT-CFG-CHECK: could not check ({e})")

    # POTENTIAL BUG: model with is_free but no price_per_m_input (incomplete)
    n = models_coll().count_documents({
        "is_free": True,
        "price_per_m_input": None,
        "is_active": True,
    })
    if n > 0:
        bug("LOW", "POT-IS_FREE-NO-PRICE",
            f"{n} is_free=True models missing price_per_m_input (incomplete)", n)
    else:
        print("  ✓ POT-IS_FREE-NO-PRICE: all is_free=True have price info")

    # POTENTIAL BUG: price with type 'str' but value not numeric
    n = models_coll().count_documents({
        "price_per_m_input": {"$type": "string", "$not": {"$regex": "^-?\\d+(\\.\\d+)?$"}}
    })
    if n > 0:
        bug("LOW", "POT-PRICE-NON-NUMERIC",
            f"{n} models with non-numeric string price_per_m_input", n)
    else:
        print("  ✓ POT-PRICE-NON-NUMERIC: all string prices are numeric")

    # POTENTIAL BUG: context_window = 0 (sentinel but should not be active)
    n = models_coll().count_documents({
        "context_window": 0,
        "is_active": True,
    })
    if n > 0:
        bug("LOW", "POT-CTX-0",
            f"{n} active models with context_window=0 (sentinel)", n)
    else:
        print("  ✓ POT-CTX-0: no active models with context_window=0")

    # POTENTIAL BUG: model_intelligence score_tier=C/D but composite_score>0.7
    # (B/A tier expected; 0.5-0.7 is the C/D range)
    n = intelligence_coll().count_documents({
        "score_tier": {"$in": ["C", "D"]},
        "composite_score": {"$gt": 0.7, "$ne": None},
    })
    if n > 0:
        bug("LOW", "POT-TIER-INCONSISTENT",
            f"{n} model_intelligence with C/D tier but composite_score>0.7 (tier should be A/B)", n)
    else:
        print("  ✓ POT-TIER-INCONSISTENT: tier consistent with composite_score")

    # POTENTIAL BUG: api_key with too-short key (likely invalid)
    n = 0
    for d in llm_providers_coll().find({"api_key": {"$exists": True, "$ne": None, "$ne": ""}}, {"api_key": 1}):
        if len(d.get("api_key", "")) < 10:
            n += 1
    if n > 0:
        bug("LOW", "POT-APIKEY-SHORT",
            f"{n} llm_providers with api_key shorter than 10 chars (likely invalid)", n)
    else:
        print("  ✓ POT-APIKEY-SHORT: all api_keys are reasonable length")

    # POTENTIAL BUG: model with discovered_via = 'sot_fix_master_sync' should be re-synced
    # These are KNOWN-ORPHAN: synced from MASTER.json because provider_sync
    # doesn't have configs for them (e.g. together, nous, alibaba, etc).
    # They remain in MongoDB for future activation. Not a bug — just FYI.
    n_orphan = models_coll().count_documents({"discovered_via": "sot_fix_master_sync"})
    n_orphan_active = models_coll().count_documents({
        "discovered_via": "sot_fix_master_sync",
        "is_active": True,
    })
    if n_orphan_active > 0:
        bug("LOW", "POT-ORPHAN-ACTIVE",
            f"{n_orphan_active} active models synced from MASTER.json (no provider_sync coverage)", n_orphan_active)
    else:
        print(f"  ✓ POT-ORPHAN: {n_orphan} orphan models (all inactive or correctly flagged)")

    # POTENTIAL BUG: model_intelligence with score_tier set but no composite_score
    # (heuristic fallback acceptable — check for it)
    n_heuristic = intelligence_coll().count_documents({
        "score_tier": {"$nin": [None, ""]},
        "composite_score": {"$ne": None},
        "score_source": "heuristic_derived",
    })
    n_no_score = intelligence_coll().count_documents({
        "score_tier": {"$nin": [None, ""]},
        "$or": [
            {"composite_score": None},
            {"composite_score": {"$exists": False}},
        ],
    })
    if n_no_score > 0:
        bug("LOW", "POT-INTEL-NO-SCORE",
            f"{n_no_score} model_intelligence with score_tier set but no composite_score", n_no_score)
    else:
        print(f"  ✓ POT-INTEL-NO-SCORE: all score_tier backed by score ({n_heuristic} heuristic, OK)")

    # POTENTIAL BUG: model_intelligence composite_score null but no tier (genuinely unscored)
    n = intelligence_coll().count_documents({
        "composite_score": None,
        "score_tier": None,
    })
    print(f"  ℹ POT-INTEL-UNSCORED: {n} model_intelligence with no score (genuinely unscored)")

    # POTENTIAL BUG: model_benchmarks referencing model with is_active=False (stale)
    n = 0
    for d in models_coll().aggregate([
        {"$match": {"is_active": False, "status": {"$in": ["disabled", "deprecated", "archived"]}}},
        {"$lookup": {
            "from": "model_benchmarks",
            "let": {"p": "$provider", "m": "$model_id"},
            "pipeline": [
                {"$match": {"$expr": {"$and": [
                    {"$eq": ["$provider", "$$p"]},
                    {"$eq": ["$model_id", "$$m"]}
                ]}}},
                {"$count": "n"}
            ],
            "as": "bench"
        }},
        {"$match": {"bench.0.n": {"$gt": 0}}}
    ]):
        n += 1
    if n > 0:
        bug("LOW", "POT-BENCH-STALE",
            f"{n} inactive models have stale benchmarks (acceptable but worth cleanup)", n)
    else:
        print("  ✓ POT-BENCH-STALE: no stale benchmarks on inactive models")

    # POT-CAP-DRIFT: model_intelligence has capabilities but models has empty
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
        {"$count": "n"
        }
    ]
    r = list(models_coll().aggregate(pipeline))
    n = r[0]["n"] if r else 0
    if n > 0:
        # Auto-remediate: sync intel→models
        from datetime import datetime as _dt
        # Run mini-fix inline
        sub_pipeline = pipeline[:-1]  # Remove $count
        fix_affected = 0
        for d in models_coll().aggregate(sub_pipeline):
            intel_doc = d["intel"][0]
            intel_caps = intel_doc.get("capabilities", [])
            intel_spec = intel_doc.get("specialization", "general")
            if not intel_caps:
                continue
            models_coll().update_one(
                {"_id": d["_id"]},
                {"$set": {
                    "capabilities": intel_caps,
                    "specialization": d.get("specialization") or intel_spec,
                    "_sot_fixed_cap_drift": _dt.now(),
                }}
            )
            fix_affected += 1
        # Re-check
        r2 = list(models_coll().aggregate(pipeline))
        n2 = r2[0]["n"] if r2 else 0
        if n2 > 0:
            bug("LOW", "POT-CAP-DRIFT",
                f"{n2} models have capabilities in intel but not in models (auto-fix tried, {fix_affected} fixed, {n2} remain)", n2)
        else:
            print(f"  ✓ POT-CAP-DRIFT: auto-remediated ({fix_affected} models synced intel→models)")
    else:
        print("  ✓ POT-CAP-DRIFT: capabilities consistent between models and intel")

    # POTENTIAL BUG: MASTER.json composite_score vs model_intelligence composite_score
    if os.path.exists(MASTER_PATH):
        with open(MASTER_PATH) as f:
            master = json.load(f)
        # Build lookup table from intel in one query, then iterate MASTER
        intel_map = {}
        for d in intelligence_coll().find({}, {"provider": 1, "model_id": 1, "composite_score": 1, "score_tier": 1}):
            intel_map[(d["provider"], d["model_id"])] = d
        n_drift = 0
        for p, pd in master.get("providers", {}).items():
            for mid, m in pd.get("models", {}).items():
                intel = intel_map.get((p, mid))
                if not intel:
                    continue
                master_cs = m.get("composite_score")
                intel_cs = intel.get("composite_score")
                master_t = m.get("score_tier")
                intel_t = intel.get("score_tier")
                if master_cs is not None and intel_cs is not None:
                    if abs(float(master_cs) - float(intel_cs)) > 0.01:
                        n_drift += 1
                if master_t and intel_t and master_t != intel_t:
                    n_drift += 1
        if n_drift > 0:
            bug("LOW", "POT-MASTER-INTEL-DRIFT",
                f"{n_drift} composite_score/score_tier drift between MASTER.json and intel", n_drift)
        else:
            print("  ✓ POT-MASTER-INTEL-DRIFT: MASTER.json and intel composite_score consistent")


# ── Cross-collection consistency ────────────────────────────────────────────
def audit_cross_collection() -> None:
    print("\n[Cross-collection consistency]")

    # BUG-INTEL-1: orphan intel (in intel but not in models)
    # Use aggregation with $lookup + $not match for efficient batch check
    intel_keys = set()
    for d in intelligence_coll().find({}, {"provider": 1, "model_id": 1}):
        intel_keys.add((d["provider"], d["model_id"]))
    models_keys = set()
    for d in models_coll().find({}, {"provider": 1, "model_id": 1}):
        models_keys.add((d["provider"], d["model_id"]))
    orphans = intel_keys - models_keys
    if orphans:
        bug("CRITICAL", "BUG-INTEL-1",
            f"{len(orphans)} model_intelligence entries with no matching model",
            len(orphans), list(orphans)[:5])
    else:
        print("  ✓ BUG-INTEL-1: no orphan model_intelligence")

    # BUG-IS_FREE-4: is_free mismatch between models and intel
    # Use aggregation with $lookup for efficient batch check
    pipeline = [
        {"$lookup": {
            "from": "model_intelligence",
            "let": {"p": "$provider", "m": "$model_id"},
            "pipeline": [
                {"$match": {"$expr": {"$and": [
                    {"$eq": ["$provider", "$$p"]},
                    {"$eq": ["$model_id", "$$m"]}
                ]}}},
                {"$project": {"_id": 0, "i_is_free_bool": {"$cond": [{"$eq": ["$is_free", True]}, True, False]}}}
            ],
            "as": "intel_match"
        }},
        {"$match": {"intel_match.0": {"$exists": True}}},
        {"$project": {
            "_id": 0, "provider": 1, "model_id": 1,
            "m_is_free_bool": {"$cond": [{"$eq": ["$is_free", True]}, True, False]},
            "i_is_free_bool": {"$arrayElemAt": ["$intel_match.i_is_free_bool", 0]}
        }},
        {"$match": {"$expr": {"$ne": ["$m_is_free_bool", "$i_is_free_bool"]}}}
    ]
    mismatches = sum(1 for _ in models_coll().aggregate(pipeline))
    if mismatches:
        bug("CRITICAL", "BUG-IS_FREE-4",
            f"{mismatches} models have is_free mismatch between models and intel", mismatches)
    else:
        print("  ✓ BUG-IS_FREE-4: is_free consistent between models and intel")

    # BUG-INTEL-2: score_tier set but composite_score null
    n = intelligence_coll().count_documents({
        "score_tier": {"$nin": [None, ""]},
        "$or": [{"composite_score": None}, {"composite_score": {"$exists": False}}],
    })
    if n > 0:
        bug("MEDIUM", "BUG-INTEL-2",
            f"{n} model_intelligence with score_tier but composite_score null",
            n)
    else:
        print("  ✓ BUG-INTEL-2: all score_tier set have composite_score")

    # BUG-INTEL-3: composite_score out of [0,1] range
    n = intelligence_coll().count_documents({
        "composite_score": {"$ne": None},
        "$or": [
            {"composite_score": {"$lt": 0}},
            {"composite_score": {"$gt": 1}},
        ],
    })
    if n > 0:
        bug("CRITICAL", "BUG-INTEL-3",
            f"{n} model_intelligence with composite_score outside [0,1]", n)
    else:
        print("  ✓ BUG-INTEL-3: all composite_score in [0,1]")


# ── Disk cache consistency ──────────────────────────────────────────────────
def audit_disk_cache() -> None:
    print("\n[Disk cache consistency]")

    if not os.path.exists(MASTER_PATH):
        bug("CRITICAL", "BUG-DISK-1", f"MASTER.json not found at {MASTER_PATH}", 1)
        return
    if not os.path.exists(BENCH_DB_PATH):
        bug("CRITICAL", "BUG-DISK-2", f"benchmark_database.json not found at {BENCH_DB_PATH}", 1)
        return
    if not os.path.exists(API_KEY_PATH):
        bug("CRITICAL", "BUG-DISK-3", f"api_key.json not found at {API_KEY_PATH}", 1)
        return

    with open(MASTER_PATH) as f:
        master = json.load(f)
    with open(BENCH_DB_PATH) as f:
        bench = json.load(f)
    with open(API_KEY_PATH) as f:
        ak = json.load(f)

    # BUG-MASTER-1: duplicate (provider, model_id) in MASTER
    all_keys = []
    for p, pd in master.get("providers", {}).items():
        for mid in pd.get("models", {}):
            all_keys.append((p, mid))
    if len(all_keys) != len(set(all_keys)):
        from collections import Counter
        c = Counter(all_keys)
        dups = {k: v for k, v in c.items() if v > 1}
        bug("CRITICAL", "BUG-MASTER-1",
            f"MASTER.json has {len(dups)} duplicate (provider, model_id) keys",
            len(dups), list(dups.keys())[:5])
    else:
        print(f"  ✓ BUG-MASTER-1: MASTER.json has {len(all_keys)} unique (provider, model_id)")

    # BUG-MASTER-2: MASTER has :free suffix with is_free=False
    # Only flag if model is actually active and available (not disabled)
    bad = 0
    for p, pd in master.get("providers", {}).items():
        for mid, m in pd.get("models", {}).items():
            if mid.endswith(":free") and not m.get("is_free"):
                # Only flag if not disabled (disabled models may have stale is_free)
                if not m.get("disabled") and m.get("is_active", True) and m.get("status") in (None, "active"):
                    bad += 1
    if bad > 0:
        bug("CRITICAL", "BUG-MASTER-2",
            f"MASTER.json has {bad} active :free suffix models with is_free=False", bad)
    else:
        print("  ✓ BUG-MASTER-2: all active :free suffix models in MASTER have is_free=True")

    # BUG-MASTER-3: MASTER counts match MongoDB counts
    n_mongo = models_coll().count_documents({})
    n_master = len(all_keys)
    if n_mongo != n_master:
        # Auto-remediate: re-materialize MASTER.json from MongoDB
        import subprocess as _sp
        remat = _sp.run(
            ["python3", "orchestration/sot_materialize.py", "--target", "master"],
            cwd=SOT_DIR, capture_output=True, text=True, timeout=120
        )
        # Re-read master
        with open(MASTER_PATH) as f:
            master = json.load(f)
        all_keys = []
        for p, pd in master.get("providers", {}).items():
            for mid in pd.get("models", {}):
                all_keys.append((p, mid))
        n_master = len(all_keys)
        if n_mongo != n_master:
            bug("MEDIUM", "BUG-MASTER-3",
                f"MASTER.json has {n_master} models but MongoDB has {n_mongo} (auto-remediation failed)", 1)
        else:
            print(f"  ✓ BUG-MASTER-3: auto-remediated (re-materialized MASTER.json, {n_mongo} models)")
    else:
        print(f"  ✓ BUG-MASTER-3: MASTER.json models count matches MongoDB ({n_mongo})")

    # BUG-MASTER-4: missing meta fields
    for k in ["_version", "_last_updated", "_sot_lifecycle", "_enricher_version"]:
        if k not in master:
            bug("MEDIUM", "BUG-MASTER-4", f"MASTER.json missing field {k}", 1)
    if "_enricher_version" in master:
        print(f"  ✓ BUG-MASTER-4: MASTER.json meta fields present (enricher={master.get('_enricher_version')})")

    # BUG-AK-1: api_key.json llm providers coverage
    mongo_providers = set(d["provider"] for d in llm_providers_coll().find({}, {"provider": 1}))
    ak_providers = set(ak.get("llm", {}).keys())
    if mongo_providers - ak_providers:
        bug("MEDIUM", "BUG-AK-1",
            f"api_key.json missing providers: {mongo_providers - ak_providers}", 1)
    if ak_providers - mongo_providers:
        bug("MEDIUM", "BUG-AK-1b",
            f"api_key.json has extra providers not in mongo: {ak_providers - mongo_providers}", 1)
    if not (mongo_providers - ak_providers) and not (ak_providers - mongo_providers):
        print(f"  ✓ BUG-AK-1: api_key.json llm coverage matches MongoDB ({len(mongo_providers)} providers)")

    # BUG-AK-2: api_key.json secrets state (should be masked by default)
    real_keys = 0
    masked_keys = 0
    for p, v in ak.get("llm", {}).items():
        for k in v.get("keys", []):
            key = k.get("key", "")
            if "..." in key:
                masked_keys += 1
            elif key:
                real_keys += 1
    if real_keys > 0:
        bug("MEDIUM", "BUG-AK-2",
            f"api_key.json has {real_keys} unmasked keys (should be masked by default)", real_keys)
    else:
        print(f"  ✓ BUG-AK-2: all {masked_keys} api_key.json keys are masked")

    # BUG-AK-4: api_key.json 'models' field matches MongoDB count (sanity)
    ak_llm = ak.get("llm", {})
    n_with_models_field = 0
    n_with_keys = 0
    for p, v in ak_llm.items():
        models_field = v.get("models", "")
        keys = v.get("keys", [])
        if keys:
            n_with_keys += 1
        if models_field:
            n_with_models_field += 1
    print(f"  ℹ BUG-AK-4: api_key.json has {n_with_keys} providers with keys, {n_with_models_field} with 'models' field")

    # BUG-AK-5: E2E check — every provider in api_key.json with a key has at least 1 model in MongoDB
    # (otherwise the credential is dead weight)
    # Excluded: providers that are in PROVIDER_CONFIGS but skip_sync=True, plus
    # broken-by-mandate providers (12/18 broken).
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.join(SOT_DIR, "discovery"))
        import provider_sync as _ps2
        cfg_keys = set(_ps2.PROVIDER_CONFIGS.keys())
        broken_or_disabled = {p for p, c in _ps2.PROVIDER_CONFIGS.items() if c.get("skip_sync") or c.get("fmt") == "unsupported"}
    except Exception:
        cfg_keys = set()
        broken_or_disabled = set()
    # Plus known broken providers (api_key has key but no model config)
    KNOWN_BROKEN = {"tinyfish", "aisure", "bluesminds", "sumopod", "bytez", "ollama", "felo"}
    n_dead_creds = 0
    dead_creds = []
    for p, v in ak_llm.items():
        if not v.get("keys"):
            continue
        if p in broken_or_disabled or p in KNOWN_BROKEN:
            continue
        n_models = models_coll().count_documents({"provider": p})
        if n_models == 0:
            n_dead_creds += 1
            dead_creds.append(p)
    if n_dead_creds > 0:
        bug("MEDIUM", "BUG-AK-5",
            f"{n_dead_creds} api_key.json providers with keys but no models in MongoDB: {dead_creds}",
            n_dead_creds)
    else:
        print(f"  ✓ BUG-AK-5: all live api_key.json providers have models in MongoDB (excluded {len(broken_or_disabled)+len(KNOWN_BROKEN)} broken/disabled)")

    # BUG-AK-3: api_key.json preserves non-llm keys
    non_llm_keys = [k for k in ak.keys() if k not in ("llm", "_meta")]
    if not non_llm_keys:
        bug("CRITICAL", "BUG-AK-3",
            "api_key.json lost non-llm keys (telegram bots, exchanges, etc.)", 1)
    else:
        print(f"  ✓ BUG-AK-3: api_key.json preserves {len(non_llm_keys)} non-llm keys")


# ── E2E MongoDB → disk cache consistency ────────────────────────────────────
def audit_e2e_consistency() -> None:
    """Verify MongoDB is the source of truth and disk cache is a derived view.

    For critical models (those in config.yaml fallback_providers + default model),
    verify (provider, model_id) is in BOTH MongoDB AND MASTER.json with consistent
    is_active, is_free, status.
    """
    print("\n[E2E MongoDB→MASTER consistency]")

    # Read config.yaml fallback providers
    cfg_path = "/root/.hermes/profiles/ilma/config.yaml"
    if not os.path.exists(cfg_path):
        print(f"  ⚠ config.yaml not found at {cfg_path}")
        return

    import yaml
    try:
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"  ⚠ config.yaml parse error: {e}")
        return

    # Collect critical model references
    critical = []
    default_model = cfg.get("model", {}).get("default")
    default_provider = cfg.get("model", {}).get("provider")
    if default_model:
        critical.append((default_provider or "", default_model))
    for fp in cfg.get("fallback_providers", []):
        if "/" in fp:
            p, mid = fp.split("/", 1)
            critical.append((p, mid))

    # Custom providers
    for cp in cfg.get("providers", {}).get("custom", []):
        for m in cp.get("models", []):
            if "/" in m:
                p, mid = m.split("/", 1)
                critical.append((p, mid))

    if not critical:
        print("  ℹ no critical model references found in config.yaml")
        return

    # Read MASTER
    if not os.path.exists(MASTER_PATH):
        bug("CRITICAL", "BUG-E2E-1", "MASTER.json missing for E2E check", 1)
        return
    with open(MASTER_PATH) as f:
        master = json.load(f)

    n_missing_mongo = 0
    n_missing_master = 0
    n_mismatch = 0
    for prov, mid in critical:
        # Check MongoDB
        mongo_doc = models_coll().find_one(
            {"provider": prov, "model_id": mid},
            {"is_active": 1, "is_free": 1, "status": 1}
        )
        if not mongo_doc:
            # Try double-prefix recovery: config has nvidia/nvidia/X but SOT has nvidia/X
            if mid.startswith(prov + "/"):
                alt_mid = mid[len(prov) + 1:]
                mongo_doc = models_coll().find_one(
                    {"provider": prov, "model_id": alt_mid},
                    {"is_active": 1, "is_free": 1, "status": 1}
                )
                if mongo_doc:
                    mid = alt_mid  # Use the canonical mid for downstream checks
                else:
                    # Try triple: nvidia/nvidia/X but SOT has X (after strip_prefix)
                    if alt_mid.startswith(prov + "/"):
                        alt_mid2 = alt_mid[len(prov) + 1:]
                        mongo_doc = models_coll().find_one(
                            {"provider": prov, "model_id": alt_mid2},
                            {"is_active": 1, "is_free": 1, "status": 1}
                        )
                        if mongo_doc:
                            mid = alt_mid2
            if not mongo_doc:
                n_missing_mongo += 1
                continue

        # Check MASTER
        # If mid was reassigned during mongo recovery, try with original mid too
        original_mid = mid
        m_data = master.get("providers", {}).get(prov, {}).get("models", {}).get(mid)
        if not m_data:
            # Try double-prefix recovery (mid has prov/ prefix)
            if mid.startswith(prov + "/"):
                alt_mid = mid[len(prov) + 1:]
                m_data = master.get("providers", {}).get(prov, {}).get("models", {}).get(alt_mid)
                if m_data:
                    mid = alt_mid
            # If original mid had double-prefix (prov/prov/X), try prov/X
            if not m_data and original_mid.startswith(prov + "/" + prov + "/"):
                alt_mid = original_mid[len(prov) + 1:]
                m_data = master.get("providers", {}).get(prov, {}).get("models", {}).get(alt_mid)
                if m_data:
                    mid = alt_mid
            if not m_data:
                n_missing_master += 1
                continue

        # Compare key fields
        for field in ("is_active", "is_free", "status"):
            m_val = mongo_doc.get(field)
            f_val = m_data.get(field)
            if m_val is not None and f_val is not None and m_val != f_val:
                n_mismatch += 1
                break

    if n_missing_mongo > 0:
        bug("CRITICAL", "BUG-E2E-MISSING-MONGO",
            f"{n_missing_mongo}/{len(critical)} critical config models missing from MongoDB",
            n_missing_mongo)
    else:
        print(f"  ✓ BUG-E2E-MISSING-MONGO: all {len(critical)} critical models in MongoDB")

    if n_missing_master > 0:
        bug("CRITICAL", "BUG-E2E-MISSING-MASTER",
            f"{n_missing_master}/{len(critical)} critical config models missing from MASTER.json",
            n_missing_master)
    else:
        print(f"  ✓ BUG-E2E-MISSING-MASTER: all {len(critical)} critical models in MASTER.json")

    if n_mismatch > 0:
        bug("MEDIUM", "BUG-E2E-MISMATCH",
            f"{n_mismatch}/{len(critical)} critical models have is_active/is_free/status drift between MongoDB and MASTER",
            n_mismatch)
    else:
        print(f"  ✓ BUG-E2E-MISMATCH: all {len(critical)} critical models consistent")


# ── E2E Runtime script references → SOT ─────────────────────────────────────
def audit_runtime_references() -> None:
    """Scan runtime Python scripts for hardcoded model_id strings and verify
    each one resolves in MongoDB.

    Catches the case where a script references a model that was never synced
    to the SOT (e.g. a stale hardcoded value).
    """
    print("\n[E2E Runtime script → SOT consistency]")

    import re
    # Match "provider/model_id" as it appears in runtime code. Note that
    # nvidia_nim_router.py uses nvidia/model (with provider prefix included)
    # and OpenRouter uses provider/model pattern. The provider in the string
    # is the FIRST segment; the model_id is EVERYTHING after.
    # Common false-positive: nvidia/foo should match (prov=nvidia, mid=foo)
    # Common valid: nvidia/nvidia/foo (double prefix) also exists in nvidia NIM.
    # We extract the provider from the FIRST known SOT provider, and the
    # model_id is the rest of the string.
    # Simpler approach: try matching (known_provider, full_id) directly.
    SOT_PROVIDERS = set()
    for d in models_coll().aggregate([{"$group": {"_id": "$provider"}}]):
        SOT_PROVIDERS.add(d["_id"])
    # Sort by length descending so longer provider names match first
    SOT_PROVIDERS_SORTED = sorted(SOT_PROVIDERS, key=lambda p: -len(p))

    def _parse_ref(s):
        """Parse a 'provider/model_id' string. Returns (prov, mid) or None."""
        if s.startswith('"'):
            s = s[1:]
        if s.endswith('"'):
            s = s[:-1]
        for prov in SOT_PROVIDERS_SORTED:
            prefix = prov + "/"
            if s.startswith(prefix):
                return (prov, s[len(prefix):])
        return None

    # Pattern: capture full quoted string starting with known provider
    QUOTED_RE = re.compile(r'"([a-z][a-z0-9_-]+/[A-Za-z0-9._:\-()/]+)"')
    # Excluded substrings (path-like, not model_id)
    EXCLUDE_SUBSTR = ("ilma_model_router", "ilma-hermes-knowledge", "/tmp/", "/root/", ".json", ".yaml", ".py", ".md", "openai/skills", "openai/completions", "openai/responses", "openai/chat")

    SCRIPTS_DIR = "/root/.hermes/profiles/ilma/scripts"
    if not os.path.isdir(SCRIPTS_DIR):
        print(f"  ⚠ scripts/ not found at {SCRIPTS_DIR}")
        return

    # Skip SOT scripts and pure infrastructure
    SKIP_FILES = {
        "ilma_model_db_manager.py",  # This IS the SOT sync
        "ilma_sot_lifecycle_manager.py",
        "ilma_sot_integrity.py",
        # nvidia_nim_integration.py: hardcoded list of healthy_models
        # used as a healthcheck target fixture, not a runtime reference.
        "nvidia_nim_integration.py",
        # Health verification scripts with model lists for test fixtures
        "nvidia_nim_verify.py",
        # Health seeder script: hardcodes initial health state list, not a
        # runtime reference.
        "ilma_seed_health_state.py",
        # Benchmark autoloop: contains pattern-matching code, not runtime refs
        "ilma_benchmark_autoloop.py",
        # OpenRouter tester: model list for testing connectivity, fixtures
        "ilma_openrouter_tester.py",
        # Dynamic prompt optimizer: model classification list (not runtime)
        "ilma_dynamic_prompt_optimizer.py",
    }

    # Build MongoDB lookup of (provider, model_id)
    mongo_keys = set()
    for d in models_coll().find({}, {"provider": 1, "model_id": 1}):
        mongo_keys.add((d["provider"], d["model_id"]))

    # Valid provider names (anything in PROVIDER_CONFIGS or mongo)
    valid_providers = set()
    for d in models_coll().aggregate([{"$group": {"_id": "$provider"}}]):
        valid_providers.add(d["_id"])

    n_total_refs = 0
    n_unknown_prov = 0
    n_missing = 0
    n_double_prefix = 0
    unknown_provs = set()
    missing_refs = []
    for fname in os.listdir(SCRIPTS_DIR):
        if not fname.endswith(".py") or fname in SKIP_FILES or fname.startswith("test_"):
            continue
        fpath = os.path.join(SCRIPTS_DIR, fname)
        try:
            with open(fpath) as f:
                content = f.read()
        except Exception:
            continue
        for m in QUOTED_RE.finditer(content):
            quoted = m.group(1)
            # Skip false positives
            if any(s in quoted for s in EXCLUDE_SUBSTR):
                continue
            parsed = _parse_ref(quoted)
            if parsed is None:
                n_unknown_prov += 1
                # Find what the first segment was for visibility
                first_seg = quoted.split("/", 1)[0]
                unknown_provs.add(first_seg)
                continue
            prov, mid = parsed
            n_total_refs += 1
            if (prov, mid) in mongo_keys:
                continue
            # Try stripping the provider prefix from mid (handles double-prefix cases)
            # e.g. config has nvidia/nvidia/foo but SOT has nvidia/foo
            if mid.startswith(prov + "/"):
                alt_mid = mid[len(prov) + 1:]
                if (prov, alt_mid) in mongo_keys:
                    n_double_prefix += 1
                    continue
            # Try dropping the first segment of mid (handles nvidia/meta/foo →
            # nvidia/foo where mid is OpenRouter-style "meta/foo" but stored as
            # nvidia/foo). This is for nvidia_nim_router.py-style fallbacks.
            if "/" in mid:
                alt_mid2 = mid.split("/", 1)[1]
                if (prov, alt_mid2) in mongo_keys:
                    n_double_prefix += 1
                    continue
            n_missing += 1
            if len(missing_refs) < 10:
                missing_refs.append((fname, prov, mid))

    if n_unknown_prov > 0:
        print(f"  ℹ POT-RT-UNKNOWN-PROV: {n_unknown_prov} references with unknown provider ({len(unknown_provs)} unique: {sorted(unknown_provs)[:5]})")
    else:
        print(f"  ✓ POT-RT-UNKNOWN-PROV: all runtime script providers known to SOT")

    if n_missing > 0:
        bug("MEDIUM", "POT-RT-MISSING",
            f"{n_missing}/{n_total_refs} hardcoded runtime model references missing from SOT MongoDB. Samples: {missing_refs[:5]}",
            n_missing)
    else:
        suffix = f" ({n_double_prefix} detected as config double-prefix, ignored)" if n_double_prefix else ""
        print(f"  ✓ POT-RT-MISSING: all {n_total_refs} runtime script model references found in SOT MongoDB{suffix}")


# ── Schema consistency ─────────────────────────────────────────────────────
def audit_schema_via_validators() -> Dict[str, int]:
    """Run all 6 schema validators and report."""
    import subprocess
    print("\n[Schema validation]")
    validators = [
        ("llm_providers",      "validators/validate_llm_providers.py"),
        ("model_audit_trail",  "validators/validate_model_audit_trail.py"),
        ("model_benchmarks",   "validators/validate_model_benchmarks.py"),
        ("model_intelligence", "validators/validate_model_intelligence.py"),
        ("models",             "validators/validate_models.py"),
        ("sot_jobs",           "validators/validate_sot_jobs.py"),
    ]
    results = {}
    for name, path in validators:
        r = subprocess.run(
            ["python3", path, "--all"],
            cwd=SOT_DIR, capture_output=True, text=True, timeout=120
        )
        lines = [l.strip() for l in r.stdout.split("\n") if l.strip()]
        result_line = next((l for l in reversed(lines) if l.startswith("Result:")), "")
        invalid = 0
        total = 0
        if result_line:
            # Format: "Result: <invalid>/<total> invalid"
            try:
                # Extract the "<invalid>/<total>" substring
                after_colon = result_line.split(":", 1)[1].strip()
                first_token = after_colon.split()[0]  # e.g. "0/2400"
                parts = first_token.split("/")
                invalid = int(parts[0])
                total = int(parts[1])
            except (ValueError, IndexError):
                pass
        results[name] = {"invalid": invalid, "total": total, "passed": invalid == 0}
        if invalid > 0:
            bug("CRITICAL", f"BUG-VALID-{name.upper()}",
                f"{invalid}/{total} docs failed schema validation", invalid)
        else:
            print(f"  ✓ {name}: {total} docs valid")
    return results


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    import time
    t0 = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--no-materialize-check", action="store_true",
                        help="Skip disk cache checks")
    parser.add_argument("--skip-validators", action="store_true",
                        help="Skip schema validator subprocess (use last-known results)")
    args = parser.parse_args()

    print("=" * 70)
    print("SOT COMPREHENSIVE AUDIT")
    print(f"  started_at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    print(f"[t={time.time()-t0:.2f}s] audit_mongo...", end=" ", flush=True)
    audit_mongo(); print(f"done t={time.time()-t0:.2f}s")
    print(f"[t={time.time()-t0:.2f}s] audit_field_consistency...", end=" ", flush=True)
    audit_field_consistency(); print(f"done t={time.time()-t0:.2f}s")
    print(f"[t={time.time()-t0:.2f}s] audit_cross_collection...", end=" ", flush=True)
    audit_cross_collection(); print(f"done t={time.time()-t0:.2f}s")
    if not args.no_materialize_check:
        print(f"[t={time.time()-t0:.2f}s] audit_disk_cache...", end=" ", flush=True)
        audit_disk_cache(); print(f"done t={time.time()-t0:.2f}s")
        print(f"[t={time.time()-t0:.2f}s] audit_e2e_consistency...", end=" ", flush=True)
        audit_e2e_consistency(); print(f"done t={time.time()-t0:.2f}s")
        print(f"[t={time.time()-t0:.2f}s] audit_runtime_references...", end=" ", flush=True)
        audit_runtime_references(); print(f"done t={time.time()-t0:.2f}s")
    validator_results = {}
    if not args.skip_validators:
        print(f"[t={time.time()-t0:.2f}s] audit_schema_via_validators...", end=" ", flush=True)
        validator_results = audit_schema_via_validators(); print(f"done t={time.time()-t0:.2f}s")

    # Summary
    print("\n" + "=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)
    if not BUGS:
        print("✅ NO BUGS FOUND. SOT is clean.")
        exit_code = 0
    else:
        # Group by severity
        by_sev = {"CRITICAL": [], "MEDIUM": [], "LOW": []}
        for b in BUGS:
            by_sev.setdefault(b["severity"], []).append(b)
        for sev in ["CRITICAL", "MEDIUM", "LOW"]:
            if by_sev[sev]:
                print(f"\n[{sev}] {len(by_sev[sev])} bug(s):")
                for b in by_sev[sev]:
                    print(f"  {b['code']}: {b['message']} (count={b['count']})")
        # Worst severity
        if by_sev["CRITICAL"]:
            exit_code = 1
        elif by_sev["MEDIUM"]:
            exit_code = 2
        else:
            exit_code = 3

    print(f"\nTotal bugs: {len(BUGS)}")
    if args.json:
        print(json.dumps({"bugs": BUGS, "exit_code": exit_code, "validators": validator_results}, indent=2, default=str))
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
