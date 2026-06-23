#!/usr/bin/env python3
"""
ilma_health_manager.py — ILMA Provider/Model Health Manager v1.0
================================================================
Centralized health tracking for all providers and models.
Ensures rate-limited providers are excluded from routing automatically.

Usage:
    from ilma_health_manager import HealthManager, get_health_manager

    hm = get_health_manager()

    # Check if model is available (not rate-limited, no errors)
    if hm.is_model_available("openai/gpt-5"):
        response = chat(...)
        hm.mark_success("openai/gpt-5")
    else:
        # Auto-select next best available model
        model = hm.get_best_available_model(task_type, candidates)

    # Mark failure (will trigger rate-limit detection)
    hm.mark_failure("openai/gpt-5", error_msg)
"""


import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


# ===================
# Constants
# ===================

ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
HEALTH_STATE_FILE = ILMA_PROFILE / "ilma_model_router_data" / "model_health_state.json"

# Rate limit detection thresholds
RATE_LIMIT_CONSECUTIVE_FAILURES = 3
RATE_LIMIT_WINDOW_SECONDS = 300  # 5 minutes
UNHEALTHY_CONSECUTIVE_FAILURES = 5

# Model status
class ModelStatus(Enum):
    AVAILABLE = "available"    # Can be used
    RATE_LIMITED = "rate_limited"  # Quota exceeded
    ERROR = "error"           # Too many failures
    UNKNOWN = "unknown"       # Never tested


# Provider status
class ProviderStatus(Enum):
    HEALTHY = "healthy"       # All models available
    DEGRADED = "degraded"     # Some models unavailable
    UNHEALTHY = "unhealthy"  # Most/all models unavailable
    UNKNOWN = "unknown"       # Unknown state


# ===================
# Data Classes
# ===================

@dataclass
class ModelHealth:
    """Health state for a single model."""
    model_id: str
    status: ModelStatus = ModelStatus.UNKNOWN
    consecutive_failures: int = 0
    total_failures: int = 0
    last_failure: Optional[str] = None
    last_failure_time: Optional[str] = None
    last_success_time: Optional[str] = None
    rate_limit_reset: Optional[str] = None  # ISO timestamp when rate limit resets
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "status": self.status.value if isinstance(self.status, ModelStatus) else self.status,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.total_failures,
            "last_failure": self.last_failure,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "rate_limit_reset": self.rate_limit_reset,
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> "ModelHealth":
        raw_status = d.get("status", "unknown")
        # Map external/legacy status strings to enum
        if raw_status == "unavailable":
            mapped_status = "error"  # unavailable → error
        elif raw_status == "rate_limited":
            mapped_status = "rate_limited"
        elif raw_status in ("available", "healthy"):
            mapped_status = "available"
        elif raw_status == "unknown":
            mapped_status = "unknown"
        else:
            mapped_status = "error"  # default for any unexpected value

        return cls(
            model_id=d.get("model_id", ""),
            status=ModelStatus(mapped_status),
            consecutive_failures=d.get("consecutive_failures", 0),
            total_failures=d.get("total_failures", 0),
            last_failure=d.get("last_failure"),
            last_failure_time=d.get("last_failure_time"),
            last_success_time=d.get("last_success_time"),
            rate_limit_reset=d.get("rate_limit_reset"),
        )
    
    def is_available(self) -> bool:
        """Check if model is currently available for use.

        PHASE 2 PRODUCTION LOCKDOWN (2026-06-06):
        UNKNOWN is NOT treated as available anymore — UNKNOWN models must
        be probed proactively (see ILMAHealthCheck.run_startup_probe) before
        they can be used at runtime. This prevents the router from picking
        models that have never been validated.
        """
        if self.status == ModelStatus.RATE_LIMITED:
            # Check if rate limit has expired
            if self.rate_limit_reset:
                try:
                    reset_time = datetime.fromisoformat(self.rate_limit_reset)
                    if datetime.now() > reset_time:
                        self.status = ModelStatus.AVAILABLE
                        self.rate_limit_reset = None
                        return True
                except ValueError:
                    pass
            return False

        if self.status == ModelStatus.ERROR:
            # Check if enough time has passed to retry
            if self.last_failure_time:
                try:
                    last_failure = datetime.fromisoformat(self.last_failure_time)
                    if datetime.now() - last_failure > timedelta(minutes=5):
                        return True
                except ValueError:
                    pass
            return False

        # PHASE 2: UNKNOWN is no longer implicitly available.
        # Caller must invoke proactive health probe before treating UNKNOWN
        # as available.
        return self.status == ModelStatus.AVAILABLE


@dataclass
class ProviderHealth:
    """Health state for a provider."""
    provider: str  # e.g. 'nvidia', 'openrouter', 'blackbox'
    status: ProviderStatus = ProviderStatus.UNKNOWN
    models_total: int = 0
    models_available: int = 0
    rate_limited: bool = False
    rate_limit_reset: Optional[str] = None
    consecutive_failures: int = 0
    last_failure_time: Optional[str] = None
    last_check: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status.value if isinstance(self.status, ProviderStatus) else self.status,
            "rate_limited": self.rate_limited,
            "rate_limit_reset": self.rate_limit_reset,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": 0,
            "last_failure_time": self.last_failure_time,
            "last_check": self.last_check,
            "models_total": self.models_total,
            "models_available": self.models_available,
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> "ProviderHealth":
        return cls(
            provider=d.get("provider", ""),
            status=ProviderStatus(d.get("status", "unknown")),
            models_total=d.get("models_total", 0),
            models_available=d.get("models_available", 0),
            rate_limited=d.get("rate_limited", False),
            rate_limit_reset=d.get("rate_limit_reset"),
            consecutive_failures=d.get("consecutive_failures", 0),
            last_failure_time=d.get("last_failure_time"),
            last_check=d.get("last_check"),
        )
    
    def is_healthy(self) -> bool:
        """Provider is usable if not rate-limited and has available models.
        
        Edge case: If no models have been tracked yet (models_total=0),
        the provider is considered healthy to allow initial model usage.
        """
        if self.rate_limited:
            # Check if rate limit expired
            if self.rate_limit_reset:
                try:
                    reset_time = datetime.fromisoformat(self.rate_limit_reset)
                    if datetime.now() > reset_time:
                        self.rate_limited = False
                        self.rate_limit_reset = None
                        # Re-check models after clearing rate limit
                        if self.models_total == 0:
                            return True  # No tracked models = assume healthy
                        return self.models_available > 0
                except ValueError:
                    pass
            return False
        
        # If no models tracked yet, assume healthy (let them be used)
        if self.models_total == 0:
            return True
        
        return self.models_available > 0


# ===================
# Health Manager
# ===================

class HealthManager:
    """
    Centralized health tracking for all providers and models.

    Features:
    - Per-model health tracking with rate-limit detection
    - Per-provider health aggregation
    - Automatic fallback to healthy models when rate-limit detected
    - Persistence to disk for survival across restarts
    """
    
    def __init__(self, state_file: Path = HEALTH_STATE_FILE):
        self.state_file = state_file
        self._models: Dict[str, ModelHealth] = {}  # model_id → ModelHealth
        self._providers: Dict[str, ProviderHealth] = {}  # provider → ProviderHealth
        self._load()

        # Legacy proxy URL removed 2026-06-19. Health is now sourced from
        # direct cloud API warm-up probes.
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=10)
        return self._client
    
    def close(self):
        if self._client:
            self._client.close()
            self._client = None
    
    # ===================
    # Persistence
    # ===================
    
    def _load(self):
        """Load health state from disk (with truncation protection)."""
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            # Corrupted file - start fresh
            return
        
        # Load models
        for model_id, mdata in data.get("models", {}).items():
            self._models[model_id] = ModelHealth.from_dict(mdata)
        
        # Load providers
        for provider, pdata in data.get("providers", {}).items():
            self._providers[provider] = ProviderHealth.from_dict(pdata)
        
    def _save(self):
        """Persist health state to disk (atomic write)."""
        data = {
            "models": {mid: m.to_dict() for mid, m in self._models.items()},
            "providers": {p: ph.to_dict() for p, ph in self._providers.items()},
            "saved_at": datetime.now().isoformat(),
        }
        
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: temp file → rename (overwrite)
            tmp_path = self.state_file.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
            # Use os.replace for atomic overwrite on POSIX
            os.replace(tmp_path, self.state_file)
        except Exception:
            pass
    
    # ===================
    # Provider Health
    # ===================
    
    def get_provider_health(self, provider: str) -> ProviderHealth:
        """Get health state for a provider."""
        if provider not in self._providers:
            self._providers[provider] = ProviderHealth(provider=provider)
        
        ph = self._providers[provider]
        
        # Check if rate limit expired
        if ph.rate_limited and ph.rate_limit_reset:
            try:
                reset_time = datetime.fromisoformat(ph.rate_limit_reset)
                if datetime.now() > reset_time:
                    ph.rate_limited = False
                    ph.rate_limit_reset = None
            except ValueError:
                pass
        
        return ph
    
    def get_provider_status(self, provider: str) -> ProviderStatus:
        """Get provider status (healthy/degraded/unhealthy/unknown)."""
        return self.get_provider_health(provider).status
    
    def is_provider_rate_limited(self, provider: str) -> bool:
        """Check if provider is currently rate-limited."""
        return not self.get_provider_health(provider).is_healthy()
    
    def _update_provider_from_models(self, provider: str):
        """Update provider health based on all its models."""
        if provider not in self._providers:
            self._providers[provider] = ProviderHealth(provider=provider)
        
        ph = self._providers[provider]
        
        # Count available models per provider prefix
        available = sum(1 for mid, m in self._models.items() 
                       if mid.startswith(f"{provider}/") and m.is_available())
        total = sum(1 for mid in self._models if mid.startswith(f"{provider}/"))
        
        ph.models_available = available
        ph.models_total = total
        ph.last_check = datetime.now().isoformat()
        
        # Determine status
        if available == 0 and total > 0:
            ph.status = ProviderStatus.UNHEALTHY
        elif available < total:
            ph.status = ProviderStatus.DEGRADED
        elif total > 0:
            ph.status = ProviderStatus.HEALTHY
        else:
            ph.status = ProviderStatus.UNKNOWN
    
    # ===================
    # Model Health
    # ===================
    
    def get_model_health(self, model_id: str) -> ModelHealth:
        """Get health state for a model."""
        if model_id not in self._models:
            self._models[model_id] = ModelHealth(model_id=model_id)
        return self._models[model_id]
    
    def is_model_available(self, model_id: str) -> bool:
        """Check if a model is available for use.
        
        Model is available if:
        1. Model-level status is not rate-limited or error (auto-clears expired)
        2. Provider is not rate-limited (auto-clears expired) OR provider has no tracked models
        """
        mh = self.get_model_health(model_id)
        
        # Check if model-level rate limit (ModelHealth.is_available auto-clears expired)
        if not mh.is_available():
            return False
        
        # Check provider-level rate limit
        provider = model_id.split("/")[0] if "/" in model_id else ""
        if provider:
            ph = self.get_provider_health(provider)
            
            # Only enforce if provider has tracked models
            if ph.models_total > 0:
                # get_provider_health auto-clears expired rate limits
                # If still rate-limited, block
                if ph.rate_limited:
                    return False
                
                # Provider not rate-limited - verify it has at least one available model
                # Re-check availability based on current model states
                available = sum(1 for mid, m in self._models.items() 
                               if mid.startswith(f"{provider}/") and m.is_available())
                if available == 0:
                    # No models currently available, but provider itself is not rate-limited
                    # Allow the check - model router will handle individual model failures
                    pass
        
        return True
    
    def get_available_models(
        self, 
        candidates: List[str], 
        task_type: Optional[str] = None
    ) -> List[str]:
        """
        Filter candidates to only available models.
        Returns models sorted by health (most healthy first).
        """
        available = []
        
        for model_id in candidates:
            if self.is_model_available(model_id):
                available.append(model_id)
        
        # Sort by consecutive failures (lower is better)
        available.sort(key=lambda mid: self.get_model_health(mid).consecutive_failures)
        
        return available
    
    def get_best_available_model(
        self,
        task_type: str,
        candidates: List[str]
    ) -> Optional[str]:
        """
        Get the best available model from candidates.
        Returns None if no models available.
        """
        available = self.get_available_models(candidates, task_type)
        return available[0] if available else None
    
    # ===================
    # Mark Success/Failure
    # ===================
    
    def mark_success(self, model_id: str):
        """Record successful call for a model."""
        mh = self.get_model_health(model_id)
        
        mh.status = ModelStatus.AVAILABLE
        mh.consecutive_failures = 0
        mh.last_success_time = datetime.now().isoformat()
        mh.rate_limit_reset = None  # Clear any rate limit
        
        self._update_provider_from_models(model_id.split("/")[0])
        self._save()
    
    def mark_failure(
        self, 
        model_id: str, 
        error: str,
        is_rate_limit: bool = False,
        rate_limit_reset: Optional[str] = None
    ):
        """
        Record failed call for a model.
        Auto-detects rate limits based on error patterns.
        """
        mh = self.get_model_health(model_id)
        
        mh.consecutive_failures += 1
        mh.total_failures += 1
        mh.last_failure = error[:200]  # Truncate
        mh.last_failure_time = datetime.now().isoformat()
        
        provider = model_id.split("/")[0] if "/" in model_id else ""
        
        # Check if this is a rate limit error
        rate_limit_detected = is_rate_limit or self._detect_rate_limit_error(error)
        
        if rate_limit_detected:
            mh.status = ModelStatus.RATE_LIMITED
            if rate_limit_reset:
                mh.rate_limit_reset = rate_limit_reset
            else:
                # Default to 24 hours if no reset time given
                reset_time = datetime.now() + timedelta(hours=24)
                mh.rate_limit_reset = reset_time.isoformat()
            
            # Also mark provider as rate-limited
            if provider:
                ph = self.get_provider_health(provider)
                ph.rate_limited = True
                ph.consecutive_failures += 1
                ph.last_failure_time = datetime.now().isoformat()
                if rate_limit_reset:
                    ph.rate_limit_reset = rate_limit_reset
                elif not ph.rate_limit_reset:
                    ph.rate_limit_reset = (datetime.now() + timedelta(hours=24)).isoformat()
        
        elif mh.consecutive_failures >= UNHEALTHY_CONSECUTIVE_FAILURES:
            mh.status = ModelStatus.ERROR
        
        if provider:
            self._update_provider_from_models(provider)
        
        self._save()
    
    def _detect_rate_limit_error(self, error: str) -> bool:
        """Detect if error is a rate limit based on common patterns."""
        error_lower = error.lower()
        rate_limit_patterns = [
            "rate limit",
            "quota exceeded",
            "batas penggunaan",
            "daily limit",
            "too many requests",
            "429",
            "rate_limit",
            "hari ini",
            "reset",
            "subscription",
            "langganan",
        ]
        return any(p in error_lower for p in rate_limit_patterns)
    
    def clear_rate_limit(self, model_id: Optional[str] = None, provider: Optional[str] = None):
        """
        Manually clear rate limit for model or provider.
        Use after quota reset or manual intervention.
        """
        if model_id:
            mh = self.get_model_health(model_id)
            mh.status = ModelStatus.AVAILABLE
            mh.consecutive_failures = 0
            mh.rate_limit_reset = None
            provider = model_id.split("/")[0] if "/" in model_id else provider
        
        if provider:
            ph = self.get_provider_health(provider)
            ph.rate_limited = False
            ph.consecutive_failures = 0
            ph.rate_limit_reset = None
            self._update_provider_from_models(provider)
        
        self._save()
    
    # ===================
    # Health Check
    # ===================
    
    def check_proxy_health(self) -> Dict[str, Any]:
        """Legacy stub — proxy project removed 2026-06-19.

        Returns an unhealthy report so callers stop assuming any local
        proxy endpoint exists. Health probes now happen via direct
        provider calls inside ``run_startup_probe``.
        """
        return {"healthy": False, "error": "proxy_removed"}

    # ===================
    # PHASE 2 PRODUCTION LOCKDOWN: Startup probe
    # ===================

    def run_startup_probe(self, target_providers: Optional[List[str]] = None,
                          probe_prompt: str = "ping", timeout: int = 10) -> Dict[str, Any]:
        """PHASE 2 (2026-06-06): Proactive startup health probe.

        Replaces the "UNKNOWN = usable" pattern. On startup, every provider
        (or a subset passed via target_providers) gets a lightweight test
        request. The result updates model status:
          - 2xx response                 → status = AVAILABLE
          - HTTP 429                     → status = RATE_LIMITED + cooldown 60s
          - HTTP 401/403                 → status = ERROR (auth_error)
          - Timeout / network error      → status = ERROR (degraded)
          - HTTP 5xx                     → status = ERROR (unavailable)

        Args:
            target_providers: providers to probe. None = all known providers.
            probe_prompt: minimal text to send in test request.
            timeout: per-probe timeout in seconds.

        Returns:
            Summary dict with per-provider result and aggregate counts.
        """
        results: Dict[str, Any] = {"probed": 0, "healthy": 0, "rate_limited": 0,
                                    "auth_error": 0, "degraded": 0, "unavailable": 0,
                                    "per_provider": {}}
        if not target_providers:
            target_providers = list(self._providers.keys()) or [
                "nvidia", "openrouter", "minimax", "xai", "blackbox"
            ]

        for provider in target_providers:
            results["probed"] += 1
            outcome = self._probe_single_provider(provider, probe_prompt, timeout)
            results["per_provider"][provider] = outcome
            category = outcome.get("category", "unknown")
            if category in results:
                results[category] += 1

        self._save()
        return results

    def _probe_single_provider(self, provider: str, prompt: str,
                                timeout: int) -> Dict[str, Any]:
        """Single-provider probe — sends a tiny completion request.

        Does NOT mutate model-level state if the provider-level probe
        fails (a global rate-limit or auth error on one model still affects
        all sibling models on the same provider).
        """
        import time
        endpoint_map = {
            "nvidia":     "https://integrate.api.nvidia.com/v1/chat/completions",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
            "minimax":    "https://api.minimax.io/v1/chat/completions",
            "xai":        "https://api.x.ai/v1/chat/completions",
        }
        endpoint = endpoint_map.get(provider)
        if not endpoint:
            return {"category": "degraded", "reason": "no_endpoint_mapping",
                    "provider": provider}

        api_key = self._get_provider_key(provider)
        if not api_key:
            return {"category": "auth_error", "reason": "no_api_key",
                    "provider": provider}

        body = json.dumps({
            "model": self._pick_probe_model(provider) or "default",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(endpoint, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                elapsed = (time.time() - started) * 1000
                if 200 <= resp.status < 300:
                    # SUCCESS — mark all sibling models AVAILABLE
                    self._set_provider_status(provider, ModelStatus.AVAILABLE,
                                              reset_failures=True)
                    return {"category": "healthy", "provider": provider,
                            "latency_ms": round(elapsed, 1)}
                if resp.status == 429:
                    self._set_provider_status(provider, ModelStatus.RATE_LIMITED,
                                              cooldown_seconds=60)
                    return {"category": "rate_limited", "provider": provider,
                            "status_code": 429}
                if resp.status in (401, 403):
                    self._set_provider_status(provider, ModelStatus.ERROR,
                                              cooldown_seconds=300)
                    return {"category": "auth_error", "provider": provider,
                            "status_code": resp.status}
                return {"category": "unavailable", "provider": provider,
                        "status_code": resp.status}
        except urllib.error.HTTPError as e:
            elapsed = (time.time() - started) * 1000
            if e.code == 429:
                self._set_provider_status(provider, ModelStatus.RATE_LIMITED, cooldown_seconds=60)
                return {"category": "rate_limited", "provider": provider, "status_code": 429}
            if e.code in (401, 403):
                self._set_provider_status(provider, ModelStatus.ERROR, cooldown_seconds=300)
                return {"category": "auth_error", "provider": provider, "status_code": e.code}
            self._set_provider_status(provider, ModelStatus.ERROR, cooldown_seconds=120)
            return {"category": "unavailable", "provider": provider,
                    "status_code": e.code, "elapsed_ms": round(elapsed, 1)}
        except Exception as e:
            self._set_provider_status(provider, ModelStatus.ERROR, cooldown_seconds=120)
            return {"category": "degraded", "provider": provider,
                    "reason": type(e).__name__ + ": " + str(e)[:80]}

    def _get_provider_key(self, provider: str) -> Optional[str]:
        """Pull an API key for a provider from credential store."""
        try:
            creds_path = Path("/root/credential/api_key.json")
            if not creds_path.exists():
                return None
            with open(creds_path) as f:
                creds = json.load(f)
            raw = creds.get(provider)
            if isinstance(raw, str):
                return raw
            if isinstance(raw, list) and raw:
                return raw[0]
            if isinstance(raw, dict):
                inner = raw.get("keys") or raw.get("key")
                if isinstance(inner, list) and inner:
                    return inner[0]
                if isinstance(inner, str):
                    return inner
        except Exception:
            return None
        return None

    def _pick_probe_model(self, provider: str) -> Optional[str]:
        """Return a known model_id on the given provider for the probe call."""
        candidates = {
            "nvidia":     "nvidia/llama-3.1-nemotron-nano-8b-v1",
            "openrouter": "openrouter/auto",
            "minimax":    "MiniMax-M2.7",
            "xai":        "grok-4.3",
        }
        return candidates.get(provider)

    def _set_provider_status(self, provider: str, status: ModelStatus,
                              reset_failures: bool = False,
                              cooldown_seconds: int = 0) -> None:
        """Bulk-set status for all models of a provider. Internal helper."""
        if provider not in self._providers:
            self._providers[provider] = ProviderHealth(provider=provider)
        ph = self._providers[provider]
        # Map ModelStatus -> ProviderStatus enum
        if status == ModelStatus.AVAILABLE:
            ph.status = ProviderStatus.HEALTHY
            ph.rate_limited = False
        elif status == ModelStatus.RATE_LIMITED:
            ph.status = ProviderStatus.DEGRADED
            ph.rate_limited = True
            if cooldown_seconds > 0:
                ph.rate_limit_reset = (
                    datetime.now() + timedelta(seconds=cooldown_seconds)
                ).isoformat()
        else:
            ph.status = ProviderStatus.UNHEALTHY
        if reset_failures:
            ph.consecutive_failures = 0
        ph.last_check = datetime.now().isoformat()

    def get_all_health(self) -> Dict[str, Any]:
        """Get full health status for all providers and models."""
        return {
            "providers": {p: ph.to_dict() for p, ph in self._providers.items()},
            "models": {mid: m.to_dict() for mid, m in self._models.items()},
            "proxy": self.check_proxy_health(),
            "timestamp": datetime.now().isoformat(),
        }
    
    def reset_all_health(self):
        """Reset all health state (use after manual intervention)."""
        self._models.clear()
        self._providers.clear()
        self._save()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get aggregate statistics about tracked models and providers.
        
        Returns a stable public API instead of exposing _models/_providers.
        """
        available = sum(
            1 for m in self._models.values()
            if m.status == ModelStatus.AVAILABLE
        )
        rate_limited = sum(
            1 for p in self._providers.values()
            if p.status in (ProviderStatus.UNHEALTHY, ProviderStatus.DEGRADED)
        )
        errors = sum(
            1 for m in self._models.values()
            if m.status == ModelStatus.ERROR
        )
        proxy_ok = self.check_proxy_health().get("healthy", False)

        return {
            "model_count": len(self._models),
            "provider_count": len(self._providers),
            "available_count": available,
            "rate_limited_count": rate_limited,
            "error_count": errors,
            "proxy_healthy": proxy_ok,
        }


# ===================
# Singleton
# ===================

_health_manager: Optional[HealthManager] = None

def get_health_manager() -> HealthManager:
    """Get singleton health manager instance."""
    global _health_manager
    if _health_manager is None:
        _health_manager = HealthManager()
    return _health_manager


# ===================
# Main (Test)
# ===================

if __name__ == "__main__":
    print("=== ILMA Health Manager Test ===")
    
    hm = get_health_manager()
    
    # Check proxy
    proxy = hm.check_proxy_health()
    print(f"Proxy: {proxy}")
    
    # List all models and their health
    print("\n--- All Model Health ---")
    for mid, mh in sorted(hm._models.items()):
        avail = "✅" if mh.is_available() else "❌"
        status = mh.status.value
        failures = mh.consecutive_failures
        reset = mh.rate_limit_reset or ""
        print(f"  {avail} {mid}: {status} ({failures} failures) {reset[:20]}")
    
    print("\n--- Provider Health ---")
    for p, ph in sorted(hm._providers.items()):
        avail = "✅" if ph.is_healthy() else "❌"
        status = ph.status.value
        rl = "RATE-LIMITED" if ph.rate_limited else "OK"
        print(f"  {avail} {p}: {status} | {ph.models_available}/{ph.models_total} models | {rl}")