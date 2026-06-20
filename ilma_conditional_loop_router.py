#!/usr/bin/env python3
"""
ILMA Conditional Loop Router
=============================
Decision engine for loop/iteration control in ILMA execution pipeline.
Routes execution flow based on judgment status, iteration count, and safety signals.

Author: ILMA Team
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Decision(Enum):
    """Loop routing decisions."""
    FINALIZE = "finalize"   # Accept and continue
    REVISE = "revise"       # Retry with revision
    ESCALATE = "escalate"   # Escalate to human review
    FAILED = "failed"       # Max iterations reached - stop
    ABORT = "abort"         # Emergency stop - unsafe


class ConditionalLoopRouter:
    """
    Routes execution based on judgment results and iteration state.

    Decision Matrix:
    - PASS + safe → FINALIZE
    - FAIL + fixable + safe + iterations OK → REVISE
    - FAIL + repeated + safe → ESCALATE
    - FAIL + unsafe OR max iterations → ABORT
    """

    def __init__(self, max_iterations: int = 300):
        self.max_iterations = max_iterations

    def route(
        self,
        judgment: Dict[str, Any],
        state: Dict[str, Any]
    ) -> Decision:
        """
        Determine next action based on judgment and execution state.

        Args:
            judgment: {'status': 'PASS'|'FAIL'|'WARN', 'failures': [...], 'warnings': [...]}
            state: {'iteration': N, 'max_iterations': N, 'repeated_failures': N, 'unsafe_detected': bool}

        Returns:
            Decision enum value
        """
        status = judgment.get("status", "FAIL")
        failures = judgment.get("failures", [])
        warnings = judgment.get("warnings", [])
        unsafe = state.get("unsafe_detected", False)
        iteration = state.get("iteration", 1)
        max_iters = state.get("max_iterations", self.max_iterations)
        repeated = state.get("repeated_failures", 0)

        # Emergency abort conditions
        if unsafe:
            logger.warning("Unsafe condition detected - ABORT")
            return Decision.ABORT

        if iteration >= max_iters:
            logger.warning(f"Max iterations reached ({max_iters}) - FAILED")
            return Decision.FAILED

        # PASS → always finalize
        if status == "PASS":
            return Decision.FINALIZE

        # FAIL analysis
        if status == "FAIL":
            if repeated >= 3:
                # Same failure pattern 3+ times
                logger.warning(f"Repeated failure pattern ({repeated}x) - ESCALATE")
                return Decision.ESCALATE

            if failures:
                # Has fixable failures
                logger.info(f"Failures detected: {failures} → REVISE")
                return Decision.REVISE

            # FAIL but no specific failures listed
            return Decision.REVISE

        # WARN → continue but log
        if status == "WARN":
            if failures:
                return Decision.REVISE
            return Decision.FINALIZE

        # Default fallback
        return Decision.FINALIZE

    def get_next_state(
        self,
        decision: Decision,
        current: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute next iteration state from decision and current state."""
        next_state = dict(current)
        next_state["iteration"] = current.get("iteration", 1) + 1

        if decision == Decision.REVISE:
            next_state["revise_count"] = next_state.get("revise_count", 0) + 1
        elif decision == Decision.ESCALATE:
            next_state["escalated"] = True
        elif decision == Decision.FAILED:
            next_state["failed"] = True
        elif decision == Decision.ABORT:
            next_state["aborted"] = True

        return next_state