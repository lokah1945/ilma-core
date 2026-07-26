#!/usr/bin/env python3
"""
ILMA Arbiter v1.0 (Phase C / TASK 2.5)
======================================
Decision engine that selects the best solution from N candidates.
- Weighted scoring: quality (30%) + tests (30%) + performance (20%) +
  security (10%) + cost (10%)
- MUST explain its decision
- Returns winner + scores + reasoning

Feature flag: config.yaml `code_forge_arbiter_enabled` (default: False)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ilma.forge.arbiter")


@dataclass
class ArbiterResult:
    winner_id: str = ""
    scores: Dict[str, float] = field(default_factory=dict)
    reasoning: str = ""
    tradeoffs: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    confidence: float = 0.0


class ILMAArbiter:
    """Decision engine that selects the best solution."""

    # Weights (must sum to 1.0)
    WEIGHTS = {
        "quality": 0.30,
        "tests": 0.30,
        "performance": 0.20,
        "security": 0.10,
        "cost": 0.10,
    }

    def select_best(self,
                    solutions: Dict[str, Any],
                    reviews: Dict[str, Any],
                    validations: Dict[str, Any]) -> ArbiterResult:
        """Select best solution from candidates. Returns ArbiterResult."""
        scores = {}

        for sol_id, sol in solutions.items():
            review = reviews.get(sol_id)
            validation = validations.get(sol_id)

            if review is None or validation is None:
                logger.warning(f"[Arbiter] Missing review/validation for {sol_id}")
                scores[sol_id] = 0.0
                continue

            # Quality score (0-100)
            quality = review.quality_score if hasattr(review, "quality_score") else 0

            # Test pass rate (0-100)
            tests = validation.test_pass_rate * 100 if hasattr(validation, "test_pass_rate") else 0

            # Performance score (0-1 → 0-100)
            perf = validation.performance_score * 100 if hasattr(validation, "performance_score") else 50

            # Security score (0-100)
            security = review.security_score if hasattr(review, "security_score") else 100

            # Cost score (free = 100, paid = 50)
            is_free = getattr(sol, "is_free", True)
            cost = 100.0 if is_free else 50.0

            # Weighted total
            total = (
                quality * self.WEIGHTS["quality"] +
                tests * self.WEIGHTS["tests"] +
                perf * self.WEIGHTS["performance"] +
                security * self.WEIGHTS["security"] +
                cost * self.WEIGHTS["cost"]
            )
            scores[sol_id] = round(total, 2)

        if not scores:
            return ArbiterResult(
                winner_id="",
                scores={},
                reasoning="No valid candidates to evaluate",
                confidence=0.0,
            )

        winner_id = max(scores, key=scores.get)
        winner_score = scores[winner_id]
        alternatives = [sid for sid in scores if sid != winner_id]
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        runner_up_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

        # Confidence: gap between winner and runner-up
        gap = winner_score - runner_up_score
        if gap > 10:
            confidence = 0.95
        elif gap > 5:
            confidence = 0.80
        elif gap > 2:
            confidence = 0.60
        else:
            confidence = 0.40

        # Build reasoning
        winner_sol = solutions[winner_id]
        winner_review = reviews[winner_id]
        winner_validation = validations[winner_id]

        reasoning_parts = [
            f"Selected {winner_id} with total score {winner_score:.2f}/100.",
            f"Generator model: {getattr(winner_sol, 'model_id', '?')} ({getattr(winner_sol, 'provider', '?')}).",
            f"Quality: {winner_review.quality_score:.0f}/100, Tests: {winner_validation.test_pass_rate*100:.0f}%, "
            f"Performance: {winner_validation.performance_score:.2f}, Security: {winner_review.security_score:.0f}/100.",
        ]
        if gap > 0:
            reasoning_parts.append(
                f"Beat runner-up ({alternatives[0] if alternatives else 'N/A'}) by {gap:.2f} points."
            )
        if not winner_review.overall_pass:
            reasoning_parts.append("WARNING: Winner has unresolved review findings.")
        if not winner_validation.overall_pass:
            reasoning_parts.append("WARNING: Winner failed some validation checks.")

        reasoning = " ".join(reasoning_parts)

        # Tradeoffs
        tradeoffs = []
        if winner_validation.performance_score < 0.7:
            tradeoffs.append("Performance is sub-optimal; consider profiling")
        if winner_review.findings:
            medium = sum(1 for f in winner_review.findings if f.severity == "MEDIUM")
            if medium > 0:
                tradeoffs.append(f"{medium} MEDIUM-severity review findings remain")
        if winner_validation.cyclomatic_complexity > 10:
            tradeoffs.append(f"High cyclomatic complexity ({winner_validation.cyclomatic_complexity})")

        return ArbiterResult(
            winner_id=winner_id,
            scores=scores,
            reasoning=reasoning,
            tradeoffs=tradeoffs,
            alternatives=alternatives,
            confidence=confidence,
        )


# Singleton
_arbiter_instance = None


def get_arbiter() -> ILMAArbiter:
    global _arbiter_instance
    if _arbiter_instance is None:
        _arbiter_instance = ILMAArbiter()
    return _arbiter_instance


if __name__ == "__main__":
    print("=== Arbiter Demo ===\n")
    from ilma_generator_harness import GeneratorHarness, Solution
    from ilma_reviewer_harness import ReviewerHarness
    from ilma_validator_harness import ValidatorHarness

    gh = GeneratorHarness()
    rh = ReviewerHarness()
    vh = ValidatorHarness()
    arbiter = ILMAArbiter()

    # Create 2 solutions
    sol_a = gh.generate({"id": "fib_memo", "title": "Fib", "description": "fib", "requirements": []}, model_id="model_A")
    sol_b = gh.generate({"id": "fib_memo", "title": "Fib", "description": "fib", "requirements": []}, model_id="model_B")

    solutions = {"sol_a": sol_a, "sol_b": sol_b}
    reviews = {"sol_a": rh.review(sol_a, model_id="reviewer_X"),
               "sol_b": rh.review(sol_b, model_id="reviewer_Y")}
    validations = {"sol_a": vh.validate(sol_a, run_tests=True),
                   "sol_b": vh.validate(sol_b, run_tests=True)}

    result = arbiter.select_best(solutions, reviews, validations)
    print(f"Winner: {result.winner_id}")
    print(f"Scores: {result.scores}")
    print(f"Confidence: {result.confidence}")
    print(f"\nReasoning: {result.reasoning}")
    if result.tradeoffs:
        print(f"\nTradeoffs:")
        for t in result.tradeoffs:
            print(f"  - {t}")
    print(f"\nAlternatives: {result.alternatives}")
