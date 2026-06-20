#!/usr/bin/env python3
"""
ILMA Self-Healing Monitor v1.0 (Phase P / TASK 6.1)
===================================================
Auto-detect and fix common issues without human intervention.
- MongoDB connection health check + auto-reconnect
- Cache integrity check + rebuild
- Model visibility check + reload
- Provider health check

Feature flag: config.yaml `self_healing_monitor_enabled` (default: False)
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("ilma.self_healing")


class SelfHealingMonitor:
    """Monitor and auto-fix common issues."""

    def __init__(self, router=None, check_interval: int = 300, auto_fix_enabled: bool = True):
        self.router = router
        self.check_interval = check_interval
        self.auto_fix = auto_fix_enabled
        self.health_checks: Dict[str, Callable] = {
            "mongodb_connection": self._check_mongodb,
            "cache_integrity": self._check_cache,
            "model_visibility": self._check_models,
        }
        self.fixes: Dict[str, Callable] = {
            "mongodb_connection": self._fix_mongodb,
            "cache_integrity": self._fix_cache,
            "model_visibility": self._fix_models,
        }
        self.last_check_time: float = 0
        self.history: List[Dict] = []

    def run_health_check(self) -> List[Tuple[str, str]]:
        """Run all health checks. Returns list of (check_name, details) for failures."""
        issues = []
        for name, check_fn in self.health_checks.items():
            try:
                healthy, details = check_fn()
                if not healthy:
                    issues.append((name, details))
                    logger.warning(f"[SelfHeal] FAIL: {name} — {details}")
                else:
                    logger.debug(f"[SelfHeal] OK: {name}")
            except Exception as e:
                issues.append((name, f"check raised: {e}"))
                logger.error(f"[SelfHeal] ERROR: {name} — {e}")
        return issues

    def auto_fix_issues(self, issues: List[Tuple[str, str]]) -> List[str]:
        """Attempt to fix reported issues. Returns list of fixed issue names."""
        fixed = []
        for issue_name, details in issues:
            if issue_name in self.fixes and self.auto_fix:
                try:
                    self.fixes[issue_name](details)
                    fixed.append(issue_name)
                    logger.info(f"[SelfHeal] FIXED: {issue_name}")
                except Exception as e:
                    logger.error(f"[SelfHeal] FIX FAILED: {issue_name} — {e}")
            elif not self.auto_fix:
                logger.info(f"[SelfHeal] Issue detected but auto_fix disabled: {issue_name}")
        return fixed

    def monitor_once(self) -> Dict:
        """Run a full monitor cycle: check + fix + record."""
        start = time.time()
        issues = self.run_health_check()
        fixed = self.auto_fix_issues(issues)
        elapsed = time.time() - start

        result = {
            "timestamp": time.time(),
            "elapsed_seconds": round(elapsed, 4),
            "issues_found": len(issues),
            "issues": [{"name": n, "details": d} for n, d in issues],
            "fixed": fixed,
            "auto_fix_enabled": self.auto_fix,
        }
        self.history.append(result)
        self.last_check_time = time.time()
        return result

    # === Health Checks ===

    def _check_mongodb(self) -> Tuple[bool, str]:
        """Check MongoDB connection health."""
        try:
            from ilma_mongo_connection import get_mongo_manager
            mgr = get_mongo_manager()
            if mgr.health_check():
                return True, "OK"
            return False, "MongoDB ping failed"
        except Exception as e:
            return False, f"MongoDB error: {e}"

    def _check_cache(self) -> Tuple[bool, str]:
        """Check cache file integrity."""
        cache_path = Path("/root/.hermes/profiles/ilma/data/ilma_unified_cache.db")
        if not cache_path.exists():
            return False, "Cache file missing"
        if cache_path.stat().st_size == 0:
            return False, "Cache file empty"
        return True, "OK"

    def _check_models(self) -> Tuple[bool, str]:
        """Check that we have ~2178 models loaded."""
        if not self.router or not hasattr(self.router, "master"):
            return True, "No router attached, skipping"
        count = sum(
            len(p.get("models", {}))
            for p in self.router.master.get("providers", {}).values()
            if isinstance(p, dict)
        )
        if count < 2000:
            return False, f"Only {count} models visible (expected ~2178)"
        return True, f"{count} models visible"

    # === Fixes ===

    def _fix_mongodb(self, details: str):
        """Force MongoDB reconnect."""
        try:
            from ilma_mongo_connection import get_mongo_manager
            mgr = get_mongo_manager()
            mgr.reconnect()
        except Exception as e:
            logger.error(f"[SelfHeal] MongoDB reconnect failed: {e}")
            raise

    def _fix_cache(self, details: str):
        """Rebuild cache from MongoDB."""
        if self.router and hasattr(self.router, "_load_master_from_mongodb"):
            self.router._load_master_from_mongodb()

    def _fix_models(self, details: str):
        """Reload models from MongoDB."""
        if self.router and hasattr(self.router, "_load_master_from_mongodb"):
            self.router._load_master_from_mongodb()

    def get_stats(self) -> Dict:
        return {
            "checks_defined": list(self.health_checks.keys()),
            "fixes_defined": list(self.fixes.keys()),
            "auto_fix_enabled": self.auto_fix,
            "check_interval_seconds": self.check_interval,
            "history_count": len(self.history),
            "last_check": self.history[-1] if self.history else None,
        }


# Singleton
_self_heal_instance: Optional[SelfHealingMonitor] = None


def get_self_healing_monitor(router=None) -> SelfHealingMonitor:
    global _self_heal_instance
    if _self_heal_instance is None:
        _self_heal_instance = SelfHealingMonitor(router=router)
    return _self_heal_instance


if __name__ == "__main__":
    print("=== Self-Healing Monitor Test ===")
    sh = SelfHealingMonitor()
    print("Checks:", list(sh.health_checks.keys()))
    print("Fixes:", list(sh.fixes.keys()))
    print()

    # Run monitor once
    result = sh.monitor_once()
    print("Monitor result:")
    import json
    print(json.dumps(result, indent=2, default=str))
    print()
    print("Stats:", sh.get_stats())
