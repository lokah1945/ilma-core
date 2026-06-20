#!/usr/bin/env python3
"""
ILMA A/B Testing Framework v1.0 (Phase P / TASK 5.1)
=====================================================
Test different routing strategies and measure which performs better.
- Random variant assignment (50/50)
- Result recording per variant
- Statistical summary (count, success rate)

Feature flag: config.yaml `ab_testing_enabled` (default: False)
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ilma.ab_testing")

# Persistent storage for experiments
EXPERIMENTS_PATH = Path("/root/.hermes/profiles/ilma/data/ab_experiments.json")


class ABTestingFramework:
    """A/B testing for routing strategies."""

    def __init__(self):
        self.experiments: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        try:
            if EXPERIMENTS_PATH.exists():
                with open(EXPERIMENTS_PATH) as f:
                    self.experiments = json.load(f)
        except Exception as e:
            logger.warning(f"[ABTesting] Could not load experiments: {e}")

    def _save(self):
        try:
            EXPERIMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(EXPERIMENTS_PATH, "w") as f:
                json.dump(self.experiments, f, indent=2)
        except Exception as e:
            logger.warning(f"[ABTesting] Could not save: {e}")

    def create_experiment(self, experiment_id: str, variant_a: str, variant_b: str,
                          metric: str = "success_rate") -> bool:
        """Create a new A/B experiment."""
        if experiment_id in self.experiments:
            return False
        self.experiments[experiment_id] = {
            "variant_a": variant_a,
            "variant_b": variant_b,
            "metric": metric,
            "results": {"a": [], "b": []},
            "created_at": str(__import__("datetime").datetime.now()),
        }
        self._save()
        logger.info(f"[ABTesting] Created experiment: {experiment_id}")
        return True

    def get_variant(self, experiment_id: str, user_id: Optional[str] = None) -> Optional[str]:
        """Get the variant assignment for this call. Returns 'a' or 'b'."""
        if experiment_id not in self.experiments:
            return None
        # Random 50/50 (could be made deterministic with user_id hashing)
        return "a" if random.random() < 0.5 else "b"

    def record_result(self, experiment_id: str, variant: str, result: float) -> bool:
        """Record a result (1.0 for success, 0.0 for failure, or any float metric)."""
        if experiment_id not in self.experiments:
            return False
        if variant not in ("a", "b"):
            return False
        self.experiments[experiment_id]["results"][variant].append(result)
        self._save()
        return True

    def get_experiment_results(self, experiment_id: str) -> Optional[Dict]:
        """Get summary statistics for an experiment."""
        if experiment_id not in self.experiments:
            return None
        exp = self.experiments[experiment_id]
        a = exp["results"]["a"]
        b = exp["results"]["b"]
        return {
            "experiment_id": experiment_id,
            "metric": exp["metric"],
            "variant_a": {
                "label": exp["variant_a"],
                "count": len(a),
                "mean": round(sum(a) / len(a), 4) if a else 0.0,
                "min": round(min(a), 4) if a else None,
                "max": round(max(a), 4) if a else None,
            },
            "variant_b": {
                "label": exp["variant_b"],
                "count": len(b),
                "mean": round(sum(b) / len(b), 4) if b else 0.0,
                "min": round(min(b), 4) if b else None,
                "max": round(max(b), 4) if b else None,
            },
            "winner": (
                "a" if (a and (not b or sum(a)/len(a) > sum(b)/len(b))) else
                "b" if b else "tie"
            ),
        }

    def list_experiments(self) -> List[str]:
        return list(self.experiments.keys())


# Singleton
_ab_instance: Optional[ABTestingFramework] = None


def get_ab_framework() -> ABTestingFramework:
    global _ab_instance
    if _ab_instance is None:
        _ab_instance = ABTestingFramework()
    return _ab_instance


if __name__ == "__main__":
    ab = ABTestingFramework()
    exp_id = "routing_strategy_v1_vs_v2"
    ab.create_experiment(exp_id, "v1_standard", "v2_predictive")

    # Simulate 100 requests
    for _ in range(60):
        variant = ab.get_variant(exp_id)
        # v1: 80% success, v2: 85% success
        success = 1.0 if (variant == "b" and random.random() < 0.85) or (variant == "a" and random.random() < 0.80) else 0.0
        ab.record_result(exp_id, variant, success)

    results = ab.get_experiment_results(exp_id)
    print("=== A/B Test Results ===")
    print(json.dumps(results, indent=2))
