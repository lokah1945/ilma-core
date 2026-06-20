#!/usr/bin/env python3
"""
ILMA Predictive Router v1.0 (Phase P / TASK 2.1)
================================================
Predicts best model BEFORE the request based on historical patterns.
- Pattern cache: task_type -> model_id
- Success history: model_id -> success_rate
- Message preview analysis (first 100 chars)

Feature flag: config.yaml `predictive_routing_enabled` (default: False — gradual rollout)
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("ilma.predict")


# Keyword patterns for message preview analysis
TASK_KEYWORDS = {
    "code": re.compile(r"\b(code|function|script|debug|fix|api|class|method|implement)\b", re.IGNORECASE),
    "analyze": re.compile(r"\b(analy[sz]e|research|investigate|compare|diagnose|evaluate|audit)\b", re.IGNORECASE),
    "translate": re.compile(r"\b(translate|translation|language|bahasa|terjemah)\b", re.IGNORECASE),
    "creative": re.compile(r"\b(write|story|poem|creative|design|brainstorm|ideate)\b", re.IGNORECASE),
    "summarize": re.compile(r"\b(summari[sz]e|summary|recap|condense|brief)\b", re.IGNORECASE),
    "math": re.compile(r"\b(math|equation|formula|calculate|solve|compute|integral)\b", re.IGNORECASE),
}


class PredictiveRouter:
    """Predicts best model for a task based on patterns and history."""

    def __init__(self, router=None, confidence_threshold: float = 0.8, history_window: int = 100):
        self.router = router
        self.confidence_threshold = confidence_threshold
        self.history_window = history_window
        # pattern_cache: task_type -> {predicted_model_id, success_count, total_count}
        self.pattern_cache: Dict[str, Dict] = {}
        # success_history: model_id -> deque of (1.0/0.0) for last N calls
        self.success_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_window))

    def predict_best_model(self, task_type: str, message_preview: str = "") -> Optional[str]:
        """Predict the best model for a task. Returns model_id or None if uncertain."""
        # 1. Check historical pattern
        if task_type in self.pattern_cache:
            pattern = self.pattern_cache[task_type]
            model_id = pattern.get("model_id")
            if model_id and pattern.get("total_count", 0) > 0:
                success_rate = pattern.get("success_count", 0) / pattern.get("total_count", 1)
                if success_rate >= self.confidence_threshold:
                    return model_id

        # 2. Analyze message preview
        if message_preview:
            detected_task = self._classify_message(message_preview)
            if detected_task != task_type and detected_task in self.pattern_cache:
                pattern = self.pattern_cache[detected_task]
                model_id = pattern.get("model_id")
                if model_id:
                    return model_id

        # 3. Fall back to keyword-based capability match
        if message_preview and self.router is not None:
            return self._keyword_match(message_preview)

        return None

    def _classify_message(self, preview: str) -> str:
        """Classify message by keyword analysis."""
        for task_name, pattern in TASK_KEYWORDS.items():
            if pattern.search(preview):
                return task_name
        return "general"

    def _keyword_match(self, preview: str) -> Optional[str]:
        """Match message to best model with that capability."""
        if not self.router or "providers" not in getattr(self.router, "master", {}):
            return None

        task = self._classify_message(preview)
        best_model = None
        best_score = 0.0

        for provider_name, provider in self.router.master.get("providers", {}).items():
            for model_id, model in provider.get("models", {}).items():
                if not model.get("is_free"):
                    continue
                capabilities = model.get("capabilities", []) or []
                if task in capabilities or "general" in capabilities:
                    score = model.get("composite_score", 0)
                    if score > best_score:
                        best_score = score
                        best_model = model_id
        return best_model

    def record_success(self, task_type: str, model_id: str, success: bool = True):
        """Record a routing outcome for future predictions."""
        if task_type not in self.pattern_cache:
            self.pattern_cache[task_type] = {"model_id": model_id, "success_count": 0, "total_count": 0}
        pattern = self.pattern_cache[task_type]
        pattern["total_count"] += 1
        if success:
            pattern["success_count"] += 1
        pattern["model_id"] = model_id  # Update to latest

        # Update per-model success history
        self.success_history[model_id].append(1.0 if success else 0.0)

    def get_stats(self) -> Dict:
        """Get predictive router statistics."""
        return {
            "patterns_learned": len(self.pattern_cache),
            "models_tracked": len(self.success_history),
            "pattern_cache": {
                k: {
                    "model_id": v["model_id"],
                    "success_rate": round(v["success_count"] / v["total_count"], 3) if v["total_count"] else 0,
                    "total_count": v["total_count"],
                }
                for k, v in self.pattern_cache.items()
            },
        }


# Singleton
_instance: Optional[PredictiveRouter] = None


def get_predictive_router(router=None) -> PredictiveRouter:
    global _instance
    if _instance is None:
        _instance = PredictiveRouter(router=router)
    return _instance


if __name__ == "__main__":
    pr = PredictiveRouter()
    # Simulate some training
    for _ in range(10):
        pr.record_success("chat", "01-ai/yi-large", success=True)
    for _ in range(2):
        pr.record_success("chat", "01-ai/yi-large", success=False)
    print("Predicted for 'chat':", pr.predict_best_model("chat", "Hello"))
    print("Stats:", pr.get_stats())
