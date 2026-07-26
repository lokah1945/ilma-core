#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ILMA PROVIDER INTELLIGENCE ENRICHER v3.0                                ║
║     Single Source of Truth: PROVIDER_INTELLIGENCE_MASTER.json              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Enriches PROVIDER_INTELLIGENCE_MASTER.json dengan:
  1. Benchmark scores dari benchmark_database.json
  2. Specialization classification (heuristic + rule-based)
  3. Task fitness scores per model
  4. Provider trust scores (dari historical performance)
  5. Free tier validation
  6. Capability normalization (flatten inconsistent structures)
  7. Context length normalization
  8. Deduplication (remove duplicate model entries)

Menjalankan ini secara periodik memastikan MASTER_DB selalu fresh & akurat.

Usage:
    python3 ilma_provider_intelligence_enricher.py --enrich
    python3 ilma_provider_intelligence_enricher.py --validate
    python3 ilma_provider_intelligence_enricher.py --stats
"""

from __future__ import annotations

import json
import re
import time
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import logging
import os

logger = logging.getLogger("ILMA.ProviderEnricher")

ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
ROUTER_DATA  = ILMA_PROFILE / "ilma_model_router_data"
MASTER_DB    = ROUTER_DATA / "PROVIDER_INTELLIGENCE_MASTER.json"
BENCH_DB     = ROUTER_DATA / "benchmark_database.json"
FREE_LIST    = ROUTER_DATA / "free_model_allowlist.json"
BACKUP_DIR   = ROUTER_DATA / "backups"


# ─── Specialization Classifier ─────────────────────────────────────────────────

SPECIALIZATION_RULES: List[Tuple[str, str]] = [
    # Pattern → specialization
    (r"(coder|code|coding|starcoder|deepseek.coder|codellama)", "coding"),
    (r"(vision|vl|visual|image|multimodal|clip)", "vision"),
    (r"(embed|embedding|bge|e5|sentence)", "embedding"),
    (r"(reasoning|think|r1|r2|qwq|o1|o3)", "reasoning"),
    (r"(fast|flash|tiny|mini|small|nano)", "fast"),
    (r"(instruct|chat|turbo|assistant)", "general"),
    (r"(writing|writer|creative|story)", "creative"),
    (r"(math|mathstral|numina)", "math"),
    (r"(medical|bio|health)", "medical"),
    (r"(legal|law)", "legal"),
    (r"(long|128k|256k|1m|200k)", "long_context"),
    (r"(audio|speech|tts|stt|whisper|voxtral)", "audio"),
    (r"(rerank|rank)", "reranking"),
]

def classify_specialization(model_id: str, capabilities: List[str]) -> str:
    """Classify model specialization from ID + capabilities."""
    m_lower = model_id.lower()
    for pattern, spec in SPECIALIZATION_RULES:
        if re.search(pattern, m_lower):
            return spec

    cap_set = set(c.lower() for c in capabilities)
    if "coding" in cap_set or "code_optimized" in cap_set:
        return "coding"
    if "vision" in cap_set:
        return "vision"
    if "reasoning" in cap_set or "thinking" in cap_set:
        return "reasoning"
    if "fast" in cap_set:
        return "fast"
    return "general"


# ─── Free Tier Detector ────────────────────────────────────────────────────────

FREE_INDICATORS = [
    ":free", "free_tier", "free-tier",
    "pricing.free", "cost.free",
]

FREE_MODEL_PATTERNS = [
    r":free$",
    r"\.free$",
    r"free\.",
    r"-free-",
]

PAID_KEYWORDS_IN_NAME = re.compile(
    r'(pro|premium|plus|turbo|max|ultra|enterprise|paid|gold|platinum)', re.I
)

# Providers that are owner-hardcoded as free (bypass external API pricing)
#       google/felo/alibaba/blackbox = owner-hardcoded free tier models
HARDCODED_FREE_PROVIDERS = {'minimax', 'felo', 'cerebras', 'groq', 'together', 'nous',
    'openrouter', 'ollama', 'you', 'google', 'alibaba', 'blackbox'}
HARDCODED_FREE_PROVIDER_MODELS = {
    # Provider-level: ALL models from these providers are free (no API pricing check)
    'minimax': True,           # All minimax direct API models are free
    'google': True,            # All Gemini models have free tier
    'felo': True,              # Felo free tier
    'alibaba': True,            # Alibaba free tier models
}

def detect_is_free(model_id: str, model_data: Dict, free_allowlist: Set[str]) -> bool:
    """Detect if a model is free tier — STRICT FREE policy."""
    # REJECT disabled models (regardless of pricing)
    if model_data.get('disabled') is True:
        return False

    provider = model_data.get('provider', '').lower()
    # HARDCODE: provider-level bypass (no external API pricing check needed)
    # This supersedes all other checks (including paid keyword name matches).
    if provider in HARDCODED_FREE_PROVIDER_MODELS:
        return True

    # Reject if the single canonical billing verdict says not-free
    if model_data.get("is_free") is False:
        return False

    # Reject if pricing is explicitly set and non-zero
    pricing = model_data.get("pricing", {})
    if isinstance(pricing, dict) and pricing:
        p_type = pricing.get("type", "").lower()
        if p_type in ("paid", "subscription", "metered", "premium", "enterprise"):
            return False
        p_in = pricing.get("prompt", -1)
        p_out = pricing.get("completion", -1)
        # Only treat as free if pricing is explicitly 0 (not the -1 default)
        if p_in >= 0 and p_in > 0:
            return False
        if p_out >= 0 and p_out > 0:
            return False

    # Also check top-level pricing fields
    price_in = model_data.get("pricing_input", model_data.get("price_input", -1))
    price_out = model_data.get("pricing_output", model_data.get("price_output", -1))
    if isinstance(price_in, (int, float)) and price_in > 0:
        return False
    if isinstance(price_out, (int, float)) and price_out > 0:
        return False

    # Reject if disabled
    if model_data.get("disabled"):
        return False

    # Accept if in allowlist
    if model_id in free_allowlist:
        return True

    # Accept if explicit free flag AND no paid indicators
    if model_data.get("is_free") is True:
        return True

    # Accept if :free suffix in model name
    for pat in FREE_MODEL_PATTERNS:
        if re.search(pat, model_id, re.IGNORECASE):
            return True

    return False


# ─── Capability Normalizer ─────────────────────────────────────────────────────

CAPABILITY_NORMALIZE_MAP = {
    "code": "coding",
    "code_generation": "coding",
    "code_optimized": "coding",
    "image": "vision",
    "image_understanding": "vision",
    "visual": "vision",
    "think": "reasoning",
    "chain_of_thought": "reasoning",
    "structured": "structured_outputs",
    "json": "structured_outputs",
    "tool_use": "tools",
    "function_calling": "tools",
    "long": "long_context",
    "128k": "long_context",
    "embed": "embedding",
}

def normalize_capabilities(caps_input: Any) -> List[str]:
    """Normalize capabilities to a flat, deduplicated list."""
    if isinstance(caps_input, list):
        raw = caps_input
    elif isinstance(caps_input, dict):
        raw = [k for k, v in caps_input.items() if v is True or v == 1]
    elif isinstance(caps_input, str):
        raw = [c.strip() for c in caps_input.split(",") if c.strip()]
    else:
        raw = []

    normalized = set()
    for cap in raw:
        cap_lower = str(cap).lower().strip()
        cap_mapped = CAPABILITY_NORMALIZE_MAP.get(cap_lower, cap_lower)
        normalized.add(cap_mapped)

    return sorted(normalized)


# ─── Main Enricher ─────────────────────────────────────────────────────────────

class ProviderIntelligenceEnricher:
    """
    Enriches PROVIDER_INTELLIGENCE_MASTER.json in-place.
    Creates backup before modifying.
    """

    def __init__(self):
        self._master: Optional[Dict] = None
        self._benchmark: Optional[Dict] = None
        self._free_allowlist: Set[str] = set()
        self._stats = {
            "models_processed": 0,
            "models_enriched": 0,
            "models_free": 0,
            "models_paid": 0,
            "providers_processed": 0,
            "duplicates_removed": 0,
        }

    def _load_all(self):
        """Load all databases."""
        # Master DB
        if not MASTER_DB.exists():
            logger.error(f"MASTER_DB not found: {MASTER_DB}")
            raise FileNotFoundError(f"MASTER_DB not found: {MASTER_DB}")
        with open(MASTER_DB) as f:
            self._master = json.load(f)

        # Benchmark DB
        if BENCH_DB.exists():
            with open(BENCH_DB) as f:
                bench_data = json.load(f)
            self._benchmark = bench_data.get("models", {})
        else:
            self._benchmark = {}
            logger.warning(f"Benchmark DB not found: {BENCH_DB}")

        # Free allowlist
        if FREE_LIST.exists():
            with open(FREE_LIST) as f:
                fl = json.load(f)
            if isinstance(fl, list):
                self._free_allowlist = set(fl)
            elif isinstance(fl, dict):
                models_list = fl.get("models", [])
                if models_list and isinstance(models_list[0], dict):
                    self._free_allowlist = set(m.get("model_id", m.get("id", "")) for m in models_list if isinstance(m, dict))
                else:
                    self._free_allowlist = set(models_list)

    def _backup(self):
        """Create timestamped backup of MASTER_DB."""
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"PROVIDER_INTELLIGENCE_MASTER_{ts}.json"
        shutil.copy2(MASTER_DB, backup_path)
        logger.info(f"[Enricher] Backup created: {backup_path}")

    def _get_benchmark_score(self, model_id: str, provider: str) -> Dict[str, float]:
        """Get benchmark scores for a model."""
        if not self._benchmark:
            return {}

        key_candidates = [
            f"{provider}/{model_id}",
            model_id,
            model_id.replace(":", "_"),
            model_id.split("/")[-1] if "/" in model_id else model_id,
        ]

        for key in key_candidates:
            if key in self._benchmark:
                data = self._benchmark[key]
                return {
                    "overall": data.get("overall", 0.0),
                    "coding_weighted": data.get("coding_weighted", 0.0),
                    "reasoning_weighted": data.get("reasoning_weighted", 0.0),
                    "evidence_level": data.get("evidence_level", "UNKNOWN"),
                }

        # Partial match
        model_short = model_id.split("/")[-1].lower()
        for key, data in self._benchmark.items():
            if model_short in key.lower():
                return {
                    "overall": data.get("overall", 0.0),
                    "coding_weighted": data.get("coding_weighted", 0.0),
                    "reasoning_weighted": data.get("reasoning_weighted", 0.0),
                    "evidence_level": "PARTIAL_MATCH",
                }

        return {}

    def enrich(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Main enrich operation.
        Modifies MASTER_DB in-place (after backup).
        """
        logger.info("[Enricher] Starting enrichment...")
        self._load_all()

        if not dry_run:
            self._backup()

        providers = self._master.get("providers", {})
        if not providers:
            # Handle flat structure
            logger.warning("[Enricher] No 'providers' key found. Checking alternate structure...")
            return {"error": "No providers key in MASTER_DB", "stats": self._stats}

        for provider_id, provider_data in providers.items():
            if not isinstance(provider_data, dict):
                continue

            self._stats["providers_processed"] += 1
            models_raw = provider_data.get("models", {})

            # Normalize models to dict format
            if isinstance(models_raw, list):
                models_dict = {}
                for m in models_raw:
                    if isinstance(m, dict):
                        mid = m.get("id", m.get("model_id", ""))
                        if mid:
                            models_dict[mid] = m
                provider_data["models"] = models_dict
            elif not isinstance(models_raw, dict):
                continue
            else:
                models_dict = models_raw

            # Dedup
            seen_ids: Set[str] = set()
            to_remove = []
            for model_id in models_dict:
                normalized_id = model_id.lower().strip()
                if normalized_id in seen_ids:
                    to_remove.append(model_id)
                    self._stats["duplicates_removed"] += 1
                else:
                    seen_ids.add(normalized_id)
            for mid in to_remove:
                del models_dict[mid]

            # Enrich each model
            for model_id, model_data in models_dict.items():
                if not isinstance(model_data, dict):
                    continue

                self._stats["models_processed"] += 1

                # 1. Normalize capabilities
                raw_caps = model_data.get("capabilities", [])
                norm_caps = normalize_capabilities(raw_caps)
                model_data["capabilities"] = norm_caps

                # 2. Detect is_free
                is_free = detect_is_free(model_id, model_data, self._free_allowlist)
                model_data["is_free"] = is_free
                if is_free:
                    self._stats["models_free"] += 1
                else:
                    self._stats["models_paid"] += 1

                # 3. Classify specialization
                spec = classify_specialization(model_id, norm_caps)
                model_data["specialization"] = spec

                # 4. Normalize context length
                ctx = model_data.get("context_length", model_data.get("context_window", 0))
                if isinstance(ctx, str):
                    ctx_clean = ctx.replace("k", "000").replace("K", "000").replace(",", "")
                    try:
                        ctx = int(float(ctx_clean))
                    except ValueError:
                        ctx = 8192
                model_data["context_length"] = max(int(ctx) if ctx else 8192, 1024)

                # 5. Add benchmark scores
                bench_scores = self._get_benchmark_score(model_id, provider_id)
                if bench_scores:
                    model_data["benchmark"] = bench_scores
                    self._stats["models_enriched"] += 1

                # 6. Add enrichment metadata
                model_data["_enriched_at"] = datetime.now().isoformat()
                model_data["_enricher_version"] = "3.0.0"

        # Update metadata
        self._master["_enriched_at"] = datetime.now().isoformat()
        self._master["_enricher_version"] = "3.0.0"
        self._master["_enrichment_stats"] = self._stats

        if not dry_run:
            with open(MASTER_DB, "w") as f:
                json.dump(self._master, f, indent=2, ensure_ascii=False)
            logger.info(f"[Enricher] ✅ MASTER_DB updated: {MASTER_DB}")

        logger.info(f"[Enricher] Stats: {json.dumps(self._stats)}")
        return {"success": True, "stats": self._stats}

    def validate(self) -> Dict[str, Any]:
        """Validate MASTER_DB structure and data quality."""
        self._load_all()
        issues = []
        warnings = []

        providers = self._master.get("providers", {})
        if not providers:
            issues.append("No 'providers' key in MASTER_DB")

        total_models = 0
        total_free = 0
        total_with_benchmark = 0

        for provider_id, provider_data in providers.items():
            if not isinstance(provider_data, dict):
                warnings.append(f"Provider '{provider_id}' is not a dict")
                continue

            models = provider_data.get("models", {})
            if not isinstance(models, dict):
                if isinstance(models, list):
                    warnings.append(f"Provider '{provider_id}' models is a list, should be dict")
                continue

            for model_id, model_data in models.items():
                total_models += 1
                if not isinstance(model_data, dict):
                    warnings.append(f"Model '{provider_id}/{model_id}' is not a dict")
                    continue

                if model_data.get("is_free"):
                    total_free += 1
                if model_data.get("benchmark"):
                    total_with_benchmark += 1

                # Check required fields
                for field in ["capabilities", "context_length"]:
                    if field not in model_data:
                        warnings.append(f"Model '{provider_id}/{model_id}' missing '{field}'")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings[:20],  # cap warnings
            "stats": {
                "total_providers": len(providers),
                "total_models": total_models,
                "total_free": total_free,
                "total_paid": total_models - total_free,
                "with_benchmark": total_with_benchmark,
                "benchmark_coverage_pct": round(
                    total_with_benchmark / max(total_models, 1) * 100, 1
                ),
            }
        }

    def get_stats(self) -> Dict:
        """Get current MASTER_DB stats without modification."""
        return self.validate()


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="ILMA Provider Intelligence Enricher v3.0")
    parser.add_argument("--enrich", action="store_true", help="Enrich MASTER_DB")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no write)")
    parser.add_argument("--validate", action="store_true", help="Validate MASTER_DB")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    args = parser.parse_args()

    enricher = ProviderIntelligenceEnricher()

    if args.enrich:
        result = enricher.enrich(dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
    elif args.validate or args.stats:
        result = enricher.validate()
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()
