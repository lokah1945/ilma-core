#!/usr/bin/env python3
"""
ILMA Dynamic Budget Allocator v1.0 (Phase P / TASK 4.1)
========================================================
Dynamic budget allocation based on task priority and time-of-day.
- Priority multipliers: critical=2.0, high=1.5, normal=1.0, low=0.5
- Off-peak discount: 20% (10pm-6am)
- Hourly budget cap with current-hour tracking

Feature flag: config.yaml `dynamic_budget_enabled` (default: False)
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("ilma.budget")

# Default config
DEFAULT_CONFIG = {
    "max_cost_per_hour": 1.0,
    "max_cost_per_day": 10.0,
    "priority_multipliers": {
        "critical": 2.0,
        "high": 1.5,
        "normal": 1.0,
        "low": 0.5,
    },
    "off_peak_discount": 0.8,
    "off_peak_hours": [22, 23, 0, 1, 2, 3, 4, 5],
    "alert_threshold": 0.80,
}

# Persistent tracking
COUNTERS_PATH = Path("/root/.hermes/profiles/ilma/data/budget_counters.json")


class DynamicBudgetAllocator:
    """Allocate budget dynamically based on priority and time of day."""

    def __init__(self, config: Optional[dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._load_counters()

    def _load_counters(self):
        """Load hourly/daily counters from disk."""
        try:
            if COUNTERS_PATH.exists():
                with open(COUNTERS_PATH) as f:
                    self._counters = json.load(f)
            else:
                self._counters = {"current_hour_cost": 0.0, "current_day_cost": 0.0,
                                  "hour_start": 0, "day_start": ""}
        except Exception as e:
            logger.warning(f"[Budget] Could not load counters: {e}")
            self._counters = {"current_hour_cost": 0.0, "current_day_cost": 0.0,
                              "hour_start": 0, "day_start": ""}

    def _save_counters(self):
        try:
            COUNTERS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(COUNTERS_PATH, "w") as f:
                json.dump(self._counters, f)
        except Exception as e:
            logger.warning(f"[Budget] Could not save counters: {e}")

    def _is_off_peak(self) -> bool:
        return datetime.now().hour in self.config["off_peak_hours"]

    def get_budget_for_task(self, task_type: str, priority: str = "normal") -> float:
        """Get the budget for a single task based on priority and time of day."""
        base = self.config["max_cost_per_hour"]
        multiplier = self.config["priority_multipliers"].get(priority, 1.0)

        if self._is_off_peak():
            multiplier *= self.config["off_peak_discount"]

        return base * multiplier

    def check_task_budget(self, task_type: str, estimated_cost: float,
                          priority: str = "normal") -> Tuple[bool, str]:
        """Check if a task is within its allocated budget."""
        # Reset counters if new hour/day
        now = datetime.now()
        if self._counters["hour_start"] != now.hour:
            self._counters["current_hour_cost"] = 0.0
            self._counters["hour_start"] = now.hour
        if self._counters["day_start"] != now.date().isoformat():
            self._counters["current_day_cost"] = 0.0
            self._counters["day_start"] = now.date().isoformat()

        # Hourly check
        task_budget = self.get_budget_for_task(task_type, priority)
        if self._counters["current_hour_cost"] + estimated_cost > task_budget:
            return False, f"Hourly budget exceeded: ${self._counters['current_hour_cost']:.4f} + ${estimated_cost:.4f} > ${task_budget:.4f}"

        # Daily check
        if self._counters["current_day_cost"] + estimated_cost > self.config["max_cost_per_day"]:
            return False, f"Daily budget exceeded: ${self._counters['current_day_cost']:.4f} + ${estimated_cost:.4f} > ${self.config['max_cost_per_day']:.4f}"

        return True, "OK"

    def record_cost(self, cost_usd: float):
        """Record actual cost after request completes."""
        self._counters["current_hour_cost"] += cost_usd
        self._counters["current_day_cost"] += cost_usd
        self._save_counters()

        # Alert at threshold
        alert_at = self.config["max_cost_per_day"] * self.config["alert_threshold"]
        if self._counters["current_day_cost"] >= alert_at:
            logger.warning(
                f"[Budget] ALERT: daily cost ${self._counters['current_day_cost']:.4f} "
                f"reached {self.config['alert_threshold']*100:.0f}% of ${self.config['max_cost_per_day']:.2f}"
            )

    def get_stats(self) -> dict:
        return {
            "current_hour_cost": round(self._counters["current_hour_cost"], 4),
            "current_day_cost": round(self._counters["current_day_cost"], 4),
            "hour_budget": self.get_budget_for_task("any", "normal"),
            "day_budget": self.config["max_cost_per_day"],
            "is_off_peak": self._is_off_peak(),
            "alert_threshold": self.config["alert_threshold"],
        }


# Singleton
_budget_instance: Optional[DynamicBudgetAllocator] = None


def get_budget_allocator() -> DynamicBudgetAllocator:
    global _budget_instance
    if _budget_instance is None:
        _budget_instance = DynamicBudgetAllocator()
    return _budget_instance


if __name__ == "__main__":
    ba = DynamicBudgetAllocator()
    print("=== Dynamic Budget Allocator Test ===\n")
    print("Stats:", ba.get_stats())

    # Test different priorities
    print("\n=== Budget by priority ===")
    for priority in ["critical", "high", "normal", "low"]:
        budget = ba.get_budget_for_task("chat", priority)
        print(f"  {priority:8s}: ${budget:.4f}/hour")

    # Test budget check
    print("\n=== Budget check tests ===")
    for cost in [0.001, 0.5, 1.5, 5.0, 15.0]:
        ok, reason = ba.check_task_budget("chat", cost, "normal")
        print(f"  Cost ${cost:.3f}: {'OK' if ok else 'BLOCKED'} ({reason})")

    # Record a cost
    print("\n=== Record cost ===")
    ba.record_cost(0.05)
    print(f"After $0.05: {ba.get_stats()}")
