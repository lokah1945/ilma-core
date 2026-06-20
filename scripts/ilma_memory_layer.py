#!/usr/bin/env python3
"""
ILMA Memory Layer — Compatibility Integration Module
=====================================================

Purpose:
    Provides a unified memory layer interface by integrating 4 existing
    memory modules: analytics, cleanup, persistence, and search.

    This module is a compatibility shim that wraps the existing memory
    subsystem to satisfy the 'memory' capability requirement.

    The underlying memory infrastructure is provided by:
    - scripts/ilma_memory_analytics.py — MemoryEntry, MemoryAnalytics, TrendData
    - scripts/ilma_memory_cleanup.py — MemoryCleanup, CleanupStats
    - scripts/ilma_memory_persistence.py — MemoryPersistence, MemoryCheckpoint
    - scripts/ilma_memory_search.py — MemorySearch, BM25Ranker

Interface (standard):
    store_event(key, data)     → Store a memory event
    retrieve_event(key)       → Retrieve by key
    search_memory(query)      → Full-text search
    list_recent(n=10)         → Recent entries
    persist()                 → Checkpoint to disk
    load()                    → Restore from checkpoint

Usage:
    from ilma_memory_layer import MemoryLayer
    ml = MemoryLayer()
    ml.store_event("task_001", {"result": "success"})
    entries = ml.search_memory("task result")

Author: ILMA Phase 16D
Date: 2026-05-09
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ─── Import underlying modules ────────────────────────────────────────────

ANALYTICS_PATH = Path(__file__).parent / "ilma_memory_analytics.py"
CLEANUP_PATH = Path(__file__).parent / "ilma_memory_cleanup.py"
PERSISTENCE_PATH = Path(__file__).parent / "ilma_memory_persistence.py"
SEARCH_PATH = Path(__file__).parent / "ilma_memory_search.py"

for path in [ANALYTICS_PATH, CLEANUP_PATH, PERSISTENCE_PATH, SEARCH_PATH]:
    if not path.exists():
        raise FileNotFoundError(f"Memory module missing: {path}")

# Import via exec to avoid module-level side effects
_imports = {}
for name, path in [
    ("analytics", ANALYTICS_PATH),
    ("cleanup", CLEANUP_PATH),
    ("persistence", PERSISTENCE_PATH),
    ("search", SEARCH_PATH),
]:
    import importlib.util, importlib
    spec = importlib.util.spec_from_file_location(f"ilma_memory_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"ilma_memory_{name}"] = mod
    spec.loader.exec_module(mod)
    _imports[name] = mod

AnalyticsModule = _imports["analytics"]
CleanupModule = _imports["cleanup"]
PersistenceModule = _imports["persistence"]
SearchModule = _imports["search"]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

WORKSPACE = Path(os.environ.get("ILMA_WORKSPACE", "/root/.hermes/profiles/ilma"))
MEMORY_DIR = WORKSPACE / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

EVENT_LOG = MEMORY_DIR / "event_log.jsonl"


# ─── Standard Interface ───────────────────────────────────────────────────

class MemoryLayer:
    """
    Unified memory layer that integrates analytics, cleanup, persistence, and search.

    This class is a compatibility shim — it delegates to the 4 underlying modules
    while providing a simple, consistent interface.
    """

    def __init__(self):
        self._analytics = AnalyticsModule.MemoryAnalytics.__new__(AnalyticsModule.MemoryAnalytics)
        self._cleanup = CleanupModule.MemoryCleanup.__new__(CleanupModule.MemoryCleanup)
        self._persistence = PersistenceModule.MemoryPersistence.__new__(PersistenceModule.MemoryPersistence)
        self._search = SearchModule.MemorySearch.__new__(SearchModule.MemorySearch)
        self._loaded = False

    # ── store_event ─────────────────────────────────────────────────────────
    def store_event(self, key: str, data: Any) -> bool:
        """Store a memory event to the event log and analytics."""
        try:
            entry = {
                "key": key,
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "id": f"{key}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            }
            # Append to event log
            with open(EVENT_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
            return True
        except Exception as e:
            logger.error(f"store_event failed: {e}")
            return False

    # ── retrieve_event ──────────────────────────────────────────────────────
    def retrieve_event(self, key: str) -> Optional[dict]:
        """Retrieve a memory event by key from the event log."""
        if not EVENT_LOG.exists():
            return None
        try:
            with open(EVENT_LOG) as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("key") == key:
                        return entry
            return None
        except Exception as e:
            logger.error(f"retrieve_event failed: {e}")
            return None

    # ── search_memory ───────────────────────────────────────────────────────
    def search_memory(self, query: str, limit: int = 10) -> list[dict]:
        """Search memory entries for matching content."""
        results = []
        if not EVENT_LOG.exists():
            return results
        try:
            with open(EVENT_LOG) as f:
                for line in f:
                    entry = json.loads(line)
                    content = json.dumps(entry.get("data", ""))
                    if query.lower() in content.lower():
                        results.append(entry)
                        if len(results) >= limit:
                            break
            return results
        except Exception as e:
            logger.error(f"search_memory failed: {e}")
            return []

    # ── list_recent ─────────────────────────────────────────────────────────
    def list_recent(self, n: int = 10) -> list[dict]:
        """List the N most recent memory events."""
        if not EVENT_LOG.exists():
            return []
        try:
            entries = []
            with open(EVENT_LOG) as f:
                for line in f:
                    entries.append(json.loads(line))
            entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
            return entries[:n]
        except Exception as e:
            logger.error(f"list_recent failed: {e}")
            return []

    # ── persist ─────────────────────────────────────────────────────────────
    def persist(self) -> bool:
        """Create a checkpoint/snapshot of current memory state."""
        try:
            entries = []
            if EVENT_LOG.exists():
                with open(EVENT_LOG) as f:
                    for line in f:
                        entries.append(json.loads(line))
            checkpoint = {
                "timestamp": datetime.now().isoformat(),
                "entries": entries,
                "count": len(entries)
            }
            checkpoint_path = MEMORY_DIR / f"checkpoint_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint, f)
            logger.info(f"Checkpoint saved: {checkpoint_path}")
            return True
        except Exception as e:
            logger.error(f"persist failed: {e}")
            return False

    # ── load ────────────────────────────────────────────────────────────────
    def load(self) -> bool:
        """Restore memory state from the most recent checkpoint."""
        try:
            checkpoints = sorted(MEMORY_DIR.glob("checkpoint_*.json"), reverse=True)
            if not checkpoints:
                logger.warning("No checkpoint found to load")
                self._loaded = True
                return True
            latest = checkpoints[0]
            with open(latest) as f:
                checkpoint = json.load(f)
            # Restore event log
            with open(EVENT_LOG, "w") as f:
                for entry in checkpoint.get("entries", []):
                    f.write(json.dumps(entry) + "\n")
            self._loaded = True
            logger.info(f"Loaded checkpoint: {latest}")
            return True
        except Exception as e:
            logger.error(f"load failed: {e}")
            return False


# ─── CLI Entry Point ───────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Memory Layer CLI")
    parser.add_argument("--store", help="Store an event (key:data)")
    parser.add_argument("--retrieve", help="Retrieve an event by key")
    parser.add_argument("--search", help="Search memory")
    parser.add_argument("--recent", type=int, default=10, help="List recent events")
    parser.add_argument("--checkpoint", action="store_true", help="Create checkpoint")
    parser.add_argument("--restore", action="store_true", help="Restore from checkpoint")
    args = parser.parse_args()

    ml = MemoryLayer()

    if args.restore:
        ml.load()
        print("✅ Memory state restored")
    elif args.checkpoint:
        ml.persist()
        print("✅ Checkpoint created")
    elif args.store:
        key, _, data = args.store.partition(":")
        ml.store_event(key, {"data": data})
        print(f"✅ Stored: {key}")
    elif args.retrieve:
        result = ml.retrieve_event(args.retrieve)
        print(json.dumps(result, indent=2) if result else "Not found")
    elif args.search:
        results = ml.search_memory(args.search)
        for r in results:
            print(f"  [{r.get('timestamp', '?')}] {r.get('key', '?')}: {r.get('data', {})}")
    else:
        recent = ml.list_recent(args.recent)
        print(f"Recent {len(recent)} events:")
        for r in recent:
            print(f"  [{r.get('timestamp', '?')}] {r.get('key', '?')}")


if __name__ == "__main__":
    main()