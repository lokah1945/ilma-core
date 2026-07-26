#!/usr/bin/env python3
"""
ILMA Log Maintenance
Safely rotates JSONL logs (Quality Gate, Approval Queue, Shadow Eval) to prevent disk bloat.
"""
import os
import time
import gzip
import shutil
from pathlib import Path

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
LOGS_DIR = ILMA_ROOT / "logs"
APPROVAL_LOG = ILMA_ROOT / "approval_queue.jsonl"
SHADOW_LOG = ILMA_ROOT / "shadow_eval_log.jsonl"

MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

def rotate_file(filepath: Path):
    if not filepath.exists():
        return
    
    if filepath.stat().st_size > MAX_SIZE_BYTES:
        ts = int(time.time())
        archive_name = filepath.with_name(f"{filepath.name}.{ts}.gz")
        
        print(f"Rotating {filepath} -> {archive_name}")
        with open(filepath, 'rb') as f_in:
            with gzip.open(archive_name, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
                
        # Clear the original file safely
        open(filepath, 'w').close()

def cleanup_caches() -> int:
    """Run unified-cache TTL expiry + per-namespace LRU eviction (audit 2026-06-20:
    cleanup_expired/lru_evict existed but were never called -> unbounded growth)."""
    removed = 0
    try:
        import sys
        sys.path.insert(0, str(ILMA_ROOT))
        from ilma_unified_cache import get_cache
        cache = get_cache()
        removed += cache.cleanup_expired()
        for ns in list(cache.stats().keys()):
            removed += cache.lru_evict(ns)
        print(f"Cache cleanup: removed {removed} entries")
    except Exception as e:
        print(f"Cache cleanup skipped: {e}")
    return removed

def main():
    print("Running log maintenance...")
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logs_to_check = [
        APPROVAL_LOG,
        SHADOW_LOG,
        LOGS_DIR / "quality_gate.jsonl",
        LOGS_DIR / "agent.log",
        # audit 2026-06-20: these grew unbounded with no rotation
        LOGS_DIR / "router_traces.ndjson",
        LOGS_DIR / "autonomy.log",
        LOGS_DIR / "errors.log",
        LOGS_DIR / "gateway.log",
    ]

    for log in logs_to_check:
        rotate_file(log)

    cleanup_caches()
    print("Log maintenance complete.")

if __name__ == "__main__":
    main()
