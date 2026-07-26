#!/usr/bin/env python3
"""
ILMA Feature Flags v1.0 (Phase P / TASK 5.2)
=============================================
Centralized feature flag management. All new Phase P features gated here.
- Default: ALL NEW FEATURES DISABLED (gradual rollout)
- Persistent to JSON file
- Can be enabled/disabled at runtime

Usage:
    from ilma_feature_flags import get_flags
    flags = get_flags()
    if flags.is_enabled("predictive_routing"):
        predicted = predictive_router.predict(...)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("ilma.feature_flags")

# Default flag values (NEW FEATURES DISABLED BY DEFAULT)
DEFAULT_FLAGS = {
    # Phase P features
    "predictive_routing": False,
    "adaptive_cache": False,
    "granular_circuit_breaker": True,  # Safe to enable
    "prometheus_metrics": False,
    "distributed_tracing": False,
    "dynamic_budget": False,
    "load_balancing": False,
    "ab_testing": False,
    "self_healing_monitor": False,
    "mongodb_connection_manager": True,  # Critical fix
    "sql_injection_validation": True,  # Critical fix
    # Existing
    "input_validation_enabled": True,
    # ── RISKY items staged behind flags (audit 2026-06-20) ──────────────────
    # Gate autonomy commit/push on validation passing (fail-safe ON: safer default).
    "autonomy_push_requires_validation": True,
    # Make domain validation BLOCKING + structural for high-criticality tasks.
    # Canary OFF by default — enable per-canary, then broaden.
    "domain_validation_blocking": False,
}

# Persistent storage
FLAGS_PATH = Path("/root/.hermes/profiles/ilma/data/feature_flags.json")


class FeatureFlags:
    """Centralized feature flag management."""

    def __init__(self):
        self.flags: Dict[str, bool] = dict(DEFAULT_FLAGS)
        self._load()

    def _load(self):
        try:
            if FLAGS_PATH.exists():
                with open(FLAGS_PATH) as f:
                    saved = json.load(f)
                self.flags.update(saved)
                logger.info(f"[FeatureFlags] Loaded {len(saved)} saved flags")
        except Exception as e:
            logger.warning(f"[FeatureFlags] Could not load: {e}")

    def _save(self):
        try:
            FLAGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(FLAGS_PATH, "w") as f:
                json.dump(self.flags, f, indent=2)
        except Exception as e:
            logger.warning(f"[FeatureFlags] Could not save: {e}")

    def is_enabled(self, flag_name: str) -> bool:
        return self.flags.get(flag_name, False)

    def enable(self, flag_name: str) -> bool:
        if flag_name not in DEFAULT_FLAGS:
            logger.warning(f"[FeatureFlags] Unknown flag: {flag_name}")
            return False
        self.flags[flag_name] = True
        self._save()
        logger.info(f"[FeatureFlags] ENABLED: {flag_name}")
        return True

    def disable(self, flag_name: str) -> bool:
        if flag_name not in DEFAULT_FLAGS:
            return False
        self.flags[flag_name] = False
        self._save()
        logger.info(f"[FeatureFlags] DISABLED: {flag_name}")
        return True

    def get_all(self) -> Dict[str, bool]:
        return dict(self.flags)

    def get_enabled(self) -> Dict[str, bool]:
        return {k: v for k, v in self.flags.items() if v}

    def reset(self):
        self.flags = dict(DEFAULT_FLAGS)
        self._save()
        logger.info("[FeatureFlags] Reset to defaults")


# Singleton
_flags_instance: Optional[FeatureFlags] = None


def get_flags() -> FeatureFlags:
    global _flags_instance
    if _flags_instance is None:
        _flags_instance = FeatureFlags()
    return _flags_instance


if __name__ == "__main__":
    flags = get_flags()
    print("=== Feature Flags ===")
    print(f"Total: {len(flags.get_all())}")
    print(f"Enabled: {len(flags.get_enabled())}")
    print()
    print("All flags:")
    for k, v in flags.get_all().items():
        marker = "✓" if v else "✗"
        print(f"  {marker} {k}: {v}")

    print()
    print("=== Toggle test ===")
    print(f"predictive_routing before: {flags.is_enabled('predictive_routing')}")
    flags.enable("predictive_routing")
    print(f"predictive_routing after enable: {flags.is_enabled('predictive_routing')}")
    flags.disable("predictive_routing")
    print(f"predictive_routing after disable: {flags.is_enabled('predictive_routing')}")
