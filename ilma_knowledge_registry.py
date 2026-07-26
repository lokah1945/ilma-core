#!/usr/bin/env python3
"""
ILMA Knowledge Registry v1.0 (Phase C / TASK 2.6)
==================================================
Records every task execution. Persists to MongoDB code_forge_knowledge collection.
- Records: task_spec, winner, reviews, validations
- Query: best practices (which model combinations work best per task type)
- Pattern learning: failure modes, model strengths

Feature flag: config.yaml `code_forge_knowledge_enabled` (default: False)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ilma.forge.knowledge")


# Local fallback storage when MongoDB unavailable
LOCAL_PATH = Path("/root/.hermes/profiles/ilma/data/code_forge_knowledge.jsonl")


class KnowledgeRegistry:
    """Records every code-forge task and learns best practices."""

    def __init__(self, mongo_db=None, collection_name: str = "code_forge_knowledge"):
        self.collection_name = collection_name
        self.db = mongo_db  # Will be injected from forge
        self._local_records: List[Dict] = []
        self._load_local()

    def _load_local(self):
        try:
            if LOCAL_PATH.exists():
                with open(LOCAL_PATH) as f:
                    for line in f:
                        if line.strip():
                            self._local_records.append(json.loads(line))
        except Exception as e:
            logger.warning(f"[Knowledge] Could not load local: {e}")

    def record_task(self,
                    task_spec: Dict,
                    winner: Any,
                    reviews: Dict,
                    validations: Dict,
                    arbiter_result: Any = None) -> bool:
        """Record a complete task execution."""
        # Build record
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "task_id": task_spec.get("id", "unknown"),
            "task_type": task_spec.get("type", "code"),
            "title": task_spec.get("title", ""),
            "winner_id": getattr(arbiter_result, "winner_id", "unknown") if arbiter_result else "unknown",
            "winner_score": getattr(arbiter_result, "scores", {}).get(getattr(arbiter_result, "winner_id", ""), 0) if arbiter_result else 0,
            "all_scores": getattr(arbiter_result, "scores", {}) if arbiter_result else {},
            "reasoning": getattr(arbiter_result, "reasoning", "") if arbiter_result else "",
            "confidence": getattr(arbiter_result, "confidence", 0) if arbiter_result else 0,
            "tradeoffs": getattr(arbiter_result, "tradeoffs", []) if arbiter_result else [],
        }

        # Add per-solution details
        record["solutions"] = []
        # Reviews + validations need to be looked up by arbiter.alternatives + winner
        for sol_id, sol in (task_spec.get("_solutions") or {}).items():
            sol_record = {
                "id": sol_id,
                "model_id": getattr(sol, "model_id", "?"),
                "provider": getattr(sol, "provider", "?"),
                "is_free": getattr(sol, "is_free", True),
                "generation_time": getattr(sol, "generation_time_seconds", 0),
            }
            if sol_id in reviews:
                r = reviews[sol_id]
                sol_record["review"] = {
                    "quality": r.quality_score,
                    "security": r.security_score,
                    "passed": r.overall_pass,
                    "findings_count": len(r.findings),
                    "items_checked": len(r.items_checked),
                }
            if sol_id in validations:
                v = validations[sol_id]
                sol_record["validation"] = {
                    "test_pass_rate": v.test_pass_rate,
                    "performance": v.performance_score,
                    "complexity": v.cyclomatic_complexity,
                    "passed": v.overall_pass,
                }
            record["solutions"].append(sol_record)

        # Persist
        try:
            if self.db is not None:
                self.db[self.collection_name].insert_one(record.copy())
                logger.info(f"[Knowledge] Recorded task {record['task_id']} to MongoDB")
            else:
                # Local fallback
                LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(LOCAL_PATH, "a") as f:
                    f.write(json.dumps(record, default=str) + "\n")
                self._local_records.append(record)
                logger.info(f"[Knowledge] Recorded task {record['task_id']} to local file")
            return True
        except Exception as e:
            logger.error(f"[Knowledge] Record failed: {e}")
            return False

    def get_best_practices(self, task_type: str = None) -> List[Dict]:
        """Aggregate best model combinations per task type."""
        records = self._local_records
        if self.db is not None:
            try:
                query = {} if task_type is None else {"task_type": task_type}
                records = list(self.db[self.collection_name].find(query, {"_id": 0}))
            except Exception as e:
                logger.warning(f"[Knowledge] MongoDB query failed: {e}, using local")

        # Aggregate: by (gen_model, rev_model)
        combo_scores: Dict[str, List[float]] = {}
        for r in records:
            for sol in r.get("solutions", []):
                key = sol.get("model_id", "?")
                score = sol.get("review", {}).get("quality", 0)
                combo_scores.setdefault(key, []).append(score)

        return sorted(
            [
                {"model_id": k, "avg_quality": round(sum(v) / len(v), 2), "samples": len(v)}
                for k, v in combo_scores.items()
            ],
            key=lambda x: x["avg_quality"],
            reverse=True,
        )

    def get_failure_patterns(self) -> List[Dict]:
        """Return all tasks where the winner had unresolved findings."""
        patterns = []
        for r in self._local_records:
            for sol in r.get("solutions", []):
                if not sol.get("validation", {}).get("passed", True):
                    patterns.append({
                        "task_id": r["task_id"],
                        "model_id": sol.get("model_id"),
                        "failure": "validation_failed",
                        "findings_count": sol.get("review", {}).get("findings_count", 0),
                    })
        return patterns

    def get_stats(self) -> Dict:
        return {
            "total_records": len(self._local_records),
            "mongo_connected": self.db is not None,
            "local_path": str(LOCAL_PATH),
        }


if __name__ == "__main__":
    print("=== Knowledge Registry Demo ===\n")
    kr = KnowledgeRegistry(mongo_db=None)
    print("Stats:", kr.get_stats())
    print()

    # Simulate recording a task
    from ilma_generator_harness import GeneratorHarness, Solution
    from ilma_reviewer_harness import ReviewerHarness
    from ilma_validator_harness import ValidatorHarness
    from ilma_arbiter import ILMAArbiter, ArbiterResult

    gh = GeneratorHarness()
    rh = ReviewerHarness()
    vh = ValidatorHarness()
    arbiter = ILMAArbiter()

    sol_a = gh.generate({"id": "fib_memo", "title": "Fib", "description": "fib", "requirements": []}, model_id="model_A")
    sol_b = gh.generate({"id": "fib_memo", "title": "Fib", "description": "fib", "requirements": []}, model_id="model_B")
    solutions = {"sol_a": sol_a, "sol_b": sol_b}
    reviews = {"sol_a": rh.review(sol_a), "sol_b": rh.review(sol_b)}
    validations = {"sol_a": vh.validate(sol_a), "sol_b": vh.validate(sol_b)}
    result = arbiter.select_best(solutions, reviews, validations)

    # Record (need to pass _solutions for the record to have full data)
    task_spec = {"id": "fib_memo", "title": "Fib", "type": "code", "_solutions": solutions}
    ok = kr.record_task(task_spec, result, reviews, validations, result)
    print(f"Recorded: {ok}")
    print()

    print("Best practices:")
    for bp in kr.get_best_practices():
        print(f"  {bp}")
    print()
    print("Failure patterns:")
    for fp in kr.get_failure_patterns():
        print(f"  {fp}")
    print()
    print("Final stats:", kr.get_stats())
