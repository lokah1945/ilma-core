#!/usr/bin/env python3
"""
ILMA Distributed Lock v1.0
============================
Distributed locking for ILMA.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta

WORKSPACE = Path("/root/.hermes/profiles/ilma")
LOCK_DIR = WORKSPACE / ".locks"

class DistributedLock:
    """Distributed lock manager."""
    
    def __init__(self):
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
    
    def acquire(self, resource: str, ttl_seconds: int = 60) -> bool:
        lock_file = LOCK_DIR / f"{resource}.lock"
        if lock_file.exists():
            try:
                with open(lock_file) as f:
                    expiry = datetime.fromisoformat(json.load(f)["expiry"])
                if datetime.now() < expiry:
                    return False
            except Exception:
                pass
        
        with open(lock_file, "w") as f:
            json.dump({
                "resource": resource,
                "acquired": datetime.now().isoformat(),
                "expiry": (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()
            }, f)
        return True
    
    def release(self, resource: str) -> bool:
        lock_file = LOCK_DIR / f"{resource}.lock"
        if lock_file.exists():
            lock_file.unlink()
            return True
        return False
    
    def is_locked(self, resource: str) -> bool:
        lock_file = LOCK_DIR / f"{resource}.lock"
        if lock_file.exists():
            try:
                with open(lock_file) as f:
                    expiry = datetime.fromisoformat(json.load(f)["expiry"])
                return datetime.now() < expiry
            except Exception:
                pass
        return False

if __name__ == "__main__":
    dl = DistributedLock()
    print(json.dumps({"status": "ready"}, indent=2))
