#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         ILMA Unified Model Router v3.0 — SSS TIER                            ║
║  Deep-optimized end-to-end routing engine. Single Source of Truth:          ║
║  PROVIDER_INTELLIGENCE_MASTER.json + ilma_provider_health_state.json         ║
║                                                                              ║
║  FREE-ONLY POLICY (Bos 2026-06-18):                                          ║
║    nvidia, minimax, ollama (local), openrouter, blackbox, google, xai,     ║
║    bluesminds, groq, together                                                ║
║  PAID PROVIDERS: openai, anthropic, google (paid), meta, mistral, cohere,  ║
║                   amazon, microsoft-azure, ai21-labs, alibaba, deepseek,    ║
║                   useai, perplexity, xai, you                                ║
║  MIXED: openrouter (free sub-set), blackbox (free sub-set)                  ║
║                                                                              ║
║  Priority dispatch: nvidia > minimax > ollama > openrouter-free >           ║
║                    blackbox-free > xai > groq > together > bluesminds >     ║
║                    google                                                    ║
║                                                                              ║
║  Database: ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json        ║
║  Health:   ilma_provider_health_state.json (renamed 2026-06-18)            ║
║  Usage:    ilma_model_router_data/model_usage.jsonl                        ║
║                                                                              ║
║  ⛔ Bos 2026-06-18: legacy web service project FULLY REMOVED                 ║
║    - 4 subproviders (qwen, openaicodex, use, arena) = GONE                  ║
║    - port 8001 dead, no proxy process                                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

Version 3.0 changes:
  - is_active is PRIMARY filter (not free_tier)
  - HealthTracker._save() FIXED (was read-only write bug)
  - All 1340+ models pre-initialized in health state
  - Priority dispatch updated: 9 WORKING providers
  - Benchmark integration (quality_score + coding_score as primary signals)
  - Task-specific capability scoring with taxonomy support
  - Circuit breaker per model (3 consecutive failures = unavailable)
  - No-repeat freshness (30-min rotation window)
  - Multi-fallback chain per routing decision
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ILMA.RouterV3")

# ══════════════════════════════════════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════════════════════════════════════

ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
ROUTER_DATA   = ILMA_PROFILE / "ilma_model_router_data"
MASTER_DB     = ROUTER_DATA / "PROVIDER_INTELLIGENCE_MASTER.json"
HEALTH_FILE   = ILMA_PROFILE / "ilma_provider_health_state.json"  # ⛔ renamed 2026-06-18
USAGE_LOG     = ROUTER_DATA / "model_usage.jsonl"

# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER POLICIES — Bos free tier rules
# ══════════════════════════════════════════════════════════════════════════════

# Bos-mandated FREE providers — always enabled (Bos 2026-06-18)
FREE_PROVIDERS: set = {
    "nvidia",   # NIM free models — use IDs as-is (no nvidia/ prefix)
    "minimax",  # MiniMax-M2.7/2.5/2.1
    "ollama",   # local Ollama models
    "xai",      # xAI Grok models (api_key valid)
    "groq",     # Groq inference
    "together", # Together AI (free sub-set)
    "bluesminds", # Bluesminds proxy
    "google",   # Google Gemini (paid user free quota)
}

# Paid providers — blocked unless allow_paid=True
PAID_PROVIDERS: set = {
    "openai", "anthropic", "meta", "mistral", "cohere",
    "amazon", "microsoft-azure", "ai21-labs", "alibaba", "deepseek",
    "useai", "perplexity", "you",
}

# Mixed providers — only is_active=True models used
MIXED_PROVIDERS: set = {"openrouter", "blackbox"}  # opencode removed 2026-06-18

# Provider priority for dispatch (higher = tried first) — Bos 2026-06-18
PROVIDER_PRIORITY: Dict[str, int] = {
    # ── Priority 1: Bos-mandated free providers (9 WORKING) ────────────────────
    "nvidia":     100,   # NIM free models (verified)
    "minimax":     95,   # MiniMax-M2.7/2.5/2.1
    "ollama":      90,   # local models
    "xai":         85,   # xAI Grok
    "groq":        80,   # Groq inference
    "together":    75,   # Together AI
    "bluesminds":  70,   # Bluesminds proxy
    "google":      65,   # Google Gemini (free quota)
    # ── Priority 2: Mixed (only free sub-set) ─────────────────────────────────
    "openrouter":  60,   # free models (:free suffix)
    "blackbox":    55,   # free sub-set
    # ── Priority 3: Paid providers (only when allow_paid=True) ────────────────
    "deepseek":   50,
    "meta":       42,
    "mistral":    40,
    "cohere":     35,
    "alibaba":    30,
    "openai":     25,
    "anthropic":  20,
    "amazon":     18,
    "microsoft-azure": 15,
    "ai21-labs":  12,
    "useai":      10,
    "perplexity":  8,
    "xai":         6,
    "you":         4,
}

# Provider priority for dispatch (higher = tried first) — Bos 2026-06-18
# ══════════════════════════════════════════════════════════════════════════════

class TaskType(Enum):
    HEAVY_CODING    = "heavy_coding"
    MEDIUM_CODING   = "medium_coding"
    REASONING_XHIGH = "reasoning_xhigh"
    RESEARCH        = "research"
    FAST_TASKS      = "fast_tasks"
    GENERAL         = "general"
    SECURITY_REVIEW = "security_review"
    VISION          = "vision"
    WRITING         = "writing"
    CREATIVE        = "creative"
    PLANNING        = "planning"
    LONG_CONTEXT    = "long_context"

# ══════════════════════════════════════════════════════════════════════════════
# TASK → CAPABILITY HINTS (weighted scoring)
# ══════════════════════════════════════════════════════════════════════════════

TASK_CAPABILITY_HINTS: Dict[str, Dict[str, float]] = {
    "heavy_coding": {
        "coding": 0.35, "reasoning": 0.20, "backend": 0.15,
        "debugging": 0.10, "instruction_following": 0.10,
        "test_generation": 0.05, "code_review": 0.05,
    },
    "medium_coding": {
        "coding": 0.30, "backend": 0.15, "debugging": 0.15,
        "instruction_following": 0.15, "reasoning": 0.15,
        "test_generation": 0.05, "code_review": 0.05,
    },
    "reasoning_xhigh": {
        "reasoning": 0.40, "instruction_following": 0.20,
        "structured_output": 0.15, "research": 0.15,
        "long_context": 0.10,
    },
    "research": {
        "research": 0.35, "reasoning": 0.25, "analysis": 0.20,
        "long_context": 0.10, "structured_output": 0.10,
    },
    "fast_tasks": {
        "quick_response": 0.40, "instruction_following": 0.30,
        "reasoning": 0.20, "coding": 0.10,
    },
    "general": {
        "general": 0.40, "reasoning": 0.25, "instruction_following": 0.20,
        "creative": 0.15,
    },
    "security_review": {
        "security": 0.40, "reasoning": 0.25, "analysis": 0.20,
        "coding": 0.15,
    },
    "vision": {
        "vision": 0.40, "multimodal": 0.35, "reasoning": 0.25,
    },
    "writing": {
        "writing": 0.35, "creative": 0.25, "reasoning": 0.20,
        "instruction_following": 0.20,
    },
    "creative": {
        "creative": 0.40, "reasoning": 0.25, "writing": 0.20,
        "instruction_following": 0.15,
    },
    "planning": {
        "reasoning": 0.35, "analysis": 0.25, "planning": 0.25,
        "structured_output": 0.15,
    },
    "long_context": {
        "long_context": 0.40, "reasoning": 0.30, "analysis": 0.20,
        "research": 0.10,
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# CONTEXT REQUIREMENTS (per task type, in tokens)
# ══════════════════════════════════════════════════════════════════════════════

CONTEXT_REQUIREMENTS: Dict[str, int] = {
    "long_context":    100_000,
    "reasoning_xhigh":  50_000,
    "research":         50_000,
    "heavy_coding":     32_000,
    "medium_coding":    16_000,
    "planning":         32_000,
    "general":           8_000,
    "fast_tasks":        4_000,
    "writing":          16_000,
    "creative":         16_000,
    "vision":           16_000,
    "security_review":  32_000,
}

# ══════════════════════════════════════════════════════════════════════════════
# CAPABILITY TAXONOMY (capability hierarchy for scoring)
# ══════════════════════════════════════════════════════════════════════════════

CAPABILITY_TAXONOMY: Dict[str, List[str]] = {
    "coding":       ["coding", "code_generation", "code_completion", "code_review", "programming"],
    "reasoning":    ["reasoning", "problem_solving", "logical_thinking", "analysis"],
    "vision":       ["vision", "multimodal", "image_understanding", "visual_reasoning"],
    "writing":      ["writing", "creative_writing", "blog_writing", "documentation"],
    "research":     ["research", "information_retrieval", "fact_checking", "summarization"],
    "fast":         ["fast", "quick_response", "low_latency"],
    "safe":         ["safe", "safety", "content_moderation", "harmlessness"],
    "multilingual": ["multilingual", "translation", "multilingual_understanding"],
}

# ══════════════════════════════════════════════════════════════════════════════
# SCORING WEIGHTS
# ══════════════════════════════════════════════════════════════════════════════

SCORE_WEIGHTS = {
    "capability":   0.30,   # How well capabilities match task hints
    "quality":      0.25,   # Benchmark quality_score (0-100 → normalized)
    "context_fit":  0.15,   # Context window vs task requirement
    "provider":     0.15,   # Provider priority trust score
    "freshness":    0.10,   # No-repeat freshness (recent usage decay)
    "health":       0.05,   # Circuit breaker health bonus
}


# ══════════════════════════════════════════════════════════════════════════════
# MODEL CANDIDATE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ModelCandidate:
    model_id: str
    provider: str
    name: str
    composite_score: float
    capability_score: float
    quality_score: float
    context_fit_score: float
    provider_priority: float
    freshness_score: float
    health_score: float
    is_active: bool
    is_free: bool
    context_window: int
    coding_score: float
    capabilities: List[str]
    routing_reason: str
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "name": self.name,
            "composite_score": round(self.composite_score, 4),
            "capability_score": round(self.capability_score, 4),
            "quality_score": round(self.quality_score, 4),
            "context_fit_score": round(self.context_fit_score, 4),
            "provider_priority": round(self.provider_priority, 4),
            "freshness_score": round(self.freshness_score, 4),
            "health_score": round(self.health_score, 4),
            "is_active": self.is_active,
            "is_free": self.is_free,
            "context_window": self.context_window,
            "coding_score": self.coding_score,
            "capabilities": self.capabilities,
            "routing_reason": self.routing_reason,
            "latency_ms": round(self.latency_ms, 1),
        }


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING RESULT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RoutingResult:
    model_id: str
    provider: str
    composite_score: float
    routing_reason: str
    is_emergency: bool
    fallbacks: List[Dict[str, Any]]
    task_type: str
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "composite_score": round(self.composite_score, 4),
            "routing_reason": self.routing_reason,
            "is_emergency": self.is_emergency,
            "fallbacks": self.fallbacks,
            "task_type": self.task_type,
            "latency_ms": round(self.latency_ms, 1),
        }


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH TRACKER (FIXED _save bug)
# ══════════════════════════════════════════════════════════════════════════════

class HealthTracker:
    """
    Tracks model health for circuit breaker.
    FIXED: _save() now uses 'w' mode (was 'r' mode = write bug).
    """

    CIRCUIT_BREAKER_THRESHOLD = 3  # consecutive failures → unavailable

    def __init__(self, health_file: Path):
        self.health_file = health_file
        self._state: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if self.health_file.exists():
            try:
                with open(self.health_file) as f:
                    data = json.load(f)
                    self._state = data.get("models", {})
            except (json.JSONDecodeError, IOError):
                self._state = {}

    def _save(self):
        """FIXED: was using 'r' mode — now uses 'w' for actual writes."""
        try:
            with open(self.health_file, "w") as f:  # ← FIXED
                json.dump({"models": self._state}, f, indent=2)
        except IOError as e:
            logger.error(f"HealthTracker._save() failed: {e}")

    def get_status(self, model_id: str) -> str:
        return self._state.get(model_id, {}).get("status", "unknown")

    def is_healthy(self, model_id: str) -> bool:
        """Returns True if model is available (not circuit-broken)."""
        status = self.get_status(model_id)
        # Treat unknown as available (never-used = assume good)
        return status != "unavailable"

    def get_health_score(self, model_id: str) -> float:
        """
        Returns health score 0.0-1.0.
        1.0 = available (proven healthy), 0.6 = degraded (soft failures),
        0.3 = unknown (unproven — penalty to reflect no track record),
        0.0 = unavailable (circuit-tripped).
        
        PHASE A: unknown=0.3 (was 0.5) — unproven models get a scoring
        penalty so known-healthy models rank above them, but they are NOT
        blocked from routing (is_healthy() gate is separate).
        """
        status = self.get_status(model_id)
        if status == "available":
            return 1.0
        elif status == "unavailable":
            return 0.0
        elif status == "degraded":
            return 0.6
        else:
            return 0.3   # unknown = unproven — scoring penalty, not blocked

    def mark_success(self, model_id: str):
        entry = self._state.setdefault(model_id, {
            "status": "unknown",
            "consecutive_failures": 0,
            "total_failures": 0,
        })
        entry["status"] = "available"
        entry["consecutive_failures"] = 0
        entry["last_success"] = datetime.now().isoformat()
        self._save()

    def mark_failure(self, model_id: str, error: str = ""):
        entry = self._state.setdefault(model_id, {
            "status": "unknown",
            "consecutive_failures": 0,
            "total_failures": 0,
        })
        entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
        entry["total_failures"] = entry.get("total_failures", 0) + 1
        entry["last_failure"] = datetime.now().isoformat()
        entry["last_error"] = error[:200] if error else None

        # Circuit breaker: 3+ consecutive failures → unavailable
        if entry["consecutive_failures"] >= self.CIRCUIT_BREAKER_THRESHOLD:
            entry["status"] = "unavailable"
            logger.warning(f"Circuit breaker OPEN: {model_id} ({entry['consecutive_failures']} failures)")

        self._save()

    def get_freshness(self, model_id: str) -> float:
        """
        Returns freshness score 0.0-1.0 based on recency of last successful call.
        1.0 = never used (max freshness), 0.0 = used within last 5 min (rate-limited).
        """
        entry = self._state.get(model_id, {})
        last_success = entry.get("last_success")

        if not last_success:
            return 1.0  # Never used = max freshness

        try:
            last_time = datetime.fromisoformat(last_success)
            minutes_ago = (datetime.now() - last_time).total_seconds() / 60.0

            if minutes_ago < 2:
                return 0.2   # Very recent — likely rate-limited
            elif minutes_ago < 10:
                return 0.5   # Recent
            elif minutes_ago < 30:
                return 0.85  # Cooling down
            else:
                return 1.0   # Cold — fully refreshed
        except (ValueError, TypeError):
            return 1.0

    def get_circuit_state(self, model_id: str) -> Dict[str, Any]:
        """Return circuit breaker state for inspection."""
        entry = self._state.get(model_id, {})
        return {
            "status": entry.get("status", "unknown"),
            "consecutive_failures": entry.get("consecutive_failures", 0),
            "total_failures": entry.get("total_failures", 0),
            "last_success": entry.get("last_success"),
            "last_failure": entry.get("last_failure"),
        }


# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED MODEL ROUTER v3.0
# ══════════════════════════════════════════════════════════════════════════════

class UnifiedModelRouter:

    def _is_strictly_free(self, model_data: dict, provider_name: str) -> bool:
        """STRICT runtime free verification for every routed model."""
        def _num(v):
            if v is None or v == "":
                return 0.0
            if isinstance(v, str):
                vv = v.strip().lower().replace("$", "")
                if vv in {"", "0", "0.0", "0.00", "free", "none", "null"}:
                    return 0.0
                try:
                    return float(vv)
                except ValueError:
                    return 1.0
            try:
                return float(v)
            except (TypeError, ValueError):
                return 1.0

        model_id = str(model_data.get("model_id", ""))
        name = str(model_data.get("name", ""))
        if re.search(r"(^|[/:_\-\s])(paid|premium|pro|enterprise|plus|turbo|max|ultra)($|[/:_\-\s])",
                     f"{provider_name}/{model_id} {name}".lower()):
            return False

        pricing = model_data.get("pricing", {}) or {}
        prices = [pricing.get("input_per_1m"), pricing.get("output_per_1m"),
                  pricing.get("prompt"), pricing.get("completion"),
                  model_data.get("price_per_m_input"), model_data.get("price_per_m_output"),
                  model_data.get("input_cost_per_1m"), model_data.get("output_cost_per_1m")]
        if any(_num(v) > 0 for v in prices):
            return False

        billing = str(model_data.get("billing", "")).lower()
        if billing in {"paid", "subscription", "metered", "premium", "enterprise"}:
            return False

        if not (model_data.get("is_free") is True or model_data.get("free_tier") is True):
            return False

        if provider_name in MIXED_PROVIDERS:
            explicit_free = (":free" in model_id.lower()) or billing == "free" or model_data.get("free_tier") is True or (
                any(v is not None for v in prices) and all(_num(v) == 0 for v in prices)
            )
            if not explicit_free:
                return False

        return True

    """
    Single source of truth for model routing.
    Primary filter: is_active (from PROVIDER_INTELLIGENCE_MASTER.json)
    Health-aware: circuit breaker + freshness rotation
    Free-only by default (allow_paid=False)
    """

    DEFAULT_FALLBACK = "minimax/MiniMax-M2.7"

    def __init__(self, allow_paid: bool = False):
        self.allow_paid = allow_paid
        self._master: Dict[str, Any] = {}
        self._health = HealthTracker(HEALTH_FILE)
        self._usage_history: Dict[str, List[datetime]] = {}
        self._load_master()

    def _load_master(self):
        if not MASTER_DB.exists():
            logger.error(f"MASTER DB not found: {MASTER_DB}")
            return
        with open(MASTER_DB) as f:
            self._master = json.load(f)
        logger.info(f"Loaded MASTER: {len(self._master.get('providers', {}))} providers, "
                    f"{sum(len(v.get('models',{})) for v in self._master.get('providers',{}).values())} models")

    # ─── Public API ──────────────────────────────────────────────────────────

    def get_best_model(self, task_type: str) -> RoutingResult:
        """Route task to best model. Returns RoutingResult with fallbacks."""
        candidates = self._score_all_models(task_type)

        if not candidates:
            return self._emergency_result(task_type, "No candidates found")

        candidates.sort(key=lambda x: x.composite_score, reverse=True)

        best = candidates[0]
        fallbacks = [c.to_dict() for c in candidates[1:11]]  # Top 10 fallbacks

        return RoutingResult(
            model_id=best.model_id,
            provider=best.provider,
            composite_score=best.composite_score,
            routing_reason=best.routing_reason,
            is_emergency=False,
            fallbacks=fallbacks,
            task_type=task_type,
            latency_ms=best.latency_ms,
        )

    def route_for_task(self, task: str) -> RoutingResult:
        """Auto-detect task type then route."""
        task_type = detect_task_type(task)
        return self.get_best_model(task_type)

    def get_cascade(self, task_type: str, max_models: int = 5) -> List[RoutingResult]:
        """
        Get cascade of models — tries highest-priority providers first (nvidia,
        minimax, ollama, openrouter, blackbox), then falls back through priority chain.
        """
        results = []
        tried = set()

        # Score all models and sort by composite score
        all_candidates = self._score_all_models(task_type)
        all_candidates.sort(key=lambda x: x.composite_score, reverse=True)

        for candidate in all_candidates:
            full_id = f"{candidate.provider}/{candidate.model_id}"
            if full_id in tried:
                continue
            if len(results) >= max_models:
                break

            result = RoutingResult(
                model_id=candidate.model_id,
                provider=candidate.provider,
                composite_score=candidate.composite_score,
                routing_reason=candidate.routing_reason,
                is_emergency=False,
                fallbacks=[],
                task_type=task_type,
                latency_ms=candidate.latency_ms,
            )
            results.append(result)
            tried.add(full_id)

        return results[:max_models]

    # ─── Core scoring engine ─────────────────────────────────────────────────

    def _score_all_models(self, task_type: str) -> List[ModelCandidate]:
        """Score all active models for task type."""
        hints = TASK_CAPABILITY_HINTS.get(task_type, TASK_CAPABILITY_HINTS["general"])
        candidates = []

        for provider_name, provider_data in self._master.get("providers", {}).items():
            # Skip deprecated legacy sub-providers (Bos 2026-06-18)
            if provider_name.startswith("legacy_sub_"):
                continue

            # Provider-level filter
            is_paid_provider = provider_name in PAID_PROVIDERS
            is_free_provider = provider_name in FREE_PROVIDERS

            models = provider_data.get("models", {})

            for model_id, model_data in models.items():
                full_id = f"{provider_name}/{model_id}"

                # PRIMARY FILTER: is_active
                if not model_data.get("is_active", False):
                    continue

                # Hard disable support
                if model_data.get("disabled", False):
                    continue

                # Secondary filter: paid providers blocked unless allow_paid=True.
                # Strict free verification is mandatory in default mode.
                if not self.allow_paid and not self._is_strictly_free(model_data, provider_name):
                    continue

                # Health check — skip unavailable models
                if not self._health.is_healthy(full_id):
                    continue

                # ── Calculate sub-scores ───────────────────────────────────

                # 1. Capability match score
                cap_score = self._calc_capability_match(model_data, hints)

                # 2. Quality score from benchmarks (0-100 → 0.0-1.0)
                quality_score = self._calc_quality(model_data)

                # 3. Context fit score
                ctx_score = self._calc_context_fit(model_data, task_type)

                # 4. Provider priority score (0.0-1.0 normalized)
                prov_priority = PROVIDER_PRIORITY.get(provider_name, 50) / 100.0

                # 5. Freshness score (0.0-1.0)
                freshness = self._health.get_freshness(full_id)

                # 6. Health score (0.0-1.0)
                health_score = self._health.get_health_score(full_id)

                # ── Weighted composite ───────────────────────────────────
                composite = (
                    cap_score    * SCORE_WEIGHTS["capability"] +
                    quality_score * SCORE_WEIGHTS["quality"] +
                    ctx_score    * SCORE_WEIGHTS["context_fit"] +
                    prov_priority * SCORE_WEIGHTS["provider"] +
                    freshness    * SCORE_WEIGHTS["freshness"] +
                    health_score * SCORE_WEIGHTS["health"]
                )

                # Build capability list
                caps = model_data.get("capabilities", [])

                # Coding score bonus for coding tasks
                coding_bonus = 0.0
                if "coding" in hints:
                    coding_val = model_data.get("coding_score", 0)
                    if isinstance(coding_val, (int, float)):
                        coding_bonus = min(0.05, coding_val / 10000.0)  # max +0.05

                candidates.append(ModelCandidate(
                    model_id=model_id,
                    provider=provider_name,
                    name=model_data.get("name", model_id),
                    composite_score=composite + coding_bonus,
                    capability_score=cap_score,
                    quality_score=quality_score,
                    context_fit_score=ctx_score,
                    provider_priority=prov_priority,
                    freshness_score=freshness,
                    health_score=health_score,
                    is_active=model_data.get("is_active", False),
                    is_free=model_data.get("is_free", model_data.get("free_tier", False)),
                    context_window=model_data.get("context_window", 0),
                    coding_score=model_data.get("coding_score", 0),
                    capabilities=caps,
                    routing_reason=(
                        f"{task_type} → {provider_name}/{model_id} "
                        f"(cap={cap_score:.2f}, qual={quality_score:.2f}, "
                        f"ctx={ctx_score:.2f}, prov={prov_priority:.2f}, "
                        f"fresh={freshness:.2f})"
                    ),
                ))

        return candidates

    def _calc_capability_match(
        self, model_data: Dict, hints: Dict[str, float]
    ) -> float:
        """Calculate how well model capabilities match task requirements."""
        model_caps = set(model_data.get("capabilities", []))
        taxonomy = model_data.get("capability_taxonomy", {})

        total_weight = sum(hints.values())
        if total_weight == 0:
            return 0.0

        matched = 0.0

        for cap, weight in hints.items():
            if cap in model_caps:
                matched += weight
                continue
            # Taxonomy expansion — check sub-categories
            if cap in taxonomy:
                for sub_cap in taxonomy[cap]:
                    if sub_cap in model_caps:
                        matched += weight * 0.5
                        break

        return min(1.0, matched / total_weight)

    def _calc_quality(self, model_data: Dict) -> float:
        """
        Calculate normalized quality score 0.0-1.0.
        Priority: benchmark_profile.overall_score > quality_score > 0
        """
        bp = model_data.get("benchmark_profile", {})
        if bp:
            score = bp.get("overall_score") or bp.get("mmlu") or 0
            if score:
                return min(1.0, score / 100.0)

        qs = model_data.get("quality_score", 0)
        if qs:
            return min(1.0, qs / 100.0)

        return 0.0

    def _calc_context_fit(self, model_data: Dict, task_type: str) -> float:
        """Calculate how well context window fits task requirements."""
        ctx = model_data.get("context_window") or 0
        required = CONTEXT_REQUIREMENTS.get(task_type, 8000)

        if ctx >= required:
            return 1.0
        elif ctx >= required * 0.5:
            return 0.7
        elif ctx >= required * 0.25:
            return 0.4
        else:
            return 0.1

    # ─── Health management ──────────────────────────────────────────────────

    def mark_success(self, model_id: str):
        self._health.mark_success(model_id)
        if model_id not in self._usage_history:
            self._usage_history[model_id] = []
        self._usage_history[model_id].append(datetime.now())

    def mark_failure(self, model_id: str, error: str = ""):
        self._health.mark_failure(model_id, error)

    # ─── Query methods ──────────────────────────────────────────────────────

    def get_active_models(self) -> List[Tuple[str, str, str]]:
        """Return all active models as (provider, model_id, status)."""
        results = []
        for pname, pdata in self._master.get("providers", {}).items():
            if pname.startswith("legacy_sub_"):
                continue
            for mid, minfo in pdata.get("models", {}).items():
                if minfo.get("is_active", False):
                    full_id = f"{pname}/{mid}"
                    status = self._health.get_status(full_id)
                    results.append((pname, mid, status))
        return results

    def get_free_models_by_provider(self, provider: str) -> List[str]:
        return [
            mid for mid, mdata
            in self._master.get("providers", {}).get(provider, {}).get("models", {}).items()
            if mdata.get("is_active", False)
        ]

    def get_all_active_free_models(self) -> List[Tuple[str, str]]:
        results = []
        for pname, pdata in self._master.get("providers", {}).items():
            if pname.startswith("legacy_sub_") or pname in PAID_PROVIDERS:
                continue
            for mid, mdata in pdata.get("models", {}).items():
                if mdata.get("is_active", False):
                    results.append((pname, mid))
        return results

    def get_provider_summary(self) -> Dict[str, Dict[str, Any]]:
        summary = {}
        for pname, pdata in self._master.get("providers", {}).items():
            if pname.startswith("legacy_sub_"):
                continue
            models = pdata.get("models", {})
            total = len(models)
            active = sum(1 for m in models.values() if m.get("is_active", False))
            free = active  # is_active = is_free for our system
            summary[pname] = {
                "total_models": total,
                "active_models": active,
                "free_models": free,
                "paid_models": total - active,
                "priority": PROVIDER_PRIORITY.get(pname, 0),
                "is_paid_provider": pname in PAID_PROVIDERS,
                "is_free_provider": pname in FREE_PROVIDERS,
                "is_mixed_provider": pname in MIXED_PROVIDERS,
            }
        return summary

    # ─── Emergency fallback ─────────────────────────────────────────────────

    def _emergency_result(self, task_type: str, reason: str) -> RoutingResult:
        return RoutingResult(
            model_id=self.DEFAULT_FALLBACK,
            provider="minimax",
            composite_score=0.0,
            routing_reason=f"EMERGENCY_FALLBACK: {reason}",
            is_emergency=True,
            fallbacks=[],
            task_type=task_type,
        )


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON PATTERN
# ══════════════════════════════════════════════════════════════════════════════

_router_instance: Optional[UnifiedModelRouter] = None
_router_allow_paid_cache: bool = False


def get_router(allow_paid: bool = False) -> UnifiedModelRouter:
    """Get singleton router instance."""
    global _router_instance, _router_allow_paid_cache
    if _router_instance is None or _router_allow_paid_cache != allow_paid:
        _router_instance = UnifiedModelRouter(allow_paid=allow_paid)
        _router_allow_paid_cache = allow_paid
    return _router_instance


# ══════════════════════════════════════════════════════════════════════════════
# TASK TYPE DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def detect_task_type(message: str) -> str:
    """
    Auto-detect task type from message content.
    Used for automatic model selection when task_type not specified.
    """
    msg = message.lower()

    # ── Heavy coding (most specific → least specific order) ─────────────────
    if any(k in msg for k in [
        "refactor", "architecture", "microservice", "database schema",
        "api design", "system design", "complex algorithm", "redesign",
        "migration", "integration architecture", "distributed system",
        "performance optimization", "benchmark",
    ]):
        return "heavy_coding"

    # ── Security ─────────────────────────────────────────────────────────────
    if any(k in msg for k in ["security", "vulnerability", "penetration", "audit", "cve", "exploit"]):
        return "security_review"

    # ── Vision ────────────────────────────────────────────────────────────────
    if any(k in msg for k in ["image", "screenshot", "visual", "see", "look at", "foto", "gambar"]):
        return "vision"

    # ── Research ─────────────────────────────────────────────────────────────
    if any(k in msg for k in ["research", "survey", "compare", "evaluate", "analyze", "investigate"]):
        return "research"

    # ── Medium coding ─────────────────────────────────────────────────────────
    if any(k in msg for k in ["write code", "implement", "function", "class", "fix bug",
                              "add feature", "create script", "build", "coding", "debug",
                              "refactor", "optimize code", "algoritma"]):
        return "medium_coding"

    # ── Writing / documentation ───────────────────────────────────────────────
    if any(k in msg for k in ["write", "blog", "article", "post", "documentation",
                              "dokumentasi", "tulis", "artikel", "konten"]):
        return "writing"

    # ── Creative ─────────────────────────────────────────────────────────────
    if any(k in msg for k in ["creative", "story", "poem", "song", "write fiction",
                              "imagination", "brainstorm", "design", "fictional"]):
        return "creative"

    # ── Planning ─────────────────────────────────────────────────────────────
    if any(k in msg for k in ["plan", "strategy", "roadmap", "milestone", "schedule",
                              "project management", "organize", "approach"]):
        return "planning"

    # ── Long context ──────────────────────────────────────────────────────────
    if any(k in msg for k in ["long context", "long document", "book", "large file",
                              "konteks panjang", "dokumen panjang", "large codebase"]):
        return "long_context"

    # ── Reasoning ─────────────────────────────────────────────────────────────
    if any(k in msg for k in ["reasoning", "think", "logical", "prove", "reason",
                              "思考", "推理", "berpikir"]):
        return "reasoning_xhigh"

    # ── Fast tasks ────────────────────────────────────────────────────────────
    if any(k in msg for k in ["quick", "simple", "short", "quick question", "just",
                              "what is", "who is", "define", "explain briefly",
                              "apa itu", "siapa", "definisikan", "cepat"]):
        return "fast_tasks"

    # ── Default ──────────────────────────────────────────────────────────────
    return "general"


# ══════════════════════════════════════════════════════════════════════════════
# USAGE LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def log_usage(model_id: str, task_type: str, success: bool, latency_ms: float):
    """Append model usage to usage log."""
    entry = {
        "model_id": model_id,
        "timestamp": datetime.now().isoformat(),
        "task_type": task_type,
        "success": success,
        "latency_ms": latency_ms,
    }
    try:
        with open(USAGE_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except IOError as e:
        logger.error(f"log_usage() failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Unified Model Router v3.0")
    parser.add_argument("--task", help="Route a task to best model")
    parser.add_argument("--task-type", help="Direct task type override")
    parser.add_argument("--cascade", action="store_true", help="Show cascade of models")
    parser.add_argument("--list-providers", action="store_true", help="List all providers")
    parser.add_argument("--list-active", action="store_true", help="List all active models")
    parser.add_argument("--health", help="Check health of specific model")
    parser.add_argument("--paid", action="store_true", help="Allow paid models")
    parser.add_argument("--top", type=int, default=10, help="Show top N models")
    args = parser.parse_args()

    router = get_router(allow_paid=args.paid)

    if args.list_providers:
        print("📊 Provider Summary (v3.0)")
        print("=" * 70)
        summary = router.get_provider_summary()
        for pname, pdata in sorted(summary.items(), key=lambda x: x[1]["priority"], reverse=True):
            flags = []
            if pdata["is_free_provider"]:   flags.append("FREE")
            if pdata["is_paid_provider"]:   flags.append("PAID")
            if pdata["is_mixed_provider"]:  flags.append("MIXED")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"\n{pname}{flag_str} (priority={pdata['priority']})")
            print(f"   Total: {pdata['total_models']} | Active: {pdata['active_models']} "
                  f"| Free: {pdata['free_models']} | Paid: {pdata['paid_models']}")

    elif args.list_active:
        print("📋 All Active Models")
        print("=" * 70)
        active = router.get_all_active_free_models()
        print(f"Total active free models: {len(active)}\n")
        by_provider: Dict[str, List] = {}
        for pname, mid in active:
            by_provider.setdefault(pname, []).append(mid)
        for pname, models in sorted(by_provider.items(), key=lambda x: PROVIDER_PRIORITY.get(x[0], 0), reverse=True):
            print(f"{pname} ({len(models)}):")
            for m in sorted(models)[:3]:
                print(f"   - {m}")
            if len(models) > 3:
                print(f"   ... +{len(models)-3} more")
            print()

    elif args.health:
        hs = router._health.get_circuit_state(args.health)
        print(f"🏥 Health state for: {args.health}")
        for k, v in hs.items():
            print(f"   {k}: {v}")

    elif args.task:
        tt = args.task_type or detect_task_type(args.task)
        print(f"🎯 Task: {args.task}")
        print(f"   Detected type: {tt}\n")

        if args.cascade:
            results = router.get_cascade(tt, max_models=args.top)
            for i, r in enumerate(results):
                marker = "⭐" if i == 0 else "  "
                print(f"{marker} {i+1}. {r.provider}/{r.model_id}")
                print(f"      score={r.composite_score:.4f} | {r.routing_reason[:80]}")
                print()
        else:
            result = router.get_best_model(tt)
            print(f"✅ Best: {result.provider}/{result.model_id}")
            print(f"   Score: {result.composite_score:.4f}")
            print(f"   Reason: {result.routing_reason[:100]}")
            print(f"   Emergency: {result.is_emergency}")
            if result.fallbacks:
                print(f"\n🔄 Top 5 fallbacks:")
                for fb in result.fallbacks[:5]:
                    print(f"   - {fb['provider']}/{fb['model_id']} ({fb['composite_score']:.4f})")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()