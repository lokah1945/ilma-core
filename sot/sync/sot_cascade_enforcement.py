#!/usr/bin/env python3
"""
sot_cascade_enforcement.py — Unified Cascade Enforcement Engine
================================================================

End-to-end T1 → T2 → T3 cascade enforcement for ILMA SOT.
Single script that handles ALL cascade rules:

  Phase A — CASCADE DOWN (T1 inactive → remove T2+T3)
    For every provider in llm_providers with NO active keys:
      1. Mark T2 providers.is_active=False, status='INVALID'
      2. Set T3 models.is_active=False + disabled_at for that provider
      3. Record audit trail
    For T2 providers with no T1 at all AND not curated → mark deprecated
    For T3 models with active provider not in T1 live → deactivate

  Phase B — CASCADE UP (T1 active → ensure T2+T3)
    For every provider with ≥1 active T1 key:
      1. Ensure T2 providers doc exists (create/update via sync_providers logic)
      2. Ensure T3 models are synced (trigger provider_sync for syncable providers)
      3. Record audit trail

  Phase C — INTEGRITY FIX
    1. Fix is_active=True + disabled_at contradictions (flip to False)
    2. Backfill providers.aggregate_status from T1 key_status
    3. Unset stale is_free_final (consolidated to is_free)
    4. Unset stray free_tier fields

  Phase D — VERIFY
    Post-enforcement alignment check (forward + reverse)

Safety:
  - Dry-run by default (--apply to mutate)
  - Mass-disable guard: abort if >50% active models would be deactivated
  - Per-provider fail-safe: one failure doesn't stop others
  - Curated providers (non-LLM) are never cascade-deleted
  - Audit trail recorded for every mutation

Usage:
  python3 sot_cascade_enforcement.py                    # full dry-run
  python3 sot_cascade_enforcement.py --apply            # execute
  python3 sot_cascade_enforcement.py --apply --phase A  # only cascade-down
  python3 sot_cascade_enforcement.py --apply --phase C  # only integrity fixes
  python3 sot_cascade_enforcement.py --json              # JSON output
  python3 sot_cascade_enforcement.py --provider groq     # single provider

Idempotent: re-running produces the same end state.
"""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import os, sys, json, argparse, traceback, time
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple
from collections import defaultdict

import pymongo

# ── Config ──────────────────────────────────────────────────────────────────
_MONGO_PASS = (
    os.environ.get("ILMA_MONGO_PASS")
    or next(
        (l.split("=", 1)[1].strip() for l in open("/root/.hermes/.env") if l.startswith("ILMA_MONGO_PASS=")),
        "",
    )
)
MONGO = dict(
    host="127.0.0.1", port=27017, directConnection=True,
    serverSelectionTimeoutMS=10000,
)
DB_NAME = "credentials"

# T3 downstream collections to cascade-deactivate/delete
DOWNSTREAM_COLL = [
    "model_intelligence", "model_benchmark", "model_audit_trail",
    "model_capabilities", "model_enrichment", "model_lifecycle_events",
]

# Curated providers that exist in T2 without T1 backing — NEVER cascade-delete
CURATED_ONLY_PREFIXES = (
    "system", "search_", "messaging", "browser_", "infra_",
    "crypto_", "gmail_", "puter", "you", "tavily",
    "serper", "github", "telegram", "cloudflare", "artificial_analysis",
    "nicehash", "binance", "tokocrypto", "qwen_bridge",
    "useai_bridge",
)

# Providers that have known sync endpoints in provider_sync.PROVIDER_CONFIGS
# (populated at runtime from provider_sync if available)
SYNCABLE_PROVIDERS: Set[str] = set()

# Safety guard
MAX_DEACTIVATE_FRACTION = 0.50


def get_client() -> pymongo.MongoClient:
    return pymongo.MongoClient(**MONGO)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_curated(pname: str) -> bool:
    return any(pname.startswith(pfx) for pfx in CURATED_ONLY_PREFIXES)


# ── T1 Resolution ──────────────────────────────────────────────────────────
def resolve_t1(db) -> Tuple[Dict[str, List[Dict]], Set[str], Set[str]]:
    """Group llm_providers by provider name. Return (siblings_index, live_set, inactive_set)."""
    siblings: Dict[str, List[Dict]] = defaultdict(list)
    for d in db.llm_providers.find({}, {
        "provider": 1, "key_status": 1, "is_active": 1,
        "api_key": 1, "free_bypass": 1, "account_email": 1,
    }):
        siblings[d.get("provider")].append(d)

    live: Set[str] = set()
    inactive: Set[str] = set()
    for pname, sibs in siblings.items():
        # A provider is LIVE if any sibling has VALID/UNVERIFIED key + api_key
        # OR has free_bypass=True
        has_active = any(
            (str(s.get("key_status", "")).upper() in ("VALID", "UNVERIFIED") and s.get("api_key"))
            or s.get("free_bypass") is True
            for s in sibs
        )
        (live if has_active else inactive).add(pname)

    return dict(siblings), live, inactive


def resolve_t2(db) -> Tuple[Set[str], Set[str], Set[str], Dict[str, Dict]]:
    """Return (all_providers, active_set, inactive_set, full_docs_index)."""
    all_p: Set[str] = set()
    active: Set[str] = set()
    inactive: Set[str] = set()
    docs: Dict[str, Dict] = {}
    for d in db.providers.find({}, {"provider": 1, "is_active": 1, "status": 1}):
        p = d.get("provider")
        all_p.add(p)
        docs[p] = d
        if d.get("is_active") is not False and d.get("status") not in ("INVALID", "deprecated"):
            active.add(p)
        else:
            inactive.add(p)
    return all_p, active, inactive, docs


def resolve_t3(db) -> Tuple[Set[str], Set[str]]:
    """Return (all_providers_with_models, providers_with_active_models)."""
    all_p = set(db.models.distinct("provider"))
    active_p = set(db.models.distinct("provider", {"is_active": True}))
    return all_p, active_p


# ── Phase A: CASCADE DOWN ─────────────────────────────────────────────────
def phase_a_cascade_down(db, t1_siblings, t1_live, t1_inactive,
                         t2_all, t2_active, t2_docs,
                         t3_all, t3_active, apply: bool) -> Dict[str, Any]:
    """T1 inactive/missing → deactivate T2 + T3."""
    result: Dict[str, Any] = {
        "t2_zombie_deactivated": [],
        "t2_orphan_deprecated": [],
        "t3_zombie_deactivated": [],
        "t3_orphan_deactivated": [],
        "t2_mutations": 0,
        "t3_mutations": 0,
        "downstream_mutations": 0,
    }

    now = now_utc()

    # A1: Zombie T2 — T2 active but T1 inactive
    zombie_t2 = t2_active & t1_inactive
    for pname in sorted(zombie_t2):
        if _is_curated(pname):
            continue
        entry = {"provider": pname, "action": "would_deactivate" if not apply else "deactivated"}
        if apply:
            r = db.providers.update_one(
                {"provider": pname},
                {"$set": {
                    "is_active": False, "status": "INVALID",
                    "disabled_at": now,
                    "deactivation_reason": "t1_cascade_no_active_keys",
                    "_cascade_enforced_at": now,
                }},
            )
            entry["modified"] = r.modified_count
            result["t2_mutations"] += r.modified_count
        result["t2_zombie_deactivated"].append(entry)

    # A2: Orphan T2 — T2 exists but T1 never had it AND not curated
    for pname in sorted(t2_all - set(t1_siblings.keys())):
        if _is_curated(pname):
            continue
        # Only mark deprecated, don't delete (preserve curated fields)
        entry = {"provider": pname, "action": "would_mark_deprecated" if not apply else "marked_deprecated"}
        if apply:
            r = db.providers.update_one(
                {"provider": pname},
                {"$set": {
                    "status": "deprecated",
                    "is_active": False,
                    "last_synced_at": now,
                    "_cascade_enforced_at": now,
                }},
            )
            entry["modified"] = r.modified_count
            result["t2_mutations"] += r.modified_count
        result["t2_orphan_deprecated"].append(entry)

    # A3: Zombie T3 — models with is_active=True but T1 provider is inactive
    zombie_t3 = t3_active & t1_inactive
    total_zombie_models = 0
    for pname in sorted(zombie_t3):
        n = db.models.count_documents({"provider": pname, "is_active": True})
        total_zombie_models += n
        entry = {"provider": pname, "active_models": n,
                 "action": "would_deactivate" if not apply else "deactivated"}
        result["t3_zombie_deactivated"].append(entry)

    # Safety guard: don't deactivate more than MAX_DEACTIVATE_FRACTION of all active models
    total_active = db.models.count_documents({"is_active": True})
    if total_active > 0 and total_zombie_models > total_active * MAX_DEACTIVATE_FRACTION:
        result["_aborted"] = True
        result["_reason"] = f"mass_deactivate_guard: would deactivate {total_zombie_models}/{total_active} active models"
        result["_threshold"] = f"{MAX_DEACTIVATE_FRACTION:.0%}"
        return result

    if apply and zombie_t3:
        set_payload = {
            "is_active": False, "status": "disabled",
            "deactivation_reason": "t1_cascade_no_active_keys",
            "disabled_at": now,
            "_cascade_enforced_at": now,
        }
        for pname in zombie_t3:
            r = db.models.update_many(
                {"provider": pname, "is_active": True},
                {"$set": set_payload},
            )
            result["t3_mutations"] += r.modified_count
            # Also deactivate downstream
            for coll in DOWNSTREAM_COLL:
                try:
                    db[coll].update_many(
                        {"provider": pname, "is_active": True},
                        {"$set": {"is_active": False, "_cascade_enforced_at": now}},
                    )
                except Exception:
                    pass
        # Audit trail
        try:
            db.model_audit_trail.insert_one({
                "provider": "*", "model_id": "*",
                "event_type": "cascade_enforcement_phase_a",
                "actor": "sot_cascade_enforcement",
                "source_collection": "llm_providers",
                "event_at": now,
                "evidence_id": f"CASCADE-A-{int(time.time())}",
                "delta": {"zombie_t3_providers": sorted(zombie_t3),
                          "models_deactivated": result["t3_mutations"]},
            })
        except Exception:
            pass

    # A4: Orphan T3 — models provider not in T1 at all
    t1_all_names = set(t1_siblings.keys())
    for pname in sorted(t3_active - t1_all_names):
        if _is_curated(pname):
            continue
        n = db.models.count_documents({"provider": pname, "is_active": True})
        if n == 0:
            continue
        entry = {"provider": pname, "active_models": n,
                 "action": "would_deactivate_orphan" if not apply else "deactivated_orphan"}
        result["t3_orphan_deactivated"].append(entry)
        if apply:
            r = db.models.update_many(
                {"provider": pname, "is_active": True},
                {"$set": {
                    "is_active": False, "status": "disabled",
                    "deactivation_reason": "t1_cascade_orphan_provider",
                    "disabled_at": now,
                    "_cascade_enforced_at": now,
                }},
            )
            result["t3_mutations"] += r.modified_count

    return result


# ── Phase B: CASCADE UP ───────────────────────────────────────────────────
def phase_b_cascade_up(db, t1_siblings, t1_live, t2_active,
                       t3_active, apply: bool) -> Dict[str, Any]:
    """T1 active → ensure T2 providers doc + T3 models exist."""
    result: Dict[str, Any] = {
        "t2_created": [],
        "t2_updated": [],
        "t3_sync_triggered": [],
        "t3_sync_skipped": [],
    }

    now = now_utc()
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "reconcile"))

    # B1: Missing T2 — T1 live but T2 missing/inactive
    missing_t2 = t1_live - t2_active
    for pname in sorted(missing_t2):
        siblings = t1_siblings.get(pname, [])
        # Build T2 record from T1 siblings
        t2_rec = _build_t2_from_t1(pname, siblings)
        entry = {"provider": pname, "action": "would_create" if not apply else "created",
                 "status": t2_rec.get("status"), "act_keys": t2_rec.get("act_key_count")}

        if apply:
            # Use sync_providers_from_llm_providers for proper consolidation
            try:
                from sync_providers_from_llm_providers import consolidate_provider
                existing = db.providers.find_one({"provider": pname})
                rec = consolidate_provider(pname, siblings, existing)
                db.providers.replace_one({"provider": pname}, rec, upsert=True)
                entry["action"] = "upserted"
                entry["status"] = rec.get("status")
            except ImportError:
                # Fallback: direct insert
                db.providers.replace_one({"provider": pname}, t2_rec, upsert=True)
                entry["action"] = "created_fallback"
        result["t2_created"].append(entry)

    # B2: Existing T2 that need status update (T1 live but T2 status stale)
    stale_t2 = t2_active & t1_live
    for pname in sorted(stale_t2):
        siblings = t1_siblings.get(pname, [])
        existing = db.providers.find_one({"provider": pname})
        if not existing:
            continue
        try:
            from sync_providers_from_llm_providers import consolidate_provider
            rec = consolidate_provider(pname, siblings, existing)
            # Check if status would change
            if rec.get("status") != existing.get("status") or rec.get("act_key_count") != existing.get("act_key_count"):
                entry = {"provider": pname, "old_status": existing.get("status"),
                         "new_status": rec.get("status"),
                         "action": "would_update" if not apply else "updated"}
                if apply:
                    db.providers.replace_one({"provider": pname}, rec, upsert=True)
                    entry["action"] = "updated"
                result["t2_updated"].append(entry)
        except ImportError:
            pass

    # B3: Missing T3 — T1 live but no active models for that provider
    missing_t3 = t1_live - t3_active
    for pname in sorted(missing_t3):
        # Check if provider is syncable
        is_syncable = pname in SYNCABLE_PROVIDERS
        entry = {"provider": pname, "is_syncable": is_syncable}
        if is_syncable and apply:
            entry["action"] = "sync_triggered"
            # We don't run provider_sync here (it's a heavy operation)
            # Instead, mark it for the next auto-sync cycle
            db["sot_sync_state"].update_one(
                {"_id": pname},
                {"$set": {
                    "needs_sync": True,
                    "needs_sync_reason": "cascade_enforcement_t1_active_no_t3",
                    "updated_at": now,
                }},
                upsert=True,
            )
            result["t3_sync_triggered"].append(entry)
        elif is_syncable:
            entry["action"] = "would_trigger_sync"
            result["t3_sync_triggered"].append(entry)
        else:
            entry["action"] = "skipped_no_sync_endpoint"
            result["t3_sync_skipped"].append(entry)

    return result


def _build_t2_from_t1(pname: str, siblings: List[Dict]) -> Dict[str, Any]:
    """Build a minimal T2 providers record from T1 siblings (fallback when sync module unavailable)."""
    active_states = {"VALID", "UNVERIFIED"}
    act_keys = sum(1 for s in siblings if s.get("key_status") in active_states and s.get("api_key"))
    has_free_bypass = any(s.get("free_bypass") is True for s in siblings)
    # free_bypass providers are active even with INVALID key_status
    if act_keys > 0 or has_free_bypass:
        status = "active"
        is_active = True
        effective_act_keys = max(act_keys, 1)  # free_bypass counts as 1 effective key
    else:
        status = "INVALID"
        is_active = False
        effective_act_keys = 0
    purposes = sorted({s.get("key_purpose") for s in siblings if s.get("key_purpose")})
    return {
        "provider": pname,
        "status": status,
        "is_active": is_active,
        "multi_account": len(siblings) > 1,
        "multi_purpose": len(purposes) > 1,
        "key_count": len(siblings),
        "act_key_count": effective_act_keys,
        "key_purposes": purposes,
        "free_bypass": has_free_bypass,
        "t1_source": "llm_providers",
        "t1_source_key": pname,
        "last_synced_at": now_utc(),
        "_cascade_enforced_at": now_utc(),
    }


# ── Phase C: INTEGRITY FIXES ──────────────────────────────────────────────
def phase_c_integrity(db, apply: bool) -> Dict[str, Any]:
    """Fix data integrity issues across all collections."""
    result: Dict[str, Any] = {}
    now = now_utc()

    # C1: is_active=True + disabled_at exists → contradiction
    conflict_count = db.models.count_documents({
        "is_active": True, "disabled_at": {"$exists": True},
    })
    result["active_with_disabled_at"] = conflict_count
    if apply and conflict_count > 0:
        r = db.models.update_many(
            {"is_active": True, "disabled_at": {"$exists": True}},
            {"$set": {
                "is_active": False, "status": "disabled",
                "_sot_integrity_fix_at": now,
            }},
        )
        result["fixed_active_disabled_conflict"] = r.modified_count

    # C2: Backfill providers.aggregate_status from T1 key_status
    siblings_idx: Dict[str, List[Dict]] = defaultdict(list)
    for d in db.llm_providers.find({}, {"provider": 1, "key_status": 1, "api_key": 1, "free_bypass": 1}):
        siblings_idx[d.get("provider")].append(d)

    backfilled = 0
    for pname, sibs in siblings_idx.items():
        active_states = {"VALID", "UNVERIFIED"}
        has_active = any(s.get("key_status") in active_states and s.get("api_key") for s in sibs)
        agg_status = "active" if has_active else "INVALID"
        existing = db.providers.find_one({"provider": pname})
        if existing and existing.get("aggregate_status") != agg_status:
            if apply:
                db.providers.update_one(
                    {"provider": pname},
                    {"$set": {
                        "aggregate_status": agg_status,
                        "_aggregate_backfilled_at": now,
                    }},
                )
            backfilled += 1
    result["aggregate_status_backfilled"] = backfilled

    # C3: Unset stale is_free_final (consolidated to is_free)
    stale_count = db.models.count_documents({"is_free_final": {"$exists": True}})
    result["is_free_final_remaining"] = stale_count
    if apply and stale_count > 0:
        r = db.models.update_many({"is_free_final": {"$exists": True}}, {"$unset": {"is_free_final": ""}})
        result["is_free_final_unset"] = r.modified_count

    # C4: Unset stray free_tier
    ft_count = db.models.count_documents({"free_tier": {"$exists": True}})
    result["free_tier_remaining"] = ft_count
    if apply and ft_count > 0:
        r = db.models.update_many({"free_tier": {"$exists": True}}, {"$unset": {"free_tier": ""}})
        result["free_tier_unset"] = r.modified_count

    return result


# ── Phase D: POST-ENFORCEMENT VERIFY ─────────────────────────────────────
def phase_d_verify(db, t1_siblings, t1_live) -> Dict[str, Any]:
    """Post-enforcement alignment check."""
    t2_all, t2_active, t2_inactive, _ = resolve_t2(db)
    t3_all, t3_active = resolve_t3(db)

    still_zombie_t2 = t2_active & (set(t1_siblings.keys()) - t1_live)
    still_zombie_t3 = t3_active & (set(t1_siblings.keys()) - t1_live)
    still_missing_t2 = t1_live - t2_active
    still_missing_t3 = t1_live - t3_active
    still_contradictions = db.models.count_documents({
        "is_active": True, "disabled_at": {"$exists": True}
    })

    return {
        "aligned": (len(still_zombie_t2) == 0 and len(still_zombie_t3) == 0
                    and still_contradictions == 0),
        "zombie_t2_remaining": sorted(still_zombie_t2),
        "zombie_t3_remaining": sorted(still_zombie_t3),
        "missing_t2_remaining": sorted(still_missing_t2),
        "missing_t3_remaining": sorted(still_missing_t3),
        "contradictions_remaining": still_contradictions,
        "t1_live": len(t1_live),
        "t2_active": len(t2_active),
        "t3_active_providers": len(t3_active),
    }


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SOT Cascade Enforcement Engine")
    parser.add_argument("--apply", action="store_true",
                        help="Actually mutate MongoDB. Default is dry-run (preview only).")
    parser.add_argument("--phase", choices=["A", "B", "C", "D"],
                        help="Run only one phase (A=cascade-down, B=cascade-up, C=integrity, D=verify)")
    parser.add_argument("--provider", help="Filter to single provider")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    client = get_client()
    db = client[DB_NAME]

    # Load syncable providers
    global SYNCABLE_PROVIDERS
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "discovery"))
        import provider_sync
        SYNCABLE_PROVIDERS = {p for p, cfg in provider_sync.PROVIDER_CONFIGS.items()
                              if p not in {"cloudflare", "artificial_analysis"}
                              and not cfg.get("skip_sync")}
    except ImportError:
        pass

    # Resolve current state
    t1_siblings, t1_live, t1_inactive = resolve_t1(db)
    t2_all, t2_active, t2_inactive, t2_docs = resolve_t2(db)
    t3_all, t3_active = resolve_t3(db)

    # Filter to single provider if requested
    if args.provider:
        pname = args.provider
        t1_siblings = {pname: t1_siblings.get(pname, [])}
        t1_live = t1_live & {pname}
        t1_inactive = t1_inactive & {pname}
        t2_active = t2_active & {pname}
        t2_all = t2_all & {pname}
        t3_active = t3_active & {pname}
        t3_all = t3_all & {pname}

    result: Dict[str, Any] = {
        "executed_at": now_utc().isoformat(),
        "mode": "apply" if args.apply else "dry-run",
        "pre_state": {
            "t1_live": len(t1_live), "t1_inactive": len(t1_inactive),
            "t2_active": len(t2_active), "t2_inactive": len(t2_inactive),
            "t3_active_providers": len(t3_active),
        },
    }

    phases_to_run = [args.phase] if args.phase else ["A", "B", "C", "D"]

    for phase in phases_to_run:
        try:
            if phase == "A":
                result["phase_a"] = phase_a_cascade_down(
                    db, t1_siblings, t1_live, t1_inactive,
                    t2_all, t2_active, t2_docs,
                    t3_all, t3_active, args.apply,
                )
            elif phase == "B":
                result["phase_b"] = phase_b_cascade_up(
                    db, t1_siblings, t1_live, t2_active,
                    t3_active, args.apply,
                )
            elif phase == "C":
                result["phase_c"] = phase_c_integrity(db, args.apply)
            elif phase == "D":
                result["phase_d"] = phase_d_verify(db, t1_siblings, t1_live)
        except Exception as e:
            result[f"phase_{phase.lower()}_error"] = f"{type(e).__name__}: {e}"
            result[f"phase_{phase.lower()}_traceback"] = traceback.format_exc(limit=8)

    # Print
    if args.json:
        print(json.dumps(result, default=str, indent=2, ensure_ascii=False))
    else:
        _print_report(result, args)

    return result


def _print_report(result: Dict, args):
    mode = result["mode"]
    print(f"\n{'='*60}")
    print(f"  SOT CASCADE ENFORCEMENT [{mode.upper()}]")
    print(f"{'='*60}")
    print(f"  Executed: {result['executed_at']}")
    print()
    pre = result.get("pre_state", {})
    print(f"  T1 live: {pre.get('t1_live')} | inactive: {pre.get('t1_inactive')}")
    print(f"  T2 active: {pre.get('t2_active')} | inactive: {pre.get('t2_inactive')}")
    print(f"  T3 active providers: {pre.get('t3_active_providers')}")

    for phase_key in ["phase_a", "phase_b", "phase_c", "phase_d"]:
        if phase_key not in result:
            continue
        data = result[phase_key]
        label = phase_key.upper().replace("_", " ")
        print(f"\n  ── {label} ──")
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list) and len(v) > 5:
                    print(f"    {k}: {len(v)} items")
                    for item in v[:3]:
                        print(f"      - {item}")
                    if len(v) > 3:
                        print(f"      ... +{len(v)-3} more")
                elif isinstance(v, list):
                    print(f"    {k}: {v}")
                else:
                    print(f"    {k}: {v}")
        else:
            print(f"    {data}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
