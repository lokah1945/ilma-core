#!/usr/bin/env python3
"""
ilma_subagent_router.py — ILMA Sub-Agent Router v2.1 (Unified)
================================================================
Health-aware routing for ALL sub-agent calls.
SINGLE SOURCE OF TRUTH: ilma_model_router.py → PROVIDER_INTELLIGENCE_MASTER.json

Features:
- Health tracking: Every call records success/failure
- Circuit breaker: Skips models with consecutive failures
- No-repeat: Avoids models used in last 30 minutes
- Free-tier-first: Only free models by default
- Evidence-based scoring: All scores from MASTER JSON
- Content validation: Empty response = failure (marks health state)

Author: ILMA Core Team
Version: 2.1.0
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
# NOTE: the local proxy layer was fully purged 2026-06-19 — execution now goes through
# ilma_model_router directly. The old PROXY_URL constant was removed (audit 2026-06-20).

# ── Direct-provider execution support ──────────────────────────────────────────
# Callable free providers (nvidia, minimax, ollama-cloud) are reachable directly.
# Legacy proxy project removed 2026-06-19.
import json as _json_dp
from pathlib import Path as _Path_dp

_ENV_FILE_DP = _Path_dp("/root/.hermes/profiles/ilma/.env")
_CREDS_DP = _Path_dp("/root/credential/api_key.json")

def _load_env_dp():
    env = {}
    try:
        for line in _ENV_FILE_DP.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env

def _load_creds_dp():
    try:
        return _json_dp.load(open(_CREDS_DP))
    except Exception:
        return {}

_ENV_DP = _load_env_dp()
_CREDS_CACHE_DP = _load_creds_dp()

def _provider_key_dp(provider: str):
    """Resolve an inference key for a direct provider."""
    env = _ENV_DP
    creds = _CREDS_CACHE_DP
    if provider == "nvidia":
        if env.get("NVIDIA_API_KEY"):
            return env["NVIDIA_API_KEY"]
        for k in creds.get("nvidia", {}):
            if isinstance(k, str) and k.startswith("nvapi-"):
                return k
    if provider == "minimax":
        return env.get("MINIMAX_API_KEY")
    if provider == "ollama":
        ks = creds.get("ollama", {}).get("keys")
        return (ks[0] if isinstance(ks, list) else ks) if ks else None
    if provider == "openrouter":
        if env.get("OPENROUTER_API_KEY"):
            return env["OPENROUTER_API_KEY"]
        o = creds.get("openrouter", {})
        return o.get("call_key") or (o.get("keys") or [None])[0]
    return None

# (base_url, needs_key)  — endpoints proven callable 2026-06-01
_DIRECT_ENDPOINTS_DP = {
    "nvidia":  "https://integrate.api.nvidia.com/v1/chat/completions",
    "minimax": "https://api.minimax.io/v1/text/chatcompletion_v2",
    "ollama":  "https://ollama.com/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTING DECISION
# ══════════════════════════════════════════════════════════════════════════════

class RoutingDecision:
    """Result of model routing decision."""
    def __init__(
        self,
        model: str,
        thinking: str,
        provider: str,
        is_fallback: bool,
        fallback_models: List[str],
        reasoning: str,
        latency_estimate_ms: float = 0.0,
        source_type: str = "",
    ):
        self.model = model
        self.thinking = thinking
        self.provider = provider
        self.is_fallback = is_fallback
        self.fallback_models = fallback_models
        self.reasoning = reasoning
        self.latency_estimate_ms = latency_estimate_ms
        self.source_type = source_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "thinking": self.thinking,
            "provider": self.provider,
            "is_fallback": self.is_fallback,
            "fallback_models": self.fallback_models,
            "reasoning": self.reasoning,
            "latency_estimate_ms": self.latency_estimate_ms,
            "source_type": self.source_type,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SUBAGENT ROUTER
# ══════════════════════════════════════════════════════════════════════════════

class SubAgentRouter:
    """
    Unified router for all sub-agent calls.
    
    ALL routing decisions come from ilma_model_router.py:
    - task classification → score candidates → ranked by composite score
    - Health tracking via circuit breaker
    - No-repeat via freshness bonus
    """

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url  # deprecated/unused; kept for signature compatibility
        self.client = httpx.Client(timeout=60.0)
        # Import router lazily to avoid circular deps
        self.router = self._get_model_router()

    def _get_model_router(self):
        from ilma_model_router import ILMAUnifiedRouter
        return ILMAUnifiedRouter()

    # ══════════════════════════════════════════════════════════════════════════
    # ROUTING
    # ══════════════════════════════════════════════════════════════════════════

    def route(
        self,
        task_type_or_desc: str,
        thinking: str = "Auto",
        allow_paid: bool = False,
    ) -> RoutingDecision:
        """Route to best model for task using pure data-driven scoring."""
        result = self.router.get_best_model(
            task_type_or_desc=task_type_or_desc,
            allow_paid=allow_paid,
        )

        model = result.get("model_id", "")
        provider = result.get("provider", "")

        return RoutingDecision(
            model=model,
            thinking=thinking,
            provider=provider,
            is_fallback=False,
            fallback_models=result.get("fallbacks", []),
            reasoning=result.get("routing_reason", "data-driven composite score"),
        )

    # ══════════════════════════════════════════════════════════════════════════
    # LEGACY COMPATIBILITY
    # ══════════════════════════════════════════════════════════════════════════
    # select_model(role, task_category) — called by ilma.py --status for health-check.
    # Thin wrapper around route() for backward compatibility.

    def select_model(
        self,
        role: str = "general",
        task_category: str = "general",
    ) -> Optional[RoutingDecision]:
        """Select best model for role+task. Delegates to pure data-driven route()."""
        result = self.router.get_best_model(task_type_or_desc=task_category, allow_paid=False)
        model = result.get("model_id", "")
        provider = result.get("provider", "")
        return RoutingDecision(
            model=model,
            thinking="Auto",
            provider=provider,
            source_type="NATIVE",
            is_fallback=False,
            fallback_models=result.get("fallbacks", []),
            reasoning=f"select_model({role},{task_category}): {result.get('routing_reason','data-driven')}",
        )

    def route_and_execute(
        self,
        message: str,
        task_type_or_desc: str,
        thinking: str = "Auto",
        allow_paid: bool = False,
        stateless: bool = False,
    ) -> Dict[str, Any]:
        """Route + execute with automatic re-routing on circuit trip.
        
        Self-healing: If selected model is circuit-tripped or returns empty,
        re-route to healthy model automatically. Continues until working model
        found or all candidates exhausted.
        
        Routing is pure data-driven: model selected based on composite score
        (capability×0.35 + intelligence×0.30 + context×0.10 + trust×0.15 +
        freshness×0.10). No hardcoded primary model.
        """
        tried: set = set()  # Models that failed (tracked persistently)

        while len(tried) < 20:  # Safety limit
            # Route fresh each time — ensures we always pick the current best
            decision = self.route(task_type_or_desc, thinking, allow_paid)

            # If selected model already tried and failed, skip to fresh routing
            if decision.model in tried:
                # Try to get a new model from fallbacks
                if decision.fallback_models:
                    fb = decision.fallback_models[0]
                    fb_model = fb.get("model_id", "") if isinstance(fb, dict) else str(fb)
                    if fb_model not in tried:
                        fb_provider = fb.get("provider", "") if isinstance(fb, dict) else ""
                        print(f"[SUBAGENT] Skipping {decision.model} (already tried), trying: {fb_model}")
                        result = self._execute(fb_model, message, thinking, stateless, provider=fb_provider)
                        # _execute already calls mark_success/mark_failure
                        if result.get("success") and result.get("content"):
                            result["used_fallback"] = True
                            result["original_model"] = decision.model
                            result["decision"] = decision.to_dict()
                            return result
                        tried.add(fb_model)
                        continue
                # All candidates exhausted
                print(f"[SUBAGENT] All candidates tried. Tried: {list(tried)}")
                break

            # Execute
            result = self._execute(decision.model, message, thinking, stateless, provider=decision.provider)
            # _execute already calls mark_success/mark_failure

            if result.get("success") and result.get("content"):
                return {**result, "decision": decision.to_dict()}

            # Execution failed
            tried.add(decision.model)

            # If circuit tripped, try fallbacks before re-routing
            if not self.router._is_healthy(decision.model):
                print(f"[SUBAGENT] Circuit trip: {decision.model}")
                for fb in decision.fallback_models:
                    fb_model = fb.get("model_id", "") if isinstance(fb, dict) else str(fb)
                    if fb_model in tried:
                        continue
                    fb_provider = fb.get("provider", "") if isinstance(fb, dict) else ""
                    print(f"[SUBAGENT] Trying fallback: {fb_model}")
                    fb_result = self._execute(fb_model, message, thinking, stateless, provider=fb_provider)
                    if fb_result.get("success") and fb_result.get("content"):
                        fb_result["used_fallback"] = True
                        fb_result["original_model"] = decision.model
                        fb_result["decision"] = decision.to_dict()
                        return fb_result
                    tried.add(fb_model)
                    if not self.router._is_healthy(fb_model):
                        break  # Circuit tripped, re-route
                # Re-route to find new candidate
                print(f"[SUBAGENT] Re-routing after circuit trip...")
                continue

        # All candidates exhausted
        tried_list = list(tried)
        return {
            "success": False,
            "content": "",
            "model": tried_list[-1] if tried_list else "",
            "error": f"No working model after {len(tried_list)} attempts. Tried: {tried_list}",
            "all_failed": True,
        }

    

    def _execute(self, model: str, message: str, thinking: str, stateless: bool, provider: str = "") -> Dict[str, Any]:
        """Execute call and update health state.

        Routing: All providers called via direct REST API (no proxy).
        Legacy proxy project removed 2026-06-19.
        """
        start = time.time()
        if provider in _DIRECT_ENDPOINTS_DP:
            result = self._call_direct(provider, model, message, timeout=60)
        else:
            result = {
                "success": False,
                "content": "",
                "model": model,
                "error": f"NO_DIRECT_ENDPOINT: {provider} (proxy removed 2026-06-19)",
            }
        elapsed_ms = (time.time() - start) * 1000

        # Update health state
        if result.get("success") and result.get("content"):
            self.router.mark_success(model)
        else:
            self.router.mark_failure(model, result.get("error", ""))

        result["latency_ms"] = elapsed_ms
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # DIRECT PROVIDER CALL (no proxy — legacy bridge removed 2026-06-19)
    # ══════════════════════════════════════════════════════════════════════════

    def _call_direct(self, provider: str, model: str, message: str, timeout: int) -> Dict[str, Any]:
        """Execute a chat call against a direct provider REST API (free-only upstream)."""
        url = _DIRECT_ENDPOINTS_DP.get(provider)
        if not url:
            return {"success": False, "content": "", "model": model,
                    "error": f"NO_DIRECT_ENDPOINT: {provider}"}
        key = _provider_key_dp(provider)
        if not key:
            return {"success": False, "content": "", "model": model,
                    "error": f"NO_KEY: {provider}"}
        # model_id already in the provider's native format (no ILMA provider prefix)
        api_model = model
        payload = {"model": api_model,
                   "messages": [{"role": "user", "content": message}],
                   "max_tokens": 2048}
        # FIX 2026-06-20 (audit C3): retry transient failures with jittered exponential
        # backoff. Previously a single post — any timeout/429/5xx = immediate failure.
        # Retry on connection/timeout errors + HTTP 429 + 5xx; fail-fast on other 4xx.
        import time as _t
        try:
            from ilma_backoff import compute_backoff
        except Exception:
            def compute_backoff(a, **k): return min(8.0, 0.5 * (2 ** a))
        MAX_ATTEMPTS = 3
        last_err = "unknown"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = self.client.post(url, json=payload, timeout=timeout, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    content = ""
                    try:
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
                    except Exception:
                        content = ""
                    if not (content and content.strip()):
                        return {"success": False, "content": "", "model": model,
                                "error": "EMPTY_RESPONSE (direct)"}
                    return {"success": True, "content": content, "model": model, "error": "", "latency_ms": 0}
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                # permanent client errors (auth/bad request) — do not retry (429 is transient)
                if resp.status_code != 429 and 400 <= resp.status_code < 500:
                    return {"success": False, "content": "", "model": model, "error": last_err}
            except Exception as e:
                last_err = str(e)
            if attempt < MAX_ATTEMPTS - 1:
                _t.sleep(compute_backoff(attempt, base_delay=0.5, max_delay=8.0))
        return {"success": False, "content": "", "model": model,
                "error": f"after {MAX_ATTEMPTS} attempts: {last_err}"}

    def close(self):
        """Clean up resources."""
        self.client.close()


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

_router_instance: Optional[SubAgentRouter] = None
_router_lock = threading.Lock()


def get_router(proxy_url: Optional[str] = None) -> SubAgentRouter:
    """Get singleton SubAgentRouter instance (thread-safe, audit 2026-06-20)."""
    global _router_instance
    if _router_instance is None:
        with _router_lock:
            if _router_instance is None:
                _router_instance = SubAgentRouter(proxy_url=proxy_url)
    return _router_instance


def close_router():
    """Close router and clean up resources."""
    global _router_instance
    if _router_instance:
        _router_instance.close()
        _router_instance = None


# =============================================================================
# NVIDIA NIM Delegate Support
# =============================================================================

NVIDIANIM_DELEGATE_MODELS = {
    "thinking": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "reasoning": "nvidia/nemotron-content-safety-reasoning-4b",
    "vision": "meta/llama-3.2-90b-vision-instruct",
    "fast": "deepseek-ai/deepseek-v4-flash",
    "coding": "qwen/qwen3.5-397b-a17b",
}

def get_nvidia_nim_delegate_model(task_type: str) -> str:
    return NVIDIANIM_DELEGATE_MODELS.get(task_type, "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")

def is_delegate_task_for_nvidia(task: str) -> bool:
    thinking_keywords = ["prove", "reason", "think", "explain", "sqrt", "proof"]
    return any(kw in task.lower() for kw in thinking_keywords)