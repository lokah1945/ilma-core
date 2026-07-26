#!/usr/bin/env python3
"""
ILMA Capability Scorer v1.0 (Phase C / TASK 3.1)
=================================================
Adds granular capability scores to model_intelligence collection:
- code_generation_score
- code_review_critique_score
- bug_detection_score
- instruction_following_score
- reasoning_depth_score

Uses deterministic heuristics from existing fields (composite_score, capabilities)
to derive capability-specific scores. Production would use benchmark results.

Feature flag: config.yaml `capability_scorer_enabled` (default: False)
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ilma.capability_scorer")

# Capability hints based on model name patterns
CAPABILITY_PATTERNS = {
    "code_generation_score": [
        re.compile(r"coder|codestral|deepseek-coder|qwen.*coder|llama.*code|yi-coder|starcoder|code-\w+", re.IGNORECASE),
        re.compile(r"qwen.*2\.5-coder", re.IGNORECASE),
        re.compile(r"deepseek-v3", re.IGNORECASE),
    ],
    "code_review_critique_score": [
        re.compile(r"claude|sonnet|opus|gpt-4|gpt-5|gemini.*pro|llama.*70b", re.IGNORECASE),
    ],
    "bug_detection_score": [
        re.compile(r"claude|sonnet|opus|gpt-4|gpt-5|gemini.*pro", re.IGNORECASE),
    ],
    "instruction_following_score": [
        re.compile(r"claude|sonnet|opus|gpt-4|gpt-5|instruct", re.IGNORECASE),
    ],
    "reasoning_depth_score": [
        re.compile(r"o1|o3|opus|sonnet|pro|thinking|reasoning", re.IGNORECASE),
    ],
}

# Default score for each capability (when no specific match)
DEFAULT_SCORES = {
    "code_generation_score": 60.0,
    "code_review_critique_score": 65.0,
    "bug_detection_score": 60.0,
    "instruction_following_score": 70.0,
    "reasoning_depth_score": 65.0,
}


class CapabilityScorer:
    """Compute granular capability scores for a model."""

    def __init__(self, router=None):
        self.router = router

    def compute_scores(self, model_doc: Dict) -> Dict[str, float]:
        """Compute all 5 capability scores for a model."""
        model_id = model_doc.get("model_id", "")
        composite = model_doc.get("composite_score", 0) or 0
        capabilities = model_doc.get("capabilities", []) or []

        scores = {}
        for cap, patterns in CAPABILITY_PATTERNS.items():
            # Start with default
            base = DEFAULT_SCORES[cap]
            # Check patterns
            matched = any(p.search(model_id) for p in patterns)
            if matched:
                # Boost by 15 if matched
                base = min(95.0, composite + 10 if composite else base + 15)
            # Adjust by composite score
            if composite and composite > 0:
                base = (base + composite) / 2
            # Adjust by capabilities
            if "code" in capabilities and cap.startswith("code_"):
                base = min(95.0, base + 5)
            if "reasoning" in capabilities and "reasoning" in cap:
                base = min(95.0, base + 5)
            scores[cap] = round(base, 2)
        return scores

    def update_sot(self, db, model_intelligence_collection: str = "model_intelligence",
                   limit: int = 100) -> Dict:
        """Update SOT with capability scores for top N models."""
        if db is None:
            logger.warning("[CapabilityScorer] No MongoDB, skipping update")
            return {"updated": 0, "errors": 0}

        cursor = db[model_intelligence_collection].find().limit(limit)
        updated = 0
        errors = 0

        for doc in cursor:
            try:
                scores = self.compute_scores(doc)
                db[model_intelligence_collection].update_one(
                    {"_id": doc["_id"]},
                    {"$set": scores}
                )
                updated += 1
            except Exception as e:
                logger.error(f"[CapabilityScorer] Failed for {doc.get('model_id')}: {e}")
                errors += 1

        return {"updated": updated, "errors": errors, "total_attempted": limit}

    def get_best_for_capability(self, db, capability: str, min_score: float = 60.0,
                                is_free: bool = True, limit: int = 10,
                                collection: str = "model_intelligence") -> List[Dict]:
        """Get top N models for a specific capability."""
        if db is None:
            return []
        query = {
            capability: {"$gte": min_score},
            "is_free": is_free,
        }
        cursor = db[collection].find(query).sort(capability, -1).limit(limit)
        return list(cursor)


if __name__ == "__main__":
    print("=== Capability Scorer Demo ===\n")
    cs = CapabilityScorer()

    # Test on sample models
    samples = [
        {"model_id": "nvidia/qwen-2.5-coder-32b-instruct", "composite_score": 75, "capabilities": ["code", "general"]},
        {"model_id": "nvidia/llama-3.3-70b-instruct", "composite_score": 80, "capabilities": ["general"]},
        {"model_id": "openai/o1-preview", "composite_score": 90, "capabilities": ["reasoning"]},
        {"model_id": "anthropic/claude-3.5-sonnet", "composite_score": 88, "capabilities": ["general", "code"]},
        {"model_id": "deepseek-ai/deepseek-coder", "composite_score": 70, "capabilities": ["code"]},
    ]
    print(f"{'Model':<40} {'gen':<6} {'rev':<6} {'bug':<6} {'inst':<6} {'reas':<6}")
    for s in samples:
        scores = cs.compute_scores(s)
        print(f"{s['model_id']:<40} {scores['code_generation_score']:<6} "
              f"{scores['code_review_critique_score']:<6} "
              f"{scores['bug_detection_score']:<6} "
              f"{scores['instruction_following_score']:<6} "
              f"{scores['reasoning_depth_score']:<6}")
