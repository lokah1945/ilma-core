#!/usr/bin/env python3
"""
ilma_client.py — ILMA Ultra-Fast Consumption Layer
ILMA v3.30 | Commit: 6d31f08

Single interface for all ILMA consumption: sub-agents, pipelines, CLI.
Zero-config, singleton, async-first.

Usage:
    from ilma_client import generate
    response = await generate("Hello, world!", max_tokens=256)

    # Or with task type hint:
    response = await generate("Write a Python quicksort", max_tokens=512, task_type="heavy_coding")

Design goals:
    1. Singleton: router initialized ONCE, reused across all calls
    2. Async-first: fully async with asyncio event loop
    3. Transparent: caching, key rotation, fallback handled internally
    4. Type-safe: clear input/output contract
    5. Minimal overhead: router call + single HTTP POST = total latency

API Provider Support:
    - openrouter:   OpenAI-compatible /v1/chat/completions
    - nvidia:       OpenAI-compatible /v1/chat/completions (NVIDIA NIM endpoint)
    - minimax:      Minimax v2 API (chatcompletion_v2)
    - ollama:       Ollama /api/chat (if local)
    - Others:       OpenAI-compatible fallback

Environment:
    HERMES_HOME=/root/.hermes/profiles/ilma
    Credentials: /root/credential/api_key.json
"""

from __future__ import annotations

import os, sys, json, time, asyncio, logging, hashlib
from typing import Optional, Any, Dict
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache

# ── Setup HERMES_HOME ────────────────────────────────────────────────────────
HERMES_HOME = os.environ.get("HERMES_HOME", "/root/.hermes/profiles/ilma")
sys.path.insert(0, HERMES_HOME)
os.environ["HERMES_HOME"] = HERMES_HOME

logger = logging.getLogger("ilma_client")
logging.basicConfig(
    level=logging.WARNING,
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)

# ─────────────────────────────────────────────────────────────────────────────
# CREDENTIAL LOADER
# ─────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_credentials() -> dict:
    """Load API credentials from /root/credential/api_key.json (cached)."""
    cred_path = "/root/credential/api_key.json"
    try:
        with open(cred_path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[ilma_client] Could not load credentials from {cred_path}: {e}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# HTTP CLIENT (reused connection via aiohttp session)
# ─────────────────────────────────────────────────────────────────────────────
class _AsyncHTTPClient:
    """
    Lightweight async HTTP client with connection reuse.
    Uses asyncio +aiohttp if available, falls back to sync httpx for simplicity.
    Singleton per event loop.
    """

    def __init__(self):
        self._session: Optional[Any] = None
        self._lock = asyncio.Lock()

    async def _ensure_session(self):
        if self._session is None:
            async with self._lock:
                if self._session is None:
                    try:
                        import aiohttp
                        self._session = aiohttp.ClientSession(
                            timeout=aiohttp.ClientTimeout(total=60),
                            connector=aiohttp.TCPConnector(limit=10, keepalive_timeout=30),
                        )
                    except ImportError:
                        # Fallback: use sync httpx in a thread pool
                        import httpx
                        self._session = httpx.AsyncClient(timeout=30)
                        self._using_httpx = True

    async def post(self, url: str, headers: dict, json_body: dict, timeout: int = 60) -> dict:
        await self._ensure_session()
        try:
            import aiohttp
            if isinstance(self._session, aiohttp.ClientSession):
                async with self._session.post(url, headers=headers, json=json_body, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    return {"status": resp.status, "body": await resp.json()}
            else:
                resp = await self._session.post(url, headers=headers, json=json_body, timeout=timeout)
                return {"status": resp.status_code, "body": resp.json()}
        except Exception as e:
            return {"status": 0, "error": str(e)}

    async def close(self):
        if self._session:
            await self._session.aclose()
            self._session = None


# Global HTTP client instance (singleton)
_http_client: Optional[_AsyncHTTPClient] = None


def _get_http_client() -> _AsyncHTTPClient:
    global _http_client
    if _http_client is None:
        _http_client = _AsyncHTTPClient()
    return _http_client


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER ENDPOINTS & API HANDLERS
# ─────────────────────────────────────────────────────────────────────────────
PROVIDER_ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "nvidia":     "https://integrate.api.nvidia.com/v1/chat/completions",
    "minimax":    "https://api.minimax.chat/v1/text/chatcompletion_v2",
    "ollama":     "http://localhost:11434/api/chat",
    "xai":        "https://api.x.ai/v1/chat/completions",
    "cohere":     "https://api.cohere.ai/v1/chat",
    "perplexity": "https://api.perplexity.ai/chat/completions",
}


def _get_api_key(provider: str) -> Optional[str]:
    """Get API key for provider from credentials file."""
    creds = _load_credentials()
    # Try different key names for same provider
    key_map = {
        "openrouter": "openrouter",
        "nvidia": "nvidia",
        "minimax": ["minimax", "minimax_api_key"],
        "ollama": None,  # local, no key
        "xai": "xai",
        "cohere": "cohere",
        "perplexity": "perplexity",
        "deepseek": "deepseek",
    }
    candidates = key_map.get(provider, provider)
    if not isinstance(candidates, list):
        candidates = [candidates]
    for key_name in candidates:
        if key_name and key_name in creds:
            return creds[key_name]
    return None


def _build_request_headers(provider: str, model_id: str) -> dict:
    """Build request headers for a provider."""
    headers = {"Content-Type": "application/json"}
    api_key = _get_api_key(provider)

    if provider == "openrouter":
        headers["Authorization"] = f"Bearer {api_key}"
        headers["HTTP-Referer"] = "https://ilma.agent"
        headers["X-Title"] = "ILMA Agent"
    elif provider == "nvidia":
        headers["Authorization"] = f"Bearer {api_key}"
    elif api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    return headers


def _is_openai_compatible(provider: str) -> bool:
    """Check if provider uses OpenAI-compatible chat completions format."""
    return provider not in ("ollama", "minimax")


def _build_openai_body(model_id: str, messages: list, max_tokens: int, **kwargs) -> dict:
    """Build OpenAI-compatible request body."""
    body = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": kwargs.get("temperature", 0.7),
    }
    if kwargs.get("stream"):
        body["stream"] = True
    return body


def _build_minimax_body(model_id: str, messages: list, max_tokens: int, **kwargs) -> dict:
    """Build Minimax v2 API request body."""
    return {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": kwargs.get("temperature", 0.7),
    }


def _build_ollama_body(model_id: str, messages: list, max_tokens: int, **kwargs) -> dict:
    """Build Ollama API request body."""
    return {
        "model": model_id,
        "messages": messages,
        "options": {
            "temperature": kwargs.get("temperature", 0.7),
            "num_predict": max_tokens,
        },
        "stream": False,
    }


def _parse_response(provider: str, response_body: dict) -> str:
    """Extract content from provider response."""
    try:
        if provider == "ollama":
            return response_body.get("message", {}).get("content", "")
        elif provider == "minimax":
            choices = response_body.get("choices", [{}])
            return choices[0].get("message", {}).get("content", "")
        else:
            # OpenAI-compatible
            choices = response_body.get("choices", [{}])
            return choices[0].get("message", {}).get("content", "")
    except (KeyError, IndexError, TypeError):
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK HTTP CLIENT (key rotation + model fallback on 429)
# ─────────────────────────────────────────────────────────────────────────────
class _FallbackHTTPClient:
    """
    Wraps _AsyncHTTPClient with automatic fallback on rate limits.

    Strategy on HTTP 429:
      1. Rotate NVIDIA key (NVIDIA has 3 keys — all share same endpoint but
         independent per-key rate limits). Cycle to next key and retry once.
      2. If no more NVIDIA keys OR non-NVIDIA: try alternative model from
         route_spread() candidates (different model from same or different provider).
      3. If all fallbacks exhausted: return the last error result.

    Tracks state per-request (not global) so concurrent requests don't interfere.
    """

    # ── Key pool for NVIDIA (class-level to persist across instances) ──────
    # 3 keys: lokah2150 (index 0), smahud (index 1), hca1988 (index 2)
    # All share same endpoint but independent per-key rate limits.
    # Round-robin ensures balanced distribution.
    NVIDIA_KEYS: list[str] = []
    _nvidia_key_idx: int = 0
    # PHASE 3: per-key cooldown tracking (epoch seconds when each key's
    # 429 cooldown expires). Persistent class attribute, indexed by
    # the key's index in NVIDIA_KEYS.
    _key_cooldown_until: Dict[int, float] = {}  # key_idx → cooldown expiry epoch
    _key_429_count: Dict[int, int] = {}  # key_idx → rolling 429 count (last 60s)
    _key_last_429_at: Dict[int, float] = {}  # key_idx → last 429 timestamp
    _lock = None  # initialized lazily in _get_lock()

    def __init__(self, http_client: _AsyncHTTPClient):
        self._http = http_client
        self._fallback_routes: list[dict] = []   # pre-loaded route alternatives
        self._route_spread: list[dict] = []       # raw route_spread() result
        self._route_idx: int = 0                  # current position in spread

    def preload_routes(self, spread: list[dict]) -> None:
        """Pre-load route_spread() candidates so we can fall back without re-routing."""
        self._route_spread = spread
        self._route_idx = 0

    # ── PHASE 2: Key pool for NVIDIA (dict-aware, hybrid rotation) ──────
    @classmethod
    def _init_nvidia_keys(cls) -> None:
        """
        Load NVIDIA API keys from credentials.

        Supports TWO formats (backward compatible):
        1. Legacy list: creds["nvidia"] = ["key1", "key2", ...]
        2. Current dict: creds["nvidia"] = {"keys": ["key1", "key2", ...], "description": "...", ...}

        All 3 keys have independent rate limits. Round-robin ensures even
        distribution across requests. Key rotation is triggered on HTTP 429.
        """
        if cls.NVIDIA_KEYS:
            return  # already loaded

        creds = _load_credentials()
        raw = creds.get("nvidia", [])

        # ── Format 1: list of keys (legacy) ──────────────────────────────
        if isinstance(raw, list):
            cls.NVIDIA_KEYS = [k for k in raw if k and isinstance(k, str) and len(k) > 10]
        # ── Format 2: dict with "keys" sub-field (current) ──────────────
        elif isinstance(raw, dict):
            # Primary path: nested list under "keys" field
            inner = raw.get("keys", [])
            if isinstance(inner, list):
                cls.NVIDIA_KEYS = [k for k in inner if k and isinstance(k, str) and len(k) > 10]
            # Fallback: iterate dict values looking for string API keys
            if not cls.NVIDIA_KEYS:
                for v in raw.values():
                    if isinstance(v, str) and len(v) > 20:
                        cls.NVIDIA_KEYS.append(v)
        # ── Format 3: bare string key ────────────────────────────────────
        elif isinstance(raw, str) and raw:
            cls.NVIDIA_KEYS = [raw]

        # Deduplicate while preserving order (in case of overlap)
        seen = set()
        deduped = []
        for k in cls.NVIDIA_KEYS:
            if k not in seen:
                seen.add(k)
                deduped.append(k)
        cls.NVIDIA_KEYS = deduped

        cls._nvidia_key_idx = 0
        if cls.NVIDIA_KEYS:
            logger.info(f"[NVIDIA] Loaded {len(cls.NVIDIA_KEYS)} API keys for round-robin rotation")

    @classmethod
    def _get_lock(cls):
        """Lazy-init threading lock for round-robin counter (per-process)."""
        import threading
        if cls._lock is None:
            cls._lock = threading.Lock()
        return cls._lock

    @classmethod
    def _next_nvidia_key(cls) -> Optional[str]:
        """PHASE 3 PRODUCTION LOCKDOWN (2026-06-06):
        Returns the next NVIDIA key in round-robin, skipping keys that are
        currently in cooldown due to a recent 429.

        The counter PERSISTS across requests — no reset. This is the
        "proactive" half of the strategy: requests naturally land on a
        different key each time, distributing load even before any 429
        occurs.

        The "reactive" half: when _mark_nvidia_key_429(key_idx) is called,
        that key's index is added to _key_cooldown_until for 60s, and the
        selector skips it during that window.
        """
        if not cls.NVIDIA_KEYS:
            cls._init_nvidia_keys()
        if not cls.NVIDIA_KEYS:
            return None

        now = time.time()
        with cls._get_lock():
            # Find first available key in round-robin order, starting at
            # current idx. Skip keys in cooldown.
            n = len(cls.NVIDIA_KEYS)
            for offset in range(n):
                idx = (cls._nvidia_key_idx + offset) % n
                cooldown_end = cls._key_cooldown_until.get(idx, 0)
                if now >= cooldown_end:
                    # Use this key. Advance idx by 1 (for next caller).
                    cls._nvidia_key_idx = (idx + 1) % n
                    return cls.NVIDIA_KEYS[idx]
            # All keys in cooldown — return the one with the earliest
            # cooldown expiry so we still make progress instead of dropping
            # the request.
            earliest = min(cls._key_cooldown_until.items(), key=lambda kv: kv[1])[0]
            cls._nvidia_key_idx = (earliest + 1) % n
            return cls.NVIDIA_KEYS[earliest]

    @classmethod
    def _mark_nvidia_key_429(cls, key_idx: int, cooldown_seconds: int = 60) -> None:
        """Mark a key as 429-rate-limited; selector will skip it for cooldown_seconds."""
        import time as _t
        with cls._get_lock():
            cls._key_cooldown_until[key_idx] = _t.time() + cooldown_seconds
            cls._key_429_count[key_idx] = cls._key_429_count.get(key_idx, 0) + 1
            cls._key_last_429_at[key_idx] = _t.time()

    @classmethod
    def _get_key_diagnostics(cls) -> Dict[str, Any]:
        """Return per-key diagnostics (for logging/debugging)."""
        now = time.time()
        out = []
        for i, k in enumerate(cls.NVIDIA_KEYS):
            cd = cls._key_cooldown_until.get(i, 0)
            out.append({
                "key_idx": i,
                "key_suffix": k[-6:] if k else "n/a",
                "in_cooldown": cd > now,
                "cooldown_remaining_s": max(0, cd - now),
                "rolling_429_count": cls._key_429_count.get(i, 0),
            })
        return {"keys": out, "current_idx": cls._nvidia_key_idx}

    @classmethod
    def _reset_nvidia_key_index(cls) -> None:
        """DEPRECATED in PHASE 3 — no longer resets counter.

        Kept as a no-op for backward compatibility with older callers.
        The round-robin counter is now persistent across requests, which
        is the whole point of proactive load balancing.
        """

    # ── Core call with 429 detection + key rotation ────────────────────────
    async def post_with_fallback(
        self,
        provider: str,
        model_id: str,
        headers: dict,
        body: dict,
        timeout: int = 60,
        attempt_key_rotation: bool = True,
        attempt_model_fallback: bool = True,
    ) -> tuple[dict, str, str]:
        """
        Make HTTP POST with automatic key rotation + model fallback on 429.

        Returns:
            (response_dict, effective_model_id, effective_provider)

        Raises:
            None — all errors are captured in response dict with status=0 or 4xx.
        """
        self._init_nvidia_keys()
        current_provider = provider
        current_model = model_id
        current_headers = dict(headers)

        # Replace Authorization header with a specific NVIDIA key
        def _apply_nvidia_key() -> None:
            if current_provider == "nvidia":
                key = self._next_nvidia_key()
                if key:
                    current_headers["Authorization"] = f"Bearer {key}"

        # ── ATTEMPT 1: primary request with current NVIDIA key ──────────────
        _apply_nvidia_key()
        response = await self._http.post(
            PROVIDER_ENDPOINTS.get(current_provider, PROVIDER_ENDPOINTS["openrouter"]),
            headers=current_headers,
            json_body=body,
            timeout=timeout,
        )

        # ── PHASE 2: Try ALL NVIDIA keys on 429 before giving up ──────────
        # Current code only rotates once. Fix: loop through ALL available keys.
        # NVIDIA has 3 keys with independent rate limits — trying all 3 maximises
        # the chance of a successful response under load.
        if response.get("status") == 429 and current_provider == "nvidia":
            retry_after = None
            try:
                rh = response.get("headers", {})
                if isinstance(rh, dict):
                    retry_after = int(rh.get("Retry-After", "0"))
            except (ValueError, TypeError):
                pass

            logger.warning(f"[ilma_client] Rate limited (429) on {current_provider}/{current_model}"
                           f"{f', Retry-After={retry_after}s' if retry_after else ''}")

            # PHASE 3: Mark the key that just hit 429 as cooldown so the
            # next selector call skips it for 60s.
            try:
                used_idx = (self._nvidia_key_idx - 1) % len(self.NVIDIA_KEYS)
                self._mark_nvidia_key_429(used_idx, cooldown_seconds=60)
            except (ZeroDivisionError, ValueError):
                pass

            # Try remaining NVIDIA keys sequentially
            keys_count = len(self.NVIDIA_KEYS)
            if attempt_key_rotation and keys_count > 1:
                for attempt in range(1, keys_count):
                    # Apply next key (round-robin increments idx each call)
                    _apply_nvidia_key()
                    logger.info(f"[ilma_client] NVIDIA key rotation: attempt {attempt + 1}/{keys_count}")
                    response = await self._http.post(
                        PROVIDER_ENDPOINTS["nvidia"],
                        headers=current_headers,
                        json_body=body,
                        timeout=timeout,
                    )
                    if response.get("status") != 429:
                        return response, current_model, current_provider
                    # 429 again → mark THIS key and try next
                    try:
                        used_idx = (self._nvidia_key_idx - 1) % len(self.NVIDIA_KEYS)
                        self._mark_nvidia_key_429(used_idx, cooldown_seconds=60)
                    except (ZeroDivisionError, ValueError):
                        pass

        # Sub-step B: Model fallback from route_spread() candidates
        if attempt_model_fallback:
            result = await self._try_fallback_models(
                current_provider, current_model, headers, body, timeout,
            )
            if result is not None:
                return result

        # All fallbacks exhausted — return last 429 response
        return response, current_model, current_provider

    async def _try_fallback_models(
        self,
        original_provider: str,
        original_model: str,
        original_headers: dict,
        body: dict,
        timeout: int,
    ) -> Optional[tuple[dict, str, str]]:
        """
        Try alternative models from route_spread() candidates (or fresh routing).
        Returns (response, model_id, provider) if a fallback succeeds, else None.
        """
        attempts = 0
        max_attempts = 3  # try at most 3 fallback models

        # Iterate through route_spread() candidates (skip index 0 = original)
        for i, candidate in enumerate(self._route_spread):
            if i == 0:
                continue  # skip primary model (already tried)
            if attempts >= max_attempts:
                break

            c_provider = candidate.get("provider", "openrouter")
            c_model = candidate.get("model_id", "")
            if not c_model or c_model == original_model:
                continue

            logger.info(f"[ilma_client] Fallback attempt {attempts+1}: trying {c_provider}/{c_model}")
            attempts += 1

            # Build headers + body for this provider
            try:
                c_endpoint = PROVIDER_ENDPOINTS.get(c_provider, PROVIDER_ENDPOINTS["openrouter"])
                c_headers = _build_request_headers(c_provider, c_model)

                if c_provider == "ollama":
                    c_body = _build_ollama_body(c_model, body.get("messages", []),
                                                 body.get("max_tokens", 1024))
                elif c_provider == "minimax":
                    c_body = _build_minimax_body(c_model, body.get("messages", []),
                                                 body.get("max_tokens", 1024))
                else:
                    c_body = dict(body, model=c_model)

                c_response = await self._http.post(c_endpoint, headers=c_headers,
                                                     json_body=c_body, timeout=timeout)

                status = c_response.get("status", 0)
                if status == 429:
                    logger.warning(f"[ilma_client] Fallback {c_provider}/{c_model} also rate limited (429)")
                    continue  # try next fallback

                if status >= 200 and status < 300:
                    logger.info(f"[ilma_client] Fallback SUCCESS: {c_provider}/{c_model}")
                    return c_response, c_model, c_provider

                # Non-429 error — stop trying (model probably invalid/config error)
                if status >= 400:
                    logger.warning(f"[ilma_client] Fallback {c_provider}/{c_model} error {status}, stopping fallback chain")
                    break

            except Exception as e:
                logger.warning(f"[ilma_client] Fallback {c_provider}/{c_model} exception: {e}")
                continue

        # All fallback attempts failed
        logger.warning(f"[ilma_client] All {attempts} fallback attempts exhausted, returning last error")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class GenerateResult:
    """Result of a generate() call."""
    content: str
    model_id: str
    provider: str
    latency_ms: float
    success: bool
    error: Optional[str] = None
    token_count: Optional[int] = None
    finish_reason: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# ILMA ROUTER (lazy singleton)
# ─────────────────────────────────────────────────────────────────────────────
_router_instance: Optional[Any] = None
_router_lock = asyncio.Lock()


async def _get_router():
    """Get or create the ILMAUnifiedRouter singleton (async-safe)."""
    global _router_instance
    if _router_instance is None:
        async with _router_lock:
            if _router_instance is None:
                import importlib
                import ilma_model_router
                importlib.reload(ilma_model_router)
                _router_instance = ilma_model_router.ILMAUnifiedRouter()
                _router_instance._invalidate_candidate_cache()
    return _router_instance


# ─────────────────────────────────────────────────────────────────────────────
# MAIN GENERATE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────
async def generate(
    prompt: str,
    max_tokens: int = 1024,
    task_type: Optional[str] = None,
    temperature: float = 0.7,
    model_override: Optional[str] = None,
    timeout: int = 60,
    mock: bool = False,
    **kwargs: Any,
) -> GenerateResult:
    """
    Ultra-fast ILMA generation — single entry point for all consumption.

    Args:
        prompt:      The input prompt/message to send.
        max_tokens:  Maximum tokens to generate (default: 1024).
        task_type:   Optional task type hint for better routing
                     (e.g., "heavy_coding", "fast_tasks", "reasoning_xhigh").
                     If None, router classifies automatically.
        temperature: Sampling temperature 0.0-2.0 (default: 0.7).
        model_override: Force a specific model (format: "provider/model_id"
                        or just "model_id"). Bypasses router selection.
        timeout:     HTTP request timeout in seconds (default: 60).
        mock:        If True, return a realistic mock response (no API calls).
                     Useful for testing and validation.
        **kwargs:    Additional provider-specific parameters.

    Returns:
        GenerateResult with: content, model_id, provider, latency_ms, success.

    Raises:
        Nothing — all errors are captured in GenerateResult.success=False.

    Example:
        from ilma_client import generate
        result = await generate("Explain quantum entanglement", max_tokens=512)
        print(result.content)
    """
    start = time.perf_counter()
    messages = [{"role": "user", "content": prompt}]
    allow_paid = bool(kwargs.pop("allow_paid", False))

    # ── MODE: MOCK (validation / testing) ───────────────────────────────────
    if mock:
        await asyncio.sleep(0.05)  # simulate minimum network latency
        latency_ms = (time.perf_counter() - start) * 1000
        mock_content = _mock_response(prompt, task_type or "general")
        return GenerateResult(
            content=mock_content,
            model_id="mock/free-model",
            provider="mock",
            latency_ms=latency_ms,
            success=True,
        )

    # ── MODE: REAL INFERENCE ────────────────────────────────────────────────
    router = await _get_router()

    try:
        # Step 1: Route (with caching, latency < 20ms warm)
        if model_override:
            # Manual model override — parse provider/model_id
            parts = model_override.split("/", 1)
            if len(parts) == 2:
                provider, model_id = parts
            else:
                provider = "openrouter"
                model_id = model_override
            if not allow_paid and hasattr(router, "is_model_runtime_allowed") and not router.is_model_runtime_allowed(provider, model_id, allow_paid=False):
                raise ValueError(f"[ilma_client] Blocked unsafe model_override under FREE_MODEL_ONLY: {provider}/{model_id}")
        else:
            # Normal routing: route_spread returns top-30 candidates.
            # Pass those to _FallbackHTTPClient so it can try model fallbacks on 429.
            route_result = router.route_spread(task_type or prompt, top_k=30)
            candidates = route_result.get("candidates") or route_result.get("spread_pool", [])  # list of scored models
            selected = route_result.get("selected_model", {})
            model_id = selected.get("model_id", "")
            provider = selected.get("provider", "openrouter")

            if not model_id:
                raise ValueError(f"[ilma_client] No model selected for prompt: {prompt[:50]}...")

            # Pre-build fallback client with route candidates for 429 fallback
            _FallbackHTTPClient._reset_nvidia_key_index()
            fb = _FallbackHTTPClient(_get_http_client())
            fb.preload_routes(candidates)

        # Step 2: Build request (use fallback client's pre-loaded route)
        # PHASE 4 PRODUCTION LOCKDOWN: scope-corrected fallback client.
        # Previously `fb = None` on line 719 overrode the outer fb before
        # the conditional block ran, causing the assert below to trip.
        if model_override:
            # Manual model override → no fallback candidates available
            endpoint = PROVIDER_ENDPOINTS.get(provider, PROVIDER_ENDPOINTS["openrouter"])
            headers = _build_request_headers(provider, model_id)
            fb = None
        else:
            # Normal routing branch: fb was set in the else above.
            # Re-read it locally to keep pyright happy.
            endpoint = PROVIDER_ENDPOINTS.get(provider, PROVIDER_ENDPOINTS["openrouter"])
            headers = _build_request_headers(provider, model_id)
            # `fb` already bound from the routing branch (line ~715)
        assert fb is not None or model_override, "fb must be set before HTTP call"

        if provider == "ollama":
            body = _build_ollama_body(model_id, messages, max_tokens, temperature=temperature, **kwargs)
        elif provider == "minimax":
            body = _build_minimax_body(model_id, messages, max_tokens, temperature=temperature, **kwargs)
        else:
            body = _build_openai_body(model_id, messages, max_tokens, temperature=temperature, **kwargs)

        # Step 3: HTTP call with auto-fallback on 429
        if model_override:
            # No fallback candidates — single shot
            response = await _get_http_client().post(endpoint, headers=headers, json_body=body, timeout=timeout)
            effective_model = model_id
            effective_provider = provider
        else:
            response, effective_model, effective_provider = await fb.post_with_fallback(  # type: ignore[union-attr]
                provider, model_id, headers, body, timeout=timeout,
            )

        latency_ms = (time.perf_counter() - start) * 1000

        if response.get("status") == 0:
            return GenerateResult(
                content="",
                model_id=effective_model,
                provider=effective_provider,
                latency_ms=latency_ms,
                success=False,
                error=f"Network error: {response.get('error', 'unknown')}",
            )

        status = response.get("status", 0)
        body_data = response.get("body", {})

        if status == 200 or status == 201:
            content = _parse_response(effective_provider, body_data)
            router._log_usage(effective_model, latency_ms, success=True, provider=effective_provider)
            return GenerateResult(
                content=content,
                model_id=effective_model,
                provider=effective_provider,
                latency_ms=latency_ms,
                success=True,
                token_count=body_data.get("usage", {}).get("total_tokens", None),
                finish_reason=body_data.get("choices", [{}])[0].get("finish_reason", None),
            )
        else:
            error_msg = body_data.get("error", {}).get("message", str(body_data))
            router._log_usage(effective_model, latency_ms, success=False, provider=effective_provider)
            return GenerateResult(
                content="",
                model_id=effective_model,
                provider=effective_provider,
                latency_ms=latency_ms,
                success=False,
                error=f"[HTTP {status}] {error_msg}",
            )

    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.error(f"[ilma_client] generate() exception: {e}")
        # Variables are already initialized above, use them directly
        return GenerateResult(
            content="",
            model_id=model_id if model_id else "unknown",
            provider=provider if provider else "unknown",
            latency_ms=latency_ms,
            success=False,
            error=str(e),
        )


# ─────────────────────────────────────────────────────────────────────────────
# MOCK RESPONSE (for validation / --mock mode)
# ─────────────────────────────────────────────────────────────────────────────
def _mock_response(prompt: str, task_type: str) -> str:
    """Return a plausible mock response based on task type."""
    responses = {
        "fast_tasks":     f"Answer: 42. (This is a simulated fast response for the query about '{prompt[:30]}...')",
        "general":        f"Here is a comprehensive answer about '{prompt[:30]}...' — covering key aspects and context.",
        "writing":        f"[Professional draft]\n\nBased on your request about '{prompt[:30]}...', here is a well-structured response.\n\n[End of draft]",
        "planning":       f"Plan for: '{prompt[:30]}...'\n\nStep 1: Assessment\nStep 2: Implementation\nStep 3: Evaluation\nStep 4: Iteration",
        "research":       f"Research summary on '{prompt[:30]}...':\n\nKey findings indicate significant complexity. Further investigation is warranted.",
        "medium_coding":  f"# Solution\n\ndef solution():\n    # Implementation for: {prompt[:40]}...\n    pass\n\n# Time complexity: O(n)",
        "heavy_coding":   f"# Production Implementation\n\n# Handling: {prompt[:40]}...\n\nclass Implementation:\n    def execute(self):\n        # Production-grade code here\n        pass",
        "reasoning_xhigh": f"Logical analysis:\n\nFor the query '{prompt[:30]}...', the reasoning proceeds as follows:\n1. Identification of key constraints\n2. Application of logical principles\n3. Derivation of conclusion",
    }
    return responses.get(task_type, f"Response to: {prompt[:50]}...")


# ─────────────────────────────────────────────────────────────────────────────
# BATCH GENERATION (parallel, fan-out to N models simultaneously)
# ─────────────────────────────────────────────────────────────────────────────
async def generate_batch(
    prompts: list[str],
    task_type: Optional[str] = None,
    max_tokens: int = 512,
    max_concurrent: int = 3,
    **kwargs,
) -> list[GenerateResult]:
    """
    Run multiple generate() calls in parallel, bounded by max_concurrent.

    Args:
        prompts:       List of prompts to generate for.
        task_type:     Optional task type for all prompts.
        max_tokens:    Max tokens per call.
        max_concurrent: Max simultaneous calls (default: 3).
        **kwargs:      Passed to generate().

    Returns:
        List[GenerateResult] in same order as prompts.
    """
    sem = asyncio.Semaphore(max_concurrent)

    async def _bounded(prompt: str) -> GenerateResult:
        async with sem:
            return await generate(prompt, max_tokens=max_tokens, task_type=task_type, **kwargs)

    results = await asyncio.gather(*[_bounded(p) for p in prompts], return_exceptions=True)
    # Convert exceptions to failed GenerateResult
    final: list[GenerateResult] = []
    for r in results:
        if isinstance(r, GenerateResult):
            final.append(r)
        else:
            final.append(GenerateResult(
                content="", model_id="unknown", provider="unknown",
                latency_ms=0, success=False, error=str(r),
            ))
    return final


# ─────────────────────────────────────────────────────────────────────────────
# USAGE / DIAGNOSTICS
# ─────────────────────────────────────────────────────────────────────────────
async def get_usage_stats() -> dict:
    """
    Return current in-memory usage statistics.
    Call flush_usage_updates() separately to persist to MASTER.
    """
    router = await _get_router()
    stats = {}
    for key, data in router._pending_usage.items():
        stats[key] = {
            "total": data["total"],
            "success": data["success"],
            "failed": data["failed"],
            "latency_count": data["latency_count"],
        }
    return stats


async def flush_usage() -> None:
    """Manually flush pending usage to SOT files."""
    router = await _get_router()
    router.flush_usage_updates()


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT (python3 ilma_client.py "prompt text" [--mock])
# ─────────────────────────────────────────────────────────────────────────────
async def _cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Client CLI")
    parser.add_argument("prompt", nargs="?", default="Hello, ILMA! What can you do?")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--task-type", default=None)
    parser.add_argument("--mock", action="store_true", help="Use mock responses (no API calls)")
    parser.add_argument("--model", default=None, help="Force specific model")
    args = parser.parse_args()

    print(f"🤖 ILMA Client v3.30")
    print(f"   Prompt: {args.prompt[:60]}{'...' if len(args.prompt) > 60 else ''}")
    print(f"   Mode:   {'MOCK' if args.mock else 'LIVE'}")
    print()

    result = await generate(
        args.prompt,
        max_tokens=args.max_tokens,
        task_type=args.task_type,
        model_override=args.model,
        mock=args.mock,
    )

    print(f"📦 Result:")
    print(f"   Model:    {result.provider}/{result.model_id}")
    print(f"   Latency:  {result.latency_ms:.1f}ms")
    print(f"   Success:  {result.success}")
    if result.error:
        print(f"   Error:    {result.error}")
    else:
        print(f"\n{result.content}")
    print()

    # Flush usage stats
    if not args.mock:
        await flush_usage()


if __name__ == "__main__":
    asyncio.run(_cli_main())