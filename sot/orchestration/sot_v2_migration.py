#!/usr/bin/env python3
"""
sot_v2_migration.py — ILMA SOT v2.0 Master Rule Migration
=========================================================

Implements MASTER RULE v2.0:
- MongoDB as single source of truth (no JSON runtime dependency)
- Collection hierarchy: llm_providers → providers → models →
  model_enrichment → model_benchmark → model_alias → model_capabilities
- (provider, model_id) as identity
- normalized_model only for analysis (not replacement)
- Provider format preserved (no canonical rename)
- Ollama cloud-only (no local)
- is_sot_for flags on every collection

This migration is IDEMPOTENT — safe to re-run.
"""
import sys
from datetime import datetime, timezone
from orchestration.sot_ops import (
    get_db, get_client, models_coll, benchmarks_coll, intelligence_coll,
    llm_providers_coll, providers_coll, audit_coll, jobs_coll
)

# ── v2.0 metadata ────────────────────────────────────────────────────────────
SOT_META = {
    "version": "2.0",
    "supersedes": "1.x (JSON-driven flow)",
    "sot_engine": "mongodb",
    "json_runtime_enabled": False,
    "json_runtime_use": "import_initial, backup, export, recovery",
    "provider_source": "llm_providers",
    "provider_generation": "automatic",
    "model_identity": "provider+model_id",
    "model_normalization_enabled": True,
    "model_enrichment_scope": "normalized_model",
    "model_storage_scope": "provider_model",
    "provider_format_preserved": True,
    "ollama_mode": "cloud_only",
    "ollama_local_enabled": False,
    "provider_separation": True,
    "master_rule_version": "2.0",
    "updated_at": datetime.now(timezone.utc).isoformat(),
}

# ── Collections needed by v2.0 hierarchy ─────────────────────────────────────
REQUIRED_COLLECTIONS = {
    "llm_providers": {
        "description": "Source credential + endpoint discovery",
        "stores": ["provider", "api_key", "endpoint", "auth", "account_status"],
        "is_sot_for": ["credentials", "endpoints", "provider_discovery"],
        "model_identity_rule": None,
        "provider_generation_rule": "source_of_truth",
    },
    "providers": {
        "description": "Generated from llm_providers",
        "stores": ["provider_metadata", "endpoint_schema", "docs", "auth_format", "category"],
        "is_sot_for": ["provider_registry", "model_registry", "endpoint_dispatch"],
        "model_identity_rule": None,
        "provider_generation_rule": "automatic_from_llm_providers",
    },
    "models": {
        "description": "Generated from providers after model discovery",
        "stores": ["model_id", "provider", "normalized_model", "capability", "original_model_id"],
        "is_sot_for": ["model_registry", "routing", "enrichment_index"],
        "model_identity_rule": "(provider, model_id) unique",
        "provider_generation_rule": "automatic_from_providers",
    },
    "model_enrichment": {
        "description": "Per-model enrichment metadata (capabilities from API docs)",
        "stores": ["context_window", "modality", "supports_tools", "supports_vision",
                   "is_reasoning", "is_code", "tier", "enrichment_source"],
        "is_sot_for": ["enrichment", "capability_lookup"],
        "model_identity_rule": "(provider, model_id) FK → models",
        "provider_generation_rule": "automatic_from_model_discovery",
    },
    "model_benchmark": {
        "description": "Performance/quality benchmark records",
        "stores": ["benchmark_id", "model_id", "provider", "score", "latency_ms",
                   "tokens_per_sec", "samples", "benchmark_type", "captured_at"],
        "is_sot_for": ["routing_score", "tier_assignment", "quality_gates"],
        "model_identity_rule": "(provider, model_id) FK → models",
        "provider_generation_rule": "automatic_from_benchmark_runs",
    },
    "model_alias": {
        "description": "Alias mapping for cross-provider name collisions",
        "stores": ["alias", "canonical_provider", "canonical_model_id", "alias_source"],
        "is_sot_for": ["alias_resolution", "dedup_queries"],
        "model_identity_rule": "alias unique",
        "provider_generation_rule": "automatic_from_normalization",
    },
    "model_capabilities": {
        "description": "Per-model capability map (subset of model_enrichment but denormalized for fast lookup)",
        "stores": ["provider", "model_id", "capabilities", "categories", "updated_at"],
        "is_sot_for": ["capability_routing", "model_selection"],
        "model_identity_rule": "(provider, model_id) FK → models",
        "provider_generation_rule": "automatic_from_enrichment",
    },
    "model_stats": {
        "description": "Aggregated model usage statistics",
        "stores": ["provider", "model_id", "call_count", "success_count",
                   "error_count", "avg_latency_ms", "last_used"],
        "is_sot_for": ["usage_analytics", "health_scoring"],
        "model_identity_rule": "(provider, model_id) FK → models",
        "provider_generation_rule": "automatic_from_runtime",
    },
}


def ensure_collections(db):
    """Create required v2.0 collections with metadata and indexes."""
    existing = set(db.list_collection_names())
    created = []
    for coll_name, meta in REQUIRED_COLLECTIONS.items():
        if coll_name in existing:
            continue
        db.create_collection(coll_name)
        # Write metadata
        db["_meta_v2_collections"].update_one(
            {"name": coll_name},
            {"$set": {"name": coll_name, **meta,
                      "created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        created.append(coll_name)
    return created


def ensure_indexes(db):
    """Create v2.0 indexes for all collections."""
    created = []

    # models: (provider, model_id) unique
    try:
        db["models"].create_index([("provider", 1), ("model_id", 1)], unique=True, name="prov_model_unique")
        created.append("models: prov_model_unique")
    except Exception as e:
        pass
    try:
        db["models"].create_index([("normalized_model", 1)], name="normalized_lookup")
        created.append("models: normalized_lookup")
    except Exception:
        pass
    try:
        db["models"].create_index([("is_active", 1)], name="active_filter")
        created.append("models: active_filter")
    except Exception:
        pass

    # model_enrichment: (provider, model_id)
    db["model_enrichment"].create_index([("provider", 1), ("model_id", 1)], unique=True, name="enrich_unique")
    created.append("model_enrichment: enrich_unique")

    # model_benchmark: (provider, model_id, benchmark_type)
    db["model_benchmark"].create_index([("provider", 1), ("model_id", 1), ("benchmark_type", 1)],
                                        name="bench_lookup")
    created.append("model_benchmark: bench_lookup")

    # model_alias: alias unique
    db["model_alias"].create_index([("alias", 1)], unique=True, name="alias_unique")
    created.append("model_alias: alias_unique")

    # model_capabilities: (provider, model_id)
    db["model_capabilities"].create_index([("provider", 1), ("model_id", 1)], unique=True, name="cap_unique")
    created.append("model_capabilities: cap_unique")

    # model_stats: (provider, model_id)
    db["model_stats"].create_index([("provider", 1), ("model_id", 1)], unique=True, name="stats_unique")
    created.append("model_stats: stats_unique")

    return created


def write_master_metadata(db):
    """Write v2.0 master metadata to _meta."""
    db["_meta"].update_one(
        {"_id": "sot_master"},
        {"$set": SOT_META},
        upsert=True
    )
    return SOT_META


def migrate_existing_to_v2(db):
    """Migrate existing data to v2.0 structure."""
    migrated = {}

    # 1. Rename model_intelligence → model_enrichment (if needed)
    #    Keep both, but write to model_enrichment if it doesn't exist
    intel_count = db["model_intelligence"].count_documents({})
    enrich_count = db["model_enrichment"].count_documents({})

    if enrich_count == 0 and intel_count > 0:
        # Copy intelligence to enrichment
        for doc in db["model_intelligence"].find({}):
            doc.pop("_id", None)
            doc["enrichment_source"] = doc.get("source", "model_intelligence_migration")
            try:
                db["model_enrichment"].insert_one(doc)
            except Exception:
                pass
        migrated["model_intelligence_to_enrichment"] = db["model_enrichment"].count_documents({})

    # 2. Rename model_benchmarks → model_benchmark
    bench_count = db["model_benchmarks"].count_documents({})
    bench_v2_count = db["model_benchmark"].count_documents({})
    if bench_v2_count == 0 and bench_count > 0:
        for doc in db["model_benchmarks"].find({}):
            doc.pop("_id", None)
            doc["benchmark_id"] = f"BM-{doc.get('provider', 'unk')}-{doc.get('model_id', 'unk')}-{doc.get('captured_at', 'unknown')}"
            try:
                db["model_benchmark"].insert_one(doc)
            except Exception:
                pass
        migrated["model_benchmarks_to_model_benchmark"] = db["model_benchmark"].count_documents({})

    # 3. Build model_alias from model_id variants in models
    alias_added = 0
    seen_aliases = set()
    for doc in db["models"].find({}, {"model_id": 1, "normalized_model": 1, "provider": 1}):
        mid = doc.get("model_id", "")
        norm = doc.get("normalized_model", "")
        prov = doc.get("provider", "")
        if norm and norm != mid and (prov, norm) not in seen_aliases:
            try:
                db["model_alias"].update_one(
                    {"alias": f"{prov}/{norm}"},
                    {"$set": {
                        "alias": f"{prov}/{norm}",
                        "canonical_provider": prov,
                        "canonical_model_id": mid,
                        "alias_source": "normalized_model",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True
                )
                seen_aliases.add((prov, norm))
                alias_added += 1
            except Exception:
                pass
    migrated["model_alias_added"] = alias_added

    # 4. Build model_capabilities from model_enrichment
    cap_added = 0
    for doc in db["model_enrichment"].find({}):
        prov = doc.get("provider", "")
        mid = doc.get("model_id", "")
        if not prov or not mid:
            continue
        caps = doc.get("capabilities", [])
        if isinstance(caps, str):
            caps = [c.strip() for c in caps.split(",") if c.strip()]
        try:
            db["model_capabilities"].update_one(
                {"provider": prov, "model_id": mid},
                {"$set": {
                    "provider": prov,
                    "model_id": mid,
                    "capabilities": caps,
                    "categories": doc.get("categories", []),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True
            )
            cap_added += 1
        except Exception:
            pass
    migrated["model_capabilities_added"] = cap_added

    # 5. Ensure ollama_cloud exists, mark ollama_local disabled
    ollama_provs = list(db["providers"].find({"name": {"$regex": "ollama", "$options": "i"}}))
    for p in ollama_provs:
        pname = p.get("name", "")
        if "local" in pname.lower():
            db["providers"].update_one(
                {"_id": p["_id"]},
                {"$set": {
                    "is_active": False,
                    "disabled_reason": "ollama_local_disabled_per_master_rule_v2",
                    "ollama_mode": "local_disabled",
                }}
            )
        elif "cloud" in pname.lower():
            db["providers"].update_one(
                {"_id": p["_id"]},
                {"$set": {
                    "is_active": True,
                    "ollama_mode": "cloud_only",
                }}
            )

    return migrated


def verify_v2_compliance(db):
    """Verify SOT v2.0 compliance."""
    results = {}

    # All required collections present
    existing = set(db.list_collection_names())
    missing = [c for c in REQUIRED_COLLECTIONS if c not in existing]
    results["missing_collections"] = missing

    # models: (provider, model_id) unique
    models_total = db["models"].count_documents({})
    distinct_keys = len(list(db["models"].aggregate([
        {"$group": {"_id": {"provider": "$provider", "model_id": "$model_id"}}}
    ])))
    results["models_total"] = models_total
    results["models_unique_keys"] = distinct_keys
    results["models_identity_violation"] = models_total - distinct_keys

    # Enrichment completeness
    enrich_total = db["model_enrichment"].count_documents({})
    results["enrichment_total"] = enrich_total
    results["enrichment_coverage_pct"] = round(100.0 * enrich_total / models_total, 2) if models_total else 0

    # Capabilities completeness
    cap_total = db["model_capabilities"].count_documents({})
    results["capabilities_total"] = cap_total

    # Aliases
    alias_total = db["model_alias"].count_documents({})
    results["aliases_total"] = alias_total

    # Benchmark
    bench_total = db["model_benchmark"].count_documents({})
    results["benchmark_total"] = bench_total

    # Providers + llm_providers
    llm_provs = db["llm_providers"].count_documents({})
    provs = db["providers"].count_documents({})
    results["llm_providers"] = llm_provs
    results["providers"] = provs

    # Ollama check
    ollama_local = db["providers"].count_documents({"name": {"$regex": "ollama_local", "$options": "i"},
                                                     "is_active": True})
    results["ollama_local_active"] = ollama_local  # should be 0

    # Master metadata
    meta = db["_meta"].find_one({"_id": "sot_master"})
    results["master_metadata"] = meta is not None
    results["master_metadata_version"] = meta.get("version") if meta else None
    results["sot_engine"] = meta.get("sot_engine") if meta else None
    results["json_runtime_enabled"] = meta.get("json_runtime_enabled") if meta else None

    # Overall compliance
    is_compliant = (
        len(missing) == 0
        and results["models_identity_violation"] == 0
        and results["ollama_local_active"] == 0
        and results["sot_engine"] == "mongodb"
        and results["json_runtime_enabled"] is False
    )
    results["v2_0_compliant"] = is_compliant

    return results


def main():
    print("=" * 70)
    print("ILMA SOT v2.0 Master Rule Migration")
    print("=" * 70)

    db = get_db()

    # 1. Create collections
    print("\n[1/5] Creating v2.0 collections...")
    created = ensure_collections(db)
    print(f"  Created: {created if created else 'all already exist'}")

    # 2. Indexes
    print("\n[2/5] Creating v2.0 indexes...")
    indexes = ensure_indexes(db)
    print(f"  Created: {len(indexes)} indexes")

    # 3. Master metadata
    print("\n[3/5] Writing master metadata v2.0...")
    meta = write_master_metadata(db)
    print(f"  version={meta['version']}, engine={meta['sot_engine']}")

    # 4. Migrate existing data
    print("\n[4/5] Migrating existing data to v2.0...")
    migrated = migrate_existing_to_v2(db)
    for k, v in migrated.items():
        print(f"  {k}: {v}")

    # 5. Verify
    print("\n[5/5] Verifying v2.0 compliance...")
    verify = verify_v2_compliance(db)
    for k, v in verify.items():
        print(f"  {k}: {v}")

    # Audit
    audit_coll().insert_one({
        "event": "sot_v2_migration",
        "evidence_id": f"ILMA-EVID-{datetime.now(timezone.utc).strftime('%Y%m%d')}-V2MIGR-{int(datetime.now(timezone.utc).timestamp()) % 100000:05d}",
        "provider": "*",
        "model_id": "*",
        "event_type": "sot_migration",
        "actor": "sot_v2_migration",
        "source_collection": "_meta",
        "event_at": datetime.now(timezone.utc),
        "master_rule_version": "2.0",
        "compliance": verify,
        "created_collections": created,
        "migrated_counts": migrated,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    print("\n" + "=" * 70)
    if verify.get("v2_0_compliant"):
        print("✅ SOT v2.0 COMPLIANT — MongoDB is the single source of truth")
    else:
        print("⚠️  SOT v2.0 not fully compliant — see verification above")
    print("=" * 70)

    return verify


if __name__ == "__main__":
    main()
