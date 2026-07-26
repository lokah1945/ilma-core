#!/usr/bin/env python3
"""
ILMA Unified Cache v1.0 (Phase 1.1 Block 3)
============================================
SQLite-based single cache with namespaces. Replaces 4 JSON + 1 SQLite cache files.

Schema:
  cache_entries (key, namespace, value, created_at, expires_at, access_count)

Namespaces (migrated from old caches):
  - provider.models    (from provider_models_cache.json)
  - dev.models         (from models_dev_cache.json)
  - ollama.models      (from ollama_cloud_models_cache.json)
  - benchmark.aa       (from benchmark_aa_cache.json)
  - response.store     (from response_store.db)

Features:
  - TTL: 7 days default
  - LRU: max 1000 entries per namespace
  - Refresh-from-MongoDB hook

Usage:
    from ilma_unified_cache import get_cache
    cache = get_cache()
    cache.set("my_key", {"foo": "bar"}, namespace="custom", ttl=86400)
    val = cache.get("my_key", namespace="custom")

Author: ILMA v3.0
Audit: AUDIT-ILMA-20260616 / Phase 1.1 Block 3
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional, Union

CACHE_PATH = Path("/root/.hermes/profiles/ilma/data/ilma_unified_cache.db")
DEFAULT_TTL = 7 * 24 * 3600  # 7 days
MAX_ENTRIES_PER_NS = 1000


class UnifiedCache:
    def __init__(self, db_path: Path = CACHE_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed_at REAL,
                    PRIMARY KEY (namespace, key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ns ON cache_entries(namespace)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache_entries(expires_at)")

    def set(self, key: str, value: Any, namespace: str = "default",
            ttl: int = DEFAULT_TTL) -> None:
        """Store value in cache. JSON-encoded."""
        expires = time.time() + ttl
        val_str = json.dumps(value, default=str)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_entries (key, namespace, value, created_at, expires_at, last_accessed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (key, namespace, val_str, time.time(), expires, time.time())
            )

    def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """Retrieve value. Returns None if missing or expired."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache_entries WHERE namespace=? AND key=?",
                (namespace, key)
            ).fetchone()
            if not row:
                return None
            val_str, expires = row
            if expires < time.time():
                # Expired
                conn.execute("DELETE FROM cache_entries WHERE namespace=? AND key=?", (namespace, key))
                return None
            # Update access count
            conn.execute(
                "UPDATE cache_entries SET access_count=access_count+1, last_accessed_at=? WHERE namespace=? AND key=?",
                (time.time(), namespace, key)
            )
            return json.loads(val_str)

    def delete(self, key: str, namespace: str = "default") -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache_entries WHERE namespace=? AND key=?", (namespace, key))

    def clear_namespace(self, namespace: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM cache_entries WHERE namespace=?", (namespace,))
            return cur.rowcount

    def cleanup_expired(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM cache_entries WHERE expires_at<?", (time.time(),))
            return cur.rowcount

    def lru_evict(self, namespace: str) -> int:
        """Keep only MAX_ENTRIES_PER_NS most recent entries."""
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE namespace=?", (namespace,)
            ).fetchone()[0]
            if count <= MAX_ENTRIES_PER_NS:
                return 0
            to_delete = count - MAX_ENTRIES_PER_NS
            cur = conn.execute(
                "DELETE FROM cache_entries WHERE namespace=? AND key IN "
                "(SELECT key FROM cache_entries WHERE namespace=? ORDER BY last_accessed_at ASC LIMIT ?)",
                (namespace, namespace, to_delete)
            )
            return cur.rowcount

    def stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT namespace, COUNT(*) FROM cache_entries GROUP BY namespace"
            ).fetchall()
            return {ns: count for ns, count in rows}


# Singleton
_cache_instance = None

def get_cache() -> UnifiedCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = UnifiedCache()
    return _cache_instance


if __name__ == "__main__":
    # Smoke test
    c = get_cache()
    c.set("test_key", {"hello": "world"}, namespace="test", ttl=60)
    val = c.get("test_key", namespace="test")
    assert val == {"hello": "world"}, f"Expected dict, got {val}"
    c.set("test_key2", [1, 2, 3], namespace="test", ttl=60)
    val2 = c.get("test_key2", namespace="test")
    assert val2 == [1, 2, 3]
    c.delete("test_key", namespace="test")
    val3 = c.get("test_key", namespace="test")
    assert val3 is None
    print("All smoke tests passed")
    print(f"Stats: {c.stats()}")
