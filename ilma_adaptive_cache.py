#!/usr/bin/env python3
"""
ILMA Adaptive Cache v1.0 (Phase P / TASK 2.2)
==============================================
Wraps UnifiedCache with pattern learning and preloading.
- Tracks access patterns per namespace
- Identifies hot items (top 10 by access count)
- Preloads hot items from MongoDB on demand

Feature flag: config.yaml `adaptive_cache_enabled` (default: False)
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Optional

from ilma_unified_cache import UnifiedCache, get_cache

logger = logging.getLogger("ilma.adaptive_cache")


class AdaptiveCache:
    """Cache wrapper that learns access patterns and preloads hot items."""

    def __init__(self, base_cache: Optional[UnifiedCache] = None,
                 hot_item_threshold: int = 10,
                 preload_size: int = 10):
        self.cache = base_cache or get_cache()
        self.hot_item_threshold = hot_item_threshold
        self.preload_size = preload_size
        # access_patterns: namespace -> {key: access_count}
        self.access_patterns: dict = defaultdict(lambda: defaultdict(int))
        self.preload_queue: list = []
        self._load_patterns_from_cache()

    def _load_patterns_from_cache(self):
        """Restore access patterns from persistent storage on startup."""
        try:
            stats = self.cache.stats()
            logger.info(f"[AdaptiveCache] Initialized with namespaces: {stats}")
        except Exception as e:
            logger.warning(f"[AdaptiveCache] Could not load patterns: {e}")

    def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """Get from cache and record access pattern."""
        result = self.cache.get(key, namespace)
        if result is not None:
            self._record_access(namespace, key)
        return result

    def set(self, key: str, value: Any, namespace: str = "default", ttl: int = None) -> None:
        """Store in cache. Resets access count for this key."""
        self.cache.set(key, value, namespace, ttl or 7 * 24 * 3600)
        if key in self.access_patterns[namespace]:
            # Reset count when content changes
            self.access_patterns[namespace][key] = 0

    def _record_access(self, namespace: str, key: str):
        """Record an access and update hot items queue."""
        self.access_patterns[namespace][key] += 1
        count = self.access_patterns[namespace][key]

        # Mark as hot if it crosses threshold
        if count >= self.hot_item_threshold and key not in self.preload_queue:
            self.preload_queue.append((namespace, key))
            # Keep queue bounded
            if len(self.preload_queue) > 100:
                self.preload_queue = self.preload_queue[-100:]
            logger.info(f"[AdaptiveCache] HOT: {namespace}:{key} (count={count})")

    def get_hot_items(self, namespace: str = None, limit: int = 10) -> list:
        """Get top N hot items, optionally filtered by namespace."""
        if namespace:
            items = [(namespace, k, v) for k, v in self.access_patterns[namespace].items()]
        else:
            items = []
            for ns, kv in self.access_patterns.items():
                for k, v in kv.items():
                    items.append((ns, k, v))
        items.sort(key=lambda x: x[2], reverse=True)
        return items[:limit]

    def preload_hot_items(self, refresh_func=None) -> int:
        """Preload hot items from source (e.g., MongoDB). Returns count preloaded."""
        if not refresh_func:
            return 0
        loaded = 0
        for namespace, key in self.preload_queue[:self.preload_size]:
            if self.cache.get(key, namespace) is None:
                try:
                    value = refresh_func(namespace, key)
                    if value is not None:
                        self.cache.set(key, value, namespace)
                        loaded += 1
                        logger.info(f"[AdaptiveCache] Preloaded {namespace}:{key}")
                except Exception as e:
                    logger.warning(f"[AdaptiveCache] Preload failed {namespace}:{key}: {e}")
        return loaded

    def get_stats(self) -> dict:
        """Get adaptive cache statistics."""
        total_accesses = sum(
            sum(counts.values())
            for counts in self.access_patterns.values()
        )
        return {
            "namespaces_tracked": len(self.access_patterns),
            "hot_items_queued": len(self.preload_queue),
            "total_accesses_recorded": total_accesses,
            "hot_items": [
                {"namespace": ns, "key": k, "access_count": c}
                for ns, k, c in self.get_hot_items(limit=10)
            ],
        }


# Singleton
_adaptive_instance: Optional[AdaptiveCache] = None


def get_adaptive_cache() -> AdaptiveCache:
    global _adaptive_instance
    if _adaptive_instance is None:
        _adaptive_instance = AdaptiveCache()
    return _adaptive_instance


if __name__ == "__main__":
    ac = AdaptiveCache()
    # Simulate access patterns
    for _ in range(15):
        ac.get("hot_key_1", namespace="provider.models")
    for _ in range(12):
        ac.get("hot_key_2", namespace="provider.models")
    for _ in range(3):
        ac.get("cold_key", namespace="provider.models")
    print("Stats:", ac.get_stats())
