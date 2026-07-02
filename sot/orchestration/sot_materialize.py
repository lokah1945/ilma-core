#!/usr/bin/env python3
import logging
logger = logging.getLogger(__name__)
"""
sot_materialize.py — SOT Materialization Engine
================================================

Reads from SOT MongoDB collections and writes the on-disk cache files
that the runtime currently consumes:

  • PROVIDER_INTELLIGENCE_MASTER.json (provider/models intelligence)
  • benchmark_database.json          (passive benchmark scores)
  • api_key.json                     (provider credentials, with masked keys)

This is the SOT → disk bridge. The runtime does NOT need to know about
MongoDB; it reads the same flat files as before. The SOT is the single
source of truth; these files are derived caches, regenerated on demand.

Idempotent. Re-running overwrites the cache atomically (write to .tmp,
fsync, rename).

Usage:
    python3 sot_materialize.py                        # materialize everything
    python3 sot_materialize.py --target master         # only MASTER.json
    python3 sot_materialize.py --target api_key        # only api_key.json
    python3 sot_materialize.py --target benchmarks     # only benchmark_db
    python3 sot_materialize.py --dry-run               # preview
    python3 sot_materialize.py --verify                # check cache is fresh
"""
import os, sys, json, argparse, shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sot_ops
from sot_ops import (
    models_coll, benchmarks_coll, intelligence_coll,
    llm_providers_coll, providers_coll, audit_coll,
    ensure_indexes, generate_evidence_id, write_audit,
    normalize, _ensure_unique_index,
)

SOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.dirname(os.path.dirname(SOT_DIR))  # /root/.hermes/profiles/ilma/
ROUTER_DIR = os.path.join(PROFILE_DIR, "ilma_model_router_data")
# api_key.json lives in /root/credential/ (system-wide)
# SOT_DIR is /root/.hermes/profiles/ilma/sot/orchestration
# Need to go up 3 levels: orchestration -> sot -> profiles/ilma -> .hermes -> root
CREDENTIAL_DIR = "/root/credential"

MASTER_PATH = os.path.join(ROUTER_DIR, "PROVIDER_INTELLIGENCE_MASTER.json")
BENCH_DB_PATH = os.path.join(ROUTER_DIR, "benchmark_database.json")
API_KEY_PATH = os.path.join(CREDENTIAL_DIR, "api_key.json")
ENRICHER_VERSION = "4.0.0-sot"

# ── Atomic write helper ──────────────────────────────────────────────────────
def _atomic_write(path: str, data: Any) -> int:
    """Write JSON atomically: .tmp → fsync → rename. Returns bytes written."""
    tmp = path + ".tmp"
    content = json.dumps(data, indent=2, default=str, ensure_ascii=False)
    with open(tmp, "w") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return len(content)

# ── Materialize PROVIDER_INTELLIGENCE_MASTER.json ────────────────────────────
def materialize_master(dry_run: bool = False) -> Dict[str, Any]:
    """Build the MASTER.json structure from MongoDB collections."""
    out: Dict[str, Any] = {
        "_version": f"SSS+++ {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "_last_updated": datetime.now(timezone.utc).isoformat(),
        "_sot_lifecycle": {
            "discovery_interval_sec": 1800,
            "auto_enrichment_enabled": True,
            "auto_deprecation_enabled": True,
            "provider_health_check_enabled": True,
            "last_sync": int(datetime.now(timezone.utc).timestamp()),
            "sync_source": "MongoDB SOT (credentials.models + credentials.model_intelligence)",
        },
        "_enriched_at": datetime.now(timezone.utc).isoformat(),
        "_enricher_version": ENRICHER_VERSION,
        "_enrichment_stats": {},
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "providers": {},
    }

    # Index intelligence by (provider, model_id) for fast join
    intel_idx: Dict[tuple, Dict] = {}
    for d in intelligence_coll().find({}):
        key = (d.get("provider"), d.get("model_id"))
        intel_idx[key] = normalize(d)

    # Group models by provider
    by_provider: Dict[str, List[Dict]] = {}
    for m in models_coll().find({}):
        pname = m.get("provider", "unknown")
        by_provider.setdefault(pname, []).append(m)

    # Pull provider info from llm_providers + providers
    # FIX 2026-06-19 (audit H4): count active keys per provider (multi-account is by
    # design: nvidia x3, openrouter x2) instead of hardcoding api_key_count=1.
    lp_idx: Dict[str, Dict] = {}
    lp_active_count: Dict[str, int] = {}
    for d in llm_providers_coll().find({}):
        pn = d.get("provider")
        if pn not in lp_idx:
            lp_idx[pn] = d
        if d.get("api_key") and d.get("key_status") in ("VALID", "UNVERIFIED"):
            lp_active_count[pn] = lp_active_count.get(pn, 0) + 1
    prov_idx: Dict[str, Dict] = {}
    for d in providers_coll().find({}):
        prov_idx[d.get("provider")] = d

    total_models = 0
    for pname, models in by_provider.items():
        # FIX 2026-06-19 (audit H3/H4): catalog fields (status, free_tier, base_url,
        # auth_format, description) live in providers (Tier-2). Tier-1 llm_providers
        # only carries credentials. Source catalog from T2; key count from T1.
        cat = prov_idx.get(pname, {})           # Tier-2 catalog
        prov_info = cat or lp_idx.get(pname, {})  # fallback to T1 if no T2 row
        prov_block = {
            "status": "active" if any(m.get("is_active") for m in models) else "disabled",
            "auth_validated": cat.get("status") in ("active", "ENDPOINT_WORKS_QUOTA_EXHAUSTED"),
            "api_key_count": lp_active_count.get(pname, 0),
            "sot_note": "materialized_from_mongodb_sot",
            "models": {},
            "provider_info": {
                "name": pname,
                "free_bypass": bool(cat.get("free_bypass", False)),
            },
        }
        if prov_info.get("base_url"):
            prov_block["provider_info"]["base_url"] = prov_info["base_url"]
        if prov_info.get("auth_format"):
            prov_block["provider_info"]["auth_format"] = prov_info["auth_format"]
        if prov_info.get("description"):
            prov_block["provider_info"]["description"] = prov_info["description"]

        for m in models:
            mid = m.get("model_id")
            intel = intel_idx.get((pname, mid), {})
            model_entry = normalize(m)
            # Merge intelligence enrichment (if exists)
            if intel:
                # Intel takes precedence for score/tier fields
                for k in (
                    "score", "score_tier", "score_source", "score_breakdown",
                    "benchmark_score", "benchmark_aa", "total_requests",
                    "error_rate", "benchmark_updated", "quality_score",
                    "cost_score", "free_tier_bonus", "last_enriched_at",
                ):
                    if intel.get(k) is not None and k in intel:
                        model_entry[k] = intel[k]
                # Capabilities merge
                if intel.get("capabilities") and not model_entry.get("capabilities"):
                    model_entry["capabilities"] = intel["capabilities"]
                if intel.get("specialization"):
                    model_entry["specialization"] = intel["specialization"]
                if intel.get("specializations"):
                    model_entry["specializations"] = intel["specializations"]
                if intel.get("description") and not model_entry.get("description"):
                    model_entry["description"] = intel["description"]
                if intel.get("model_status"):
                    for k, v in intel["model_status"].items():
                        if v is not None:
                            model_entry[k] = v
            prov_block["models"][mid] = model_entry
            total_models += 1

        out["providers"][pname] = prov_block

    out["_enrichment_stats"] = {
        "total_providers": len(by_provider),
        "total_models": total_models,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "composite_score_formula": "0.45*intelligence + 0.30*coding + 0.15*math + 0.05*capability_breadth + 0.05*usage_health (AA+heuristic) | 0.7*capability_breadth + 0.3*usage_health (heuristic only, capped 60)",
        "source": "MongoDB SOT (credentials.models + credentials.model_intelligence)",
        "sot_model_entries": total_models,
        "sot_intel_entries": intelligence_coll().count_documents({}),
    }

    if dry_run:
        return {
            "status": "preview",
            "providers": len(by_provider),
            "models": total_models,
        }

    bytes_written = _atomic_write(MASTER_PATH, out)
    return {
        "status": "success",
        "target": MASTER_PATH,
        "providers": len(by_provider),
        "models": total_models,
        "bytes": bytes_written,
    }

# ── Materialize benchmark_database.json ──────────────────────────────────────
def materialize_benchmarks(dry_run: bool = False) -> Dict[str, Any]:
    """Build the benchmark_database.json structure from MongoDB."""
    out = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_entries": 0,
        "total_models": 0,
        "models": {},
        "benchmarks": {},
        "entries": [],
        "benchmark_entries": [],
        "metadata": {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "source": "MongoDB SOT (credentials.model_benchmarks)",
            "sot_synchronized_at": datetime.now(timezone.utc).isoformat(),
            "sot_benchmark_entries": benchmarks_coll().count_documents({}),
            "sot_benchmark_alias_entries": 0,
        },
    }

    for d in benchmarks_coll().find({}):
        d = normalize(d)
        provider = d.get("provider", "unknown")
        mid = d.get("model_id", "")
        source = d.get("benchmark_source", "unknown")
        full_key = f"{provider}/{mid}"
        alias_key = mid

        # Per-benchmark entry
        out["benchmark_entries"].append({
            "model_id": full_key,
            "test_timestamp": d.get("fetched_at") or d.get("last_benchmarked"),
            "status": d.get("freshness_status", "unknown"),
            "avg_latency_ms": None,  # not tracked in SOT
            "success_count": d.get("total_requests", 0) or 0,
            "failure_count": 0,
            "quality_score": (
                d.get("avg_score") / 100.0
                if d.get("avg_score") is not None
                else (
                    d.get("aa_intelligence_index") / 100.0
                    if d.get("aa_intelligence_index") is not None
                    else None
                )
            ),
            "notes": f"Source: {source}",
            "reasoning_score": (
                d.get("aa_intelligence_index") / 100.0
                if d.get("aa_intelligence_index") is not None
                else None
            ),
        })
        # Main entry per model (latest source wins)
        bm_entry = {
            "model_id": mid,
            "provider": provider,
            "full_model_id": full_key,
            "avg_score": d.get("avg_score"),
            "quality_baseline_score": d.get("quality_baseline_score") or d.get("aa_intelligence_index"),
            "total_requests": d.get("total_requests"),
            "error_rate": d.get("error_rate"),
            "last_updated": d.get("fetched_at"),
            "last_benchmarked": d.get("last_benchmarked"),
            "freshness_status": d.get("freshness_status", "sot_materialized"),
            "source": f"sot:{source}",
        }
        out["benchmarks"][full_key] = bm_entry
        out["benchmarks"][alias_key] = bm_entry
        out["models"][full_key] = bm_entry
        out["models"][alias_key] = bm_entry
        # Flat entries (legacy)
        out["entries"].append({
            "model_id": full_key,
            "provider": provider,
            "status": bm_entry["freshness_status"],
            "last_tested": bm_entry["last_benchmarked"],
            "last_updated": bm_entry["last_updated"],
            "quality_baseline_score": bm_entry["quality_baseline_score"],
        })

    out["total_entries"] = len(out["entries"])
    out["total_models"] = len(out["models"])
    out["metadata"]["sot_benchmark_alias_entries"] = len(out["benchmarks"])

    if dry_run:
        return {
            "status": "preview",
            "benchmark_entries": len(out["benchmark_entries"]),
            "models": out["total_models"],
        }

    bytes_written = _atomic_write(BENCH_DB_PATH, out)
    return {
        "status": "success",
        "target": BENCH_DB_PATH,
        "benchmark_entries": len(out["benchmark_entries"]),
        "models": out["total_models"],
        "bytes": bytes_written,
    }

# ── Materialize api_key.json (with masked keys) ──────────────────────────────
def materialize_api_key(dry_run: bool = False,
                        include_secrets: bool = False) -> Dict[str, Any]:
    """Build the api_key.json structure from MongoDB.

    The api_key.json file is a flat dictionary of provider names (openai,
    telegram, nvidia, etc.) — NOT just llm providers. This function
    only OVERWRITES the `llm` subkey, leaving all other top-level keys
    (telegram bots, exchange creds, etc.) untouched.

    Default mode: secrets are masked (key_prefix...key_suffix) so the file
    is safe to commit. Use --include-secrets to embed the full key.
    """
    # Load existing api_key.json (preserve non-llm keys)
    if os.path.exists(API_KEY_PATH):
        try:
            with open(API_KEY_PATH) as f:
                out = json.load(f)
        except Exception:
            out = {}
    else:
        out = {}
    if not isinstance(out, dict):
        out = {}

    out.setdefault("llm", {})
    # FIX 2026-06-19 (audit H3): catalog fields (url/free_tier/description/env_var) live
    # in providers (Tier-2); Tier-1 llm_providers only carries credentials + per-key
    # status. Accumulate keys per provider so multi-account creds (nvidia x3,
    # openrouter x2) are not collapsed to a single key.
    prov_idx = {d.get("provider"): d for d in providers_coll().find({})}
    updated = 0
    for d in llm_providers_coll().find({}):
        d = normalize(d)
        provider = d.get("provider")
        if not provider:
            continue
        key = d.get("api_key") or ""
        if not include_secrets and key:
            # Mask: keep first 6 + last 4 chars
            masked = f"{key[:6]}...{key[-4:]}" if len(key) > 12 else f"{key[:3]}***"
        else:
            masked = key
        cat = prov_idx.get(provider, {})
        key_entry = {
            "key": masked,
            "account": d.get("account_email", "owner"),
            "status": d.get("key_status", "UNVERIFIED"),
        }
        if d.get("key_purpose"):
            key_entry["purpose"] = d["key_purpose"]
        block = out["llm"].get(provider)
        if not isinstance(block, dict) or block.get("_sot_source") != "credentials.llm_providers+providers":
            existing = block if isinstance(block, dict) else {}
            block = {
                "category": cat.get("category", existing.get("category", "LLM")),
                "description": cat.get("description", existing.get("description", d.get("description", ""))),
                "env_var": cat.get("env_var", d.get("env_var", provider)),
                "keys": [],
                "url": cat.get("base_url", existing.get("url")),
                "url_endpoint": existing.get("url_endpoint", cat.get("base_url")),
                "free_bypass": bool(cat.get("free_bypass", False)),
                "_sot_source": "credentials.llm_providers+providers",
            }
            out["llm"][provider] = block
        block["keys"].append(key_entry)
        updated += 1

    # Update _meta
    if "_meta" not in out or not isinstance(out["_meta"], dict):
        out["_meta"] = {}
    out["_meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    out["_meta"]["sot_synchronized_at"] = datetime.now(timezone.utc).isoformat()
    out["_meta"]["sot_llm_providers"] = updated

    if dry_run:
        return {"status": "preview", "providers": updated}

    bytes_written = _atomic_write(API_KEY_PATH, out)
    return {
        "status": "success",
        "target": API_KEY_PATH,
        "providers": updated,
        "secrets_included": include_secrets,
        "bytes": bytes_written,
    }

# ── Verify cache is fresh ────────────────────────────────────────────────────
def verify_cache() -> Dict[str, Any]:
    """Check that on-disk cache files exist and look reasonable."""
    out = {}
    for path in (MASTER_PATH, BENCH_DB_PATH, API_KEY_PATH):
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).isoformat() if exists else None
        out[path] = {"exists": exists, "size": size, "mtime": mtime}
    return out

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["master", "benchmarks", "api_key", "all"],
                        default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--include-secrets", action="store_true",
                        help="api_key.json: embed full api_key values (default: masked)")
    args = parser.parse_args()

    ensure_indexes(force=True)

    if args.verify:
        import json as _j
        print(_j.dumps(verify_cache(), indent=2))
        return

    print("=== SOT Materializer ===")
    print(f"  target: {args.target}")
    print(f"  dry_run: {args.dry_run}")
    print(f"  include_secrets: {args.include_secrets}")

    # Acquire job lock
    job_id = f"mat-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    job = sot_ops.acquire_job_lock(
        job_id=job_id, job_type="materialize", actor="sot_materialize",
        idempotency_key=f"mat:{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
    )
    if job is None:
        print(f"[JOB] Another materialization is running. Skipping.")
        return

    try:
        results = {}
        if args.target in ("master", "all"):
            print("\n[1/3] Materializing PROVIDER_INTELLIGENCE_MASTER.json...")
            r = materialize_master(dry_run=args.dry_run)
            results["master"] = r
            print(f"  → {r}")
        if args.target in ("benchmarks", "all"):
            print("\n[2/3] Materializing benchmark_database.json...")
            r = materialize_benchmarks(dry_run=args.dry_run)
            results["benchmarks"] = r
            print(f"  → {r}")
        if args.target in ("api_key", "all"):
            print("\n[3/3] Materializing api_key.json...")
            r = materialize_api_key(dry_run=args.dry_run, include_secrets=args.include_secrets)
            results["api_key"] = r
            print(f"  → {r}")

        # Audit trail
        eid = generate_evidence_id(code="MAT")
        write_audit(
            provider="*", model_id="*",
            event_type="materialize_run", actor="sot_materialize",
            source_collection="models",
            delta=results, evidence_id=eid,
            notes=f"SOT → disk materialization (target={args.target}, dry_run={args.dry_run})"
        )
        sot_ops.finish_job(job_id, "success", result=results)
        print(f"\n[DONE] evidence_id={eid}")
    except Exception as e:
        sot_ops.finish_job(job_id, "error", error=str(e)[:500])
        print(f"\n[ERROR] {e}")
        raise

if __name__ == "__main__":
    main()
