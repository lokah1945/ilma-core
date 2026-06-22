#!/usr/bin/env python3
"""
reconcile_from_llm_providers.py — SOT Cascade Pipeline
========================================================

Reads `llm_providers` (Single Source of Truth) and reconciles `models`
+ downstream collections. Driven entirely by SOT — no hardcoded
WORKING_PROVIDERS list.

Reconcilation rules (Bos 2026-06-19):

  1. CASCADE-IN
     For each provider in llm_providers where status != INVALID:
       - If provider has no entries in `models`, run sync_provider()
         (provider_sync.py must be in sys.path).
       - Already-existing entries: refresh is_free from SOT, refresh
         provider_status from SOT.

  2. CASCADE-OUT (orphan cleanup)
     For each provider in `models` whose provider isn't in llm_providers:
       - Delete from models + model_intelligence + model_benchmark +
         model_audit_trail (cascade FK).
       - Mark provider_status='historical' on the docs we just touched
         (audit trail preserves history).

  3. CASCADE-OUT (SOT-stale)
     For each provider in models whose llm_providers.status is INVALID
     (or any non-active):
       - Set is_active=False, status='disabled', provider_status='INVALID'
         (keep docs — preserve provenance).
       - Do NOT delete; allow admin to recover if status flips back.

  4. ENUM NORMALIZATION
     Any model docs with discovered_via values NOT in schema enum
     (legacy patcher strings) get rewritten to 'sot_reconcile'.

  5. DATA INTEGRITY
     Reconcile is_free ↔ free_tier (single source of truth = is_free).
     Resolve is_active=True + disabled_at conflicts (set is_active=False).

  6. PER-PROVIDER ISOLATION
     Each provider handled in its own try/except — one failure does not
     stop the rest (fail-safe per-item).

Usage:
    python3 reconcile_from_llm_providers.py                  # full reconcile (dry-run by default)
    python3 reconcile_from_llm_providers.py --apply          # actually mutate MongoDB
    python3 reconcile_from_llm_providers.py --provider nvidia  # single provider only
    python3 reconcile_from_llm_providers.py --json           # JSON output

Idempotent: re-running produces the same end state.
"""
import os, sys, json, argparse, traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Set
import pymongo

MONGO_HOST = "172.16.103.253"
MONGO_PORT = 27017
MONGO_USER = "quantumtraffic"
MONGO_PASS = (__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), ""))
DB_NAME = "credentials"

# Collections affected by cascade
DOWNSTREAM_COLL = ["model_intelligence", "model_benchmark", "model_audit_trail"]

# Enum values allowed for models.discovered_via (must match schema v2)
DISCOVERED_VIA_ENUM = {
    "provider_direct", "openrouter", "sot_fix_master_sync",
    "sot_fix_v2", "passive", "manual", "live_purge_20260618",
    "sot_reconcile",
}

# Provider statuses considered "live" (NOT requiring cascade-out)
LIVE_STATUSES = {"active", "ENDPOINT_WORKS_QUOTA_EXHAUSTED"}


def get_client():
    return pymongo.MongoClient(
        host=MONGO_HOST, port=MONGO_PORT,
        username=MONGO_USER, password=MONGO_PASS,
        serverSelectionTimeoutMS=10000,
    )


def now_utc():
    return datetime.now(timezone.utc)


def load_sot_providers(db) -> Dict[str, Dict[str, Any]]:
    """Index llm_providers docs by provider name. Provides authoritative SOT view."""
    outIndex: Dict[str, Dict[str, Any]] = {}
    for d in db["llm_providers"].find({}):
        outIndex.setdefault(d["provider"], d)  # first wins for parallel keys
    return outIndex


def load_models_providers(db) -> Set[str]:
    """Distinct provider values currently in models collection."""
    return set(db["models"].distinct("provider"))


# ── 1. CASCADE-IN ─────────────────────────────────────────────────────────────
def reconcile_cascade_in(db, sot_index: Dict[str, Dict[str, Any]],
                        models_providers: Set[str], apply: bool) -> Dict[str, Any]:
    """For SOT providers that have live aggregate status but no models — log/optionally invoke provider_sync.

    FIX 2026-06-19: aggregate over siblings — provider is live if ANY sibling has key_status=VALID/UNVERIFIED.
    """
    from_provider_sync = []
    needs_sync = []
    siblings_idx: Dict[str, List[Dict]] = {}
    for d in db["llm_providers"].find({}):
        siblings_idx.setdefault(d["provider"], []).append(d)

    for pname, sibs in siblings_idx.items():
        if not _aggregate_provider_live(sibs):
            continue
        if pname not in models_providers:
            needs_sync.append({"provider": pname,
                               "sib_count": len(sibs),
                               "act_keys": sum(1 for s in sibs if s.get("key_status") in {"VALID","UNVERIFIED"})})
    if needs_sync and apply:
        # Late import so this script can run without provider_sync deps for read-only audit
        SOT_DIR = os.path.dirname(os.path.abspath(__file__))
        discovery_dir = os.path.join(os.path.dirname(SOT_DIR), "discovery")
        if discovery_dir not in sys.path:
            sys.path.insert(0, discovery_dir)
        try:
            import provider_sync
            for entry in needs_sync:
                pname = entry["provider"]
                try:
                    r = provider_sync.sync_provider(pname, dry_run=False)
                    entry["sync_result"] = r
                    from_provider_sync.append(entry)
                except Exception as e:
                    entry["sync_error"] = str(e)
        except ImportError as e:
            for entry in needs_sync:
                entry["sync_error"] = f"import failed: {e}"
    return {"needs_sync": needs_sync, "synced": from_provider_sync}


# ── 2. CASCADE-OUT (orphan / never-was-in-SOT) ────────────────────────────────
def reconcile_cascade_out_orphan(db, sot_index: Dict[str, Dict[str, Any]],
                                 apply: bool) -> Dict[str, Any]:
    """Delete models + downstream for providers not in SOT at all."""
    sot_pnames = set(sot_index.keys())
    orphan_pnames = set(db["models"].distinct("provider")) - sot_pnames
    out = {"orphan_providers": sorted(orphan_pnames), "deleted": {}}
    if not orphan_pnames:
        return out
    if not apply:
        # Count only
        for coll in ["models"] + DOWNSTREAM_COLL:
            n = db[coll].count_documents({"provider": {"$in": list(orphan_pnames)}})
            out["deleted"][coll] = {"would_delete": n}
        return out
    deleted_at = now_utc()
    audit_marker = {"_sot_cascade_at": deleted_at,
                    "_sot_cascade_reason": "orphan_provider_not_in_sot"}
    for coll in ["models"] + DOWNSTREAM_COLL:
        # Mark first (preserve audit trail), then delete
        marked = db[coll].update_many(
            {"provider": {"$in": list(orphan_pnames)}},
            {"$set": audit_marker},
        )
        result = db[coll].delete_many({"provider": {"$in": list(orphan_pnames)}})
        out["deleted"][coll] = {"marked": marked.modified_count, "deleted": result.deleted_count}
    return out


# ── 3. CASCADE-OUT (SOT-stale only — keep docs but mark disabled) ─────────────
# FIX 2026-06-19: llm_providers was slimmed — no per-doc `status` anymore.
# Aggregate across siblings: any sibling with key_status=VALID/UNVERIFIED → live.
# Also: any provider with recent successful model syncs (refreshed_at < 24h) → live.
# This prevents false-negative when key_status is stale (e.g. TIMEOUT) but pipeline still works.
def _aggregate_provider_live(siblings: List[Dict]) -> bool:
    """A provider is 'live' if any sibling has key_status in {VALID, UNVERIFIED}."""
    for s in siblings:
        if s.get("key_status") in {"VALID", "UNVERIFIED"} and s.get("api_key"):
            return True
    return False


def _provider_has_recent_sync(db, pname: str, hours: int = 24) -> bool:
    """A provider is 'recently live' if any of its models has refreshed_at within window.

    FIX 2026-06-19 (audit M2): models.refreshed_at is stored as an ISO-8601 STRING
    (all 1954 docs), not a BSON date. A `$gte: <datetime>` filter is type-bracketed by
    MongoDB and matches ZERO string-typed docs, silently disabling this safety net —
    which would wrongly cascade-out recently-synced providers (e.g. byteplus/TIMEOUT).
    Match both representations: BSON-date docs via datetime cutoff, legacy string docs
    via lexicographic comparison against the ISO cutoff (valid for same-format ISO-8601).
    """
    from datetime import timedelta
    cutoff_dt = now_utc() - timedelta(hours=hours)
    cutoff_iso = cutoff_dt.isoformat()
    cnt = db["models"].count_documents({
        "provider": pname,
        "is_active": True,
        "$or": [
            {"refreshed_at": {"$gte": cutoff_dt}},   # BSON-date docs
            {"refreshed_at": {"$gte": cutoff_iso}},  # ISO-8601 string docs (lexicographic)
        ],
    })
    return cnt > 0


def reconcile_cascade_out_stale(db, sot_index: Dict[str, Dict[str, Any]],
                                 apply: bool) -> Dict[str, Any]:
    """Mark models is_active=False for SOT providers with non-live aggregate status,
    UNLESS provider has recent successful model syncs (indicates SOT status stale)."""
    out = []
    llm_p = db["llm_providers"]
    siblings_idx: Dict[str, List[Dict]] = {}
    for d in llm_p.find({}):
        siblings_idx.setdefault(d["provider"], []).append(d)

    # FIX 2026-06-19 (audit C3/M1): SAFETY CAP. A bad SOT read (empty llm_providers,
    # field-name drift, etc.) must never mass-disable the fleet. Compute the full
    # disable plan first; if it would deactivate more than MAX_DISABLE_FRACTION of all
    # active models, abort WITHOUT writing and surface the plan for an admin to review.
    MAX_DISABLE_FRACTION = 0.50
    total_active = db["models"].count_documents({"is_active": True})

    plan = []
    for pname in sot_index.keys():
        siblings = siblings_idx.get(pname, [])
        live_by_siblings = _aggregate_provider_live(siblings)
        live_by_recent_sync = _provider_has_recent_sync(db, pname)
        if live_by_siblings or live_by_recent_sync:
            continue
        matched = db["models"].count_documents({"provider": pname, "is_active": True})
        if matched == 0:
            continue
        plan.append({"provider": pname,
                     "active_to_disable": matched,
                     "reason": "no_live_sibling_no_recent_sync"})

    plan_total = sum(p["active_to_disable"] for p in plan)
    if total_active > 0 and plan_total > total_active * MAX_DISABLE_FRACTION:
        return {"disabled_providers": [],
                "aborted": True,
                "reason": "mass_disable_guard_tripped",
                "would_disable": plan_total,
                "total_active": total_active,
                "threshold": f"{MAX_DISABLE_FRACTION:.0%}",
                "plan": plan}

    for p in plan:
        out.append(p)
        if apply:
            db["models"].update_many(
                {"provider": p["provider"], "is_active": True},
                {"$set": {
                    "is_active": False,
                    "status": "disabled",
                    "deactivation_reason": "no_live_sibling_no_recent_sync",
                    "deactivated_at": now_utc(),
                }},
            )
    return {"disabled_providers": out}


# ── 4. ENUM NORMALIZATION ─────────────────────────────────────────────────────
def reconcile_enum_discovered_via(db, apply: bool) -> Dict[str, Any]:
    """Normalize discovered_via enum values to 'sot_reconcile' if invalid."""
    bad_query = {"discovered_via": {"$nin": list(DISCOVERED_VIA_ENUM)}}
    bad_count = db["models"].count_documents(bad_query)
    out = {"invalid_discovered_via_documents": bad_count}
    if apply and bad_count > 0:
        r = db["models"].update_many(
            bad_query,
            {"$set": {
                "discovered_via": "sot_reconcile",
                "_sot_enum_normalized_at": now_utc(),
            }},
        )
        out["updated"] = r.modified_count
    return out


# ── 5. DATA INTEGRITY ─────────────────────────────────────────────────────────
def reconcile_integrity(db, apply: bool) -> Dict[str, Any]:
    """Resolve is_free ↔ free_tier, disabled_at vs is_active conflicts."""
    out = {}

    # 5a. free_tier CONSOLIDATED into is_free (2026-06-23) — drop any stray free_tier docs
    #     instead of mirroring (is_free is the single canonical billing field now).
    if apply:
        r = db["models"].update_many({"free_tier": {"$exists": True}},
                                     {"$unset": {"free_tier": ""}})
        out["free_tier_dropped"] = r.modified_count

    # 5b. is_active=True + disabled_at exists → conflict
    conflict = db["models"].count_documents({
        "disabled_at": {"$exists": True},
        "is_active": True,
    })
    out["active_with_disabled_at"] = conflict
    if apply and conflict > 0:
        r = db["models"].update_many(
            {"disabled_at": {"$exists": True}, "is_active": True},
            {"$set": {
                "is_active": False,
                "status": "disabled",
                "_sot_disabled_at_sync": now_utc(),
            }},
        )
        out["active_disabled_conflict_fixed"] = r.modified_count

    return out


# ── MAIN ORCHESTRATION ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Actually mutate MongoDB. Default is dry-run (preview only).")
    parser.add_argument("--provider", help="Filter to single provider (for cascade-in/-out stale only)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    client = get_client()
    db = client[DB_NAME]
    sot = load_sot_providers(db)
    if args.provider:
        sot = {args.provider: sot[args.provider]} if args.provider in sot else {}
    models_providers = load_models_providers(db)

    result: Dict[str, Any] = {
        "executed_at": now_utc().isoformat(),
        "mode": "apply" if args.apply else "dry-run",
        "sot_providers": sorted(sot.keys()),
        "models_providers": sorted(models_providers),
        "sot_count": len(sot),
        "models_provider_count": len(models_providers),
        "orphan_providers_in_models": sorted(models_providers - set(sot.keys())),
    }

    # Run each step in isolation — partial failure does not abort.
    # #14 dedup (2026-06-23): sot_auto_sync.cascade_out_provider is the SINGLE live
    # cascade OWNER (T1 is_active=false ⇒ delete T2+T3). reconcile's cascade-out steps
    # are forced AUDIT-ONLY here (apply=False) so they never mutate/thrash against it —
    # they only report. cascade_in (build) + enum/integrity may still apply.
    steps = {}
    for name, fn in [
        ("cascade_in",          lambda: reconcile_cascade_in(db, sot, models_providers, args.apply)),
        ("cascade_out_orphan",  lambda: reconcile_cascade_out_orphan(db, sot, False)),  # audit-only
        ("cascade_out_stale",   lambda: reconcile_cascade_out_stale(db, sot, False)),   # audit-only
        ("enum_discovered_via", lambda: reconcile_enum_discovered_via(db, args.apply)),
        ("data_integrity",      lambda: reconcile_integrity(db, args.apply)),
    ]:
        try:
            steps[name] = fn()
        except Exception as e:
            steps[name] = {"error": f"{type(e).__name__}: {e}",
                           "traceback": traceback.format_exc(limit=5)}
    result["steps"] = steps

    if args.json:
        print(json.dumps(result, default=str, indent=2, ensure_ascii=False))
    else:
        print(f"\n=== sot-reconcile from llm_providers [{result['mode']}] ===")
        print(f"  SOT providers:        {result['sot_count']}")
        print(f"  Models providers:     {result['models_provider_count']}")
        print(f"  Orphan in models:     {result['orphan_providers_in_models']}")
        for name, step in steps.items():
            print(f"\n  [{name}]")
            if "error" in step:
                print(f"    ERROR: {step['error']}")
                continue
            for k, v in step.items():
                if isinstance(v, list) and len(v) > 5:
                    print(f"    {k}: {len(v)} items (showing 3):")
                    for item in v[:3]:
                        print(f"      - {item}")
                else:
                    print(f"    {k}: {v}")
        print()
    return result


if __name__ == "__main__":
    main()
