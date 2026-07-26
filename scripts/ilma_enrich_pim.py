#!/usr/bin/env python3
"""
ILMA Model Intelligence Enricher v1.0
======================================
Enrich PROVIDER_INTELLIGENCE_MASTER.json dengan:
1. Benchmark data dari benchmark_database.json
2. Synthetic scores dari quality_score (untuk model kosong)
3. Capabilities inference dari provider/model metadata

Run: python3 scripts/ilma_enrich_pim.py
Author: ILMA Core Team
"""
import json
import logging
import re
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger("ILMA.Enricher")

ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
PIM_PATH = ILMA_PROFILE / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"
BM_PATH  = ILMA_PROFILE / "ilma_model_router_data" / "benchmark_database.json"
BACKUP_PATH = ILMA_PROFILE / "ilma_model_router_data" / f"PROVIDER_INTELLIGENCE_MASTER.backup_enrich.json"

# ─────────────────────────────────────────────────────────────────────────────
# BENCHMARK PROFILE TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────

def make_benchmark_profile(entry: dict, source: str = "benchmark_database") -> dict:
    """Build benchmark_profile dict from a benchmark entry."""
    qs = entry.get("quality_score", 0)
    rs = entry.get("reasoning_score", qs)
    cs = entry.get("coding_score", qs)
    ms = entry.get("math_score", rs)
    vs = entry.get("vision_score", 0)

    return {
        "benchmark_available": True,
        "source": source,
        "quality_score": qs,
        "coding_score": cs,
        "reasoning_score": rs,
        "math_score": ms,
        "vision_score": vs,
        "overall_score": qs,  # primary key for routing
        "confidence": 0.9,    # high confidence for real benchmarks
        "last_benchmark_seen": entry.get("test_timestamp", datetime.utcnow().isoformat()),
        "evidence": f"benchmark_entry:{entry.get('model_id', '')}",
    }

def make_synthetic_profile(quality_score: float, provider: str, model_id: str) -> dict:
    """Build synthetic benchmark_profile for models without real benchmark data."""
    if quality_score <= 0:
        quality_score = 0.5  # minimum baseline

    # Provider quality tiers (empirical)
    provider_tiers = {
        "nvidia":      (0.80, 0.85, 0.80),  # (base, reasoning, coding)
        "openrouter":  (0.75, 0.80, 0.78),
        "deepseek":    (0.78, 0.85, 0.82),
        "google":      (0.75, 0.80, 0.70),
        "meta":        (0.72, 0.75, 0.78),
        "mistral":     (0.72, 0.78, 0.74),
        "openai":      (0.80, 0.82, 0.78),
        "anthropic":   (0.82, 0.85, 0.72),
        "minimax":     (0.72, 0.78, 0.72),
        "alibaba":     (0.70, 0.75, 0.74),
        "xai":         (0.72, 0.78, 0.70),
        "amazon":      (0.68, 0.70, 0.68),
        "cohere":      (0.68, 0.70, 0.65),
        "ai21-labs":   (0.70, 0.72, 0.68),
        "microsoft-azure": (0.70, 0.72, 0.70),
        "useai":       (0.68, 0.70, 0.65),
        "blackbox":    (0.65, 0.68, 0.65),
        "ollama":      (0.60, 0.62, 0.60),
        "perplexity":  (0.65, 0.68, 0.62),
    }

    tier = provider_tiers.get(provider, (0.65, 0.68, 0.65))
    base, reasoning, coding = tier

    # Scale by quality_score if provided
    if quality_score > 0.5:
        # Adjust tier based on quality_score
        scale = quality_score / 0.75  # normalize around 0.75
        base = min(0.95, base * scale)
        reasoning = min(0.95, reasoning * scale)
        coding = min(0.95, coding * scale)
    else:
        base, reasoning, coding = tier

    # Model-specific heuristics
    model_lower = model_id.lower()
    if any(kw in model_lower for kw in ["reasoning", "think", "chain"]):
        reasoning = max(reasoning, 0.80)
    if any(kw in model_lower for kw in ["vision", "vl-", "multimodal"]):
        # Vision models
        pass  # keep defaults
    if any(kw in model_lower for kw in ["mini", "nano", "small", "lite"]):
        base *= 0.85
        reasoning *= 0.85
        coding *= 0.85
    if any(kw in model_lower for kw in ["large", "ultra", "mega", "72b", "405b", "671b"]):
        base = min(0.95, base * 1.10)
        reasoning = min(0.95, reasoning * 1.10)
        coding = min(0.95, coding * 1.10)

    return {
        "benchmark_available": True,
        "source": "synthetic_from_quality",
        "quality_score": round(base, 3),
        "coding_score": round(coding, 3),
        "reasoning_score": round(reasoning, 3),
        "math_score": round(reasoning * 0.9, 3),
        "vision_score": 0.0,
        "overall_score": round(base, 3),
        "confidence": 0.5,  # synthetic = lower confidence
        "last_benchmark_seen": datetime.utcnow().isoformat() + "Z",
        "evidence": f"synthetic:provider={provider},q={quality_score}",
    }

# ─────────────────────────────────────────────────────────────────────────────
# CAPABILITIES INFERENCE
# ─────────────────────────────────────────────────────────────────────────────

def make_capabilities(model_id: str, benchmark_profile: dict) -> dict:
    """Infer capabilities_detail from model name + benchmark scores."""
    model_lower = model_id.lower()
    overall = benchmark_profile.get("overall_score", 0.5)
    reasoning = benchmark_profile.get("reasoning_score", overall)
    coding = benchmark_profile.get("coding_score", overall)

    cap = {
        "reasoning": round(reasoning, 3),
        "coding": round(coding, 3),
        "backend": round(coding * 0.9, 3),
        "frontend": round(coding * 0.7, 3),
        "debugging": round(coding * 0.85, 3),
        "instruction_following": round(min(1.0, overall * 1.1), 3),
        "structured_output": round(overall * 0.9, 3),
        "research": round(reasoning * 0.85, 3),
        "long_context": 0.7,
        "vision": benchmark_profile.get("vision_score", 0.0),
        "speed": 0.7,
        "cost_efficiency": 0.8,
        "security_review": round(reasoning * 0.6, 3),
    }

    # Model-type overrides
    if any(kw in model_lower for kw in ["coder", "code", "coding", "dev"]):
        cap["coding"] = round(min(1.0, coding * 1.1), 3)
        cap["backend"] = round(min(1.0, coding * 1.05), 3)

    if any(kw in model_lower for kw in ["mini", "nano", "small", "lite"]):
        cap["speed"] = 0.9
        cap["cost_efficiency"] = 0.95
        cap["coding"] *= 0.85
        cap["reasoning"] *= 0.85

    if any(kw in model_lower for kw in ["reasoning", "think", "chain", "o1", "o3", "o4"]):
        cap["reasoning"] = round(min(1.0, reasoning * 1.15), 3)
        cap["structured_output"] = round(min(1.0, cap["structured_output"] * 1.1), 3)

    if any(kw in model_lower for kw in ["vision", "vl-", "-vl-", "multimodal", "GPT-4V", "gpt-4v"]):
        cap["vision"] = max(cap["vision"], 0.75)
        cap["multimodal"] = 0.8

    if any(kw in model_lower for kw in ["flash", "fast", "quick", "speed"]):
        cap["speed"] = 0.95
        cap["cost_efficiency"] = 0.95

    return cap

# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENRICHMENT
# ─────────────────────────────────────────────────────────────────────────────

def load_benchmark_db() -> dict:
    """Load benchmark entries into lookup dict: model_id → entry."""
    with open(BM_PATH) as f:
        bm = json.load(f)
    entries = bm.get("benchmark_entries", [])
    lookup = {}
    for entry in entries:
        model_id = entry.get("model_id", "")
        lookup[model_id] = entry
        # Also normalize: "nvidia/01-ai/yi-large" → "01-ai/yi-large"
        parts = model_id.split("/")
        if len(parts) >= 2:
            short = "/".join(parts[1:])  # remove provider prefix
            if short not in lookup:
                lookup[short] = entry
            # Try without provider completely
            bare = parts[-1]
            if bare not in lookup:
                lookup[bare] = entry
    return lookup

def normalize_model_id(mid: str) -> str:
    """Normalize model ID for matching: lowercase, remove spaces."""
    return mid.lower().strip().replace(" ", "-").replace("_", "-")

def find_benchmark_match(model_id: str, benchmark_lookup: dict, provider: str) -> dict | None:
    """Find best match for model in benchmark lookup."""
    norm_id = normalize_model_id(model_id)

    # Try exact normalized
    if norm_id in benchmark_lookup:
        return benchmark_lookup[norm_id]

    # Try provider/model_id format
    for bm_key in benchmark_lookup:
        bm_norm = normalize_model_id(bm_key)
        if norm_id == bm_norm:
            return benchmark_lookup[bm_key]
        # Partial match: model_id appears in benchmark key
        if norm_id in bm_norm or bm_norm in norm_id:
            return benchmark_lookup[bm_key]
        # Last component match
        norm_parts = norm_id.split("/")
        bm_parts = bm_norm.split("/")
        if norm_parts[-1] == bm_parts[-1] if bm_parts else False:
            return benchmark_lookup[bm_key]

    return None

def main():
    logger.info("🚀 ILMA Model Intelligence Enricher starting...")

    # Load PIM
    logger.info(f"📂 Loading PIM: {PIM_PATH}")
    with open(PIM_PATH) as f:
        pim = json.load(f)

    # Backup
    logger.info(f"💾 Backing up PIM to: {BACKUP_PATH}")
    import shutil
    shutil.copy(PIM_PATH, BACKUP_PATH)

    # Load benchmark DB
    logger.info(f"📂 Loading benchmark DB: {BM_PATH}")
    benchmark_lookup = load_benchmark_db()
    logger.info(f"   Loaded {len(benchmark_lookup)} benchmark entries")

    # Counters
    stats = {
        "total": 0,
        "benchmark_enriched": 0,
        "synthetic_enriched": 0,
        "capabilities_filled": 0,
        "already_enriched": 0,
    }

    # Process each provider and model
    for pname, pdata in pim.get("providers", {}).items():
        for mid, mdata in pdata.get("models", {}).items():
            stats["total"] += 1

            # Check if already enriched
            bp = mdata.get("benchmark_profile", {})
            qs = mdata.get("quality_score", 0)
            cap = mdata.get("capabilities_detail", {})

            # Strategy: always update benchmark_profile if we have better data
            # Priority: real benchmark > synthetic from quality_score > existing

            # Try to find real benchmark match
            bm_match = find_benchmark_match(mid, benchmark_lookup, pname)

            if bm_match:
                # Real benchmark data available
                new_bp = make_benchmark_profile(bm_match)
                # Merge: only update if new score is better or existing is weak
                existing_overall = bp.get("overall_score", 0) if bp else 0
                new_overall = new_bp.get("overall_score", 0)
                if new_overall > existing_overall or not bp:
                    mdata["benchmark_profile"] = new_bp
                    stats["benchmark_enriched"] += 1
                else:
                    stats["already_enriched"] += 1
            elif qs > 0:
                # No benchmark but has quality_score → synthetic
                new_bp = make_synthetic_profile(qs, pname, mid)
                existing_overall = bp.get("overall_score", 0) if bp else 0
                new_overall = new_bp.get("overall_score", 0)
                # Only update if improvement or not yet enriched
                if new_overall > existing_overall or not bp:
                    mdata["benchmark_profile"] = new_bp
                    stats["synthetic_enriched"] += 1
                else:
                    stats["already_enriched"] += 1
            elif not bp:
                # No quality_score, no benchmark → minimum baseline
                mdata["benchmark_profile"] = make_synthetic_profile(0.5, pname, mid)
                stats["synthetic_enriched"] += 1

            # Fill capabilities_detail if empty
            current_bp = mdata.get("benchmark_profile", {})
            current_cap = mdata.get("capabilities_detail", {})
            if not current_cap or not any(current_cap.values()):
                mdata["capabilities_detail"] = make_capabilities(mid, current_bp)
                stats["capabilities_filled"] += 1

    # Update metadata
    pim["_enriched_at"] = datetime.utcnow().isoformat()
    pim["_enricher_version"] = "1.0.0"
    if "_enrichment_stats" not in pim:
        pim["_enrichment_stats"] = {}
    pim["_enrichment_stats"].update(stats)

    # Save enriched PIM
    logger.info(f"💾 Saving enriched PIM...")
    with open(PIM_PATH, "w") as f:
        json.dump(pim, f, indent=2, ensure_ascii=False)

    # Report
    total = stats["total"]
    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ ENRICHMENT COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Total models processed:  {total}")
    logger.info(f"  Real benchmark enriched:  {stats['benchmark_enriched']} ({100*stats['benchmark_enriched']/total:.1f}%)")
    logger.info(f"  Synthetic enriched:       {stats['synthetic_enriched']} ({100*stats['synthetic_enriched']/total:.1f}%)")
    logger.info(f"  Already enriched:         {stats['already_enriched']}")
    logger.info(f"  Capabilities filled:       {stats['capabilities_filled']}")
    logger.info(f"  Backup: {BACKUP_PATH}")
    logger.info(f"  Updated: {PIM_PATH}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()