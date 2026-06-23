#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║       ILMA UNIFIED MODEL ROUTER v1.0 — CERTIFIED: CONTROLLED_CANARY         ║
║       Single Source of Truth: PROVIDER_INTELLIGENCE_MASTER.json             ║
╚══════════════════════════════════════════════════════════════════════════════╝

PRINSIP UTAMA:
  ✅ Hanya 1 file database: PROVIDER_INTELLIGENCE_MASTER.json
  ✅ Routing decisions berbasis evidence dari dalam database itu sendiri
  ✅ Benchmark score, capability scores, intelligence scores — semua EMBEDDED
  ✅ Tidak ada file tambahan (benchmark_database.json, free_model_rankings.json, dll)
  ✅ Health tracking via ilma_provider_health_state.json (runtime state, bukan data)
  ✅ Usage log via model_usage.jsonl (append-only log, bukan database)

SCORING ENGINE (per task type):
  1. capability_match_score — cocok nggak capability model dengan task requirements
  2. intelligence_score      — benchmark_profile.overall_score (kalau ada) atau
                                capabilities_detail.reasoning × 0.6 + quality_score × 0.4
  3. context_fit_score       — context_window cocok dengan task
  4. provider_trust_score    — historical reliability provider
  5. freshness_bonus         — avoid recently-used models (30 min window)

TASK TYPES: heavy_coding, medium_coding, reasoning_xhigh, research,
            fast_tasks, general, security_review, vision, writing,
            creative, planning, long_context

Author: ILMA Core Team
Version: 1.0.0
"""

from __future__ import annotations

# FIX 2026-06-21: suppress RequestsDependencyWarning globally (urllib3/chardet
# version mismatch from Debian-packaged requests — cosmetic, not functional).
import warnings as _w
_w.filterwarnings("ignore", message="urllib3.*", module="requests")

import json
import logging
import os
import random
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from functools import wraps

logger = logging.getLogger("ILMA.UnifiedRouter")


# ══════════════════════════════════════════════════════════════════════════════
# TIMEOUT EXCEPTION + WRAPPER (Phase 4F)
# ══════════════════════════════════════════════════════════════════════════════

class RoutingTimeoutError(Exception):
    """Raised when get_best_model() exceeds its timeout threshold."""
    pass


def _timeout_wrapper(func, timeout_seconds: float = 30.0, fallback_func=None):
    """
    Wrap a function with a threading.Timer-based timeout.

    If the function takes longer than timeout_seconds, a RoutingTimeoutError
    is raised in the calling thread. If fallback_func is provided, it is
    called instead of raising (useful for non-critical context where a default
    answer is acceptable).

    Uses threading.Timer so it works in any thread context (not just main).
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = [None]
        exc = [None]

        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exc[0] = e

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout=timeout_seconds)

        if t.is_alive():
            # Function is still running — timeout triggered
            if fallback_func is not None:
                logger.warning(f"[Router] {func.__name__} timed out after {timeout_seconds}s, returning fallback")
                return fallback_func()
            raise RoutingTimeoutError(f"{func.__name__} exceeded {timeout_seconds}s timeout")

        if exc[0] is not None:
            raise exc[0]

        return result[0]

    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
# PATHS — ALL DATA FROM SINGLE SOURCE
# ══════════════════════════════════════════════════════════════════════════════

# Force an ABSOLUTE profile path: if ILMA_PROFILE env is unset/relative/empty,
# fall back to the canonical absolute dir. A relative value made HEALTH_FILE
# resolve against cwd → "[Router] Failed to save health state: No such file..."
# whenever the router ran from a different cwd (e.g. a coding sandbox). (fix 2026-06-22)
_ILMA_PROFILE_ENV = os.environ.get("ILMA_PROFILE", "").strip()
ILMA_PROFILE = (Path(_ILMA_PROFILE_ENV)
                if _ILMA_PROFILE_ENV and os.path.isabs(_ILMA_PROFILE_ENV)
                else Path("/root/.hermes/profiles/ilma"))
ROUTER_DATA  = ILMA_PROFILE / "ilma_model_router_data"
MASTER_DB    = ROUTER_DATA / "PROVIDER_INTELLIGENCE_MASTER.json"
HEALTH_FILE  = ROUTER_DATA / "model_health_state.json"
USAGE_LOG    = ROUTER_DATA / "model_usage.jsonl"
TRACE_FILE   = ILMA_PROFILE / "logs" / "router_traces.ndjson"

# ══════════════════════════════════════════════════════════════════════════════
# FAILURE CLASSIFICATION + TIERED CIRCUIT BREAKER (Phase 4C-R Enhancement)
# ══════════════════════════════════════════════════════════════════════════════
# Classification of failure types (mirrors SubAgentRouter error_type values)
SOFT_FAILURES = {
    "transient_5xx",        # 502/503/504 — retry after short delay
    "temporary_network_error", # DNS/timeout — likely transient
    "rate_limit",            # 429 — retry after cooldown
}
HARD_FAILURES = {
    "malformed_response",    # non-JSON — model is sick, not transient
    "empty_content",         # model returned nothing — clear failure
    "schema_mismatch",       # response structure wrong — config error
    "unknown_error",         # generic unknown — treat as hard to be safe
}
RATE_LIMIT_FAILURES = {"rate_limit"}  # HTTP 429 — rotate key or cooldown
CRITICAL_FAILURES = {
    "authentication_error",  # 401 — key invalid/expired
    "permission_error",     # 403 — permission denied
}

# Tiered circuit breaker policy (Phase 4C-R)
class CircuitBreakerPolicy:
    """
    Tiered circuit breaker with failure-type-aware cooldown.
    Enhancement: replaces flat CIRCUIT_THRESHOLD=3 / CIRCUIT_COOLDOWN=300.
    """
    # Thresholds (consecutive failures)
    DEGRADE_THRESHOLD   = 3   # 3 failures → degraded (slow, not blocked)
    DISABLE_THRESHOLD   = 5   # 5 failures → temporarily disabled
    # Cooldowns per failure type (seconds)
    SOFT_COOLDOWN       = 10  # transient error → 10s pause
    DEGRADED_COOLDOWN   = 30  # 3-failure degraded → 30s wait
    DISABLED_COOLDOWN   = 90  # 5-failure disabled → 90s wait
    RATE_LIMIT_COOLDOWN = 60  # 429/key exhaustion → 60s
    CRITICAL_COOLDOWN   = 300 # auth error → 5min
    # For 1-timeout: use SOFT_COOLDOWN, not DISABLED_COOLDOWN
    TIMEOUT_COOLDOWN    = 10  # httpx timeout → 10s (1 timeout ≠ disable)

    @classmethod
    def classify_failure(cls, error_type: str) -> str:
        """Return: 'soft' | 'hard' | 'rate_limit' | 'critical'"""
        if error_type in RATE_LIMIT_FAILURES:
            return "rate_limit"
        if error_type in CRITICAL_FAILURES:
            return "critical"
        if error_type in HARD_FAILURES:
            return "hard"
        return "soft"

    @classmethod
    def get_cooldown(cls, failure_class: str, consecutive_failures: int,
                     is_timeout_once: bool = False) -> float:
        """Return cooldown in seconds based on failure class + count."""
        if is_timeout_once:
            return cls.TIMEOUT_COOLDOWN  # 1 timeout = 10s, not 90s
        if consecutive_failures >= cls.DISABLE_THRESHOLD:
            return cls.DISABLED_COOLDOWN
        if consecutive_failures >= cls.DEGRADE_THRESHOLD:
            return cls.DEGRADED_COOLDOWN
        if failure_class == "rate_limit":
            return cls.RATE_LIMIT_COOLDOWN
        if failure_class == "critical":
            return cls.CRITICAL_COOLDOWN
        if failure_class == "hard":
            return cls.DEGRADED_COOLDOWN
        return cls.SOFT_COOLDOWN  # soft failures: 10s only

# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER TRUST SCORES
# ══════════════════════════════════════════════════════════════════════════════

PROVIDER_BANNED = {"blackbox", "perplexity"}

# ── Dynamic callability gate (2026-06-01) ────────────────────────────────────
# Written by scripts/ilma_callability_validator.py. Providers proven UN-callable
# (e.g. no inference key) are skipped at routing time so the agent never wastes a
# turn on a model it cannot actually reach. Fail-open: if file missing, gate noop.
def _load_uncallable_providers() -> set:
    import json as _json, os as _os
    path = _os.path.join(_os.path.dirname(__file__),
                         "ilma_model_router_data", "provider_callability.json")
    try:
        with open(path) as _f:
            data = _json.load(_f)
        out = set()
        # Only direct cloud providers go into the callability gate. Legacy
        # proxy labels are not consulted (legacy proxy project removed).
        return out
    except Exception:
        return set()

PROVIDER_UNCALLABLE = _load_uncallable_providers()
PROVIDER_BANNED = PROVIDER_BANNED | PROVIDER_UNCALLABLE

# ── Runtime provider policy gates (FREE MODEL ONLY by default) ───────────────
FREE_PROVIDERS: Set[str] = {"nvidia", "minimax", "ollama"}
MIXED_PROVIDERS: Set[str] = {"openrouter", "blackbox", "opencode"}
PAID_PROVIDERS: Set[str] = {
    "openai", "anthropic", "google", "meta", "mistral", "cohere",
    "amazon", "microsoft-azure", "ai21-labs", "alibaba", "deepseek",
    "xai", "perplexity", "you", "together", "groq", "cerebras",
}
PAID_MODEL_KEYWORDS: Tuple[str, ...] = (
    "paid", "premium", "pro", "enterprise", "plus", "turbo", "max", "ultra"
)

def _safe_float_price(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, str):
        v = value.strip().lower().replace("$", "")
        if v in {"", "0", "0.0", "0.00", "free", "none", "null"}:
            return 0.0
        try:
            return float(v)
        except ValueError:
            return 1.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 1.0

def _has_paid_keyword(text: str) -> bool:
    text = (text or "").lower()
    return bool(re.search(r"(^|[/:_\-\s])(paid|premium|pro|enterprise|plus|turbo|max|ultra)($|[/:_\-\s])", text))

# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER TRUST SCORES
# ══════════════════════════════════════════════════════════════════════════════

# Provider trust — direct cloud providers only. Legacy proxy project removed.
_PROVIDER_TRUST_BASE = {
    "nvidia":        1.00,
    "openrouter":    0.95,
    "minimax":       0.90,
    "ollama":        0.92,    # Cloud — verified fast(0.4-1.3s)+free+high-IQ 2026-06-01
    "deepseek":      0.88,
    "alibaba":       0.85,
    "google":        0.80,
    "meta":          0.78,
    "mistral":       0.75,
    "openai":        0.70,
    "anthropic":     0.70,
    "cohere":        0.65,
    "ai21-labs":     0.65,
    "amazon":        0.62,
    "microsoft-azure": 0.60,
    "useai":         0.85,
    "xai":           0.75,
}

PROVIDER_TRUST: Dict[str, float] = _PROVIDER_TRUST_BASE

# ══════════════════════════════════════════════════════════════════════════════
# TASK → CAPABILITY REQUIREMENTS
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
        "reasoning": 0.25, "research": 0.25, "long_context": 0.20,
        "instruction_following": 0.15, "structured_output": 0.15,
    },
    "fast_tasks": {
        "speed": 0.30, "cost_efficiency": 0.25, "instruction_following": 0.20,
        "reasoning": 0.15, "coding": 0.10,
    },
    "general": {
        "reasoning": 0.25, "instruction_following": 0.25,
        "coding": 0.15, "structured_output": 0.15,
        "cost_efficiency": 0.20,
    },
    "security_review": {
        "security_review": 0.35, "reasoning": 0.25,
        "coding": 0.20, "instruction_following": 0.20,
    },
    "vision": {
        "vision": 0.40, "multimodal": 0.25,
        "reasoning": 0.15, "instruction_following": 0.10,
        "long_context": 0.10,
    },
    "audio": {
        "audio": 0.50, "multimodal": 0.25,
        "instruction_following": 0.15, "speed": 0.10,
    },
    "video": {
        "video": 0.55, "multimodal": 0.30, "instruction_following": 0.15,
    },
    "writing": {
        "reasoning": 0.30, "instruction_following": 0.25,
        "structured_output": 0.20, "research": 0.15,
        "cost_efficiency": 0.10,
    },
    "creative": {
        "reasoning": 0.30, "instruction_following": 0.25,
        "cost_efficiency": 0.20, "multimodal": 0.15,
        "structured_output": 0.10,
    },
    "planning": {
        "reasoning": 0.35, "instruction_following": 0.25,
        "structured_output": 0.20, "long_context": 0.10,
        "cost_efficiency": 0.10,
    },
    "long_context": {
        "long_context": 0.45, "reasoning": 0.20,
        "structured_output": 0.15, "instruction_following": 0.10,
        "cost_efficiency": 0.10,
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# TASK → SCORING WEIGHTS (composite score formula per dimension)
# ══════════════════════════════════════════════════════════════════════════════

TASK_WEIGHTS: Dict[str, Dict[str, float]] = {
    "heavy_coding":    {"capability": 0.35, "intelligence": 0.30, "context": 0.10, "trust": 0.15, "freshness": 0.10},
    "medium_coding":   {"capability": 0.30, "intelligence": 0.25, "context": 0.15, "trust": 0.15, "freshness": 0.15},
    "reasoning_xhigh": {"capability": 0.30, "intelligence": 0.35, "context": 0.10, "trust": 0.15, "freshness": 0.10},
    "research":        {"capability": 0.25, "intelligence": 0.30, "context": 0.15, "trust": 0.15, "freshness": 0.15},
    "fast_tasks":      {"capability": 0.20, "intelligence": 0.20, "context": 0.10, "trust": 0.20, "freshness": 0.30},
    "general":         {"capability": 0.25, "intelligence": 0.25, "context": 0.15, "trust": 0.20, "freshness": 0.15},
    "security_review": {"capability": 0.35, "intelligence": 0.30, "context": 0.10, "trust": 0.15, "freshness": 0.10},
    "vision":          {"capability": 0.40, "intelligence": 0.20, "context": 0.15, "trust": 0.15, "freshness": 0.10},
    "audio":           {"capability": 0.45, "intelligence": 0.20, "context": 0.10, "trust": 0.15, "freshness": 0.10},
    "video":           {"capability": 0.50, "intelligence": 0.15, "context": 0.10, "trust": 0.15, "freshness": 0.10},
    "writing":         {"capability": 0.30, "intelligence": 0.25, "context": 0.15, "trust": 0.15, "freshness": 0.15},
    "creative":        {"capability": 0.30, "intelligence": 0.25, "context": 0.15, "trust": 0.15, "freshness": 0.15},
    "planning":        {"capability": 0.30, "intelligence": 0.30, "context": 0.10, "trust": 0.15, "freshness": 0.15},
    "long_context":    {"capability": 0.25, "intelligence": 0.25, "context": 0.25, "trust": 0.15, "freshness": 0.10},
}

# ══════════════════════════════════════════════════════════════════════════════
# TASK DETECTION KEYWORDS
# ══════════════════════════════════════════════════════════════════════════════

TASK_KEYWORDS: Dict[str, List[str]] = {
    "heavy_coding": [
        "fullstack", "full-stack", "arsitektur", "platform", "microservice",
        "dari awal", "implement from scratch", "build from scratch",
        "rewrite", "migration", "kompleks", "system design",
    ],
    "medium_coding": [
        "api", "endpoint", "backend", "frontend", "function", "class",
        "script", "tool", "fix", "bug", "patch", "debug", "refactor",
        "add feature", "modify", "connect", "integration",
    ],
    "reasoning_xhigh": [
        "reasoning", "analisis", "planning", "strategi", "complex",
        "think", "pikir", "思考", "logika",
    ],
    "research": [
        "research", "deep", "cari", "investigat", "study",
        "analisis", "survey", "review", "find",
    ],
    "security_review": [
        "security", "pentest", "vulnerability", "audit",
        "injection", "exploit", "auth review",
    ],
    "vision": [
        "image", "gambar", "foto", "vision", "visual",
        "lihat", "analyze image", "ocr",
    ],
    "audio": [
        "audio", "suara", "voice", "speech", "tts", "transcribe",
        "transcription", "whisper", "music", "sound", "stt", "narasi",
    ],
    "video": [
        "video", "klip", "movie", "film", "animation", "animasi",
        "sora", "veo", "text-to-video", "generate video",
    ],
    "fast_tasks": [
        "fast", "quick", "ringkas", "cepat", "simple",
        "brief", "singkat",
    ],
}

TASK_ALIASES: Dict[str, str] = {
    "coding": "medium_coding",
    "code_generation": "medium_coding",
    "bug_fix": "medium_coding",
    "refactor": "medium_coding",
    "debug": "medium_coding",
    "complex_reasoning": "reasoning_xhigh",
    "analysis": "reasoning_xhigh",
    "deep_research": "research",
    "long_context_task": "long_context",
    "document_analysis": "research",
    "audit": "security_review",
    "creative_writing": "writing",
    "image_analysis": "vision",
    "speech": "audio",
    "tts": "audio",
    "transcription": "audio",
    "speech_to_text": "audio",
    "video_generation": "video",
    "text_to_video": "video",
    "writing": "writing",
}

# Tasks that REQUIRE a specialist: a model lacking the capability is hard-excluded
# from the candidate pool (with graceful fallback if no specialist exists).
# Non-chat endpoints/caps — excluded from chat/text routing (BUG-2 fix). These serve
# /v1/{rerank,embeddings,images,video,audio,moderations}, not /v1/chat/completions.
_NON_CHAT_ENDPOINTS = {"rerank", "reranking", "embeddings", "embedding", "moderations",
                       "image-generations", "image-edits", "video-generations",
                       "audio-speech", "audio-transcriptions"}
_NON_CHAT_CAPS = {"rerank", "embedding", "image", "image_edit", "video", "tts", "stt",
                  "music", "safety_filter"}
# model-id substrings that mark a non-chat specialist (MASTER may lack endpoint_type)
_NON_CHAT_ID_PATTERNS = ("rerank", "reranker", "embed", "embedqa", "nv-embed", "bge-",
                         "-tts", "tts-", "/tts", "whisper", "stable-diffusion", "sdxl",
                         "flux", "dall-e", "-asr", "parakeet", "magpie", "moderation",
                         "-guard", "nemoretriever", "arctic-embed")

HARD_CAPABILITY_TASKS: Dict[str, str] = {
    "vision": "vision", "audio": "audio", "video": "video",
}


# ══════════════════════════════════════════════════════════════════════════════
# ILMA UNIFIED MODEL ROUTER
# ══════════════════════════════════════════════════════════════════════════════

class ILMAUnifiedRouter:
    """
    Unified Model Router — satu engine untuk semua kebutuhan routing.

    SOT: PROVIDER_INTELLIGENCE_MASTER.json
    - 1,341 models, 25 providers
    - All scores embedded: benchmark_profile, capabilities_detail, subagent_specialization
    - No external benchmark files needed

    Workflow per routing call:
      1. classify_task() — detect task type dari description
      2. build_candidate_pool() — filter free + active models
      3. score_candidates() — compute composite score per model
      4. apply_health_filter() — skip rate-limited/unhealthy
      5. apply_no_repeat() — avoid recently-used models
      6. sort_and_return() — ranked by composite_score
    """


    def _is_strictly_free(self, model_data: Dict, provider_name: str) -> bool:
        """Runtime free check — reads the FINAL precomputed verdict from the models SOT.

        The trap-safe free/paid decision (force_free hardcode, mixed-provider ':free'/
        '-free' suffix rules, direct-provider price/flags) is computed ONCE at sync/enrich
        time by sot/enrichment/sot_billing_classify.py and stored on each models doc as
        `is_free`. Runtime just reads the boolean — no per-request computation, no
        delay. When the field is absent (a model not yet classified) default to PAID,
        which is the trap-safe stance ("not explicitly free → paid").
        """
        if "is_free" in model_data:
            return model_data.get("is_free") is True
        # Pre-classification docs: trap-safe default → PAID (is_free is the only gate;
        # provider-level free override lives in T1 free_bypass, applied at classify time).
        return False

    def is_model_runtime_allowed(self, provider: str, model_id: str, allow_paid: bool = False) -> bool:
        """Validate a concrete provider/model before execution or manual override."""
        provider = (provider or "").strip()
        model_id = (model_id or "").strip()
        master = self._load_master()
        pdata = master.get("providers", {}).get(provider, {})
        if pdata.get("disabled", False):
            return False
        models = pdata.get("models", {})
        candidates = [model_id]
        if model_id.startswith(provider + "/"):
            candidates.append(model_id[len(provider)+1:])
        found = None
        found_mid = None
        for mid in candidates:
            if mid in models:
                found = models[mid]
                found_mid = mid
                break
        if found is None:
            return False
        if found.get("disabled", False) or found.get("deprecated", False):
            return False
        if found.get("is_active") is not True:
            return False
        model_copy = dict(found)
        model_copy["model_id"] = found_mid or model_id
        model_copy["provider"] = provider
        return True if allow_paid else self._is_strictly_free(model_copy, provider)

    def __init__(self, allow_paid: bool = False):
        self.allow_paid = allow_paid
        self._lock = __import__("threading").RLock()

        # Caches — auto-invalidate on master DB change
        self._master_cache: Optional[Dict] = None
        self._master_mtime: float = 0
        self._health_cache: Optional[Dict] = None
        self._health_mtime: float = 0
        self._recent_used: Dict[str, datetime] = {}

        # Circuit breaker
        self._failure_count: Dict[str, int] = {}
        self._cooldown_until: Dict[str, float] = {}
        self.CIRCUIT_THRESHOLD = 3
        self.CIRCUIT_COOLDOWN = 300  # seconds

        # ── PHASE 1: LATENCY OPTIMIZATION — CANDIDATE POOL CACHE ─────────────
        # LRU-style cache for candidate pool results. Key = (task_type, allow_paid).
        # TTL = 120s. This eliminates redundant _build_candidate_pool calls for
        # repeated queries, reducing routing latency from ~22ms → ~6ms.
        self._candidate_cache: Dict[str, Dict] = {}   # "task:free" → {candidates, ts}
        self._CACHE_TTL: float = 120.0                # seconds

        # ── PHASE 2: SAFE EXPLORATION — CONSECUTIVE FAILURE TRACKING ───────────
        # Track consecutive failures per model for auto-disable during exploration
        self._exploration_failures: Dict[str, int] = {}  # model_id → consecutive_failures
        self.EXPLORATION_MAX_FAILURES = 3               # auto-disable after N failures

        # ── PHASE 4: PROVIDER DIVERSITY TRACKING (Anti-monopoly) ──────────────
        # Rolling window of recent provider selections for diversity-aware routing.
        # Prevents any single provider from dominating >60% of traffic.
        # maxlen=20 means diversity penalty activates after ~8 same-provider selections.
        from collections import deque
        self._provider_rolling: deque = deque(maxlen=20)

        # ── PHASE 3: REAL-TIME FEEDBACK LOOP — USAGE LOGGING ───────────────────
        # In-memory accumulation of usage stats. Written to disk periodically
        # via flush_usage_updates() to avoid per-request disk I/O.
        self._pending_usage: Dict[str, Dict] = {}  # model_id → {total, success, fail, latencies}
        self._usage_flush_threshold = 50           # flush after N pending entries
        self.USAGE_FILE = ROUTER_DATA / "model_usage.jsonl"

        # ── PHASE 4: PRE-COMPUTED COMPOSITE SCORES ──────────────────────────────────
        # Pre-compute composite_score for every (model_id, task_type) pair at init.
        # This eliminates ~520 score computations per new task_type seen at runtime.
        # Key = "task_type:allow_paid" (e.g. "heavy_coding:free")
        # Value = sorted list of (model_id, provider, base_composite_score)
        # Dynamic: freshness + health multipliers applied at runtime.
        self._precomputed: Dict[str, List[Tuple[str, str, float]]] = {}
        self._precomputed_ts: float = 0.0

        # Lazy pre-compute — triggered on first score lookup for each task_type.
        # This runs once per task_type, results cached for the session.
        self._TASK_TYPES_TO_PRECOMPUTE = list(TASK_WEIGHTS.keys())  # all 8 types

        logger.info(f"[Router] Initialized | allow_paid={allow_paid}")

    # ══════════════════════════════════════════════════════════════════════════
    # DATA LOADERS
    # ══════════════════════════════════════════════════════════════════════════

    def _load_master(self) -> Dict:
        """
        v7.0: Load PROVIDER_INTELLIGENCE_MASTER equivalent from MongoDB.
        100% MongoDB-driven — no JSON fallback per v7.0 spec.

        MongoDB collections queried:
          - model_intelligence  (per-model score, tier, capabilities, context)
          - models              (per-model variant metadata, normalized_model)
          - providers           (provider config: free_tier, base_url, status)
          - llm_providers       (api_key, base_url — separate from providers)

        Returned shape mirrors the JSON legacy file (for backward compat):
          {
            "providers": { provider_name: { models: {...}, free_tier, base_url, status, ... } },
            "routing_rules": {...}
          }
        """
        with self._lock:
            now = time.time()
            # 30s TTL cache for MongoDB load
            if (self._master_cache is not None
                    and self._master_mtime is not None
                    and (now - self._master_mtime) < 30):
                return self._master_cache

            try:
                master = self._load_master_from_mongodb()
                self._master_cache = master
                self._master_mtime = now
                self._master_source = "mongodb"
                n_providers = len(master.get("providers", {}))
                logger.debug(f"[Router] MASTER loaded from mongodb: {n_providers} providers")
            except Exception as e:
                # v7.0: ZERO JSON FALLBACK. If MongoDB fails, raise loudly so the
                # operator notices — do NOT silently fall back to a stale JSON.
                logger.error(f"[Router] MongoDB master load FAILED: {e}")
                raise RuntimeError(
                    f"v7.0: 100% MongoDB-driven — cannot fall back to JSON. "
                    f"MongoDB error: {e}"
                ) from e
            return self._master_cache

    def _load_master_from_mongodb(self) -> Dict:
        """
        v7.0: Build the MASTER equivalent dict from 4 MongoDB collections.

        Joins:
          model_intelligence (intel) ← models (1:1 by model_id)
                                ← providers (1:1 by provider)
                                ← llm_providers (1:0..1 by provider, for api_key/base_url)
        """
        from pymongo import MongoClient

        # FIX 2026-06-21: Use MongoConnectionManager defaults (no hardcoded IP).
        # The manager reads ILMA_MONGO_HOST/ILMA_MONGO_PASS from env or .env.
        from ilma_mongo_connection import get_mongo_manager
        mgr = get_mongo_manager()
        self._mongo_client = mgr.get_client()
        db_mongo = self._mongo_client["credentials"]

        # Pull all needed docs in 4 queries (1 per collection)
        intel_docs = list(db_mongo["model_intelligence"].find(
            {}, {"_id": 0}
        ))
        model_docs = list(db_mongo["models"].find(
            {}, {"_id": 0}
        ))
        provider_docs = list(db_mongo["providers"].find(
            {}, {"_id": 0}
        ))
        llm_provider_docs = list(db_mongo["llm_providers"].find(
            {}, {"_id": 0}
        ))

        # Build lookup tables
        models_by_id = {m.get("model_id"): m for m in model_docs if m.get("model_id")}
        providers_by_name = {p.get("provider"): p for p in provider_docs if p.get("provider")}
        # FIX 2026-06-19: multi-key providers (notably openrouter: inference + provisioning)
        # have several llm_providers docs. The MASTER api_key is used for MODEL INVOCATION,
        # so prefer an inference-capable key and never fall back to a provisioning-only key.
        # A naive dict comprehension kept whichever doc came last (could be provisioning).
        _PURPOSE_RANK = {"inference": 0, "primary": 1, "secondary": 2,
                         "experimental": 3, None: 4, "backup": 5, "provisioning": 9}
        llm_by_name: Dict[str, Dict] = {}
        for p in llm_provider_docs:
            name = p.get("provider")
            if not name:
                continue
            cur = llm_by_name.get(name)
            if cur is None or (_PURPOSE_RANK.get(p.get("key_purpose"), 4)
                               < _PURPOSE_RANK.get(cur.get("key_purpose"), 4)):
                llm_by_name[name] = p

        # v7.1: count tier auto-fixes for one summary log instead of 819 separate warnings
        _mismatch_count = 0

        # Group models by provider (loop over model_docs to ensure 2,178 visible)
        master = {"providers": {}, "routing_rules": {}}
        # Build intel lookup once
        intel_by_id = {i.get("model_id"): i for i in intel_docs if i.get("model_id")}
        for model in model_docs:
            model_id = model.get("model_id")
            provider_name = model.get("provider")
            if not model_id or not provider_name:
                continue
            intel = intel_by_id.get(model_id, {})
            model_meta = model
            prov_meta = providers_by_name.get(provider_name, {})
            llm_meta = llm_by_name.get(provider_name, {})

            # Validate / fix score_tier vs composite_score
            # FIX 2026-06-21: auto-derive tier from score instead of logging 819 warnings.
            # DB `score_tier` may drift from actual composite_score; the record uses
            # `tier or expected_tier` (line 700) anyway, so the mismatch is cosmetic.
            # Downgrade to DEBUG; the first occurence per tier logged at INFO for visibility.
            score = intel.get("composite_score", 0.0) or 0.0
            tier = intel.get("score_tier", "")
            expected_tier = (
                "A" if score >= 60 else
                "B" if score >= 45 else
                "C" if score >= 35 else "D"
            )
            if tier != expected_tier:
                # v7.1: no longer WARNING — auto-corrected in record; one summary after loop
                logger.debug(f"[Router] tier auto-fix: {model_id} {tier}→{expected_tier} score={score}")
                _mismatch_count += 1

            # Compose the model record (subset of fields used by router)
            record = {
                "model_id":           model_id,
                "normalized_model":   intel.get("normalized_model") or model_meta.get("normalized_model", ""),
                "original_model_id":  model_meta.get("original_model_id", model_id),
                "provider":           provider_name,
                "status":             intel.get("status", "active"),
                "is_active":          intel.get("is_active", True),
                "is_free":            model_meta.get("is_free", intel.get("is_free", llm_meta.get("free_bypass", False))),  # Phase R: per-model is_free from models collection (authoritative)
                # FINAL free/paid verdict precomputed in the models SOT (sot_billing_classify).
                # This is what the runtime free gate reads — trap-safe, zero runtime cost.
                "is_free":      model_meta.get("is_free", False),
                "composite_score":    score,
                "score_tier":         tier or expected_tier,  # FIX 2026-06-19: ~1336 models have no intel doc → intel={}; hard intel["score_tier"] crashed the whole mongo MASTER build. Use computed tier (line above) / score-derived fallback.
                "context_window":     model_meta.get("context_window", 4096),  # Phase 1.2: models collection authoritative
                "capabilities":       intel.get("capabilities", model_meta.get("capabilities", [])),
                # FIX 2026-06-20: feed the enriched scoring SOT to the router. `score`
                # (0..100 composite) is consumed by _get_intelligence_score priority 0b;
                # `capabilities_detail` drives _get_capability_match_score. Without these
                # the router collapsed both signals to 0.5 and ranked by provider trust.
                "score":              score,  # = intel composite_score (0..100)
                "capabilities_detail": intel.get("capabilities_detail", {}),
                "price_per_m_input":  model_meta.get("price_per_m_input", 0.0),
                "price_per_m_output": model_meta.get("price_per_m_output", 0.0),
                "benchmark_aa":       intel.get("benchmark_aa", {}),
                "benchmark_profile":  intel.get("benchmark_profile", {}),
                "quality_score":      intel.get("quality_score", 0.0),
                "enriched_at":        intel.get("enriched_at", ""),
                # Provider context
                "free_bypass":        prov_meta.get("free_bypass", False),
                # Hardcode free override (providers.force_free) — admin marks a provider
                # as free regardless of real billing (e.g. minimax paid plan, nvidia/ollama).
                "free_bypass":        prov_meta.get("free_bypass", False),
                "base_url":           llm_meta.get("base_url") or prov_meta.get("base_url", ""),
                "api_key":            llm_meta.get("api_key", ""),  # present in master for routing context
                "provider_status":    prov_meta.get("status", "active"),
            }
            # v7.0: if score is missing/zero, compute from sub-scores
            if not record["composite_score"]:
                rec = record
                sub = [
                    intel.get("intelligence_score", 0.0) or 0.0,
                    intel.get("reasoning_score", 0.0) or 0.0,
                    intel.get("quality_score", 0.0) or 0.0,
                ]
                valid = [s for s in sub if s > 0]
                if valid:
                    avg = sum(valid) / len(valid)
                    rec["composite_score"] = round(avg, 2)
                    rec["score_tier"] = (
                        "A" if avg >= 60 else
                        "B" if avg >= 45 else
                        "C" if avg >= 35 else "D"
                    )

            master["providers"].setdefault(provider_name, {
                "models": {},
                "free_bypass": record["free_bypass"],
                "base_url": record["base_url"],
                "status": record["provider_status"],
            })
            master["providers"][provider_name]["models"][model_id] = record

        # v7.1: one summary log instead of 819 separate warnings
        if _mismatch_count > 0:
            logger.info(f"[Router] tier auto-fix: {_mismatch_count} models had score_tier != computed_tier (auto-corrected in record)")

        return master

    def _load_health(self) -> Dict:
        """Load runtime health state. Creates file with proxy-derived defaults if missing."""
        with self._lock:
            try:
                mtime = HEALTH_FILE.stat().st_mtime
                if self._health_cache is None or (mtime - self._health_mtime) > 15:
                    with open(HEALTH_FILE) as f:
                        self._health_cache = json.load(f)
                    self._health_mtime = mtime
            except FileNotFoundError:
                # First run: seed health state from proxy model discovery
                self._health_cache = self._bootstrap_health_state()
                self._save_health(self._health_cache)
            except Exception:
                self._health_cache = {"models": {}, "providers": {}}
            return self._health_cache

    def _save_health(self, health: Dict):
        """Persist health state to disk ATOMICALLY (FIX 2026-06-20 / audit C4).
        Previously a non-atomic full-file open(w)+dump with no lock: the 30-min root
        timer and the on-demand orchestrator can write concurrently → truncated/corrupt
        circuit-breaker state. Write to a temp file in the same dir + os.replace (atomic
        rename on POSIX), so a reader always sees a complete file."""
        try:
            HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = HEALTH_FILE.with_suffix(HEALTH_FILE.suffix + f".tmp.{os.getpid()}")
            with open(tmp, "w") as f:
                json.dump(health, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, HEALTH_FILE)
        except Exception as e:
            logger.warning(f"[Router] Failed to save health state: {e}")
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

    def _bootstrap_health_state(self) -> Dict:
        """
        Bootstrap health state. With the legacy proxy project removed, there
        is no remote proxy to probe — start with an empty health cache and
        let warm-up probes populate it on demand.
        """
        return {
            "models": {},
            "providers": {},
            "_meta": {
                "bootstrap": True,
                "note": "Empty seed — direct cloud APIs only (proxy removed)",
            }
        }

    def _load_usage(self) -> List[Dict]:
        """Load append-only usage log."""
        entries = []
        try:
            if USAGE_LOG.exists():
                lines = USAGE_LOG.read_text().strip().split("\n")
                for line in lines[-500:]:
                    if line.strip():
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            pass
        except Exception:
            pass
        return entries

    # ══════════════════════════════════════════════════════════════════════════
    # TASK CLASSIFICATION
    # ══════════════════════════════════════════════════════════════════════════

    def classify_task(self, task_desc: str) -> str:
        """
        Classify task description into task type.
        
        Strategy: keyword matching → alias resolution → default 'general'
        """
        if not task_desc:
            return "general"

        desc = task_desc.lower().strip()

        # Direct alias check
        if desc in TASK_ALIASES:
            return TASK_ALIASES[desc]

        # Try exact match
        if desc in TASK_WEIGHTS:
            return desc

        # Keyword matching — first match wins
        for task_type, keywords in TASK_KEYWORDS.items():
            for kw in keywords:
                if kw in desc:
                    # Check if it's a heavy_coding override
                    if task_type == "medium_coding":
                        heavy_kw = ["fullstack", "arsitektur", "platform", "microservice",
                                    "dari awal", "build from scratch", "system design"]
                        if any(h in desc for h in heavy_kw):
                            return "heavy_coding"
                    return task_type

        # Check aliases by keyword
        for alias, canonical in TASK_ALIASES.items():
            if alias in desc:
                return canonical

        return "general"

    # ══════════════════════════════════════════════════════════════════════════
    # SCORING ENGINE
    # ══════════════════════════════════════════════════════════════════════════

    def _get_intelligence_score(self, model_data: Dict) -> float:
        """
        Get normalized intelligence score for model.
        
        Priority:
        1. benchmark_profile.overall_score (if available and > 0)
        2. capabilities_detail weighted average (reasoning × 0.6 + others)
        3. quality_score from catalog
        4. Fallback to 0.5 (medium)
        """
        # Priority 0 (NEW 2026-06-01): Artificial Analysis benchmark data.
        # AA indices are ~0..70 in current dataset -> normalize to 0..1.
        aa = model_data.get("benchmark_aa") or {}
        if aa:
            def _num(v):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
            ai = _num(aa.get("ai_index"))
            code = _num(aa.get("coding_index"))
            math = _num(aa.get("math_index"))
            parts, weights = [], []
            if ai is not None:   parts.append(ai);   weights.append(0.55)
            if code is not None: parts.append(code); weights.append(0.30)
            if math is not None: parts.append(math); weights.append(0.15)
            if parts:
                wsum = sum(weights)
                raw = sum(x * w for x, w in zip(parts, weights)) / wsum if wsum else 0.0
                return min(1.0, max(0.0, raw / 70.0))

        # Priority 0b: unified `score` (0..100) computed by model_db_manager.enrich()
        uni = model_data.get("score")
        if isinstance(uni, (int, float)) and uni > 0:
            return min(1.0, max(0.0, uni / 100.0))

        # Priority 1: benchmark_profile.overall_score
        bp = model_data.get("benchmark_profile", {})
        if bp:
            overall = bp.get("overall_score", 0)
            if overall > 0:
                return min(1.0, overall)

        # Priority 2: capabilities_detail weighted
        cap = model_data.get("capabilities_detail", {})
        if cap and any(cap.values()):
            reasoning = cap.get("reasoning", 0)
            coding = cap.get("coding", 0)
            inst_follow = cap.get("instruction_following", 0)
            structured = cap.get("structured_output", 0)

            # Weighted composite
            score = (reasoning * 0.35 + coding * 0.25 +
                     inst_follow * 0.20 + structured * 0.10 +
                     cap.get("backend", 0) * 0.05 +
                     cap.get("research", 0) * 0.05)
            return min(1.0, max(0.0, score))

        # Priority 3: quality_score
        qs = model_data.get("quality_score", 0)
        if qs and qs > 0:
            # Scale fix (P4CR4): values > 1.0 are likely benchmark percentages (0-100 scale)
            # e.g., quality_score=90 means 90% → normalize to 0-1 range
            if qs > 1.0:
                qs = qs / 100.0
            # Fair scoring floor (P4CR4): quality_score ≤ 0.5 means "insufficient evidence"
            # (model was newly enriched with conservative baseline or known low score).
            # Treat as fallback (0.5) so these models are ranked fairly, not excluded.
            # Models with quality_score > 0.5 have real evidence and use their actual score.
            if qs <= 0.5:
                return 0.5  # insufficient evidence → medium baseline
            return min(1.0, qs)

        # Fallback
        return 0.5

    def _get_capability_match_score(
        self,
        model_data: Dict,
        task_type: str,
    ) -> float:
        """
        Compute how well model's capabilities match task requirements.
        
        Returns 0-1 score based on weighted capability overlap.
        """
        hints = TASK_CAPABILITY_HINTS.get(task_type, TASK_CAPABILITY_HINTS["general"])
        cap = model_data.get("capabilities_detail", {})

        if not cap or not hints:
            return 0.5  # neutral

        total_weight = sum(hints.values())
        score = 0.0

        for cap_name, weight in hints.items():
            model_cap = cap.get(cap_name, 0)
            # Score contribution = weight × model_cap (0-1)
            score += (weight / total_weight) * model_cap

        return min(1.0, max(0.0, score))

    def _get_context_fit_score(self, model_data: Dict, task_type: str) -> float:
        """
        Score based on context window appropriateness for task.
        
        Different tasks need different context sizes.
        """
        context = model_data.get("context_window", 0) or model_data.get("context_length", 0) or 0

        # Unknown context window (common for ollama-cloud models) -> neutral,
        # do NOT penalise to 0.3 which unfairly sinks high-IQ fast models.
        if not context:
            return 0.7

        # Context requirements per task type
        requirements = {
            "long_context":   128000,
            "research":       64000,
            "heavy_coding":   32000,
            "medium_coding":  16000,
            "reasoning_xhigh": 64000,
            "general":        8192,
            "fast_tasks":     8192,
            "vision":         32000,
            "writing":        16000,
        }

        required = requirements.get(task_type, 8192)

        if context >= required:
            # Adequate or overkill — score based on not-too-much
            if context > required * 8:
                return 0.75  # overkill is not ideal
            return 1.0
        elif context >= required * 0.5:
            return 0.7
        elif context >= required * 0.25:
            return 0.5
        else:
            return 0.3

    def _get_provider_trust_score(self, provider: str) -> float:
        """Get provider trust score (0-1)."""
        return PROVIDER_TRUST.get(provider, 0.5)

    def _get_freshness_bonus(self, model_id: str, task_type: str) -> float:
        """
        Compute freshness bonus — avoid recently used models.
        
        Models used in last 30 minutes get penalty.
        """
        cutoff = datetime.now() - timedelta(minutes=30)
        last_used = self._recent_used.get(model_id)

        if last_used and last_used > cutoff:
            # Recency penalty: more recent = bigger penalty
            minutes_ago = (datetime.now() - last_used).total_seconds() / 60
            penalty = max(0.0, 0.3 - (minutes_ago / 100))  # 0.3 at 0 min, 0 at 30 min
            return -penalty

        return 0.0

    def _is_healthy(self, model_id: str) -> bool:
        """
        Check if model is healthy (not rate-limited, not circuit-tripped).

        Direct cloud APIs only — no proxy translation needed.
        """
        # Circuit breaker check (in-memory)
        cooldown = self._cooldown_until.get(model_id, 0)
        if time.time() < cooldown:
            return False

        failures = self._failure_count.get(model_id, 0)
        if failures >= self.CIRCUIT_THRESHOLD:
            return False

        # Health state check (persisted)
        health = self._load_health()
        model_state = health.get("models", {}).get(model_id, {})

        if model_state.get("rate_limited", False):
            return False
        if model_state.get("unavailable", False):
            return False

        return True

    def _proxy_id(self, model_id: str) -> str:
        """Identity — direct cloud API only, no legacy proxy format."""
        return model_id

    def _is_healthy_by_proxy_id(self, proxy_id: str) -> bool:
        """
        Check health state using model ID.
        """
        # Circuit breaker check (in-memory)
        cooldown = self._cooldown_until.get(proxy_id, 0)
        if time.time() < cooldown:
            return False
        failures = self._failure_count.get(proxy_id, 0)
        if failures >= self.CIRCUIT_THRESHOLD:
            return False

        # Persisted health state check
        health = self._load_health()
        models_health = health.get("models", {})

        # Exact match first
        model_state = models_health.get(proxy_id)
        if model_state is not None:
            if model_state.get("unavailable", False):
                return False
            if model_state.get("rate_limited", False):
                return False
            if model_state.get("status") == "unknown":
                return False
            return True

        # Fuzzy match: find health entries that share the model-name part.
        # Handles DB model naming variants like "mistral-large-3" vs
        # "mistral-large-3-675b-instruct-2512" pointing to the same model.
        parts = proxy_id.split("/")
        model_name_part = "/".join(parts[1:]) if len(parts) > 1 else parts[0]

        fuzzy_matches = [
            (hk, state) for hk, state in models_health.items()
            if proxy_id.startswith(hk)
            or model_name_part.endswith(hk.split("/")[-1])
        ]

        if fuzzy_matches:
            for health_key, state in fuzzy_matches:
                if state.get("unavailable", False):
                    return False
                if state.get("rate_limited", False):
                    return False
                if state.get("status") == "unknown":
                    return False
            return True

        # No health state entry found — optimistic for free providers. Direct
        # cloud APIs (NVIDIA, OpenRouter, MiniMax, xAI, ollama, etc.) haven't
        # been systematically probed yet, so absence of evidence ≠ evidence of
        # absence — assume healthy by default. Conservative blocking here would
        # eliminate all candidates silently.
        # Verified-free / force_free providers are optimistically healthy when unprobed
        # (keep in sync with providers.force_free: nvidia/groq/cerebras/minimax/ollama).
        _FREE_API_PROVIDERS = frozenset({"nvidia", "wrapper-nvidia", "openrouter",
                                          "minimax", "xai", "ollama", "ollama-cloud",
                                          "groq", "cerebras",
                                          "cohere", "perplexity", "you",
                                          "blackbox", "useai"})
        proxy_parts = proxy_id.split("/")
        proxy_provider = proxy_parts[0] if proxy_parts else proxy_id

        if proxy_provider in _FREE_API_PROVIDERS:
            logger.debug(f"[_is_healthy_by_proxy_id] No health entry for {proxy_id} "
                         f"(provider={proxy_provider}) — allowing optimistically")
            return True

        logger.debug(f"[_is_healthy_by_proxy_id] No health entry for {proxy_id} — conservative block")
        return False

    def _is_provider_healthy(self, provider: str) -> bool:
        """
        PHASE 1 NON-NEGOTIABLE: Provider-level health check.
        
        Returns True only if the provider has no known health issues.
        This is used as a pre-filter in _build_candidate_pool to exclude
        entire providers before any scoring happens.
        
        Health state is model-level (per proxy_id). Provider-level health is
        inferred from model-level data:
        - If ANY model under this provider is marked unavailable → provider
          likely has systemic issues → return False.
        - If NO health state entry exists for any model under this provider
          (free providers like nvidia, openrouter, minimax, xai, ollama) →
          assume healthy (optimistic default). These providers haven't been
          probed yet so absence of evidence ≠ evidence of absence.
        
        Also checks in-memory circuit breaker state for any model under
        this provider.
        """
        # 1. Check in-memory circuit breaker for this provider
        #    (any model in cooldown = provider is experiencing issues)
        for model_id in self._cooldown_until:
            if model_id.startswith(f"{provider}/") or provider in model_id:
                if time.time() < self._cooldown_until.get(model_id, 0):
                    logger.debug(f"[_is_provider_healthy] {provider} blocked by circuit breaker on {model_id}")
                    return False

        # 2. Check persisted health state for provider-level entry
        health = self._load_health()
        providers_health = health.get("providers", {})
        if provider in providers_health:
            pstate = providers_health[provider]
            if pstate.get("unavailable", False):
                logger.debug(f"[_is_provider_healthy] {provider} marked unavailable in health state")
                return False
            if pstate.get("rate_limited", False):
                logger.debug(f"[_is_provider_healthy] {provider} marked rate_limited in health state")
                return False

        # 3. Check model-level health: if ALL known models for this provider
        #    are marked unavailable → provider is likely unhealthy.
        #    But: if we have NO health data for this provider (free providers
        #    never probed), assume healthy optimistically.
        models_health = health.get("models", {})
        provider_model_keys = [k for k in models_health if k.startswith(f"{provider}/")]
        
        if not provider_model_keys:
            # No health data for this provider (NVIDIA, OpenRouter, etc.)
            # → assume healthy. These are free providers; blocking them without
            # evidence would eliminate all candidates.
            return True
        
        # We have health data for some models under this provider
        unavailable_count = sum(
            1 for k in provider_model_keys
            if models_health[k].get("unavailable", False)
        )
        total_checked = len(provider_model_keys)
        
        # If ALL known models are unavailable, block the provider
        if unavailable_count == total_checked and total_checked >= 3:
            logger.debug(f"[_is_provider_healthy] {provider} blocked: all {total_checked} health-probed models unavailable")
            return False
        
        return True

    def _precompute_scores_for_task_type(self, task_type: str, allow_paid: bool) -> None:
        """
        PHASE 4: Pre-compute composite_score for ALL active models for a given
        task_type. Results cached in _precomputed["task_type:allow_paid"].

        This runs lazily on first access for each task_type, then cached.
        Composite = base (capability + intelligence + context + trust)
        Dynamic multipliers (freshness, health) applied at runtime in _compute_composite_score.
        """
        cache_key = f"{task_type}:{int(allow_paid)}"
        if cache_key in self._precomputed:
            return  # already pre-computed

        weights = TASK_WEIGHTS.get(task_type, TASK_WEIGHTS["general"])
        scored = []

        # Iterate all models in MASTER
        master = self._load_master()
        for pname, pdata in master.get("providers", {}).items():
            if pdata.get("disabled", False):
                continue
            for mid, mdata in pdata.get("models", {}).items():
                if not mdata.get("is_active", False):
                    continue
                if mdata.get("deprecated") or mdata.get("disabled"):
                    continue

                full_id = f"{pname}/{mid}"
                mdata_copy = dict(mdata)
                mdata_copy["model_id"] = mid
                mdata_copy["provider"] = pname

                # Strict free filter for default production mode.
                if not allow_paid and not self._is_strictly_free(mdata_copy, pname):
                    continue

                # Pre-compute cache keys use full provider/model identity.
                mdata_copy["model_id"] = full_id

                # Base composite (no freshness, no health — those are dynamic)
                intelligence = self._get_intelligence_score(mdata_copy)
                capability   = self._get_capability_match_score(mdata_copy, task_type)
                context_fit  = self._get_context_fit_score(mdata_copy, task_type)
                trust        = self._get_provider_trust_score(pname)
                freshness    = 0.0  # dynamic — not pre-computed

                base = (
                    weights["capability"]   * capability +
                    weights["intelligence"]  * intelligence +
                    weights["context"]       * context_fit +
                    weights["trust"]         * trust +
                    weights["freshness"]     * freshness
                )

                # Latency penalty (static in model_data)
                lp = mdata_copy.get("latency_penalty", 0.0)
                try:
                    lp = float(lp) if lp is not None else 0.0
                except (TypeError, ValueError):
                    lp = 0.0
                base -= lp

                scored.append((full_id, pname, round(base, 4)))

        # Sort descending by base score, cache
        scored.sort(key=lambda x: x[2], reverse=True)
        self._precomputed[cache_key] = scored
        logger.debug(f"[Router] Pre-computed {len(scored)} scores for {task_type} (allow_paid={allow_paid})")

    # ══════════════════════════════════════════════════════════════════════════
    # COMPOSITE SCORE COMPUTATION
    # ══════════════════════════════════════════════════════════════════════════
    def _compute_composite_score(
        self,
        model_data: Dict,
        task_type: str,
        allow_paid: bool = False,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute composite score for model + task combination.

        Returns: (composite_score, score_breakdown)
        """
        # ── PHASE 4: TRY PRE-COMPUTED BASE SCORE ───────────────────────────────
        # If this task_type has been pre-computed, look up the base score from
        # the sorted pre-computed list. Only compute freshness + health at runtime.
        # This reduces score computation from ~15 component function calls → ~5.
        model_id_str = model_data.get("model_id", "")
        provider     = model_data.get("provider", "")
        cache_key   = f"{task_type}:{int(allow_paid)}"
        precomputed_base = None

        if cache_key in self._precomputed and model_id_str:
            for mid, pname, base_val in self._precomputed[cache_key]:
                if mid == model_id_str:
                    precomputed_base = base_val
                    break

        if precomputed_base is not None:
            # Use pre-computed base, apply ONLY dynamic factors
            composite = precomputed_base
            freshness = self._get_freshness_bonus(model_id_str, task_type)
            weights   = TASK_WEIGHTS.get(task_type, TASK_WEIGHTS["general"])
            composite += weights["freshness"] * freshness  # add back freshness
            health_score = self._get_health_score(model_id_str, provider)
            composite   *= health_score
            # For breakdown: we don't have component-level scores from pre-compute
            # so we compute just the dynamic parts for reporting
            dynamic_cap  = self._get_capability_match_score(model_data, task_type)
            dynamic_int   = self._get_intelligence_score(model_data)
            dynamic_ctx   = self._get_context_fit_score(model_data, task_type)
            dynamic_trust = self._get_provider_trust_score(provider)
            lp = model_data.get("latency_penalty", 0.0)
            try:
                lp = float(lp) if lp is not None else 0.0
            except (TypeError, ValueError):
                lp = 0.0
            breakdown = {
                "capability_score":   round(dynamic_cap, 4),
                "intelligence_score": round(dynamic_int, 4),
                "context_score":      round(dynamic_ctx, 4),
                "trust_score":        round(dynamic_trust, 4),
                "freshness_bonus":    round(freshness, 4),
                "latency_penalty":    round(lp, 4),
                "health_score":       round(health_score, 4),
            }
            return composite, breakdown

        # ── FALLBACK: compute all components from scratch ──────────────────────
        weights = TASK_WEIGHTS.get(task_type, TASK_WEIGHTS["general"])
        provider = model_data.get("provider", "")

        intelligence = self._get_intelligence_score(model_data)
        capability = self._get_capability_match_score(model_data, task_type)
        context_fit = self._get_context_fit_score(model_data, task_type)
        trust = self._get_provider_trust_score(provider)
        freshness = self._get_freshness_bonus(model_data.get("model_id", ""), task_type)

        composite = (
            weights["capability"]    * capability +
            weights["intelligence"]   * intelligence +
            weights["context"]       * context_fit +
            weights["trust"]         * trust +
            weights["freshness"]     * freshness
        )

        # Latency penalty (2026-06-01): persistently deprioritise models proven slow.
        # `latency_penalty` is a 0..1 fraction subtracted from the composite so a
        # high-IQ-but-slow model (e.g. deepseek-v4-pro ~40s) ranks below a fast
        # comparable model, without removing it from the candidate pool.
        latency_penalty = 0.0
        try:
            lp = model_data.get("latency_penalty")
            if lp is not None:
                latency_penalty = float(lp)
        except (TypeError, ValueError):
            latency_penalty = 0.0
        composite = composite - latency_penalty

        # ── HEALTH-AWARE SCORING (P4CR3-2) ──────────────────────────────────
        # Health is NOT a binary filter (it was in _is_healthy) — it's a
        # 0.0-1.0 multiplier that penalises degraded/recovering models so
        # a fully-healthy candidate with slightly lower benchmark score can
        # still rank above a broken-but-high-IQ model.
        health_score = self._get_health_score(
            model_data.get("model_id", ""),
            provider,
        )
        composite *= health_score   # multiplicative penalty
        # ── END HEALTH-AWARE SCORING ─────────────────────────────────────────

        breakdown = {
            "capability_score":   round(capability, 4),
            "intelligence_score": round(intelligence, 4),
            "context_score":     round(context_fit, 4),
            "trust_score":       round(trust, 4),
            "freshness_bonus":   round(freshness, 4),
            "latency_penalty":   round(latency_penalty, 4),
            "health_score":      round(health_score, 4),   # NEW
        }

        return min(1.0, max(0.0, composite)), breakdown

    # ══════════════════════════════════════════════════════════════════════════
    # HEALTH SCORE (P4CR3-2) — 0.0-1.0 multiplier for composite score
    # ══════════════════════════════════════════════════════════════════════════

    def _get_health_score(self, model_id: str, provider: str) -> float:
        """
        Compute health score (0.0-1.0) from runtime state.

        Unlike _is_healthy() which returns bool and is used for candidate
        filtering, this returns a continuous score so degraded models are
        penalised in ranking rather than outright excluded.

        Score semantics:
          1.0 = fully healthy (no recent failures, no rate limits)
          0.8 = soft warnings (1 timeout, minor latency)
          0.6 = degraded (2+ consecutive failures, or provider-level rate-limit)
          0.3 = temp-disabled (circuit tripped, but still reachable)
          0.0 = hard-disabled (auth error, key invalid, explicitly unavailable)

        Source: state/ilma_model_health.json (runtime health state)
        """
        # Circuit-breaker in-memory state
        cooldown = self._cooldown_until.get(model_id, 0)
        if time.time() < cooldown:
            return 0.0   # hard-disabled by circuit

        failures = self._failure_count.get(model_id, 0)
        if failures >= 10:
            return 0.0   # hard-disabled
        elif failures >= 5:
            return 0.2   # temp-disabled, approaching hard disable
        elif failures >= 3:
            return 0.4   # degraded
        elif failures >= 1:
            return 0.7   # soft warning — 1 failure only

        # Health file (persisted state — survives restart)
        health = self._load_health()
        model_state = health.get("models", {}).get(model_id, {})

        if model_state.get("unavailable", False):
            return 0.0   # hard-disabled
        if model_state.get("rate_limited", False):
            return 0.3   # provider-level rate limit

        # Check provider-level rate limit (e.g., NVIDIA API 429)
        provider_state = health.get("providers", {}).get(provider, {})
        if provider_state.get("rate_limited", False):
            return 0.6   # provider degraded, but model may still work

        # consecutive_failures from health file (may differ from in-memory)
        cf = model_state.get("consecutive_failures", 0)
        if cf >= 5:
            return 0.2
        elif cf >= 2:
            return 0.5

        # PHASE A: Treat unknown status as degraded — optimistic but cautious
        # Unknown = never been used via this router; penalize slightly to avoid
        # over-trusting untested models while still allowing them to be selected.
        if model_state.get("status") == "unknown":
            return 0.5   # degraded: tested model preferred over untested

        return 1.0   # fully healthy

    # ══════════════════════════════════════════════════════════════════════════
    # CANDIDATE POOL BUILDING
    # ══════════════════════════════════════════════════════════════════════════

    def _build_candidate_pool(
        self,
        task_type: str,
        allow_paid: bool,
    ) -> List[Tuple[str, str, Dict]]:  # (model_id, provider, model_data)
        """
        Build candidate pool from MASTER_DB.
        
        Filter by:
        - is_free OR allow_paid
        - not banned provider
        - is healthy
        """
        db = self._load_master()
        candidates = []

        for pname, pdata in db.get("providers", {}).items():
            if pname in PROVIDER_BANNED:
                continue

            # ── PROVIDER-LEVEL DISABLE FLAG (Cascading) ──
            # If provider.disabled = True → ALL models under it are disabled
            # regardless of individual model disabled=False setting.
            if pdata.get("disabled", False):
                continue

            # ── PHASE 1 NON-NEGOTIABLE: Provider Health Pre-Filter ──
            # Skip entire provider if known unhealthy (circuit breaker or health state).
            # This runs BEFORE any model iteration — eliminates the provider in O(1).
            if not self._is_provider_healthy(pname):
                continue

            for mid, mdata in pdata.get("models", {}).items():
                # Skip deprecated
                if mdata.get("deprecated", False):
                    continue

                # ── MODEL-LEVEL DISABLE FLAG (Tiered) ──
                # Model is disabled if: model.disabled=True OR
                # (provider.disabled=True → all models disabled regardless of their own status)
                if mdata.get("disabled", False):
                    continue

                # ── PHASE 4 NON-NEGOTIABLE: is_active MUST be True ─────────────────
                # Only models with is_active=True may be selected.
                # is_active=None or is_active=False → skip.
                if mdata.get("is_active") is not True:
                    continue

                # ── CHAT-ONLY GUARD (BUG-2 fix 2026-06-23) ─────────────────────────
                # get_best_model routes TEXT/chat tasks → must never pick a non-chat
                # specialist (rerank/embedding/image/video/audio/moderation) which serves
                # a different endpoint and would error/garbage on /chat/completions.
                # endpoint_type/primary_cap may be absent in the MASTER record, so also
                # match the model-id pattern (robust regardless of enrichment coverage).
                if (mdata.get("endpoint_type") in _NON_CHAT_ENDPOINTS
                        or mdata.get("primary_cap") in _NON_CHAT_CAPS
                        or any(p in mid.lower() for p in _NON_CHAT_ID_PATTERNS)):
                    continue

                # Strict free filter. Paid models are reachable only when allow_paid=True is
                # explicitly passed by an admin/user path that already validated policy.
                mdata_policy = dict(mdata)
                mdata_policy["model_id"] = mid
                mdata_policy["provider"] = pname
                if not allow_paid and not self._is_strictly_free(mdata_policy, pname):
                    continue

                # Skip models that the health probe has proven to return empty content.
                full_id = f"{pname}/{mid}"
                if not self._is_healthy_by_proxy_id(full_id):
                    continue

                # Attach full_id to model_data for scoring (use copy to avoid mutating DB)
                mdata_with_id = dict(mdata)
                mdata_with_id["model_id"] = full_id
                candidates.append((mid, pname, mdata_with_id))

        # ── HARD CAPABILITY FILTER (2026-06-20) ──────────────────────────────
        # vision/audio/video tasks MUST get a specialist. Exclude any model that
        # lacks the required capability so a high-scoring general model can never
        # win a niche task. Graceful fallback: if no specialist exists in the pool
        # (e.g. no free audio model), keep the full pool so routing never fails.
        req_cap = HARD_CAPABILITY_TASKS.get(task_type)
        if req_cap:
            specialists = [c for c in candidates
                           if self._model_has_capability(c[2], req_cap)]
            if specialists:
                logger.debug(f"[Router] hard {req_cap} filter: {len(specialists)}/{len(candidates)} specialists")
                return specialists
            logger.warning(f"[Router] no {req_cap}-capable "
                           f"{'free ' if not allow_paid else ''}model in pool — "
                           f"falling back to full pool (soft capability)")
        return candidates

    @staticmethod
    def _model_has_capability(mdata: Dict, cap: str) -> bool:
        """True if a model genuinely has `cap` (vision/audio/video). Reads the enriched
        capabilities_detail (SOT) first, then the capabilities list; treats image models
        as vision-capable."""
        cd = mdata.get("capabilities_detail") or {}
        if isinstance(cd.get(cap), (int, float)) and cd.get(cap, 0) >= 0.5:
            return True
        caps = mdata.get("capabilities") or []
        if cap in caps:
            return True
        if cap == "vision" and ("image" in caps or (cd.get("multimodal", 0) or 0) >= 0.6):
            return True
        return False

    def _get_cached_candidates(
        self,
        task_type: str,
        allow_paid: bool,
        min_quality: float = 0.0,
    ) -> List[Tuple[str, str, Dict]]:
        """
        Return cached candidate list if fresh (TTL=120s), else rebuild + cache.

        PHASE 1 LATENCY OPTIMIZATION:
        - Cache key = (task_type, allow_paid) → eliminates redundant pool builds
        - Early pruning: only is_active=True + quality_score >= min_quality
        - Reduces candidates from 516 → ~82, cutting scoring time ~60-70%

        TTL=120s balances freshness (model activations change rarely) vs speed
        (repeated queries within 2 min hit cache immediately).

        PHASE 4 PRODUCTION LOCKDOWN (2026-06-06):
        Cache is auto-invalidated if MASTER.json's mtime has changed since
        the cache was last populated. This prevents stale `is_active=False`
        models from leaking into routing when an external process (e.g.
        the cron sync, a manual edit, or the benchmark autoloop) modifies
        the master DB while the router is still using cached candidates.
        """
        import hashlib
        cache_key = f"{task_type}:{'paid' if allow_paid else 'free'}"

        now = time.time()
        cached = self._candidate_cache.get(cache_key)

        # PHASE 4: mtime-aware invalidation — if MASTER changed since
        # cache was written, drop cache and rebuild.
        try:
            current_mtime = MASTER_DB.stat().st_mtime
        except OSError:
            current_mtime = 0

        if cached and (now - cached["ts"]) < self._CACHE_TTL \
                and cached.get("master_mtime") == current_mtime:
            return cached["candidates"]

        # Cache miss — rebuild candidate pool
        raw_candidates = self._build_candidate_pool(task_type, allow_paid)

        # ── PHASE 1 EARLY PRUNING ─────────────────────────────────────────────
        # is_active gate: only explicitly activated models in candidate pool.
        # This alone reduces candidates from 516 → ~82 (6× speedup in scoring).
        # Additional min_quality filter removes low-quality models.
        pruned = []
        for mid, pname, mdata in raw_candidates:
            if not mdata.get("is_active", False):
                continue
            qs = mdata.get("quality_score", 0.0)
            if min_quality > 0 and qs < min_quality:
                continue
            pruned.append((mid, pname, mdata))

        # Cache pruned result
        self._candidate_cache[cache_key] = {
            "candidates": pruned,
            "ts": now,
            "master_mtime": current_mtime,  # PHASE 4: mtime-aware invalidation
        }
        return pruned

    def _invalidate_candidate_cache(self):
        """Clear candidate cache. Call after MASTER reload."""
        self._candidate_cache.clear()

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN ROUTING API
    # ══════════════════════════════════════════════════════════════════════════

    def get_best_model(
        self,
        task_type_or_desc: str,
        allow_paid: Optional[bool] = None,
        avoid_models: Optional[List[str]] = None,
        _timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Get best model for task.

        Args:
            task_type_or_desc: Task type string or natural language description
            allow_paid: Override self.allow_paid (None = use instance default)
            avoid_models: Model IDs to skip
            _timeout: Maximum seconds to wait (default 30s). If exceeded, return
                     emergency fallback.

        Returns:
            {
                "model_id": str,
                "provider": str,
                "is_free": bool,
                "composite_score": float,
                "capability_score": float,
                "intelligence_score": float,
                "context_score": float,
                "trust_score": float,
                "routing_reason": str,
                "fallbacks": [...],
            }

        Raises:
            RoutingTimeoutError: If timeout is exceeded and no fallback is configured
                                 (not raised by default — emergency fallback is returned).
        """
        def impl():
            return self._get_best_model_impl(task_type_or_desc, allow_paid, avoid_models)

        def fallback():
            return self._emergency_fallback()

        return _timeout_wrapper(impl, timeout_seconds=_timeout, fallback_func=fallback)()

    def _get_best_model_impl(
        self,
        task_type_or_desc: str,
        allow_paid: Optional[bool] = None,
        avoid_models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        allow = self.allow_paid if allow_paid is None else allow_paid
        avoid = set(avoid_models or [])

        # ── Internal trace logger ────────────────────────────────────────────
        def _log_route_trace(
            event: str,
            best_result: Optional[Dict[str, Any]] = None,
            fallback_used: bool = False,
        ):
            """Append a JSON trace line to router_traces.ndjson."""
            import traceback as _tb
            entry = {
                "timestamp":       datetime.now().isoformat(),
                "event":          event,
                "task_type":      task_type_or_desc,
                "classified":     task,
                "allow_paid":     allow,
                "candidates":    len(candidates) if 'candidates' in dir() else 0,
                "scored":         len(scored) if 'scored' in dir() else 0,
                "fallback_used":  fallback_used,
            }
            if best_result:
                entry.update({
                    "best_model_id":    best_result.get("model_id"),
                    "provider":         best_result.get("provider"),
                    "composite_score":  best_result.get("composite_score"),
                    "capability_score": best_result.get("capability_score"),
                    "intelligence_score": best_result.get("intelligence_score"),
                    "context_score":    best_result.get("context_score"),
                    "trust_score":      best_result.get("trust_score"),
                    "routing_reason":   best_result.get("routing_reason"),
                    "is_emergency":     best_result.get("is_emergency", False),
                })
            try:
                TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(TRACE_FILE, "a") as fh:
                    fh.write(json.dumps(entry) + "\n")
            except Exception:
                pass  # Never let tracing break routing

        # Classify task
        if task_type_or_desc in TASK_WEIGHTS:
            task = task_type_or_desc
        else:
            task = self.classify_task(task_type_or_desc)

        # Build candidates (PHASE 1: cached + early pruning via is_active)
        candidates = self._get_cached_candidates(task, allow)

        if not candidates:
            _log_route_trace("candidates_built", fallback_used=True)
            return self._emergency_fallback()

        # ── PHASE 4: Trigger pre-computation for this task_type ──────────────────
        # This populates _precomputed for this task_type so each candidate's
        # _compute_composite_score call hits the fast pre-computed base path.
        self._precompute_scores_for_task_type(task, allow)

        # Score all candidates
        scored = []
        for mid, pname, mdata in candidates:
            full_id = f"{pname}/{mid}"

            # Skip avoid list
            if full_id in avoid or mid in avoid:
                continue

            composite, breakdown = self._compute_composite_score(mdata, task, allow_paid=allow)

            scored.append({
                "model_id":        mid,
                "provider":        pname,
                "is_free":        mdata.get("is_free", False),  # single canonical billing field
                "composite_score": round(composite, 4),
                "capability_score": breakdown["capability_score"],
                "intelligence_score": breakdown["intelligence_score"],
                "context_score":  breakdown["context_score"],
                "trust_score":    breakdown["trust_score"],
                "specialization": mdata.get("subagent_specialization", {}).get("primary_role_hint", "general"),
                "model_data":      mdata,
            })

        # Sort by composite score descending
        scored.sort(key=lambda x: x["composite_score"], reverse=True)

        if not scored:
            _log_route_trace("scoring_complete", fallback_used=True)
            return self._emergency_fallback()

        # Primary result
        best = scored[0]
        fallbacks = scored[1:6]  # top 5 fallbacks

        # ── SAFETY NET: is_active enforcement ───────────────────────────────
        # Even though _get_cached_candidates filters is_active=True models,
        # we double-check here so get_best_model NEVER returns an inactive model.
        best_is_active = best["model_data"].get("is_active", False)
        if not best_is_active:
            if fallbacks:
                best = fallbacks[0]  # use next-best active model
                if not best["model_data"].get("is_active", False):
                    return self._emergency_fallback()
            else:
                return self._emergency_fallback()

        # ── PHASE 4 SAFETY NET: is_free enforcement ───────────────────────────
        # If allow_paid is False (default), the chosen model MUST be free.
        # The pre-filter in _build_candidate_pool already enforces this, but
        # a paranoid last check here ensures no paid model leaks into runtime
        # even if the candidate pool was constructed under unusual conditions.
        if not allow:
            # Walk the scored list and pick the first model that is actually
            # free. If we land here, it usually means the candidate pool
            # included something tagged incorrectly upstream.
            if not self._is_strictly_free(best["model_data"], best["provider"]):
                logger.warning(
                    f"[PHASE 4 SAFETY NET] Best model {best['model_id']} "
                    f"is NOT free but allow_paid=False. Scanning fallbacks..."
                )
                promoted = None
                for fb in fallbacks:
                    if self._is_strictly_free(fb["model_data"], fb["provider"]):
                        promoted = fb
                        break
                if promoted is None:
                    logger.error(
                        f"[PHASE 4 SAFETY NET] No free model in top-6 "
                        f"candidates. Falling back to emergency.")
                    return self._emergency_fallback()
                logger.info(
                    f"[PHASE 4 SAFETY NET] Switched {best['model_id']} → "
                    f"{promoted['model_id']} (free-only enforcement)")
                best = promoted

        # Build reason
        reason = (
            f"{task}: {best['model_id']} "
            f"(cap={best['capability_score']}, "
            f"intel={best['intelligence_score']}, "
            f"context={best['context_score']}, "
            f"trust={best['trust_score']}, "
            f"total={best['composite_score']})"
        )

        # Update recent used
        self._recent_used[best["model_id"]] = datetime.now()

        result = {
            "model_id":           best["model_id"],
            "provider":           best["provider"],
            "is_free":            best["is_free"],
            "composite_score":    best["composite_score"],
            "capability_score":   best["capability_score"],
            "intelligence_score": best["intelligence_score"],
            "context_score":      best["context_score"],
            "trust_score":        best["trust_score"],
            "specialization":     best["specialization"],
            "routing_reason":     reason,
            "routing_method":     "ILMAUnifiedRouter_v1.0",
            "fallbacks": [
                {"model_id": f["model_id"], "provider": f["provider"], "score": f["composite_score"]}
                for f in fallbacks
            ],
            "use_nvidia_parallel": best["provider"] == "nvidia",
            "recommended_parallel_degree": 3 if best["provider"] == "nvidia" else 1,
        }
        _log_route_trace("routing_complete", best_result=result)
        return result

    def route(
        self,
        task_type_or_desc: str,
        n_fallbacks: int = 5,
        allow_paid: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Full routing result with primary + fallbacks.

        Returns dict with route + fallback_chain.
        """
        result = self.get_best_model(task_type_or_desc, allow_paid=allow_paid)

        # Get more fallbacks
        task = self.classify_task(task_type_or_desc) if task_type_or_desc not in TASK_WEIGHTS else task_type_or_desc
        allow = self.allow_paid if allow_paid is None else allow_paid
        candidates = self._build_candidate_pool(task, allow)

        scored = []
        for mid, pname, mdata in candidates:
            if mid == result.get("model_id"):
                continue
            composite, breakdown = self._compute_composite_score(mdata, task, allow_paid=allow)
            scored.append({
                "model_id":  mid,
                "provider":  pname,
                "score":     round(composite, 4),
                "cap_score": breakdown["capability_score"],
                "intel_score": breakdown["intelligence_score"],
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        fallbacks = scored[:n_fallbacks]

        result["fallback_chain"] = [
            {"model_id": f["model_id"], "provider": f["provider"], "score": f["score"]}
            for f in fallbacks
        ]
        result["total_candidates"] = len(candidates)

        return result

    def route_spread(
        self,
        task_type_or_desc: str,
        top_k: int = 30,   # Must be ≥30 to include exploration models (rank 7+)
        allow_paid: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Weighted random selection from Top-K candidates with freshness penalty.

        Unlike route() which always returns the #1 ranked model, route_spread()
        selects from the top K candidates using a weighted random algorithm that
        reduces the weight of models used recently. This distributes load more
        evenly across high-quality models while keeping the best model dominant.

        Selection weights (softmax-style):
          Rank 1:  35% base  → adjusted by freshness
          Rank 2:  25% base  → adjusted by freshness
          Rank 3:  20% base
          Rank 4:  12% base
          Rank 5+:  8% base  (diminishing for 6-30)

        Freshness penalty: models used within 30 min get 50% weight reduction.

        PHASE 2: Safe exploration — 5% traffic to exploration_phase=True models.
        Exploration models are included when they rank within the top-K pool
        (requires top_k ≥ 30 since exploration models typically rank 7-30).

        Returns dict with selected model + full distribution for monitoring.
        """
        # Get ranked candidates (winner + top_k fallbacks to capture exploration models)
        # top_k=30 → n_fallbacks=29 → route returns winner + 29 fallbacks = 30 items
        result = self.route(task_type_or_desc, n_fallbacks=min(top_k - 1, 50),
                           allow_paid=allow_paid)

        winner = {
            "model_id": result.get("model_id"),
            "provider":  result.get("provider"),
            "score":     result.get("composite_score", result.get("score", 0)),
            # model_data is NOT available for winner — set empty, exploration=False
            "model_data": {},
        }
        fallbacks = result.get("fallback_chain", [])

        # Build pool: winner + fallbacks (max top_k items)
        # Note: winner/fallbacks from route() don't carry model_data — we look them
        # up from the master cache below so exploration_phase and other metadata
        # are available for PHASE 2 safe-exploration and PHASE 3 usage logging.
        raw_pool = [winner] + [{"model_id": f["model_id"], "provider": f["provider"],
                             "score": f["score"], "model_data": {}} for f in fallbacks]

        # PHASE 4 PRODUCTION LOCKDOWN (2026-06-06):
        # Provider-interleaved pool construction. route() returns models
        # sorted purely by composite score, which means a single provider
        # with many high-quality models (e.g. NVIDIA with 51 active free
        # candidates) dominates the top-K. We interleave the pool by
        # provider so the top-K contains at least N distinct providers.
        # The first item is always the original winner (highest score).
        if len(raw_pool) > 1:
            by_provider: Dict[str, List[Dict]] = {}
            for c in raw_pool:
                by_provider.setdefault(c["provider"], []).append(c)
            # Sort each provider's bucket by score
            for prov_list in by_provider.values():
                prov_list.sort(key=lambda c: c["score"], reverse=True)
            # Interleave round-robin across providers, starting with
            # the original winner's provider so #1 is preserved.
            providers_ordered = sorted(by_provider.keys(),
                                        key=lambda p: 0 if p == winner["provider"] else 1)
            interleaved: List[Dict] = []
            cursor = 0
            while len(interleaved) < top_k and any(by_provider[p] for p in providers_ordered):
                for p in providers_ordered:
                    if by_provider[p]:
                        interleaved.append(by_provider[p].pop(0))
                        if len(interleaved) >= top_k:
                            break
                cursor += 1
            pool = interleaved[:top_k]
        else:
            pool = raw_pool[:top_k]

        # ── PHASE 7 PRODUCTION LOCKDOWN (2026-06-06): Provider weight cap.
        # Prevent a single provider from dominating >60% of the spread pool.
        # Even with score-based interleaving, a provider with many high-quality
        # models (NVIDIA: 87 free candidates) can crowd out others.
        # Fix: hard-cap each provider at max 60% of pool candidates, trim from
        # lowest-scoring candidates first (they were least likely to be picked anyway).
        if len(pool) >= 3:
            max_provider_pct = 0.60
            by_provider_raw: Dict[str, List[Dict]] = {}
            for c in pool:
                by_provider_raw.setdefault(c["provider"], []).append(c)

            # Trim over-represented providers but continue into weighted selection.
            max_items = max(1, int(len(pool) * max_provider_pct))
            trimmed_pool = []
            for prov, prov_list in by_provider_raw.items():
                prov_list.sort(key=lambda c: c["score"], reverse=True)
                trimmed_pool.extend(prov_list[:max_items])

            trimmed_pool.sort(key=lambda c: c["score"], reverse=True)
            pool = trimmed_pool

        if len(pool) == 1:
            return {**result, "selected_model": pool[0], "selection_method": "single-winner",
                    "spread_pool": pool, "candidates": pool,
                    "distribution": {pool[0]["model_id"]: 1.0}}

        # ── STEP 1: Enrich pool with model_data from MASTER cache ───────────────
        # route() returns winner + fallbacks but WITHOUT model_data.
        # We must look up each model's metadata here to access exploration_phase,
        # quality_score, etc. for PHASE 2 (exploration split) and PHASE 3 (usage).
        master = self._load_master()
        for candidate in pool:
            pname = candidate["provider"]
            mid   = candidate["model_id"]
            # model_data from master
            candidate["model_data"] = (
                master.get("providers", {}).get(pname, {}).get("models", {}).get(mid, {})
            )

        # ── STEP 1: Compute freshness-adjusted weights for all pool members ──
        cutoff = datetime.now() - timedelta(minutes=30)
        weights = []
        for i, candidate in enumerate(pool):
            # Freshness penalty: models used in last 30 min get 50% weight reduction
            freshness = 1.0
            last_used = self._recent_used.get(candidate["model_id"])
            if last_used and last_used > cutoff:
                freshness = 0.5

            # Rank-based base weight (softmax-ish)
            # Ranks: 1→0.35, 2→0.25, 3→0.20, 4→0.12, 5→0.08
            rank_weights = [0.35, 0.25, 0.20, 0.12, 0.08]
            rank_base = rank_weights[i] if i < len(rank_weights) else 0.05

            # PHASE 4 PRODUCTION LOCKDOWN (2026-06-06):
            # Provider-diversity boost. If a provider already dominates
            # the recent routing history, under-represented providers get
            # a small weight bump so we don't lock into one provider.
            # Reads the last N routing decisions from _recent_used and
            # counts how many hit this provider.
            recent_hits = sum(
                1 for mid, ts in self._recent_used.items()
                if ts and ts > cutoff
                and mid.startswith(candidate["provider"] + "/")
            )
            # 0 hits = no penalty, 5+ hits = 30% penalty
            diversity_factor = 1.0 - min(0.30, recent_hits * 0.06)

            weight = rank_base * freshness * diversity_factor
            weights.append(weight)

            # Tag candidate with metadata
            candidate["_pool_rank"] = i + 1
            candidate["_is_exploration"] = candidate.get("model_data", {}).get("exploration_phase", False)

        # ── STEP 2: PHASE 2 — Safe exploration split ────────────────────────────
        established = [c for c in pool if not c.get("_is_exploration", False)]
        exploration = [c for c in pool if c.get("_is_exploration", False)]

        # 5% traffic to exploration models, 95% to established
        if exploration and random.random() < 0.05:
            # Exploration route: pick from exploration pool
            pool_to_use = exploration
            selection_source = "exploration"
            # Weights for exploration candidates — preserve their original rank weights
            sel_weights = [weights[pool.index(c)] for c in exploration]
        else:
            # Established route: pick from established pool
            pool_to_use = established if established else pool
            selection_source = "established"
            sel_weights = [weights[pool.index(c)] for c in pool_to_use]

        # ── STEP 2B: Provider Diversity Penalty (Anti-NVIDIA Monopoly) ─────────
        # Count recent same-provider selections in rolling window.
        # Apply penalty to providers dominating >50% of recent traffic.
        if self._provider_rolling:
            provider_counts: Dict[str, int] = {}
            for p in self._provider_rolling:
                provider_counts[p] = provider_counts.get(p, 0) + 1
            window_size = len(self._provider_rolling)
            for i, candidate in enumerate(pool_to_use):
                p = candidate.get("provider", "")
                recent_pct = provider_counts.get(p, 0) / window_size if window_size > 0 else 0
                if recent_pct > 0.5:
                    # Penalize providers that are >50% of recent window
                    # Penalty scales: 50%=0.7x, 75%=0.5x, 100%=0.3x
                    penalty = 1.0 - (recent_pct - 0.5) * 1.6
                    sel_weights[i] *= max(0.1, penalty)

        # Normalize weights
        total_w = sum(sel_weights)
        if total_w <= 0:
            normalized = [1.0 / len(sel_weights)] * len(sel_weights)
        else:
            normalized = [s / total_w for s in sel_weights]

        # Weighted random selection
        sel_idx = random.choices(range(len(pool_to_use)), weights=normalized, k=1)[0]
        selected = pool_to_use[sel_idx]
        is_exploration = selected.get("_is_exploration", False)

        # ── STEP 2C: Track provider selection for diversity ─────────────────
        # Record selected provider in rolling window for anti-monopoly penalty.
        sel_provider = selected.get("provider", "")
        self._provider_rolling.append(sel_provider)

        # ── PHASE 3: LOG USAGE (async accumulation, no per-request disk I/O) ───
        self._log_usage(
            model_id=selected["model_id"],
            latency_ms=0,
            success=True,
            provider=selected.get("provider", ""),
        )

        # Build distribution dict (weights for full pool)
        total_w_all = sum(weights) if weights else 1
        distribution = {pool[i]["model_id"]: round(weights[i] / total_w_all, 4)
                       for i in range(len(pool)) if i < len(weights)}

        result["selected_model"] = selected
        result["selection_method"] = f"weighted_random_spread[{selection_source}]"
        result["spread_pool"] = pool
        result["candidates"] = pool  # backward-compatible name consumed by ilma_client fallback
        result["distribution"] = distribution
        result["is_exploration_model"] = is_exploration
        result["exploration_failures"] = self._exploration_failures.get(selected["model_id"], 0)
        result["routing_reason"] = (
            f"route_spread[{len(pool)} candidates, source={selection_source}, "
            f"selected rank-{selected.get('_pool_rank','?')} '{selected['model_id']}' "
            f"via weighted random (freshness penalty applied)]"
        )

        return result

    def _log_usage(self, model_id: str, latency_ms: float, success: bool, provider: str = ""):
        """
        PHASE 3: Real-time feedback loop — accumulate usage stats in memory.

        Args:
            model_id:   Full model_id (e.g. 'deepseek-v4-pro').
            provider:   Provider name (e.g. 'deepseek-ai'). If provided, the
                        storage key is 'provider/model_id' for unambiguous lookup
                        in flush_usage_updates().
            latency_ms: Observed round-trip latency for this request.
            success:    True if request succeeded, False if failed.

        Stats are flushed to model_usage.jsonl and merged into
        PROVIDER_INTELLIGENCE_MASTER.json via flush_usage_updates().
        """
        # Normalise key: use provider/model_id when provider is known.
        # model_id may already contain a provider prefix (e.g. "minimax/MiniMax-M3").
        # Strip it before prepending to avoid double-prefixes.
        parts = model_id.rsplit("/", 1)
        bare_id = parts[-1]
        key = f"{provider}/{bare_id}" if provider else bare_id
        if key not in self._pending_usage:
            self._pending_usage[key] = {
                "total": 0, "success": 0, "failed": 0,
                "latency_sum": 0.0, "latency_count": 0,
            }
        stats = self._pending_usage[key]
        stats["total"] += 1
        if success:
            stats["success"] += 1
            # Exponential moving average: EMA_latency = 0.8*old + 0.2*new
            if stats["latency_count"] > 0:
                stats["avg_latency"] = (
                    0.8 * stats.get("avg_latency", latency_ms)
                    + 0.2 * latency_ms
                )
            else:
                stats["avg_latency"] = latency_ms
            stats["latency_count"] += 1
        else:
            stats["failed"] += 1
            # Track consecutive failures for exploration auto-disable.
            # Key in _pending_usage = "provider/model_id". Extract provider
            # from the key so _auto_disable_exploration_model scopes to the
            # correct provider (avoids disabling wrong model in different provider).
            failure_provider = ""
            for _key in self._pending_usage:
                if _key.endswith(f"/{model_id}") or _key == model_id:
                    if "/" in _key:
                        failure_provider = _key.split("/", 1)[0]
                    break
            self._exploration_failures[model_id] = self._exploration_failures.get(model_id, 0) + 1
            # Auto-disable if consecutive failures >= threshold
            if self._exploration_failures.get(model_id, 0) >= self.EXPLORATION_MAX_FAILURES:
                self._auto_disable_exploration_model(model_id, provider=failure_provider)

        # Flush to disk when threshold reached
        if len(self._pending_usage) >= self._usage_flush_threshold:
            self.flush_usage_updates()

    def _auto_disable_exploration_model(self, model_id: str, provider: str = ""):
        """
        PHASE 2: Auto-disable a model after N consecutive exploration failures.

        Args:
            model_id: bare model name (may appear in multiple providers).
            provider: optional provider scope — if set, only search this provider.
        """
        master = self._load_master()
        providers_to_search = (
            {provider: master["providers"][provider]}
            if provider and provider in master.get("providers", {})
            else master.get("providers", {})
        )

        for pname, pdata in providers_to_search.items():
            models = pdata.get("models", {})
            # model_id may be bare ("deepseek-v4-flash") or composite.
            # Search by bare name (last segment) for safety.
            found_key = None
            for mkey in models:
                if mkey == model_id or mkey.endswith(f"/{model_id}"):
                    found_key = mkey
                    break

            if found_key is not None:
                models[found_key]["is_active"] = False
                failure_count = self._exploration_failures.get(model_id, 0)
                models[found_key]["disabled_reason"] = f"exploration_failed:{failure_count}x"
                logger.warning(f"[Router] Auto-disabled {found_key} after {failure_count} exploration failures")
                break
        # Write back: persist the auto-disable to MongoDB (canonical store)
        # then invalidate cache so disabled model is excluded immediately.
        try:
            # MongoDB canonical: set is_active=False on model_intelligence + models
            # FIX 2026-06-21: use shared MongoConnectionManager (no hardcoded IP)
            if not hasattr(self, "_mongo_client") or self._mongo_client is None:
                from ilma_mongo_connection import get_mongo_manager
                mgr = get_mongo_manager()
                self._mongo_client = mgr.get_client()
            mongo_db = self._mongo_client["credentials"]
            for pname, pdata in master.get("providers", {}).items():
                for mid, mdata in pdata.get("models", {}).items():
                    if mdata.get("is_active") is False and mdata.get("disabled_reason"):
                        mongo_db["model_intelligence"].update_one(
                            {"model_id": mid, "provider": pname},
                            {"$set": {
                                "is_active": False,
                                "disabled_reason": mdata["disabled_reason"],
                                "disabled_at": datetime.now().isoformat(),
                            }},
                        )
                        mongo_db["models"].update_one(
                            {"model_id": mid, "provider": pname},
                            {"$set": {
                                "is_active": False,
                                "disabled_reason": mdata["disabled_reason"],
                            }},
                        )
            self._invalidate_candidate_cache()
        except Exception as e:
            logger.error(f"[Router] Failed to persist auto-disable to MongoDB: {e}")

    def flush_usage_updates(self):
        """
        PHASE 3: Flush accumulated usage stats to model_usage.jsonl and
        update PROVIDER_INTELLIGENCE_MASTER.json with new reliability_score.

        Called automatically when _pending_usage reaches flush threshold,
        or can be called manually (e.g., on scheduler tick).
        """
        if not self._pending_usage:
            return

        now = datetime.now().isoformat()
        lines = []
        updated_models = []

        for model_id, stats in list(self._pending_usage.items()):
            reliability = (stats["success"] / stats["total"]) if stats["total"] > 0 else 0.0
            lines.append(json.dumps({
                "timestamp": now,
                "model_id": model_id,
                "total": stats["total"],
                "success": stats["success"],
                "failed": stats["failed"],
                "reliability": round(reliability, 4),
                "avg_latency": round(stats.get("avg_latency", 0), 2),
            }))
            updated_models.append((model_id, reliability, stats.get("avg_latency", 0)))

        # Append to usage log
        try:
            self.USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.USAGE_FILE, "a") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            logger.warning(f"[Router] Failed to write usage log: {e}")

        # Update MASTER.json with new reliability scores
        try:
            master = self._load_master()
            for model_id, reliability, avg_lat in updated_models:
                # Handle both composite "provider/model" keys (from route_spread)
                # and bare "model" keys (from manual _log_usage calls).
                # MASTER stores models under provider/{model_id} or bare model_id.
                parts = model_id.rsplit("/", 1)
                lookup_key = parts[-1]  # bare model_id
                master_model = None
                for pname, pdata in master.get("providers", {}).items():
                    # Try composite key first (provider/model_id)
                    if model_id in pdata.get("models", {}):
                        master_model = pdata["models"][model_id]
                        break
                    # Fall back to bare key (legacy / direct calls)
                    if lookup_key in pdata.get("models", {}):
                        master_model = pdata["models"][lookup_key]
                        break
                if master_model is None:
                    logger.debug(f"[_log_usage] {model_id} not in MASTER — skipped")
                    continue

                # Update reliability_score
                old_rel = master_model.get("reliability_score", 1.0)
                # EMA update: blend with existing
                master_model["reliability_score"] = round(
                    old_rel * 0.7 + reliability * 0.3, 4
                )
                # Update avg_latency
                if avg_lat > 0:
                    old_lat = master_model.get("avg_latency_ms", avg_lat)
                    master_model["avg_latency_ms"] = round(
                        old_lat * 0.7 + avg_lat * 0.3, 2
                    )
                # Recompute composite_score if reliability dropped
                if reliability < 0.5 and master_model.get("is_active", False):
                    master_model["is_active"] = False
                    master_model["disabled_reason"] = "reliability_below_50pct"

            # ── SCORE CHANGE DETECTION — trigger Hourly Optimizer if >10% delta ─
            self._maybe_trigger_hourly_optimizer(updated_models, master)

            # Persist usage updates to MongoDB (canonical store).
            # Keep flushing to JSON LEGACY for backward-compat only (audit trail).
            try:
                # FIX 2026-06-21: use shared MongoConnectionManager (no hardcoded IP)
                if not hasattr(self, "_mongo_client") or self._mongo_client is None:
                    from ilma_mongo_connection import get_mongo_manager
                    mgr = get_mongo_manager()
                    self._mongo_client = mgr.get_client()
                mongo_db = self._mongo_client["credentials"]
                # Track which model_intelligence docs need a refreshed composite_score.
                now_iso = datetime.now().isoformat()
                for model_id, reliability, avg_lat in updated_models:
                    # model_id may be composite "provider/model" or bare "model"
                    parts = model_id.split("/", 1)
                    if len(parts) == 2:
                        pname_lookup, mid_lookup = parts
                    else:
                        pname_lookup, mid_lookup = "", model_id
                    if not pname_lookup:
                        continue
                    mongo_db["model_intelligence"].update_one(
                        {"model_id": mid_lookup, "provider": pname_lookup},
                        {"$set": {
                            "reliability_score": reliability,
                            "avg_latency_ms": avg_lat,
                            "usage_updated_at": now_iso,
                        }},
                    )
                # If any model was auto-disabled for reliability, propagate
                for pname, pdata in master.get("providers", {}).items():
                    for mid, mdata in pdata.get("models", {}).items():
                        if mdata.get("is_active") is False and mdata.get("disabled_reason"):
                            mongo_db["model_intelligence"].update_one(
                                {"model_id": mid, "provider": pname},
                                {"$set": {
                                    "is_active": False,
                                    "disabled_reason": mdata["disabled_reason"],
                                    "disabled_at": now_iso,
                                }},
                            )
                            mongo_db["models"].update_one(
                                {"model_id": mid, "provider": pname},
                                {"$set": {
                                    "is_active": False,
                                    "disabled_reason": mdata["disabled_reason"],
                                }},
                            )
                self._invalidate_candidate_cache()
            except Exception as e:
                logger.warning(f"[Router] Failed to persist usage stats to MongoDB: {e}")
        except Exception as e:
            logger.warning(f"[Router] Failed to update MASTER with usage stats: {e}")

        logger.info(f"[Router] Flushed usage for {len(self._pending_usage)} models, "
                    f"{len(updated_models)} updated in MASTER")
        self._pending_usage.clear()

    def _maybe_trigger_hourly_optimizer(
        self,
        updated_models: list,  # [(model_id, new_reliability, avg_lat), ...]
        master: dict,
    ):
        """
        PHASE TRIGGER: If any model's reliability_score changed by >10%
        from the usage flush, immediately trigger the Hourly Optimizer cron job
        to propagate score changes faster than the next scheduled tick.

        Hourly Optimizer job ID: a115de75d3ef
        """
        TRIGGER_THRESHOLD = 0.10  # 10% absolute change
        JOB_ID = "a115de75d3ef"

        triggered = []
        for model_id, new_reliability, _ in updated_models:
            # model_id may be composite "provider/model" or bare "model"
            parts = model_id.split("/", 1)
            if len(parts) == 2:
                pname_lookup, mid_lookup = parts
            else:
                pname_lookup, mid_lookup = "", model_id

            old_rel = 1.0  # default if not found
            for pname, pdata in master.get("providers", {}).items():
                if model_id in pdata.get("models", {}):
                    mdata = pdata["models"][model_id]
                    old_rel = mdata.get("reliability_score", 1.0)
                # Use previous flush reliability (before this update) for delta
                prev_rel = getattr(self, "_last_flush_rel", {})
                old_base = prev_rel.get(
                    model_id,
                    old_rel  # First flush: compare against current MASTER reliability
                )
                delta = abs(new_reliability - old_base)
                if delta > TRIGGER_THRESHOLD:
                    triggered.append((model_id, old_base, new_reliability, delta))
                break

        if not triggered:
            return

        # Log trigger event
        for model_id, old_r, new_r, delta in triggered:
            logger.warning(
                f"[Router] Score change \u062510% for {model_id}: "
                f"{old_r:.3f}\u2192{new_r:.3f} (\u0394={delta:.3f}) \u2014 triggering Hourly Optimizer"
            )

        # Trigger cron job via Hermes scheduler API
        try:
            import subprocess
            result = subprocess.run(
                ["hermes", "cron", "run", JOB_ID],
                capture_output=True, text=True, timeout=30,
                cwd="/root/.hermes/profiles/ilma",
            )
            if result.returncode == 0:
                logger.info(f"[Router] Hourly Optimizer triggered successfully")
            else:
                logger.warning(
                    f"[Router] Hourly Optimizer trigger failed: {result.stderr[:200]}"
                )
        except FileNotFoundError:
            logger.warning("[Router] 'hermes' CLI not in PATH — skipping job trigger")
        except Exception as e:
            logger.warning(f"[Router] Failed to trigger Hourly Optimizer: {e}")

        # Store current reliability as baseline for next flush
        if not hasattr(self, "_last_flush_rel"):
            self._last_flush_rel = {}
        for model_id, new_reliability, _ in updated_models:
            self._last_flush_rel[model_id] = new_reliability

    def list_free_models(self, task_type: Optional[str] = None) -> List[Dict]:
        """
        List all free models, optionally filtered by task type.
        
        Returns list of {model_id, provider, composite_score, ...}
        """
        if task_type is None:
            task = "general"
        elif task_type in TASK_WEIGHTS:
            task = task_type
        else:
            task = self.classify_task(task_type)

        candidates = self._build_candidate_pool(task, allow_paid=False)

        results = []
        for mid, pname, mdata in candidates:
            composite, breakdown = self._compute_composite_score(mdata, task, allow_paid=False)
            results.append({
                "model_id":          mid,
                "provider":          pname,
                "is_free":           True,
                "composite_score":   round(composite, 4),
                "capability_score":  breakdown["capability_score"],
                "intelligence_score": breakdown["intelligence_score"],
                "context_score":     breakdown["context_score"],
                "specialization":    mdata.get("subagent_specialization", {}).get("primary_role_hint", "general"),
            })

        results.sort(key=lambda x: x["composite_score"], reverse=True)
        return results[:50]

    def log_usage(
        self,
        model_id: str,
        provider: str,
        task_type: str,
        success: bool,
        latency_ms: float = 0,
    ):
        """Log model usage for freshness tracking and feedback."""
        entry = {
            "timestamp":   datetime.now().isoformat(),
            "model_id":    model_id,
            "provider":    provider,
            "task_type":   task_type,
            "success":     success,
            "latency_ms":  latency_ms,
        }

        try:
            with open(USAGE_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
            self._recent_used[model_id] = datetime.now()
        except Exception as e:
            logger.warning(f"[Router] Failed to log usage: {e}")

        # Circuit breaker management
        if success:
            self._failure_count[model_id] = max(0, self._failure_count.get(model_id, 0) - 1)
        else:
            self._failure_count[model_id] = self._failure_count.get(model_id, 0) + 1
            if self._failure_count[model_id] >= self.CIRCUIT_THRESHOLD:
                self._cooldown_until[model_id] = time.time() + self.CIRCUIT_COOLDOWN
                logger.warning(f"[Router] Circuit trip: {model_id} (cooldown {self.CIRCUIT_COOLDOWN}s)")

    def _update_health_failure_count(self, model_id: str, count: int):
        """Persist failure count to health file. Called on every mark_failure/mark_success."""
        health = self._load_health()
        model_key = model_id  # Use as-is; subagent router uses same namespace
        if "models" not in health:
            health["models"] = {}
        if model_key not in health["models"]:
            health["models"][model_key] = {
                "status": "unknown", "consecutive_failures": 0,
                "total_failures": 0, "unavailable": False, "rate_limited": False,
                "last_error": None, "last_success": None,
            }
        health["models"][model_key]["consecutive_failures"] = count
        health["models"][model_key]["last_error"] = datetime.now().isoformat()
        self._save_health(health)

    def mark_success(self, model_id: str):
        """Record successful call. Persists to health file. Resets tiered state."""
        self._failure_count[model_id] = max(0, self._failure_count.get(model_id, 0) - 1)
        self._update_health_failure_count(model_id, self._failure_count[model_id])
        # Remove cooldown on success (model recovered)
        if model_id in self._cooldown_until:
            del self._cooldown_until[model_id]
        # Update health file: mark healthy
        health = self._load_health()
        if "models" not in health:
            health["models"] = {}
        if model_id not in health["models"]:
            health["models"][model_id] = {"status": "unknown",
                "consecutive_failures": 0, "total_failures": 0,
                "unavailable": False, "rate_limited": False,
                "last_error": None, "last_success": None, "cooldown_until": None}
        health["models"][model_id]["status"] = "healthy"
        health["models"][model_id]["consecutive_failures"] = 0
        health["models"][model_id]["last_success"] = datetime.utcnow().isoformat()
        health["models"][model_id]["cooldown_until"] = None
        self._save_health(health)

    def mark_failure(self, model_id: str, error_type: str = "unknown_error",
                     is_timeout_once: bool = False):
        """
        Record failed call with failure-type classification.
        Uses CircuitBreakerPolicy for tiered cooldown (Phase 4C-R Enhancement).

        Args:
            model_id: model identifier
            error_type: one of SubAgentRouter error_type values (e.g. 'timeout',
                        'rate_limit', 'malformed_response', etc.)
            is_timeout_once: set True if this is a single httpx timeout
                              (1 timeout = 10s cooldown, not 90s)
        """
        self._failure_count[model_id] = self._failure_count.get(model_id, 0) + 1
        count = self._failure_count[model_id]
        self._update_health_failure_count(model_id, count)

        # Classify and determine cooldown
        failure_class = CircuitBreakerPolicy.classify_failure(error_type)
        if is_timeout_once and failure_class == "soft":
            # 1-timeout should not immediately disable model
            cooldown = CircuitBreakerPolicy.TIMEOUT_COOLDOWN
        else:
            cooldown = CircuitBreakerPolicy.get_cooldown(failure_class, count, is_timeout_once)

        now = time.time()
        self._cooldown_until[model_id] = now + cooldown

        # Determine tiered status
        if count >= CircuitBreakerPolicy.DISABLE_THRESHOLD:
            status = "disabled"
        elif count >= CircuitBreakerPolicy.DEGRADE_THRESHOLD:
            status = "degraded"
        else:
            status = "degraded"  # 1-2 failures = soft degraded

        # Persist to health file
        health = self._load_health()
        if "models" not in health:
            health["models"] = {}
        if model_id not in health["models"]:
            health["models"][model_id] = {"status": "unknown",
                "consecutive_failures": 0, "total_failures": 0,
                "unavailable": False, "rate_limited": False,
                "last_error": None, "last_success": None, "cooldown_until": None}
        health["models"][model_id].update({
            "status": status,
            "consecutive_failures": count,
            "last_error": error_type,
            "cooldown_until": datetime.fromtimestamp(now + cooldown).isoformat(),
            "failure_class": failure_class,
            "failure_count": count,
        })
        if failure_class == "rate_limit":
            health["models"][model_id]["rate_limited"] = True
        if failure_class in ("hard", "critical"):
            health["models"][model_id]["unavailable"] = True
        self._save_health(health)

        log_msg = (f"[CircuitBreaker] {model_id}: {failure_class}={error_type} "
                   f"(x{count}) → {status}, cooldown {cooldown}s")
        if failure_class == "critical":
            logger.error(log_msg)
        else:
            logger.warning(log_msg)

    def _emergency_fallback(self) -> Dict[str, Any]:
        """Return hardcoded emergency fallback when all routing fails."""
        return {
            "model_id":           "MiniMax-M3",
            "provider":           "minimax",
            "is_free":            True,
            "composite_score":    0.75,
            "capability_score":   0.70,
            "intelligence_score": 0.78,
            "context_score":      0.85,
            "trust_score":        1.00,
            "routing_reason":     "EMERGENCY_FALLBACK: using verified free minimax/MiniMax-M3",
            "routing_method":     "ILMAUnifiedRouter_v1.0",
            "fallbacks":          [],
            "is_emergency":       True,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        db = self._load_master()
        providers = db.get("providers", {})
        total_models = sum(len(p.get("models", {})) for p in providers.values())
        free_models = sum(
            sum(1 for m in p.get("models", {}).values()
                if m.get("is_free", False))
            for p in providers.values()
        )

        return {
            "total_providers":        len(providers),
            "total_models":          total_models,
            "total_free_candidates": free_models,
            "allow_paid":            self.allow_paid,
            "routing_method":       "ILMAUnifiedRouter_v1.0",
            # MongoDB-driven mode (v7.0) no longer requires the legacy JSON file to exist;
            # guard so get_stats() (called by health monitors) can't raise FileNotFoundError.
            "master_db_size_mb":     (round(MASTER_DB.stat().st_size / 1024 / 1024, 2)
                                       if MASTER_DB.exists() else None),
            "master_last_modified":  (datetime.fromtimestamp(MASTER_DB.stat().st_mtime).isoformat()
                                       if MASTER_DB.exists() else None),
            "circuit_breaker_state": {
                "tripped_models": [
                    m for m, c in self._failure_count.items()
                    if c >= self.CIRCUIT_THRESHOLD
                ],
                "cooldown_count": len([
                    m for m, t in self._cooldown_until.items()
                    if time.time() < t
                ]),
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS — BACKWARD COMPAT
# ══════════════════════════════════════════════════════════════════════════════

_router_instance: Optional[ILMAUnifiedRouter] = None
_router_lock = threading.Lock()


def get_router(allow_paid: bool = False) -> ILMAUnifiedRouter:
    """Get singleton router instance with policy-state isolation.

    A router initialized for free-only mode must not be silently reused for an
    explicit paid request, and vice versa. Recreate the singleton if the caller
    requests a different allow_paid policy.

    Thread-safe: background daemon threads (health/optimizer) and request threads
    can call this concurrently — double-checked locking prevents double construction
    and torn singleton state (audit 2026-06-20).
    """
    global _router_instance
    if _router_instance is None or getattr(_router_instance, "allow_paid", False) != allow_paid:
        with _router_lock:
            if _router_instance is None or getattr(_router_instance, "allow_paid", False) != allow_paid:
                _router_instance = ILMAUnifiedRouter(allow_paid=allow_paid)
    return _router_instance


def get_best_model(
    task_type: str,
    prefer_free: bool = True,
    avoid_models: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Get best model for task type."""
    router = get_router(allow_paid=not prefer_free)
    return router.get_best_model(task_type, avoid_models=avoid_models)


def route_task(
    task_type: str,
    max_fallbacks: int = 5,
) -> Dict[str, Any]:
    """Route task with primary + fallback chain."""
    router = get_router()
    return router.route(task_type, n_fallbacks=max_fallbacks)


def list_free_models(task_type: Optional[str] = None) -> List[Dict]:
    """List all free models optionally filtered by task."""
    router = get_router()
    return router.list_free_models(task_type)


def detect_task_type(task: str) -> str:
    """Detect task type from description."""
    router = get_router()
    return router.classify_task(task)


def get_router_stats() -> Dict[str, Any]:
    """Get router statistics."""
    router = get_router()
    return router.get_stats()


def is_model_allowed(model_id: str, is_free: bool = True) -> bool:
    """Check if a concrete provider/model is runtime allowed under free-only policy."""
    router = get_router()
    if "/" in model_id:
        provider, mid = model_id.split("/", 1)
    else:
        provider, mid = "openrouter", model_id
    return router.is_model_runtime_allowed(provider, mid, allow_paid=not is_free)


def log_usage(model_id: str, provider: str, task_type: str, success: bool = True):
    """Log model usage."""
    router = get_router()
    router.log_usage(model_id, provider, task_type, success)


def mark_success(model_id: str):
    """Record successful model call."""
    router = get_router()
    router.mark_success(model_id)


def mark_failure(model_id: str, error: str = ""):
    """Record failed model call."""
    router = get_router()
    router.mark_failure(model_id, error)


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY EXPORTS for old consumers
# ══════════════════════════════════════════════════════════════════════════════

def calculate_route_score(
    model_data: Dict,
    task_type: str,
    provider: str,
    benchmark_score: float = 0.0,
    allow_paid: bool = True,
) -> float:
    """
    Legacy wrapper that delegates to the router's scoring engine.
    """
    router = get_router()
    task = TASK_ALIASES.get(task_type, task_type)
    m_id = model_data.get("model_id", "")
    composite, breakdown = router._compute_composite_score(model_data, task, allow_paid=allow_paid)
    return composite


def load_provider_db() -> Dict:
    """Load PROVIDER_INTELLIGENCE_MASTER.json (backward compat)."""
    router = get_router()
    return router._load_master()


def _load_benchmark_db() -> Dict:
    """
    Legacy: benchmark data is NOW embedded in PROVIDER_INTELLIGENCE_MASTER.json.
    Returns a flat lookup dict for compat. Maps model_id → benchmark scores.
    """
    db = load_provider_db()
    result = {}
    for pname, pdata in db.get("providers", {}).items():
        for mid, mdata in pdata.get("models", {}).items():
            bp = mdata.get("benchmark_profile", {})
            if bp and bp.get("overall_score", 0) > 0:
                result[f"{pname}/{mid}"] = {
                    "overall": bp.get("overall_score", 0),
                    "coding_weighted": bp.get("coding_score", bp.get("overall_score", 0)),
                    "reasoning_weighted": bp.get("reasoning_score", bp.get("overall_score", 0)),
                }
    return result


def PROVIDER_TRUST_SCORES_FN() -> Dict:
    """Provider trust scores (backward compat)."""
    return PROVIDER_TRUST


# Alias for backward compat
PROVIDER_TRUST_SCORES = PROVIDER_TRUST


# Expose task weights and keyword map for consumers
TASK_WEIGHTS_LEGACY = TASK_WEIGHTS


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ILMA Unified Model Router")
    parser.add_argument("--task", "-t", type=str, help="Task type or description")
    parser.add_argument("--list", "-l", action="store_true", help="List free models")
    parser.add_argument("--stats", "-s", action="store_true", help="Router statistics")
    parser.add_argument("--classify", "-c", type=str, help="Classify task")
    args = parser.parse_args()

    if args.stats:
        print(json.dumps(get_router_stats(), indent=2))
    elif args.classify:
        print(detect_task_type(args.classify))
    elif args.list:
        task = args.task or None
        models = list_free_models(task)
        for m in models[:20]:
            print(f"  {m['model_id']} ({m['provider']}) score={m['composite_score']}")
    elif args.task:
        result = get_best_model(args.task)
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()

# =============================================================================
# NVIDIA NIM Thinking Model Detection
# =============================================================================

NVIDIANIM_THINKING_MODELS = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-content-safety-reasoning-4b",
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "qwen/qwen3.5-397b-a17b",
    "meta/llama-4-maverick-17b-128e-instruct",
]

def is_nvidia_nim_thinking_model(model: str) -> bool:
    return any(m in model or model in m for m in NVIDIANIM_THINKING_MODELS)

def get_nvidia_thinking_params(model: str) -> dict:
    if "nemotron" in model:
        return {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}
    elif "qwen" in model:
        return {"chat_template_kwargs": {"thinking": True}, "reasoning_budget": 16384}
    elif "maverick" in model:
        return {"chat_template_kwargs": {"thinking": True}, "reasoning_budget": 16384}
    return {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 8192}


# ══════════════════════════════════════════════════════════════════════════════
# v2.1 COMPATIBILITY LAYER (2026-06-01) — for ilma_master_orchestrator / ilma_orchestrator
# Provides simple tuple-style routing + direct execution while preserving the
# rich ILMAUnifiedRouter class API used everywhere else. Free-only enforced.
# ══════════════════════════════════════════════════════════════════════════════

def route_task_simple(prompt, task_type=None, force_model=None):
    """Return (model_id, provider, reason) for the v2.x orchestrators.

    NOTE: distinct from route_task() (which returns the rich fallback-chain dict).
    """
    try:
        router = get_router(allow_paid=False)
        if force_model:
            if "/" in force_model:
                prov, mid = force_model.split("/", 1)
            else:
                prov, mid = "openrouter", force_model
            if router.is_model_runtime_allowed(prov, mid, allow_paid=False):
                return mid, prov, "Forced verified-free model"
            logger.warning(f"[Router] Blocked unsafe forced model override: {force_model}")
        desc = task_type or prompt
        res = router.get_best_model(desc, allow_paid=False)
        mid = res.get("model_id") or "minimax-m2.7"
        prov = res.get("provider") or "minimax"
        reason = res.get("routing_reason") or f"best free model for {desc[:40]}"
        return mid, prov, reason
    except Exception as e:
        return "minimax-m2.7", "minimax", f"fallback ({e})"


def execute_call(model_id, provider, message, **kwargs):
    """Execute a single chat call via ProviderKernel (free callable providers)."""
    try:
        from ilma_provider_kernel import ProviderKernel
        kernel = ProviderKernel()
        messages = [{"role": "user", "content": message}]
        return kernel.call(provider, model_id, messages, **kwargs)
    except Exception as e:
        return f"Error: execute_call failed ({e})"
