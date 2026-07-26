#!/usr/bin/env python3
"""
ILMA Provider Load Balancer v1.0 (Phase P / TASK 4.2)
======================================================
Distributes requests across providers to avoid overloading any single one.
- Tracks current load per provider
- Picks least-loaded provider from candidates
- Configurable max concurrent per provider

Feature flag: config.yaml `load_balancing_enabled` (default: False)
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ilma.load_balancer")


class ProviderLoadBalancer:
    """Distribute requests across multiple providers."""

    def __init__(self, max_concurrent_per_provider: int = 10):
        self.max_concurrent = max_concurrent_per_provider
        self.provider_load: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._stats = {"total_requests": 0, "skipped_overloaded": 0}

    def select_provider(self, candidates: List[Any]) -> Optional[Any]:
        """Pick the least-loaded provider from candidates."""
        if not candidates:
            return None

        with self._lock:
            available = []
            for c in candidates:
                provider = self._get_provider_name(c)
                load = self.provider_load.get(provider, 0)
                if load < self.max_concurrent:
                    available.append((c, load))

            self._stats["total_requests"] += 1

            if not available:
                # All overloaded — pick least loaded (could degrade, but don't fail)
                self._stats["skipped_overloaded"] += 1
                logger.warning(f"[LoadBalancer] All {len(candidates)} providers overloaded, picking least loaded")
                return min(candidates, key=lambda c: self.provider_load.get(self._get_provider_name(c), 0))

            # Pick least loaded from available
            return min(available, key=lambda x: x[1])[0]

    def _get_provider_name(self, candidate: Any) -> str:
        if isinstance(candidate, dict):
            return candidate.get("provider", "unknown")
        return str(candidate)

    @contextmanager
    def track_request(self, provider: str):
        """Context manager to track request lifecycle."""
        self.start_request(provider)
        try:
            yield
        finally:
            self.end_request(provider)

    def start_request(self, provider: str):
        with self._lock:
            self.provider_load[provider] = self.provider_load.get(provider, 0) + 1

    def end_request(self, provider: str):
        with self._lock:
            current = self.provider_load.get(provider, 0)
            self.provider_load[provider] = max(0, current - 1)

    def get_load(self, provider: str) -> int:
        with self._lock:
            return self.provider_load.get(provider, 0)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "providers_tracked": len(self.provider_load),
                "current_load": dict(self.provider_load),
                "max_concurrent": self.max_concurrent,
                "total_requests": self._stats["total_requests"],
                "skipped_overloaded": self._stats["skipped_overloaded"],
            }


# Singleton
_lb_instance: Optional[ProviderLoadBalancer] = None


def get_load_balancer(max_concurrent: int = 10) -> ProviderLoadBalancer:
    global _lb_instance
    if _lb_instance is None:
        _lb_instance = ProviderLoadBalancer(max_concurrent_per_provider=max_concurrent)
    return _lb_instance


if __name__ == "__main__":
    lb = ProviderLoadBalancer(max_concurrent_per_provider=3)

    candidates = [
        {"provider": "nvidia", "model_id": "m1"},
        {"provider": "openrouter", "model_id": "m2"},
        {"provider": "groq", "model_id": "m3"},
        {"provider": "cerebras", "model_id": "m4"},
    ]

    print("=== Test 1: Initial selection ===")
    for i in range(10):
        selected = lb.select_provider(candidates)
        print(f"  Request {i+1}: {selected['provider']}/{selected['model_id']} (load={lb.get_load(selected['provider'])})")
        lb.end_request(selected['provider'])  # simulate immediate completion

    print()
    print("=== Test 2: With active requests (nvidia busy) ===")
    # Saturate nvidia
    for _ in range(3):
        lb.start_request("nvidia")
    print(f"  nvidia load: {lb.get_load('nvidia')}")
    selected = lb.select_provider(candidates)
    print(f"  Selected: {selected['provider']} (nvidia should be skipped)")

    print()
    print("=== Test 3: All overloaded ===")
    for p in ["nvidia", "openrouter", "groq", "cerebras"]:
        for _ in range(3):
            lb.start_request(p)
    selected = lb.select_provider(candidates)
    print(f"  Selected (degraded): {selected['provider']}")

    print()
    print("=== Stats ===")
    print(lb.get_stats())
