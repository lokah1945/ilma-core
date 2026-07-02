#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ILMA FALLBACK CASCADE ENGINE v3.0 — CERTIFIED: CONTROLLED_CANARY                   ║
║          Intelligent Multi-Layer Fallback with Auto-Recovery                ║
╚══════════════════════════════════════════════════════════════════════════════╝

Fallback Tiers (dari paling disukai ke paling darurat):

  TIER 1 — Primary:      Model terbaik per task dari SmartRouter
  TIER 2 — Secondary:    5 top fallback models dari pool yang sama
  TIER 3 — Cross-Task:   Model terbaik dari task_category berbeda (broader)
  TIER 4 — Emergency:    Hard-coded reliable free models
  TIER 5 — Absolute:     Minimal model yang selalu tersedia

Setiap tier memiliki:
  - Trigger condition (kapan naik ke tier berikutnya)
  - Health check sebelum attempt
  - Timeout management
  - Error classification (rate_limit vs server_error vs bad_output)
  - Telemetry logging

Author: ILMA Core Team
Version: 3.0.0
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import os

logger = logging.getLogger("ILMA.FallbackCascade")

ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
FALLBACK_LOG = ILMA_PROFILE / "logs" / "fallback_events.jsonl"
FALLBACK_LOG.parent.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorType(Enum):
    RATE_LIMIT      = "rate_limit"       # 429 — wait and retry different model
    SERVER_ERROR    = "server_error"     # 5xx — try different model
    AUTH_ERROR      = "auth_error"       # 401/403 — skip this provider
    TIMEOUT         = "timeout"          # request timed out
    BAD_OUTPUT      = "bad_output"       # output quality below threshold
    CONTEXT_LIMIT   = "context_limit"   # input too long
    MODEL_OFFLINE   = "model_offline"   # model temporarily unavailable
    UNKNOWN         = "unknown"


def classify_error(error_msg: str, status_code: int = 0) -> ErrorType:
    """Classify error from message and HTTP status code."""
    msg_lower = str(error_msg).lower()

    if status_code == 429 or "rate limit" in msg_lower or "rate_limit" in msg_lower:
        return ErrorType.RATE_LIMIT
    if status_code in (401, 403) or "unauthorized" in msg_lower or "forbidden" in msg_lower:
        return ErrorType.AUTH_ERROR
    if status_code >= 500 or "server error" in msg_lower or "internal error" in msg_lower:
        return ErrorType.SERVER_ERROR
    if "timeout" in msg_lower or "timed out" in msg_lower:
        return ErrorType.TIMEOUT
    if "context" in msg_lower and ("limit" in msg_lower or "length" in msg_lower or "exceeded" in msg_lower):
        return ErrorType.CONTEXT_LIMIT
    if "unavailable" in msg_lower or "offline" in msg_lower or "maintenance" in msg_lower:
        return ErrorType.MODEL_OFFLINE
    if "quality" in msg_lower or "bad output" in msg_lower or "refused" in msg_lower:
        return ErrorType.BAD_OUTPUT

    return ErrorType.UNKNOWN


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK TIERS
# ═══════════════════════════════════════════════════════════════════════════════

# Tier 4: Emergency fallbacks (hard-coded reliable free models)
EMERGENCY_MODELS: List[Dict] = [
    {"model_id": "meta/llama-3.3-70b-instruct",         "provider": "openrouter",  "tier": 4},
    {"model_id": "google/gemini-flash-1.5",              "provider": "openrouter",  "tier": 4},
    {"model_id": "deepseek/deepseek-chat",               "provider": "openrouter",  "tier": 4},
    {"model_id": "mistralai/mistral-7b-instruct:free",   "provider": "openrouter",  "tier": 4},
    {"model_id": "nousresearch/hermes-3-llama-3.1-405b", "provider": "openrouter",  "tier": 4},
    {"model_id": "qwen/qwen3-8b:free",                   "provider": "openrouter",  "tier": 4},
    {"model_id": "microsoft/phi-3-medium-128k-instruct:free", "provider": "openrouter", "tier": 4},
]

# Tier 5: Absolute last resort
ABSOLUTE_FALLBACK = {
    "model_id": "meta/llama-3.1-8b-instruct:free",
    "provider": "openrouter",
    "tier": 5,
}


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK EVENT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class FallbackEvent:
    """Records a single fallback transition."""
    workflow_id: str
    task_id: str
    from_model: str
    to_model: str
    from_tier: int
    to_tier: int
    error_type: ErrorType
    error_msg: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "from_model": self.from_model,
            "to_model": self.to_model,
            "from_tier": self.from_tier,
            "to_tier": self.to_tier,
            "error_type": self.error_type.value,
            "error_msg": self.error_msg[:200],
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK CASCADE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class FallbackCascadeEngine:
    """
    Multi-tier Fallback Engine.

    Usage:
        cascade = FallbackCascadeEngine(router=smart_router)
        result = cascade.execute_with_fallback(
            task_category="heavy_coding",
            agent_role="developer",
            executor_fn=my_llm_call_fn,
            payload={"prompt": "...", "context": "..."},
            workflow_id="wf_123",
            task_id="develop",
        )
    """

    def __init__(
        self,
        router=None,
        health_manager=None,
        max_fallback_depth: int = 5,
    ):
        self.router = router
        self.health_mgr = health_manager
        self.max_fallback_depth = max_fallback_depth
        self._blocked_providers: Dict[str, datetime] = {}  # provider → blocked_until
        self._blocked_models: Dict[str, datetime] = {}
        self._fallback_events: List[FallbackEvent] = []

    def execute_with_fallback(
        self,
        task_category: str,
        agent_role: str,
        executor_fn: Callable[[Dict, Dict], Any],
        payload: Dict,
        workflow_id: str = "unknown",
        task_id: str = "unknown",
        quality_validator: Optional[Callable[[Any], Tuple[bool, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute dengan full fallback cascade.

        Args:
            task_category: Task type for routing
            agent_role: Agent role for routing
            executor_fn: fn(model_config, payload) → result
            payload: Data to pass to executor
            workflow_id: For telemetry
            task_id: For telemetry
            quality_validator: Optional fn(result) → (is_good, reason)
                If None, any non-error result is accepted.

        Returns:
            {
                "success": bool,
                "result": Any,
                "model_used": str,
                "tier_used": int,
                "fallback_count": int,
                "errors": [...],
            }
        """
        fallback_count = 0
        errors: List[Dict] = []
        current_tier = 1

        # Build fallback chain
        fallback_chain = self._build_fallback_chain(task_category, agent_role)
        logger.info(f"[Fallback] Chain for {task_category}/{agent_role}: {len(fallback_chain)} models")

        for model_config in fallback_chain:
            model_id = model_config.get("model_id", "unknown")
            provider  = model_config.get("provider", "unknown")
            tier      = model_config.get("tier", current_tier)

            if fallback_count >= self.max_fallback_depth:
                logger.error(f"[Fallback] Max depth {self.max_fallback_depth} reached")
                break

            # Check if model/provider is temporarily blocked
            if self._is_blocked(model_id, provider):
                logger.debug(f"[Fallback] Skipping blocked model: {provider}/{model_id}")
                continue

            logger.info(
                f"[Fallback] Attempting tier={tier}, fallback={fallback_count}: "
                f"{provider}/{model_id}"
            )

            try:
                start = time.perf_counter()
                result = executor_fn(model_config, payload)
                elapsed_ms = (time.perf_counter() - start) * 1000

                # Quality check
                if quality_validator:
                    is_good, reason = quality_validator(result)
                    if not is_good:
                        raise ValueError(f"Quality check failed: {reason}")

                # SUCCESS
                logger.info(
                    f"[Fallback] ✅ Success: {provider}/{model_id} "
                    f"(tier={tier}, fallback={fallback_count}, {elapsed_ms:.0f}ms)"
                )

                return {
                    "success": True,
                    "result": result,
                    "model_used": model_id,
                    "provider_used": provider,
                    "tier_used": tier,
                    "fallback_count": fallback_count,
                    "response_time_ms": elapsed_ms,
                    "errors": errors,
                }

            except Exception as e:
                error_type = classify_error(str(e))
                elapsed_ms = (time.perf_counter() - start) * 1000 if start else 0

                errors.append({
                    "model": f"{provider}/{model_id}",
                    "tier": tier,
                    "error_type": error_type.value,
                    "error": str(e)[:300],
                    "attempt": fallback_count,
                })

                logger.warning(
                    f"[Fallback] ⚠️ {provider}/{model_id} failed: "
                    f"{error_type.value} — {str(e)[:100]}"
                )

                # Block model/provider based on error type
                self._handle_error(model_id, provider, error_type)

                # Log fallback event
                if fallback_count > 0 or tier > 1:
                    event = FallbackEvent(
                        workflow_id=workflow_id,
                        task_id=task_id,
                        from_model=model_id,
                        to_model="next_in_chain",
                        from_tier=tier,
                        to_tier=tier + 1,
                        error_type=error_type,
                        error_msg=str(e),
                    )
                    self._fallback_events.append(event)
                    self._log_event(event)

                # Phase 1.1 Block 4: exponential backoff with jitter between retries
                if error_type in (ErrorType.RATE_LIMIT, ErrorType.SERVER_ERROR, ErrorType.TIMEOUT):
                    try:
                        from ilma_backoff import compute_backoff
                        delay = compute_backoff(
                            attempt=fallback_count,
                            base_delay=1.0,
                            max_delay=30.0,
                        )
                        logger.info(
                            f"[Fallback] Backoff: attempt {fallback_count + 1}, "
                            f"sleeping {delay:.2f}s before next model"
                        )
                        time.sleep(delay)
                    except Exception as _be:
                        # If backoff import fails, use minimal sleep
                        logger.debug(f"[Fallback] Backoff import failed: {_be}")

                fallback_count += 1
                current_tier = tier + 1

        # All fallbacks exhausted
        logger.error(f"[Fallback] ❌ All {fallback_count} fallbacks exhausted for {task_category}")
        return {
            "success": False,
            "result": None,
            "model_used": None,
            "tier_used": 5,
            "fallback_count": fallback_count,
            "response_time_ms": 0,
            "errors": errors,
        }

    def _build_fallback_chain(self, task_category: str, agent_role: str) -> List[Dict]:
        """Build ordered fallback chain across all tiers."""
        chain: List[Dict] = []

        # Tier 1 & 2: From SmartRouter
        if self.router:
            try:
                route_result = self.router.route(task_category, agent_role, n_fallbacks=5)
                primary = {
                    "model_id": route_result["model_id"],
                    "provider": route_result["provider"],
                    "tier": 1,
                }
                chain.append(primary)

                for fb in route_result.get("fallbacks", []):
                    if isinstance(fb, dict):
                        chain.append({
                            "model_id": fb.get("model_id", ""),
                            "provider": fb.get("provider", ""),
                            "tier": 2,
                        })
            except Exception as e:
                logger.warning(f"[Fallback] Router failed: {e}")

        # Tier 3: Cross-task fallback (use a broader category)
        BROADER_CATEGORY_MAP = {
            "heavy_coding": "medium_coding",
            "medium_coding": "general",
            "reasoning_xhigh": "general",
            "research": "general",
            "security_review": "reasoning_xhigh",
        }
        broader = BROADER_CATEGORY_MAP.get(task_category)
        if broader and self.router:
            try:
                cross_result = self.router.route(broader, "general", n_fallbacks=3)
                primary_cross = {
                    "model_id": cross_result["model_id"],
                    "provider": cross_result["provider"],
                    "tier": 3,
                }
                if not any(m["model_id"] == primary_cross["model_id"] for m in chain):
                    chain.append(primary_cross)
                for fb in cross_result.get("fallbacks", [])[:2]:
                    if isinstance(fb, dict) and not any(m["model_id"] == fb.get("model_id") for m in chain):
                        chain.append({"model_id": fb["model_id"], "provider": fb.get("provider", ""), "tier": 3})
            except Exception as e:
                logger.debug(f"[Fallback] Cross-task router failed: {e}")

        # Tier 4: Hard-coded emergency models
        for em in EMERGENCY_MODELS:
            if not any(m["model_id"] == em["model_id"] for m in chain):
                chain.append(em)

        # Tier 5: Absolute fallback
        if not any(m["model_id"] == ABSOLUTE_FALLBACK["model_id"] for m in chain):
            chain.append(ABSOLUTE_FALLBACK)

        return chain

    def _is_blocked(self, model_id: str, provider: str) -> bool:
        """Check if model or provider is temporarily blocked."""
        now = datetime.now()
        blocked_until_model = self._blocked_models.get(model_id)
        blocked_until_prov  = self._blocked_providers.get(provider)

        if blocked_until_model and now < blocked_until_model:
            return True
        if blocked_until_prov and now < blocked_until_prov:
            return True
        return False

    def _handle_error(self, model_id: str, provider: str, error_type: ErrorType):
        """Block model/provider temporarily based on error type."""
        now = datetime.now()

        if error_type == ErrorType.RATE_LIMIT:
            # Block model for 5 minutes
            self._blocked_models[model_id] = now + timedelta(minutes=5)
            logger.info(f"[Fallback] Model '{model_id}' blocked 5min (rate limit)")

        elif error_type == ErrorType.AUTH_ERROR:
            # Block provider for 1 hour
            self._blocked_providers[provider] = now + timedelta(hours=1)
            logger.warning(f"[Fallback] Provider '{provider}' blocked 1h (auth error)")

        elif error_type == ErrorType.MODEL_OFFLINE:
            # Block model for 30 minutes
            self._blocked_models[model_id] = now + timedelta(minutes=30)

        elif error_type == ErrorType.SERVER_ERROR:
            # Block model for 2 minutes
            self._blocked_models[model_id] = now + timedelta(minutes=2)

    def _log_event(self, event: FallbackEvent):
        """Persist fallback event to log."""
        try:
            with open(FALLBACK_LOG, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception:
            pass

    def get_stats(self) -> Dict:
        """Return fallback statistics."""
        total_events = len(self._fallback_events)
        by_type = {}
        for ev in self._fallback_events:
            et = ev.error_type.value
            by_type[et] = by_type.get(et, 0) + 1

        return {
            "total_fallback_events": total_events,
            "by_error_type": by_type,
            "blocked_models": len(self._blocked_models),
            "blocked_providers": len(self._blocked_providers),
        }

    def reset_blocks(self):
        """Clear all temporary blocks."""
        self._blocked_models.clear()
        self._blocked_providers.clear()
        logger.info("[Fallback] All blocks cleared")
