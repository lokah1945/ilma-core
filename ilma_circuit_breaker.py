#!/usr/bin/env python3
"""
ILMA Granular Circuit Breaker v1.0 (Phase P / TASK 2.3)
=======================================================
Per-provider circuit breaker with CLOSED/OPEN/HALF_OPEN states.
- Tracks failures per provider
- Recovers individually (provider A can be OPEN while B is CLOSED)
- Half-open: limited probes before full recovery

Feature flag: config.yaml `granular_circuit_breaker_enabled` (default: True)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger("ilma.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class ProviderCircuitState:
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0.0
    open_time: float = 0.0


class GranularCircuitBreaker:
    """Per-provider circuit breaker."""

    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 half_open_max_requests: int = 3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_requests = half_open_max_requests
        self.provider_states: Dict[str, ProviderCircuitState] = {}

    def _get_state(self, provider: str) -> ProviderCircuitState:
        if provider not in self.provider_states:
            self.provider_states[provider] = ProviderCircuitState()
        return self.provider_states[provider]

    def can_attempt(self, provider: str) -> bool:
        """Check if a request to this provider can proceed."""
        state = self._get_state(provider)

        if state.state == CircuitState.CLOSED:
            return True

        if state.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - state.open_time > self.recovery_timeout:
                state.state = CircuitState.HALF_OPEN
                state.successes = 0
                logger.info(f"[CircuitBreaker] {provider}: OPEN → HALF_OPEN")
                return True
            return False

        if state.state == CircuitState.HALF_OPEN:
            return True

        return True

    def record_failure(self, provider: str, error: Optional[Exception] = None):
        """Record a failure for a provider."""
        state = self._get_state(provider)
        state.failures += 1
        state.last_failure_time = time.time()

        if state.state == CircuitState.HALF_OPEN:
            # Failed in half-open → back to OPEN
            state.state = CircuitState.OPEN
            state.open_time = time.time()
            logger.warning(f"[CircuitBreaker] {provider}: HALF_OPEN → OPEN (failed during probe)")
            return

        if state.failures >= self.failure_threshold and state.state == CircuitState.CLOSED:
            state.state = CircuitState.OPEN
            state.open_time = time.time()
            logger.warning(
                f"[CircuitBreaker] {provider}: CLOSED → OPEN "
                f"(failures={state.failures}, error={error})"
            )

    def record_success(self, provider: str):
        """Record a success for a provider."""
        state = self._get_state(provider)

        if state.state == CircuitState.HALF_OPEN:
            state.successes += 1
            if state.successes >= self.half_open_max_requests:
                state.state = CircuitState.CLOSED
                state.failures = 0
                state.successes = 0
                logger.info(
                    f"[CircuitBreaker] {provider}: HALF_OPEN → CLOSED "
                    f"(recovered after {self.half_open_max_requests} successes)"
                )
        elif state.state == CircuitState.CLOSED:
            # Decay failure count on success
            state.failures = max(0, state.failures - 1)

    def get_state(self, provider: str) -> str:
        return self._get_state(provider).state.value

    def get_stats(self) -> dict:
        return {
            "providers": len(self.provider_states),
            "states": {
                p: {
                    "state": s.state.value,
                    "failures": s.failures,
                    "successes": s.successes,
                    "open_time": s.open_time,
                }
                for p, s in self.provider_states.items()
            },
        }

    def reset(self, provider: Optional[str] = None):
        """Reset circuit breaker state."""
        if provider:
            if provider in self.provider_states:
                del self.provider_states[provider]
        else:
            self.provider_states.clear()


# Singleton
_cb_instance: Optional[GranularCircuitBreaker] = None


def get_circuit_breaker() -> GranularCircuitBreaker:
    global _cb_instance
    if _cb_instance is None:
        _cb_instance = GranularCircuitBreaker()
    return _cb_instance


if __name__ == "__main__":
    cb = GranularCircuitBreaker(failure_threshold=3, recovery_timeout=2.0, half_open_max_requests=2)

    print("=== Test 1: Normal operation ===")
    print(f"can_attempt(openai): {cb.can_attempt('openai')}")  # True
    cb.record_success("openai")
    print(f"After 1 success, state: {cb.get_state('openai')}")  # CLOSED

    print()
    print("=== Test 2: Trip on failures ===")
    for i in range(5):
        cb.record_failure("nvidia")
    print(f"After 5 failures, state: {cb.get_state('nvidia')}")  # OPEN
    print(f"can_attempt(nvidia): {cb.can_attempt('nvidia')}")  # False

    print()
    print("=== Test 3: Recovery ===")
    time.sleep(2.1)
    print(f"After timeout, can_attempt(nvidia): {cb.can_attempt('nvidia')}")  # True (HALF_OPEN)
    cb.record_success("nvidia")
    cb.record_success("nvidia")
    print(f"After 2 successes, state: {cb.get_state('nvidia')}")  # CLOSED

    print()
    print("=== Test 4: Independent providers ===")
    cb2 = GranularCircuitBreaker(failure_threshold=2)
    for _ in range(3):
        cb2.record_failure("provider_a")
    print(f"provider_a state: {cb2.get_state('provider_a')}")  # OPEN
    print(f"provider_b state: {cb2.get_state('provider_b')}")  # CLOSED (independent)
