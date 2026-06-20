#!/usr/bin/env python3
"""
ILMA Competitive Review v1.0 (Phase C / TASK 4.1)
=================================================
N models solve same problem, ILMA picks best. This is the core of
Dual-Harness Code Forge — multiple solutions compete.

Feature flag: config.yaml `competitive_review_enabled` (default: False)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ilma_code_forge import DualHarnessCodeForge, ForgeResult

logger = logging.getLogger("ilma.competitive_review")


class CompetitiveReview:
    """Run competitive review with N models solving the same problem."""

    def __init__(self, forge: Optional[DualHarnessCodeForge] = None):
        self.forge = forge or DualHarnessCodeForge()

    def solve_competitively(self, task_spec: Dict, num_solutions: int = 3) -> ForgeResult:
        """N solutions compete. Best wins via arbiter."""
        logger.info(f"[CompetitiveReview] {task_spec.get('id')}: {num_solutions} models competing")
        return self.forge.execute_task(task_spec, num_solutions=num_solutions)

    def run_tournament(self, tasks: List[Dict], num_solutions: int = 3) -> List[ForgeResult]:
        """Run a tournament: each task gets N competing solutions."""
        results = []
        for task in tasks:
            r = self.solve_competitively(task, num_solutions=num_solutions)
            results.append(r)
        return results


if __name__ == "__main__":
    print("=== Competitive Review Demo ===\n")
    cr = CompetitiveReview()

    # 3 models solve fib_memo, winner selected
    task = {
        "id": "fib_memo",
        "title": "Fibonacci with memoization",
        "description": "Calculate fibonacci(n) efficiently",
        "type": "code",
    }

    print("=== Tournament: 3 models solving fib_memo ===")
    result = cr.solve_competitively(task, num_solutions=3)
    print(f"Winner: {result.arbiter_result.winner_id}")
    print(f"Generator models used: {result.generator_models}")
    print(f"Reviewer models used: {result.reviewer_models}")
    print(f"All scores: {result.arbiter_result.scores}")
    print(f"Confidence: {result.arbiter_result.confidence}")
    print(f"Reasoning: {result.arbiter_result.reasoning[:200]}")
    print(f"Total time: {result.total_time_seconds}s")

    print()
    print("=== Tournament: 3 models solving lru_cache ===")
    task2 = {
        "id": "lru_cache",
        "title": "LRU Cache",
        "description": "O(1) get/put cache with eviction",
        "type": "code",
    }
    result2 = cr.solve_competitively(task2, num_solutions=3)
    print(f"Winner: {result2.arbiter_result.winner_id}")
    print(f"All scores: {result2.arbiter_result.scores}")
    print(f"Confidence: {result2.arbiter_result.confidence}")
