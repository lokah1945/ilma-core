#!/usr/bin/env python3
"""
ILMA Exponential Backoff with Jitter v1.0 (Phase 1.3.1)
========================================================
Implements: delay = min(max_delay, base_delay * (2 ** attempt)) * random(0.5, 1.5)

Example: base=1s, max=30s
  attempt 0 → 0.5-1.5s
  attempt 1 → 1.0-3.0s
  attempt 2 → 2.0-6.0s
  attempt 3 → 4.0-12.0s

Usage:
    from ilma_backoff import compute_backoff
    delay = compute_backoff(attempt=2, base_delay=1.0, max_delay=30.0)
    time.sleep(delay)

Config integration: config.yaml retry_policy section
Author: ILMA v3.0
Audit: AUDIT-ILMA-20260616 / Phase 1.3.1
"""
from __future__ import annotations

import random
from typing import Optional


def compute_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter_min: float = 0.5,
    jitter_max: float = 1.5,
    rng: Optional[random.Random] = None,
) -> float:
    """Compute exponential backoff with jitter.
    
    Formula: delay = min(max_delay, base_delay * (2 ** attempt)) * random(jitter_min, jitter_max)
    
    Args:
        attempt: retry attempt number (0-indexed)
        base_delay: base delay in seconds
        max_delay: maximum delay cap
        jitter_min/jitter_max: random factor bounds
        rng: optional Random instance for deterministic testing
    """
    if attempt < 0:
        attempt = 0
    exp = min(max_delay, base_delay * (2 ** attempt))
    rng = rng or random
    jitter = rng.uniform(jitter_min, jitter_max)
    return min(max_delay, exp * jitter)


if __name__ == "__main__":
    # Smoke test
    rng = random.Random(42)  # deterministic
    print("Exponential backoff with jitter (base=1s, max=30s):")
    for a in range(5):
        d = compute_backoff(a, base_delay=1.0, max_delay=30.0, rng=rng)
        print(f"  attempt={a} → {d:.2f}s")
    print()
    print("Test: full sequence capped at max=10s:")
    rng = random.Random(123)
    for a in range(8):
        d = compute_backoff(a, base_delay=1.0, max_delay=10.0, rng=rng)
        print(f"  attempt={a} → {d:.2f}s")
