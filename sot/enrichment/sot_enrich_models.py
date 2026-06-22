#!/usr/bin/env python3
"""
sot_enrich_models.py — unified, models-driven enrichment + scoring writer
=========================================================================
THE missing keystone (audit 2026-06-20): the legacy intelligence writer iterated
MASTER.json, so only ~553/1888 active models were scored and the router got no
usable signal. This writer iterates the `models` collection itself and, for EVERY
active model, produces the runtime SOT for selection:

  model_intelligence  ← composite_score + score_tier + capabilities_detail (router vocab)
  model_capabilities  ← capabilities list + specialization (was None for all)
  model_enrichment    ← provenance + sources

Scoring uses sot_ops.compute_score (AA-weighted when AA benchmark rows exist, else a
capability+usage heuristic). The router consumes `composite_score` (as `score`) and
`capabilities_detail` directly — model_intelligence is the single scoring SOT.

Sources blended per model: model_benchmark (AA `artificial_analysis` + `passive`
usage), the models row (context_window, price, is_free), and model_id pattern
classification. OpenRouter/official pricing already lands in `models`.

CLI:
  python3 sot_enrich_models.py --full           # (re)score ALL active models
  python3 sot_enrich_models.py --only-missing   # only models lacking intelligence
  python3 sot_enrich_models.py --provider groq  # one provider
  python3 sot_enrich_models.py --dry-run
  python3 sot_enrich_models.py --stats
"""
from __future__ import annotations
import os, re, sys, json, time, argparse, logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pymongo

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "orchestration"))
import sot_ops  # compute_score, infer_capabilities, infer_specialization  # noqa: E402

logger = logging.getLogger("ilma.sot.enrich")

MONGO = dict(host="172.16.103.253", port=27017, username="quantumtraffic",
             password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")), authSource="admin", directConnection=True,
             serverSelectionTimeoutMS=10000)
ENRICH_VERSION = "models-driven-v1"

# Router capability vocabulary (must match TASK_CAPABILITY_HINTS in ilma_model_router.py)
ROUTER_CAPS = ["coding", "reasoning", "vision", "audio", "video", "multimodal",
               "instruction_following", "structured_output", "long_context", "speed",
               "cost_efficiency", "research", "backend", "debugging", "test_generation",
               "code_review", "security_review"]

# video-generation/understanding model id patterns (sot_ops has no video capability)
_VIDEO_PAT = re.compile(
    r"(video|sora|veo|kling|runway|wan-?\d|cogvideo|mochi|hunyuan-?video|"
    r"ltx|seedance|dreamina|pika|luma|ray-?\d|minimax-?video)")


def get_db():
    return pymongo.MongoClient(**MONGO)["credentials"]


def now_utc():
    return datetime.now(timezone.utc)


# ── benchmark signal lookup (AA + passive) ─────────────────────────────────────
def _load_benchmarks(db) -> Dict[tuple, Dict[str, Any]]:
    """Index benchmark signals by (provider, model_id): AA indices + passive usage."""
    idx: Dict[tuple, Dict[str, Any]] = {}
    for b in db.model_benchmark.find({}):
        key = (b.get("provider"), b.get("model_id"))
        rec = idx.setdefault(key, {})
        src = b.get("benchmark_source")
        if src == "artificial_analysis":
            # AA index fields (per enricher): aa_intelligence_index/aa_coding_index/aa_math_index
            rec["benchmark_aa"] = {
                "ai_index": b.get("aa_intelligence_index"),
                "coding_index": b.get("aa_coding_index"),
                "math_index": b.get("aa_math_index"),
            }
        elif src in ("passive", "stub_runtime_audit"):
            for f in ("avg_score", "quality_baseline_score"):
                v = b.get(f)
                try:
                    if v is not None and float(v) > 0:
                        rec.setdefault("benchmark_score", float(v))
                except (TypeError, ValueError):
                    pass
            er = b.get("error_rate")
            try:
                if er is not None:
                    rec["error_rate"] = float(er)
            except (TypeError, ValueError):
                pass
    return idx


# ── capability confidence (router vocabulary) ──────────────────────────────────
def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def capabilities_detail(model_id: str, caps: List[str], aa: Dict[str, Any],
                        ctx_window: Optional[int], is_free: bool) -> Dict[str, float]:
    """Per-capability confidence 0..1 keyed by the router's TASK_CAPABILITY_HINTS vocab."""
    cset = set(caps)                                  # from sot_ops.infer_capabilities
    aa_code = _f((aa or {}).get("coding_index"))
    aa_ai = _f((aa or {}).get("ai_index"))
    ctx = ctx_window or 0

    mid = model_id.lower()
    coding = max(0.9 if "code" in cset else 0.35,
                 (aa_code / 70.0) if aa_code else 0.0)
    reasoning = max(0.9 if "reasoning" in cset else 0.45,
                    (aa_ai / 70.0) if aa_ai else 0.0)
    # vision/audio/video — used by the router's HARD capability filter for niche tasks.
    vision = 0.9 if ("vision" in cset or "image" in cset) else 0.0
    audio = 0.9 if "audio" in cset else 0.0
    video = 0.9 if _VIDEO_PAT.search(mid) else 0.0
    multimodal = 0.75 if (cset & {"vision", "audio", "image"} or video) else 0.1
    speed = 0.9 if "fast" in cset else 0.5
    long_context = (0.95 if ctx >= 131072 else 0.8 if ctx >= 32768
                    else 0.55 if ctx >= 16384 else 0.35)
    d = {
        "coding": round(min(1.0, coding), 3),
        "reasoning": round(min(1.0, reasoning), 3),
        "vision": round(vision, 3),
        "audio": round(audio, 3),
        "video": round(video, 3),
        "multimodal": round(multimodal, 3),
        "instruction_following": 0.8 if (cset & {"instruct"}) else 0.6,
        "structured_output": 0.6,
        "long_context": round(long_context, 3),
        "speed": round(speed, 3),
        "cost_efficiency": 0.95 if is_free else 0.4,
        "research": round(min(1.0, 0.5 * reasoning + 0.5 * long_context), 3),
    }
    # coding-derived sub-skills
    d["backend"] = round(coding * 0.9, 3)
    d["debugging"] = round(coding * 0.85, 3)
    d["test_generation"] = round(coding * 0.8, 3)
    d["code_review"] = round(coding * 0.85, 3)
    d["security_review"] = round(min(1.0, 0.5 * coding + 0.5 * reasoning), 3)
    return d


# ── enrich one model ────────────────────────────────────────────────────────
def enrich_model(db, m: Dict[str, Any], bench: Dict[tuple, Dict[str, Any]],
                 dry_run: bool) -> Dict[str, Any]:
    provider = m.get("provider")
    mid = m.get("model_id")
    if not provider or not mid:
        return {"skipped": "no_key"}

    caps = sot_ops.infer_capabilities(mid)
    spec = sot_ops.infer_specialization(mid)
    bsig = bench.get((provider, mid), {})
    aa = bsig.get("benchmark_aa") or {}
    ctx = m.get("context_window")
    is_free = bool(m.get("is_free"))

    minfo = {
        "capabilities": caps,
        "benchmark_aa": {k: v for k, v in aa.items() if v is not None} or None,
        "benchmark_score": bsig.get("benchmark_score"),
        "error_rate": bsig.get("error_rate"),
    }
    score = sot_ops.compute_score(minfo)
    cap_detail = capabilities_detail(mid, caps, aa, ctx, is_free)

    intel_doc = {
        "provider": provider, "model_id": mid,
        "composite_score": score["score"],
        "score_tier": score["score_tier"],
        "score_source": score["score_source"],
        "score_breakdown": score["score_breakdown"],
        "capabilities": caps,
        "capabilities_detail": cap_detail,
        "specialization": spec,
        "benchmark_aa": minfo["benchmark_aa"] or {},
        "quality_score": bsig.get("benchmark_score", 0.0) or 0.0,
        "cost_score": 1.0 if is_free else 0.4,
        "is_free": is_free,
        "context_window": ctx,
        "is_active": bool(m.get("is_active", True)),
        "status": m.get("status", "active"),
        "enrichment_version": ENRICH_VERSION,
        "enrichment_sources": (["artificial_analysis"] if aa else [])
                              + (["passive"] if bsig.get("benchmark_score") else [])
                              + ["pattern_classifier", "provider_catalog"],
        "provenance": f"sot_enrich_models:{ENRICH_VERSION}:{score['score_source']}",
        "enriched_at": now_utc(),
    }
    if dry_run:
        return {"provider": provider, "model_id": mid, "score": score["score"],
                "tier": score["score_tier"], "spec": spec, "would_write": True}

    db.model_intelligence.update_one(
        {"provider": provider, "model_id": mid}, {"$set": intel_doc}, upsert=True)
    db.model_capabilities.update_one(
        {"provider": provider, "model_id": mid},
        {"$set": {"provider": provider, "model_id": mid, "capabilities": caps,
                  "capabilities_detail": cap_detail, "specialization": spec,
                  "updated_at": now_utc()}}, upsert=True)
    db.model_enrichment.update_one(
        {"provider": provider, "model_id": mid},
        {"$set": {"provider": provider, "model_id": mid,
                  "enrichment_sources": intel_doc["enrichment_sources"],
                  "enrichment_version": ENRICH_VERSION, "enriched_at": now_utc()}},
        upsert=True)
    return {"provider": provider, "model_id": mid, "score": score["score"],
            "tier": score["score_tier"], "spec": spec}


def run(mode: str = "full", provider: Optional[str] = None,
        dry_run: bool = False) -> Dict[str, Any]:
    db = get_db()
    q = {"is_active": True}
    if provider:
        q["provider"] = provider
    if mode == "only-missing":
        have = {(d["provider"], d["model_id"])
                for d in db.model_intelligence.find({}, {"provider": 1, "model_id": 1})}
    bench = _load_benchmarks(db)

    t0 = time.time()
    n, tiers, srcs = 0, {}, {}
    for m in db.models.find(q, {"provider": 1, "model_id": 1, "context_window": 1,
                                "is_free": 1, "is_active": 1, "status": 1}):
        if mode == "only-missing" and (m.get("provider"), m.get("model_id")) in have:
            continue
        r = enrich_model(db, m, bench, dry_run)
        if r.get("skipped"):
            continue
        n += 1
        tiers[r.get("tier")] = tiers.get(r.get("tier"), 0) + 1
    return {"mode": mode, "dry_run": dry_run, "provider": provider,
            "enriched": n, "tier_distribution": tiers,
            "elapsed_s": round(time.time() - t0, 1)}


def stats() -> Dict[str, Any]:
    db = get_db()
    active = db.models.count_documents({"is_active": True})
    intel = db.model_intelligence.count_documents({})
    with_detail = db.model_intelligence.count_documents({"capabilities_detail": {"$exists": True, "$ne": {}}})
    from collections import Counter
    tiers = Counter(d.get("score_tier") for d in db.model_intelligence.find({}, {"score_tier": 1}))
    specs = Counter(d.get("specialization") for d in db.model_capabilities.find({}, {"specialization": 1}))
    return {"active_models": active, "model_intelligence": intel,
            "with_capabilities_detail": with_detail,
            "coverage_pct": round(100.0 * intel / active, 1) if active else 0,
            "tier_distribution": dict(tiers), "specialization": dict(specs)}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--full", action="store_true")
    g.add_argument("--only-missing", action="store_true")
    g.add_argument("--stats", action="store_true")
    ap.add_argument("--provider")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.stats:
        print(json.dumps(stats(), indent=2, default=str)); return
    mode = "only-missing" if args.only_missing else "full"
    print(json.dumps(run(mode=mode, provider=args.provider, dry_run=args.dry_run),
                     indent=2, default=str))


if __name__ == "__main__":
    main()
