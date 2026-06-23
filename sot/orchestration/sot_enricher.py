#!/usr/bin/env python3
"""
sot_enricher.py — SOT Enrichment Engine
==========================================

Reads existing on-disk intelligence artifacts (MASTER.json,
benchmark_database.json, benchmark_aa_cache.json) and writes enriched
data into the SOT MongoDB collections:

  • credentials.model_benchmarks   (per source: passive, aa, heuristic)
  • credentials.model_intelligence (composite scores + metadata)
  • credentials.model_audit_trail  (enrichment_run events)

Idempotent: re-runs overwrite existing docs by (provider, model_id, source).
Safe to run multiple times.

Usage:
    python3 sot_enricher.py              # enrich all
    python3 sot_enricher.py --dry-run    # preview only
    python3 sot_enricher.py --stats      # show collection counts
    python3 sot_enricher.py --audit      # show recent audit_trail events
"""
import os, sys, json, argparse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Add parent dir so we can import sot_ops
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sot_ops
from sot_ops import (
    benchmarks_coll, intelligence_coll, audit_coll, jobs_coll,
    models_coll, ensure_indexes, generate_evidence_id, write_audit,
    compute_score, normalize, _ensure_unique_index,
)

# ── Data source paths ─────────────────────────────────────────────────────────
SOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.dirname(os.path.dirname(SOT_DIR))  # /root/.hermes/profiles/ilma/
ROUTER_DIR = os.path.join(PROFILE_DIR, "ilma_model_router_data")

MASTER_PATH = os.path.join(ROUTER_DIR, "PROVIDER_INTELLIGENCE_MASTER.json")
BENCH_DB_PATH = os.path.join(ROUTER_DIR, "benchmark_database.json")
AA_CACHE_PATH = os.path.join(PROFILE_DIR, "benchmark_aa_cache.json")

# ── Loaders ───────────────────────────────────────────────────────────────────
def _load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)

def _now() -> datetime:
    return datetime.now(timezone.utc)

# ── Passive benchmark writer (from benchmark_database.json) ──────────────────
def write_passive_benchmarks(dry_run: bool = False) -> Dict[str, Any]:
    """Port entries from benchmark_database.json → model_benchmarks (source=passive)."""
    bench = _load_json(BENCH_DB_PATH)
    bm = bench.get("benchmarks", {})
    if not bm:
        return {"status": "warning", "reason": "no_passive_data", "written": 0}
    coll = benchmarks_coll()
    written = 0
    evidence_id = generate_evidence_id(code="ENRICH-BM")
    for key, b in bm.items():
        provider = b.get("provider") or key.split("/", 1)[0]
        model_id = b.get("model_id") or key
        # Skip if no real benchmark data
        if b.get("avg_score") is None and b.get("quality_baseline_score") is None:
            continue
        doc = {
            "provider": provider,
            "model_id": model_id,
            "benchmark_source": "passive",
            "evidence_type": "PASSIVE",
            "fetched_at": _now(),
            "avg_score": b.get("avg_score"),
            "quality_baseline_score": b.get("quality_baseline_score"),
            "total_requests": b.get("total_requests"),
            "error_rate": b.get("error_rate"),
            "freshness_status": b.get("freshness_status"),
            "last_benchmarked": b.get("last_benchmarked"),
            "raw_source": {
                "source": b.get("source"),
                "full_model_id": b.get("full_model_id"),
                "last_updated": b.get("last_updated"),
            },
        }
        if dry_run:
            written += 1
            continue
        try:
            coll.update_one(
                {"provider": provider, "model_id": model_id, "benchmark_source": "passive"},
                {"$set": {**doc, "fetched_at": _now()}},
                upsert=True,
            )
            written += 1
        except Exception as e:
            print(f"  [WARN] passive {provider}/{model_id}: {e}")
    return {"status": "success", "source": "passive", "written": written, "evidence_id": evidence_id}

# ── AA benchmark writer (from benchmark_aa_cache.json) ───────────────────────
def write_aa_benchmarks(dry_run: bool = False) -> Dict[str, Any]:
    """Port entries from benchmark_aa_cache.json → model_benchmarks (source=artificial_analysis)."""
    aa = _load_json(AA_CACHE_PATH)
    records = aa.get("records", [])
    if not records:
        return {"status": "warning", "reason": "no_aa_data", "written": 0}
    coll = benchmarks_coll()
    written = 0
    evidence_id = generate_evidence_id(code="ENRICH-AA")
    for rec in records:
        slug = rec.get("slug")
        if not slug:
            continue
        # AA provider name is human-readable (e.g. "OpenAI") — we need
        # to match to our internal provider name. Use slug only for now;
        # downstream intelligence join will resolve.
        provider = (rec.get("provider") or "").lower()
        # Map common AA providers to internal names
        provider_map = {
            "openai": "openai",
            "anthropic": "anthropic",
            "google": "google",
            "meta": "meta",
            "deepseek": "deepseek",
            "alibaba": "alibaba",
            "qwen": "alibaba",
            "mistral": "mistral",
            "xai": "xai",
            "minimax": "minimax",
        }
        internal_provider = provider_map.get(provider, provider or "unknown")
        doc = {
            "provider": internal_provider,
            "model_id": slug,
            "benchmark_source": "artificial_analysis",
            "evidence_type": "PROXY",
            "fetched_at": _now(),
            "aa_intelligence_index": rec.get("artificial_analysis_intelligence_index"),
            "aa_coding_index": rec.get("artificial_analysis_coding_index"),
            "aa_math_index": rec.get("artificial_analysis_math_index"),
            "mmlu_pro": rec.get("mmlu_pro"),
            "gpqa": rec.get("gpqa"),
            "livecodebench": rec.get("livecodebench"),
            "raw_source": {
                "name": rec.get("name"),
                "aa_provider": rec.get("provider"),
                "release_date": rec.get("release_date"),
                "fetched_at": rec.get("fetched_at"),
            },
        }
        if dry_run:
            written += 1
            continue
        try:
            coll.update_one(
                {"provider": internal_provider, "model_id": slug, "benchmark_source": "artificial_analysis"},
                {"$set": {**doc, "fetched_at": _now()}},
                upsert=True,
            )
            written += 1
        except Exception as e:
            print(f"  [WARN] aa {internal_provider}/{slug}: {e}")
    return {"status": "success", "source": "artificial_analysis", "written": written, "evidence_id": evidence_id}

# ── Model intelligence writer (from MASTER.json) ─────────────────────────────
def write_intelligence(dry_run: bool = False) -> Dict[str, Any]:
    """Port composite score + metadata from MASTER.json → model_intelligence.

    Each model in MASTER becomes one model_intelligence doc.
    """
    master = _load_json(MASTER_PATH)
    providers = master.get("providers", {})
    if not providers:
        return {"status": "error", "reason": "no_master_data", "written": 0}
    coll = intelligence_coll()
    written = 0
    evidence_id = generate_evidence_id(code="ENRICH-INTEL")
    for pname, pdata in providers.items():
        models = pdata.get("models", {})
        for mid, m in models.items():
            # Skip entries that have no usable info
            if not isinstance(m, dict):
                continue
            # Construct intelligence doc
            caps = m.get("capabilities") or m.get("specializations") or sot_ops.infer_capabilities(mid)
            specs = m.get("specializations") or m.get("specialization") or sot_ops.infer_specialization(mid)
            if isinstance(specs, str):
                specs = [specs]
            doc = {
                "provider": pname,
                "model_id": mid,
                "quality_score": _safe_float(m.get("score"), 0.0, 100.0) / 100.0 if m.get("score") is not None else None,
                "composite_score": _safe_float(m.get("score"), 0.0, 100.0) / 100.0 if m.get("score") is not None else None,
                "score_tier": m.get("score_tier"),
                "capabilities": caps,
                "specialization": specs[0] if specs else "general",
                "recommended_use_cases": m.get("recommended_use_cases", []),
                "enrichment_version": "1.0.0",
                "enriched_at": _now(),
                "enrichment_sources": m.get("enrichment_sources", ["master_json"]),
                "provenance": f"master_json:{master.get('_enricher_version','unknown')}",
                "pricing": _build_pricing(m),
                "context_window": m.get("context_window"),
                "is_free": bool(m.get("is_free")),  # single canonical field (free_tier/billing dropped)
                "trust_score": _safe_float(m.get("trust_score"), 0.0, 1.0),
                "benchmarks": {
                    "score": m.get("score"),
                    "score_breakdown": m.get("score_breakdown"),
                    "benchmark_aa": m.get("benchmark_aa"),
                    "benchmark_score": m.get("benchmark_score"),
                    "error_rate": m.get("error_rate"),
                    "total_requests": m.get("total_requests"),
                },
                "model_status": {
                    "status": m.get("status"),
                    "is_active": m.get("is_active"),
                    "disabled": m.get("disabled"),
                    "disabled_reason": m.get("disabled_reason"),
                    "user_allowed": m.get("user_allowed"),
                    "admin_override": m.get("admin_override"),
                },
                "last_verified": m.get("last_verified"),
                "description": m.get("description"),
            }
            if dry_run:
                written += 1
                continue
            try:
                coll.update_one(
                    {"provider": pname, "model_id": mid},
                    {"$set": {**doc, "enriched_at": _now()}},
                    upsert=True,
                )
                # Also propagate capabilities/specialization to models collection
                # to keep them in sync (avoids POT-CAP-DRIFT)
                try:
                    models_coll().update_one(
                        {"provider": pname, "model_id": mid},
                        {"$set": {
                            "capabilities": caps,
                            "specialization": specs[0] if specs else "general",
                            "_sot_synced_from_intel": _now(),
                        }}
                    )
                except Exception:
                    pass
                written += 1
            except Exception as e:
                print(f"  [WARN] intel {pname}/{mid}: {e}")
    return {"status": "success", "source": "master_json", "written": written, "evidence_id": evidence_id}


def _safe_float(v, lo=None, hi=None) -> Optional[float]:
    try:
        f = float(v)
        if lo is not None: f = max(lo, f)
        if hi is not None: f = min(hi, f)
        return f
    except (TypeError, ValueError):
        return None

def _build_pricing(m: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    pi = m.get("price_per_m_input")
    po = m.get("price_per_m_output")
    if pi is not None:
        out["input_per_m"] = _safe_float(pi, 0.0)
    if po is not None:
        out["output_per_m"] = _safe_float(po, 0.0)
    if not out:
        # Try nested pricing object
        nested = m.get("pricing") or {}
        if isinstance(nested, dict):
            if nested.get("prompt") is not None:
                out["input_per_m"] = _safe_float(nested.get("prompt"), 0.0)
            if nested.get("completion") is not None:
                out["output_per_m"] = _safe_float(nested.get("completion"), 0.0)
    if out:
        out["currency"] = "USD"
    return out


# ── Main orchestration ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()

    ensure_indexes(force=True)

    if args.stats:
        print("=== SOT collection stats ===")
        for label, coll in [
            ("models", models_coll()),
            ("model_benchmarks", benchmarks_coll()),
            ("model_intelligence", intelligence_coll()),
            ("model_audit_trail", audit_coll()),
            ("sot_jobs", jobs_coll()),
        ]:
            print(f"  {label}: {coll.count_documents({})} docs")
        # Per-source breakdown
        print("\n  benchmarks by source:")
        for s in benchmarks_coll().aggregate([{"$group": {"_id": "$benchmark_source", "count": {"$sum": 1}}}]):
            print(f"    {s['_id']}: {s['count']}")
        print("  intelligence by tier:")
        for s in intelligence_coll().aggregate([{"$group": {"_id": "$score_tier", "count": {"$sum": 1}}}]):
            print(f"    {s['_id']}: {s['count']}")
        return

    if args.audit:
        print("=== Recent model_audit_trail events ===")
        for d in audit_coll().find().sort("event_at", -1).limit(20):
            print(f"  [{d.get('event_at')}] {d.get('event_type')} | {d.get('provider')}/{d.get('model_id')} | actor={d.get('actor')} | eid={d.get('evidence_id')}")
        return

    print("=== SOT Enricher starting ===")
    print(f"  MASTER: {MASTER_PATH} ({os.path.getsize(MASTER_PATH) if os.path.exists(MASTER_PATH) else 0} bytes)")
    print(f"  BENCH_DB: {BENCH_DB_PATH} ({os.path.getsize(BENCH_DB_PATH) if os.path.exists(BENCH_DB_PATH) else 0} bytes)")
    print(f"  AA_CACHE: {AA_CACHE_PATH} ({os.path.getsize(AA_CACHE_PATH) if os.path.exists(AA_CACHE_PATH) else 0} bytes)")
    print(f"  dry_run: {args.dry_run}")

    # Acquire job lock
    job_id = f"enrich-{_now().strftime('%Y%m%d-%H%M%S')}"
    job = sot_ops.acquire_job_lock(
        job_id=job_id, job_type="enrichment", actor="sot_enricher",
        idempotency_key=f"enrich:{_now().strftime('%Y%m%d-%H')}"
    )
    if job is None:
        print(f"[JOB] Another enrich job is running (idempotency_key hit). Skipping.")
        return

    try:
        results = {}
        # 1) Passive benchmarks
        print("\n[1/3] Writing passive benchmarks...")
        r1 = write_passive_benchmarks(dry_run=args.dry_run)
        results["passive"] = r1
        print(f"  → {r1}")

        # 2) AA benchmarks
        print("\n[2/3] Writing AA benchmarks...")
        r2 = write_aa_benchmarks(dry_run=args.dry_run)
        results["aa"] = r2
        print(f"  → {r2}")

        # 3) Model intelligence
        print("\n[3/3] Writing model intelligence...")
        r3 = write_intelligence(dry_run=args.dry_run)
        results["intelligence"] = r3
        print(f"  → {r3}")

        # Write audit trail (one event per source)
        eid = generate_evidence_id(code="ENRICH")
        write_audit(
            provider="*", model_id="*",
            event_type="enrichment_run", actor="sot_enricher",
            source_collection="model_intelligence",
            delta=results, evidence_id=eid,
            notes=f"Full SOT enrichment cycle (dry_run={args.dry_run})"
        )

        # Finish job
        sot_ops.finish_job(job_id, "success", result=results)
        print(f"\n[DONE] evidence_id={eid}")

    except Exception as e:
        sot_ops.finish_job(job_id, "error", error=str(e)[:500])
        print(f"\n[ERROR] {e}")
        raise

if __name__ == "__main__":
    main()
