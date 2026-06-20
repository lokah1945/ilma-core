#!/usr/bin/env python3
"""
sot_auto_sync.py — SOT models auto-build engine (Tier-1 driven, delta + prune)
==============================================================================
Concept (Bos 2026-06-19): `models` is DYNAMIC; only `llm_providers` is static.
Whenever llm_providers changes (add / edit / remove) OR on a 6-hourly schedule,
the models collection must auto-rebuild to reflect each provider's CURRENT model
list — models can be ADDED (new upstream) or REMOVED (vanished upstream).

This engine is SOT-driven: the set of providers to sync = ACTIVE providers in
llm_providers that have a known sync endpoint (provider_sync.PROVIDER_CONFIGS).
A provider added to llm_providers is therefore auto-included with no code change.

Per-provider delta:
  • upsert models the provider currently serves   (add new + refresh existing)
  • HARD-DELETE models that vanished upstream      (+ downstream collections)
  • SAFETY GUARD: never prune on empty/failed fetch, and refuse to delete more
    than PRUNE_MAX_FRACTION of a provider's active models in one pass (guards
    against a transient/garbage /v1/models response wiping a whole catalog).
  • model-list hash → downstream enrich/materialize only re-run when it changed.

Triggers:
  • real-time   : sot_sync_daemon.py (change stream on llm_providers) → sync_one()
  • scheduled   : ilma-sot-sync.timer every 6h → --full

CLI:
  python3 sot_auto_sync.py --full            # delta-sync ALL target providers
  python3 sot_auto_sync.py --changed         # only providers whose llm_providers fp changed
  python3 sot_auto_sync.py --provider groq   # one provider
  python3 sot_auto_sync.py --full --dry-run  # preview, no writes
  python3 sot_auto_sync.py --status          # show sync state
"""
from __future__ import annotations
import os, sys, json, time, hashlib, argparse, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import pymongo

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "discovery"))
sys.path.insert(0, os.path.join(_HERE, "..", "orchestration"))
import provider_sync  # noqa: E402

logger = logging.getLogger("ilma.sot.autosync")

MONGO = dict(host="172.16.103.253", port=27017, username="quantumtraffic",
             password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")), authSource="admin", directConnection=True,
             serverSelectionTimeoutMS=10000)
DB_NAME = "credentials"
STATE_COLL = "sot_sync_state"            # per-provider sync fingerprint + stats
DOWNSTREAM = ["model_intelligence", "model_benchmark", "model_capabilities",
              "model_enrichment", "model_lifecycle_events"]  # model_audit_trail kept (ledger)

PRUNE_MAX_FRACTION = 0.50   # refuse to delete >50% of a provider's active models in one run
MAX_WORKERS = 6             # bounded provider concurrency
SYNC_PERIOD_HOURS = 6

# providers that exist in configs but are not directly syncable
_SKIP = {"cloudflare", "artificial_analysis"}


def get_db():
    return pymongo.MongoClient(**MONGO)[DB_NAME]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ── SOT resolution ────────────────────────────────────────────────────────────
def resolve_target_providers(db) -> List[str]:
    """Providers to sync = ACTIVE in llm_providers (Tier-1 SOT) AND have a sync config.
    SOT-driven: adding a provider to llm_providers auto-includes it (if a config exists)."""
    active = set()
    for d in db.llm_providers.find({"is_active": {"$ne": False}}, {"provider": 1}):
        p = d.get("provider")
        if p:
            active.add(p)
    syncable = {p for p, cfg in provider_sync.PROVIDER_CONFIGS.items()
                if p not in _SKIP and not cfg.get("skip_sync")}
    targets = sorted(active & syncable)
    skipped = sorted(active - syncable)
    if skipped:
        logger.info(f"[autosync] active llm_providers without sync endpoint (skipped): {skipped}")
    return targets


def provider_fingerprint(db, pname: str) -> str:
    """Hash of the Tier-1 credential state for a provider (account set, statuses, key presence).
    Changes iff the provider's llm_providers rows are added/edited/removed."""
    rows = []
    for d in db.llm_providers.find({"provider": pname}):
        rows.append((d.get("account_email"), d.get("key_status"),
                     bool(d.get("is_active", True)), bool(d.get("api_key")),
                     d.get("key_purpose")))
    rows.sort(key=lambda x: tuple("" if v is None else str(v) for v in x))
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:16]


def models_hash(ids: List[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(ids), sort_keys=True).encode()).hexdigest()[:16]


def _state(db, pname: str) -> Dict[str, Any]:
    return db[STATE_COLL].find_one({"_id": pname}) or {}


def _save_state(db, pname: str, **fields):
    fields["updated_at"] = now_utc()
    db[STATE_COLL].update_one({"_id": pname}, {"$set": fields}, upsert=True)


# ── Prune (hard-delete vanished models) with safety guard ──────────────────────
def prune_provider(db, pname: str, live_ids: Set[str], dry_run: bool,
                   force: bool = False) -> Dict[str, Any]:
    """Hard-delete models (and downstream rows) of `pname` whose model_id is NOT in
    the provider's current live set. Guarded against accidental mass-wipes."""
    if not live_ids:
        return {"pruned": 0, "skipped_reason": "empty_live_set_fetch_suspect"}

    db_ids = set(db.models.distinct("model_id", {"provider": pname}))
    vanished = sorted(db_ids - live_ids)
    if not vanished:
        return {"pruned": 0}

    # SAFETY: refuse to nuke a large fraction of the provider's WHOLE catalog in one
    # pass unless forced (guards against a transient/garbage /v1/models response).
    total = len(db_ids)
    if (not force and total > 0
            and len(vanished) > total * PRUNE_MAX_FRACTION):
        logger.warning(f"[autosync] {pname}: prune guard tripped — would delete "
                       f"{len(vanished)}/{total} models; SKIPPED (use --force-prune).")
        return {"pruned": 0, "skipped_reason": "prune_guard_tripped",
                "would_delete": len(vanished), "total": total}

    if dry_run:
        return {"pruned": 0, "would_prune": len(vanished), "sample": vanished[:5]}

    deleted = {"models": 0}
    for i in range(0, len(vanished), 400):
        batch = vanished[i:i + 400]
        flt = {"provider": pname, "model_id": {"$in": batch}}
        deleted["models"] += db.models.delete_many(flt).deleted_count
        for c in DOWNSTREAM:
            db[c].delete_many(flt)
    # audit (one summary event — keeps the ledger meaningful, not 1 row per model)
    try:
        db.model_audit_trail.insert_one({
            "provider": pname, "model_id": "*", "event_type": "model_disabled",
            "actor": "sot_auto_sync", "source_collection": "models",
            "event_at": now_utc(), "evidence_id": f"AUTOSYNC-PRUNE-{pname}-{int(time.time())}",
            "delta": {"pruned_vanished": len(vanished), "sample": vanished[:10]},
        })
    except Exception:
        pass
    return {"pruned": deleted["models"], "vanished": len(vanished)}


# ── Per-provider delta sync ────────────────────────────────────────────────────
def sync_provider_delta(db, pname: str, dry_run: bool = False,
                        force_prune: bool = False) -> Dict[str, Any]:
    """Upsert current models + hard-delete vanished ones. Returns delta stats."""
    t0 = time.time()
    try:
        res = provider_sync.sync_provider(pname, dry_run=dry_run)
    except Exception as e:
        return {"provider": pname, "status": "error", "reason": str(e)[:160]}

    status = res.get("status")
    live_ids = set(res.get("live_ids") or [])
    out = {"provider": pname, "status": status,
           "added": res.get("added", 0), "updated": res.get("updated", 0),
           "live": res.get("live", 0)}

    if status == "success":
        prune = prune_provider(db, pname, live_ids, dry_run, force=force_prune)
        out["prune"] = prune
        mh = models_hash(sorted(live_ids))
        prev = _state(db, pname)
        out["models_changed"] = (mh != prev.get("models_hash"))
        if not dry_run:
            _save_state(db, pname,
                        llm_fp=provider_fingerprint(db, pname),
                        models_hash=mh, model_count=len(live_ids),
                        last_synced_at=now_utc(), last_status="success",
                        added=out["added"], updated=out["updated"],
                        pruned=prune.get("pruned", 0))
    else:
        out["reason"] = res.get("reason")
        if not dry_run:
            _save_state(db, pname, last_synced_at=now_utc(), last_status=status,
                        last_reason=res.get("reason"),
                        llm_fp=provider_fingerprint(db, pname))
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


def cascade_out_provider(db, pname: str, dry_run: bool = False) -> Dict[str, Any]:
    """Provider removed from llm_providers → hard-delete ALL its models + downstream."""
    n = db.models.count_documents({"provider": pname})
    if dry_run:
        return {"provider": pname, "would_delete_models": n}
    flt = {"provider": pname}
    deleted = db.models.delete_many(flt).deleted_count
    for c in DOWNSTREAM:
        db[c].delete_many(flt)
    db[STATE_COLL].delete_one({"_id": pname})
    try:
        db.model_audit_trail.insert_one({
            "provider": pname, "model_id": "*", "event_type": "model_disabled",
            "actor": "sot_auto_sync", "source_collection": "llm_providers",
            "event_at": now_utc(), "evidence_id": f"AUTOSYNC-CASCADEOUT-{pname}-{int(time.time())}",
            "delta": {"provider_removed_from_llm_providers": True, "deleted_models": deleted},
        })
    except Exception:
        pass
    return {"provider": pname, "deleted_models": deleted}


# ── Orchestration ──────────────────────────────────────────────────────────────
def _enrich_provider(provider: str, dry_run: bool = False) -> Dict[str, Any]:
    """Score + classify a provider's models after a sync: model_intelligence (scoring SOT)
    AND is_free_final (billing SOT) so new models are immediately selectable AND have a
    final free/paid verdict baked in."""
    try:
        sys.path.insert(0, os.path.join(_HERE, "..", "enrichment"))
        import sot_enrich_models, sot_billing_classify
        r = sot_enrich_models.run(mode="full", provider=provider, dry_run=dry_run)
        b = sot_billing_classify.run(provider=provider, dry_run=dry_run)
        return {"provider": provider, "enriched": r.get("enriched"),
                "tiers": r.get("tier_distribution"),
                "billing": {"free": b.get("free"), "paid": b.get("paid")}}
    except Exception as e:
        logger.warning(f"[autosync] enrich {provider} failed: {e}")
        return {"provider": provider, "error": str(e)[:120]}


def _enrich_all() -> Dict[str, Any]:
    """Full re-score + re-classify billing for all models (6h sweep after AA refresh)."""
    try:
        sys.path.insert(0, os.path.join(_HERE, "..", "enrichment"))
        import sot_enrich_models, sot_billing_classify
        r = sot_enrich_models.run(mode="full", dry_run=False)
        b = sot_billing_classify.run(dry_run=False)
        return {"scope": "all", "enriched": r.get("enriched"),
                "tiers": r.get("tier_distribution"),
                "billing": {"free": b.get("free"), "paid": b.get("paid")}}
    except Exception as e:
        logger.warning(f"[autosync] full enrich failed: {e}")
        return {"scope": "all", "error": str(e)[:120]}


def _refresh_aa() -> None:
    """Refresh Artificial Analysis benchmark rows (key from search_providers)."""
    try:
        sys.path.insert(0, os.path.join(_HERE, "..", "enrichment"))
        import sot_aa_ingest
        db = get_db()
        recs = sot_aa_ingest.fetch_aa(db)
        idx = sot_aa_ingest.build_aa_index(recs)
        import pymongo as _pm
        now = now_utc()
        ops = []
        for m in db.models.find({"is_active": True}, {"provider": 1, "model_id": 1}):
            aa = idx.get(sot_aa_ingest._norm(m["model_id"]))
            if not aa:
                continue
            ops.append(_pm.UpdateOne(
                {"provider": m["provider"], "model_id": m["model_id"],
                 "benchmark_source": "artificial_analysis"},
                {"$set": {"provider": m["provider"], "model_id": m["model_id"],
                          "benchmark_source": "artificial_analysis", "evidence_type": "PROXY",
                          "aa_intelligence_index": aa.get("ai_index"),
                          "aa_coding_index": aa.get("coding_index"),
                          "aa_math_index": aa.get("math_index"), "fetched_at": now}},
                upsert=True))
        if ops:
            db.model_benchmark.bulk_write(ops, ordered=False)
        logger.info(f"[autosync] AA refresh: matched {len(ops)} models")
    except Exception as e:
        logger.warning(f"[autosync] AA refresh failed (non-fatal): {e}")


def _detect_removed(db, targets: List[str]) -> List[str]:
    """Providers we previously synced that are no longer active in llm_providers."""
    known = {d["_id"] for d in db[STATE_COLL].find({}, {"_id": 1})}
    return sorted(known - set(targets))


def run_sync(mode: str = "full", provider: Optional[str] = None,
             dry_run: bool = False, force_prune: bool = False) -> Dict[str, Any]:
    db = get_db()
    provider_sync._load_url_overrides()
    targets = resolve_target_providers(db)

    if provider:
        targets = [provider] if provider in targets else []
        if not targets:
            return {"error": f"{provider} not an active syncable provider"}
    elif mode == "changed":
        changed = []
        for p in targets:
            if provider_fingerprint(db, p) != _state(db, p).get("llm_fp"):
                changed.append(p)
        targets = changed

    results, removed_results = [], []
    # cascade-out providers removed from llm_providers (only on full/changed sweeps)
    if not provider:
        for rp in _detect_removed(db, resolve_target_providers(db)):
            removed_results.append(cascade_out_provider(db, rp, dry_run=dry_run))

    if targets:
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(targets))) as ex:
            futs = {ex.submit(sync_provider_delta, get_db(), p, dry_run, force_prune): p
                    for p in targets}
            for f in as_completed(futs):
                results.append(f.result())

    changed_any = any(r.get("models_changed") or r.get("added") or
                      (r.get("prune", {}) or {}).get("pruned") for r in results) \
        or bool(removed_results)

    # ENRICH: new/changed models get a real composite_score + capabilities_detail so
    # they are immediately selectable (audit 2026-06-20: enrichment is part of the model
    # lifecycle). On the 6h FULL sweep we also refresh AA benchmarks and re-score the
    # WHOLE fleet (AA updates affect every model, not just changed providers).
    enriched = []
    if not dry_run:
        if mode == "full" and not provider:
            _refresh_aa()                                   # AA quality layer
            enriched.append(_enrich_all())                  # full re-score
        else:
            changed_providers = [r["provider"] for r in results
                                 if r.get("status") == "success"
                                 and (r.get("models_changed") or r.get("added")
                                      or (r.get("prune", {}) or {}).get("pruned"))]
            for p in changed_providers:
                enriched.append(_enrich_provider(p, dry_run=False))

    # trigger downstream materialize only when something actually changed
    materialized = None
    if changed_any and not dry_run and mode != "no_downstream":
        try:
            import sot_materialize
            materialized = {
                "master": sot_materialize.materialize_master(dry_run=False).get("status"),
                "api_key": sot_materialize.materialize_api_key(dry_run=False, include_secrets=False).get("status"),
            }
        except Exception as e:
            materialized = {"error": str(e)[:120]}

    summary = {
        "mode": mode, "dry_run": dry_run, "ts": now_utc().isoformat(),
        "targets": len(targets),
        "synced_ok": sum(1 for r in results if r.get("status") == "success"),
        "errors": sum(1 for r in results if r.get("status") == "error"),
        "added": sum(r.get("added", 0) for r in results),
        "pruned": sum((r.get("prune", {}) or {}).get("pruned", 0) for r in results),
        "enriched": enriched,
        "removed_providers": removed_results,
        "materialized": materialized,
        "results": results,
    }
    return summary


def show_status() -> Dict[str, Any]:
    db = get_db()
    rows = list(db[STATE_COLL].find({}))
    return {"providers_tracked": len(rows),
            "state": sorted(({"provider": r["_id"],
                              "models": r.get("model_count"),
                              "last_status": r.get("last_status"),
                              "last_synced_at": str(r.get("last_synced_at")),
                              "added": r.get("added"), "pruned": r.get("pruned")}
                             for r in rows), key=lambda x: x["provider"])}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--full", action="store_true", help="delta-sync all target providers")
    g.add_argument("--changed", action="store_true", help="only providers whose llm_providers fp changed")
    g.add_argument("--provider", help="sync one provider")
    g.add_argument("--status", action="store_true", help="show sync state")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-prune", action="store_true", help="bypass mass-delete guard")
    args = ap.parse_args()

    if args.status:
        print(json.dumps(show_status(), indent=2, default=str)); return
    mode = "changed" if args.changed else "full"
    out = run_sync(mode=mode, provider=args.provider,
                   dry_run=args.dry_run, force_prune=args.force_prune)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
