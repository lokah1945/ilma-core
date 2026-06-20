#!/usr/bin/env python3
"""
ILMA Code Forge v1.0 (Phase C / TASK 2.1)
=========================================
Dual-Harness Code Forge orchestrator. Coordinates:
- Generator (different model per call)
- Reviewer (MUST be different from generator)
- Validator (static + dynamic + perf + security)
- Arbiter (weighted scoring, explained)
- Knowledge Registry (records every task)

TIER 1: Generation (parallel-ready)
TIER 2: Review (multi-reviewer)
TIER 3: Validation
TIER 4: Decision (Arbiter)
TIER 5: Knowledge Update

Feature flag: config.yaml `code_forge_enabled` (default: False)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ilma_generator_harness import GeneratorHarness, Solution
from ilma_reviewer_harness import ReviewerHarness, ReviewReport
from ilma_validator_harness import ValidatorHarness, ValidationReport
from ilma_arbiter import ILMAArbiter, ArbiterResult
from ilma_knowledge_registry import KnowledgeRegistry

logger = logging.getLogger("ilma.forge")


@dataclass
class ForgeResult:
    """End-to-end result of a forge task."""
    task_id: str
    winner_solution: Optional[Solution] = None
    arbiter_result: Optional[ArbiterResult] = None
    all_solutions: Dict[str, Solution] = field(default_factory=dict)
    all_reviews: Dict[str, ReviewReport] = field(default_factory=dict)
    all_validations: Dict[str, ValidationReport] = field(default_factory=dict)
    generator_models: List[str] = field(default_factory=list)
    reviewer_models: List[str] = field(default_factory=list)
    total_time_seconds: float = 0.0
    knowledge_recorded: bool = False


class DualHarnessCodeForge:
    """Orchestrates dual-harness code generation with review + validation."""

    def __init__(self,
                 router=None,
                 generator: Optional[GeneratorHarness] = None,
                 reviewer: Optional[ReviewerHarness] = None,
                 validator: Optional[ValidatorHarness] = None,
                 arbiter: Optional[ILMAArbiter] = None,
                 knowledge: Optional[KnowledgeRegistry] = None):
        self.router = router
        self.generator = generator or GeneratorHarness(router=router)
        self.reviewer = reviewer or ReviewerHarness(router=router)
        self.validator = validator or ValidatorHarness()
        self.arbiter = arbiter or ILMAArbiter()
        self.knowledge = knowledge or KnowledgeRegistry(mongo_db=None)

    def execute_task(self, task_spec: Dict, num_solutions: int = 2) -> ForgeResult:
        """Execute a full forge task: generate N → review → validate → arbitrate → record."""
        start = time.time()
        task_id = task_spec.get("id", "unknown")

        logger.info(f"[Forge] Task {task_id}: generating {num_solutions} solutions")

        # TIER 1: Generation
        solutions = {}
        generator_models = []
        for i in range(num_solutions):
            sol_id = f"sol_{i}"
            try:
                sol = self.generator.generate(
                    task_spec,
                    model_id=f"generator_{i}"  # distinct IDs
                )
                solutions[sol_id] = sol
                generator_models.append(sol.model_id)
            except Exception as e:
                logger.error(f"[Forge] Generator {sol_id} failed: {e}")

        if not solutions:
            return ForgeResult(task_id=task_id, total_time_seconds=time.time() - start)

        # TIER 2: Review (MUST use different model — but in offline test we just label)
        reviews = {}
        reviewer_models = []
        for i, (sol_id, sol) in enumerate(solutions.items()):
            # Different reviewer ID per solution
            reviewer_id = f"reviewer_{i}_distinct"
            try:
                report = self.reviewer.review(sol, model_id=reviewer_id)
                reviews[sol_id] = report
                reviewer_models.append(reviewer_id)
            except Exception as e:
                logger.error(f"[Forge] Reviewer for {sol_id} failed: {e}")

        # TIER 3: Validation
        validations = {}
        for sol_id, sol in solutions.items():
            try:
                val = self.validator.validate(sol, run_tests=True)
                validations[sol_id] = val
            except Exception as e:
                logger.error(f"[Forge] Validator for {sol_id} failed: {e}")

        # TIER 4: Arbiter decision
        arbiter_result = self.arbiter.select_best(solutions, reviews, validations)

        # TIER 5: Knowledge update
        task_with_solutions = {**task_spec, "_solutions": solutions}
        knowledge_recorded = self.knowledge.record_task(
            task_with_solutions,
            arbiter_result,
            reviews,
            validations,
            arbiter_result,
        )

        # Build ForgeResult
        winner_solution = solutions.get(arbiter_result.winner_id)
        elapsed = time.time() - start

        return ForgeResult(
            task_id=task_id,
            winner_solution=winner_solution,
            arbiter_result=arbiter_result,
            all_solutions=solutions,
            all_reviews=reviews,
            all_validations=validations,
            generator_models=generator_models,
            reviewer_models=reviewer_models,
            total_time_seconds=round(elapsed, 3),
            knowledge_recorded=knowledge_recorded,
        )


# Singleton
_forge_instance: Optional[DualHarnessCodeForge] = None


def get_forge(router=None) -> DualHarnessCodeForge:
    global _forge_instance
    if _forge_instance is None:
        _forge_instance = DualHarnessCodeForge(router=router)
    return _forge_instance


if __name__ == "__main__":
    print("=== Dual-Harness Code Forge E2E Demo ===\n")
    forge = DualHarnessCodeForge()

    # Task 1: Fibonacci with memoization
    print("=" * 60)
    print("TASK 1: fib_memo")
    print("=" * 60)
    task1 = {
        "id": "fib_memo",
        "title": "Fibonacci with memoization",
        "description": "Calculate fibonacci(n) efficiently using memoization",
        "type": "code",
        "requirements": [
            "Use memoization for efficiency",
            "Handle n=0 and n=1 correctly",
            "Raise ValueError for negative n",
        ],
    }
    result1 = forge.execute_task(task1, num_solutions=2)
    print(f"Winner: {result1.arbiter_result.winner_id}")
    print(f"Generator models: {result1.generator_models}")
    print(f"Reviewer models: {result1.reviewer_models}")
    print(f"Scores: {result1.arbiter_result.scores}")
    print(f"Confidence: {result1.arbiter_result.confidence}")
    print(f"Reasoning: {result1.arbiter_result.reasoning[:200]}")
    print(f"Total time: {result1.total_time_seconds}s")
    print(f"Knowledge recorded: {result1.knowledge_recorded}")

    # Task 2: LRU cache
    print()
    print("=" * 60)
    print("TASK 2: lru_cache")
    print("=" * 60)
    task2 = {
        "id": "lru_cache",
        "title": "LRU Cache implementation",
        "description": "Implement an LRU cache with O(1) get/put",
        "type": "code",
        "requirements": ["O(1) get/put", "Evict least recently used on overflow"],
    }
    result2 = forge.execute_task(task2, num_solutions=2)
    print(f"Winner: {result2.arbiter_result.winner_id}")
    print(f"Scores: {result2.arbiter_result.scores}")
    print(f"Confidence: {result2.arbiter_result.confidence}")

    # Task 3: HTTP retry
    print()
    print("=" * 60)
    print("TASK 3: http_retry")
    print("=" * 60)
    task3 = {
        "id": "http_retry",
        "title": "HTTP GET with retry",
        "description": "HTTP GET with exponential backoff retry",
        "type": "code",
        "requirements": ["Exponential backoff", "Configurable max_retries"],
    }
    result3 = forge.execute_task(task3, num_solutions=2)
    print(f"Winner: {result3.arbiter_result.winner_id}")
    print(f"Scores: {result3.arbiter_result.scores}")
    print(f"Confidence: {result3.arbiter_result.confidence}")
