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
# Phase 73b — RUNTIME MEDIA CAPABILITY EXECUTION (image / stt / embedding / tts /
# rerank / video).  SOT-driven, FREE-first.  Wired 2026-06-21 (task001).
#
# Why: the orchestrator → SubAgentRouter path was chat-only. A media request
# (e.g. "generate an image") got misclassified as a `vision` chat task and the
# only working image backend was hardcoded xAI (PAID). These executors close
# that gap: capability → SOT free pick (ilma_sot_dispatcher) → correct transport.
# Transport detail (URL/payload shape) lives HERE; SOT owns model SELECTION.
# Verified free transports (2026-06-21): image=wrapper-nvidia genai (FLUX.1-schnell),
# stt=groq whisper, embedding=wrapper-nvidia. NO xAI unless allow_paid=True.
# ══════════════════════════════════════════════════════════════════════════════

# Non-chat capabilities routed through the SOT capability dispatcher.
MEDIA_CAPABILITIES = {"image", "image_edit", "video", "tts", "stt",
                      "embedding", "rerank", "music"}

# Intent → capability (EN + ID).  Order matters: most-specific first so that
# "transcribe this voice note" does not collide with "voice"/tts, etc.
_MEDIA_INTENT = [
    ("stt",        ["transcribe", "transcription", "transcript ", "speech to text",
                    "speech-to-text", "voice note", "transkrip", "audio to text",
                    "stt "]),
    ("tts",        ["text to speech", "text-to-speech", " tts", "read aloud",
                    "bacakan", "narasikan", "voice over", "voiceover", "jadikan suara",
                    "ubah jadi suara", "say this aloud"]),
    ("image_edit", ["edit image", "edit gambar", "edit this image", "inpaint",
                    "ubah gambar", "modify image", "retouch", "image edit"]),
    ("video",      ["generate video", "generate a video", "buat video",
                    "buatkan video", "create video", "create a video", "text to video",
                    "text-to-video", "animate this", "video generation"]),
    ("image",      ["generate image", "generate an image", "generate a picture",
                    "create image", "create an image", "make an image", "make a picture",
                    "buat gambar", "buatkan gambar", "bikin gambar", "gambarkan",
                    "buatkan ilustrasi", "buat ilustrasi", "draw me", "draw a",
                    "image generation", "text to image", "text-to-image",
                    "featured image", "thumbnail image", "generate art"]),
    ("rerank",     ["rerank", "re-rank", "rerank documents", "rerank these"]),
    ("embedding",  ["embedding for", "embed this", "embed the", "vectorize",
                    "vector representation", "compute embeddings"]),
]


def detect_media_capability(text: str) -> Optional[str]:
    """Return a non-chat capability id if the request is a media/specialist task,
    else None (→ normal chat routing).  Conservative: only fires on explicit
    generation/transcription/embedding intent so plain chat is never hijacked."""
    t = f" {(text or '').lower()} "
    for cap, kws in _MEDIA_INTENT:
        if any(k in t for k in kws):
            return cap
    return None


# Local wrapper-nvidia (force_free, key-pooled) — preferred media transport.
_WRAPPER_NVIDIA_BASE = "http://127.0.0.1:9100"
_NVIDIA_GENAI_BASE = "https://ai.api.nvidia.com"
# Embedding model that is actually provisioned on the pooled NVIDIA accounts
# (the SOT free embed picks 404 on this account; verified 2026-06-21).
_NVIDIA_EMBED_DEFAULT = "nvidia/nv-embedqa-e5-v5"
_IMAGE_FREE_DEFAULT = "black-forest-labs/flux.1-schnell"  # nvidia genai slug


def _media_provider_key_dp(provider: str) -> Optional[str]:
    """Resolve an API key for a media provider, handling nested account dicts
    in /root/credential/api_key.json (e.g. together keyed by account email)."""
    p = (provider or "").lower()
    # env first
    env_name = {"nvidia": "NVIDIA_API_KEY", "groq": "GROQ_API_KEY",
                "together": "TOGETHER_API_KEY", "minimax": "MINIMAX_API_KEY",
                "xai": "XAI_API_KEY", "openai": "OPENAI_API_KEY"}.get(p)
    if env_name and _ENV_DP.get(env_name):
        return _ENV_DP[env_name]
    entry = _CREDS_CACHE_DP.get(p)
    if isinstance(entry, dict):
        # flat shapes
        if isinstance(entry.get("api_key"), str):
            return entry["api_key"]
        ks = entry.get("keys")
        if isinstance(ks, list) and ks and isinstance(ks[0], str):
            return ks[0]
        if isinstance(ks, str):
            return ks
        # nested account dicts (e.g. together -> {"a@b.com": {"api_key": ...}})
        for v in entry.values():
            if isinstance(v, dict) and isinstance(v.get("api_key"), str):
                return v["api_key"]
            if isinstance(v, dict):
                vk = v.get("keys")
                if isinstance(vk, list) and vk and isinstance(vk[0], str):
                    return vk[0]
    elif isinstance(entry, str):
        return entry
    return None


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
    # Phase 73 — SOT FREE-ONLY DIRECT (capability → model) dispatch
    # ══════════════════════════════════════════════════════════════════════════

    def route_capability(self, capability: str, *, strict: bool = False,
                         allow_paid: bool = False,
                         provider: Optional[str] = None,
                         quality: Optional[str] = None,
                         thinking: str = "Auto") -> RoutingDecision:
        """SOT-only routing for ANY non-chat capability (image, tts, stt,
        embedding, video, audio, rerank, ...).

        - strict=False (default) → soft fallback to raw is_free=True for ramp-up
        - allow_paid=True → bypass FREE filter (NOT ILMA default).
        - provider=None → best across all FREE providers in SOT.
        """
        try:
            from ilma_sot_dispatcher import sot_dispatch
            disp = sot_dispatch(capability, strict=strict,
                                allow_paid=allow_paid,
                                provider=provider,
                                quality=quality)
        except Exception as e:
            logger.warning(f"SOT dispatch unavailable ({e}); falling back to chat router")
            return self.route(task_type_or_desc=capability,
                              thinking=thinking,
                              allow_paid=allow_paid)

        if disp.get("error"):
            return RoutingDecision(
                model="",
                thinking=thinking,
                provider="",
                source_type="SOT",
                is_fallback=False,
                fallback_models=[],
                reasoning=f"SOT dispatch failed: {disp.get('error')} | "
                          f"hint={disp.get('hint', '')}",
            )
        alts = [
            f"{a['provider']}/{a['model_id']}"
            for a in disp.get("alternatives", [])
        ]
        return RoutingDecision(
            model=disp["model_id"],
            thinking=thinking,
            provider=disp["provider"],
            source_type="SOT",
            is_fallback=False,
            fallback_models=alts,
            reasoning=("SOT free-only dispatch — provider={prov} model={m} "
                       "ep={e} if={iff} score={sc}").format(
                prov=disp["provider"], m=disp["model_id"],
                e=disp.get("endpoint_type"),
                iff=disp.get("is_free_final"),
                sc=disp.get("score")),
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

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 73b — MEDIA CAPABILITY EXECUTION (SOT-driven, FREE-first)
    # ══════════════════════════════════════════════════════════════════════════

    def execute_capability(self, capability: str, prompt: str = "", *,
                           allow_paid: bool = False,
                           audio_path: Optional[str] = None,
                           input_text: Optional[str] = None,
                           out_path: Optional[str] = None,
                           **kw) -> Dict[str, Any]:
        """Resolve the best FREE model for a non-chat capability via SOT, then
        execute it against the correct transport. Returns a normalized dict:
            {success, capability, provider, model, path|url|text|vector, error}
        NEVER falls back to a paid provider unless allow_paid=True.
        """
        cap = (capability or "").strip().lower()
        # 1) SOT free-only model selection (strict first, soft fallback).
        decision = None
        try:
            from ilma_sot_dispatcher import sot_dispatch
            decision = sot_dispatch(cap, strict=True, allow_paid=allow_paid)
            if decision.get("error"):
                decision = sot_dispatch(cap, strict=False, allow_paid=allow_paid)
        except Exception as e:
            logger.warning(f"[CAP] SOT dispatch failed for {cap}: {e}")
            decision = {"error": str(e)}
        provider = (decision or {}).get("provider") or ""
        model = (decision or {}).get("model_id") or ""
        logger.info(f"[CAP] capability={cap} sot_pick={provider}/{model} "
                    f"free={decision.get('is_free_final') if decision else '?'}")

        # 2) Dispatch to the transport-aware executor.
        try:
            if cap in ("image", "image_edit"):
                res = self._exec_image(provider, model, prompt, out_path=out_path,
                                       allow_paid=allow_paid, edit=(cap == "image_edit"),
                                       **kw)
            elif cap == "stt":
                res = self._exec_stt(provider, model, audio_path=audio_path, **kw)
            elif cap == "embedding":
                res = self._exec_embedding(provider, model,
                                           input_text=input_text or prompt, **kw)
            elif cap == "tts":
                res = self._exec_tts(provider, model,
                                     input_text=input_text or prompt,
                                     out_path=out_path, allow_paid=allow_paid, **kw)
            elif cap == "rerank":
                res = self._exec_rerank(provider, model, query=prompt, **kw)
            else:  # video / music — no verified free HTTP transport yet
                res = {"success": False,
                       "error": f"capability '{cap}' has no wired free transport yet "
                                f"(SOT pick: {provider}/{model})",
                       "needs_backend": True}
        except Exception as e:
            res = {"success": False, "error": f"{type(e).__name__}: {e}"}

        res.setdefault("capability", cap)
        res.setdefault("provider", provider)
        res.setdefault("model", model)
        res["sot_decision"] = {"provider": provider, "model": model,
                               "is_free_final": (decision or {}).get("is_free_final"),
                               "endpoint_type": (decision or {}).get("endpoint_type"),
                               "score": (decision or {}).get("score")}
        return res

    def _image_out_path(self, out_path: Optional[str], ext: str = "jpg") -> str:
        import os as _os, hashlib as _h, time as _t
        if out_path:
            _os.makedirs(_os.path.dirname(out_path) or ".", exist_ok=True)
            return out_path
        d = "/root/.hermes/profiles/ilma/cache/images"
        _os.makedirs(d, exist_ok=True)
        return f"{d}/cap_{_h.md5(str(_t.time()).encode()).hexdigest()[:12]}.{ext}"

    def _exec_image(self, provider: str, model: str, prompt: str, *,
                    out_path: Optional[str] = None, allow_paid: bool = False,
                    edit: bool = False, **kw) -> Dict[str, Any]:
        """FREE-first image generation. Order:
        1. wrapper-nvidia genai (local, force_free, key-pooled) — FLUX.1-schnell
        2. nvidia genai direct (ai.api.nvidia.com) with NVIDIA_API_KEY
        3. together /v1/images/generations (only if allow_paid — Together is paid in SOT)
        4. xAI (only if allow_paid)
        """
        import os as _os, base64 as _b64
        prov = (provider or "").lower()
        # genai slug: nvidia models use lowercase namespace/name; default to verified FLUX.
        genai_model = (model or "").lower() if prov in ("nvidia", "wrapper-nvidia") else _IMAGE_FREE_DEFAULT
        if not genai_model or "/" not in genai_model:
            genai_model = _IMAGE_FREE_DEFAULT
        payload = {"prompt": prompt, "mode": "base", "steps": 4}

        def _save_b64(b64: str, src_model: str, src_prov: str) -> Dict[str, Any]:
            path = self._image_out_path(out_path)
            with open(path, "wb") as f:
                f.write(_b64.b64decode(b64))
            ok = _os.path.exists(path) and _os.path.getsize(path) > 1000
            return {"success": ok, "path": path, "provider": src_prov,
                    "model": src_model, "billing": "free",
                    "error": "" if ok else "decoded image too small"}

        # 1 + 2: NVIDIA genai (wrapper preferred, then direct)
        attempts = [(_WRAPPER_NVIDIA_BASE, "wrapper-local-key", "wrapper-nvidia")]
        nv_key = _media_provider_key_dp("nvidia")
        if nv_key:
            attempts.append((_NVIDIA_GENAI_BASE, nv_key, "nvidia"))
        last_err = ""
        for base, key, src_prov in attempts:
            for mdl in [genai_model, _IMAGE_FREE_DEFAULT]:
                url = f"{base}/v1/genai/{mdl}"
                try:
                    r = self.client.post(url, json=payload, timeout=120,
                                         headers={"Authorization": f"Bearer {key}",
                                                  "Accept": "application/json"})
                    if r.status_code == 200:
                        data = r.json()
                        arts = data.get("artifacts") or []
                        if arts and arts[0].get("base64"):
                            return _save_b64(arts[0]["base64"], mdl, src_prov)
                        # some models return data[].b64_json / url
                        d0 = (data.get("data") or [{}])[0]
                        if d0.get("b64_json"):
                            return _save_b64(d0["b64_json"], mdl, src_prov)
                        last_err = f"{src_prov}:{mdl} 200 but no image in {str(data)[:120]}"
                    else:
                        last_err = f"{src_prov}:{mdl} HTTP {r.status_code}: {r.text[:120]}"
                except Exception as e:
                    last_err = f"{src_prov}:{mdl} {type(e).__name__}: {e}"
                if mdl == genai_model and genai_model == _IMAGE_FREE_DEFAULT:
                    break  # don't retry the same model twice

        # 3: Together (OpenAI-compatible, returns URL) — paid in SOT, gated.
        if allow_paid:
            tg_key = _media_provider_key_dp("together")
            if tg_key:
                try:
                    r = self.client.post("https://api.together.xyz/v1/images/generations",
                        json={"model": "black-forest-labs/FLUX.1-schnell",
                              "prompt": prompt, "steps": 4, "n": 1,
                              "response_format": "b64_json"},
                        timeout=120, headers={"Authorization": f"Bearer {tg_key}"})
                    if r.status_code == 200:
                        d0 = (r.json().get("data") or [{}])[0]
                        if d0.get("b64_json"):
                            res = _save_b64(d0["b64_json"], "black-forest-labs/FLUX.1-schnell", "together")
                            res["billing"] = "paid"
                            return res
                        if d0.get("url"):
                            return {"success": True, "url": d0["url"],
                                    "provider": "together", "billing": "paid",
                                    "model": "black-forest-labs/FLUX.1-schnell"}
                    last_err = f"together HTTP {r.status_code}: {r.text[:120]}"
                except Exception as e:
                    last_err = f"together {type(e).__name__}: {e}"

        return {"success": False, "provider": "nvidia", "model": genai_model,
                "error": f"all FREE image backends failed: {last_err}"
                         + ("" if allow_paid else " (paid providers disabled — pass allow_paid=True for Together/xAI)")}

    def _exec_stt(self, provider: str, model: str, *, audio_path: Optional[str] = None,
                  **kw) -> Dict[str, Any]:
        """Speech-to-text via groq whisper (free, OpenAI-compatible multipart)."""
        import os as _os
        if not audio_path or not _os.path.exists(audio_path):
            return {"success": False, "error": "stt requires an existing audio_path"}
        key = _media_provider_key_dp("groq")
        if not key:
            return {"success": False, "error": "no groq key for STT"}
        mdl = model if (provider == "groq" and model) else "whisper-large-v3"
        try:
            with open(audio_path, "rb") as fh:
                r = self.client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {key}"},
                    data={"model": mdl, "response_format": "json"},
                    files={"file": (_os.path.basename(audio_path), fh)},
                    timeout=120)
            if r.status_code == 200:
                return {"success": True, "text": r.json().get("text", ""),
                        "provider": "groq", "model": mdl, "billing": "free"}
            return {"success": False, "error": f"groq STT HTTP {r.status_code}: {r.text[:150]}"}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

    def _exec_embedding(self, provider: str, model: str, *, input_text: str = "",
                        **kw) -> Dict[str, Any]:
        """Embeddings via wrapper-nvidia (force_free, local, key-pooled)."""
        mdl = model if (provider in ("nvidia", "wrapper-nvidia") and model) else _NVIDIA_EMBED_DEFAULT
        for mdl_try in [mdl, _NVIDIA_EMBED_DEFAULT]:
            try:
                r = self.client.post(f"{_WRAPPER_NVIDIA_BASE}/v1/embeddings",
                    json={"model": mdl_try, "input": input_text, "input_type": "query"},
                    headers={"Authorization": "Bearer wrapper-local-key"}, timeout=60)
                if r.status_code == 200:
                    vec = (r.json().get("data") or [{}])[0].get("embedding")
                    if vec:
                        return {"success": True, "vector": vec, "dim": len(vec),
                                "provider": "wrapper-nvidia", "model": mdl_try,
                                "billing": "free"}
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
                continue
            last = f"HTTP {r.status_code}: {r.text[:120]}"
        return {"success": False, "error": f"embedding failed: {last}"}

    def _exec_rerank(self, provider: str, model: str, *, query: str = "",
                     documents: Optional[List[str]] = None, **kw) -> Dict[str, Any]:
        """Rerank via wrapper-nvidia (best-effort; NVIDIA reranking NIM)."""
        docs = documents or kw.get("docs") or []
        if not docs:
            return {"success": False, "error": "rerank requires 'documents' list"}
        mdl = model or "nvidia/llama-3.2-nv-rerankqa-1b-v2"
        try:
            r = self.client.post(f"{_WRAPPER_NVIDIA_BASE}/v1/ranking",
                json={"model": mdl, "query": {"text": query},
                      "passages": [{"text": d} for d in docs]},
                headers={"Authorization": "Bearer wrapper-local-key"}, timeout=60)
            if r.status_code == 200:
                return {"success": True, "rankings": r.json().get("rankings"),
                        "provider": "wrapper-nvidia", "model": mdl, "billing": "free"}
            return {"success": False, "error": f"rerank HTTP {r.status_code}: {r.text[:120]}"}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

    def _exec_tts(self, provider: str, model: str, *, input_text: str = "",
                  out_path: Optional[str] = None, allow_paid: bool = False,
                  **kw) -> Dict[str, Any]:
        """Text-to-speech. Tries edge-tts (free, local) if installed; no other
        verified free HTTP TTS endpoint exists (nvidia speech 404s). Honest fail
        otherwise so callers can surface a clear message instead of silent paid use."""
        import os as _os, asyncio as _asyncio
        path = out_path or self._image_out_path(None, ext="mp3")
        try:
            import edge_tts  # type: ignore
            async def _run():
                voice = kw.get("voice", "en-US-AriaNeural")
                await edge_tts.Communicate(input_text, voice).save(path)
            _asyncio.run(_run())
            if _os.path.exists(path) and _os.path.getsize(path) > 256:
                return {"success": True, "path": path, "provider": "edge",
                        "model": "microsoft/edge-tts", "billing": "free"}
        except ImportError:
            pass
        except Exception as e:
            return {"success": False, "error": f"edge-tts: {type(e).__name__}: {e}"}
        return {"success": False, "needs_backend": True,
                "error": "no free TTS backend available (install `edge-tts` for the "
                         "free local path; nvidia/genai speech endpoints 404 on this account)"}

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


def execute_capability(capability: str, prompt: str = "", **kw) -> Dict[str, Any]:
    """Module-level convenience: SOT-driven FREE-first execution of a non-chat
    capability (image, stt, embedding, tts, rerank, ...)."""
    return get_router().execute_capability(capability, prompt, **kw)


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