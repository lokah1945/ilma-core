#!/usr/bin/env python3
"""
ILMA PROVIDER KERNEL v2.2  (Phase 71: added blackbox 2026-06-04)
================================================
Layer 2 Execution: actual provider communication for FREE callable providers.
Credentials via ilma_credentials_v2.get_credential (always a string key).

Supported execution paths (all verified callable 2026-06-01):
  - nvidia      -> integrate.api.nvidia.com
  - minimax     -> api.minimax.io  /v1/text/chatcompletion_v2
  - ollama      -> ollama.com/v1   (cloud)
  - openrouter  -> openrouter.ai/api/v1 (call key)
  - blackbox    -> api.blackbox.ai  (Phase 71)
"""

import requests
import logging
import asyncio
from typing import Any, Dict, Optional
from ilma_credentials_v2 import get_credential

logger = logging.getLogger("ILMA.ProviderKernel")


def _runtime_model_allowed(provider: str, model_id: str, allow_paid: bool = False) -> bool:
    try:
        from ilma_model_router import get_router
        router = get_router(allow_paid=allow_paid)
        return router.is_model_runtime_allowed(provider, model_id, allow_paid=allow_paid)
    except Exception as exc:
        logger.warning(f"ProviderKernel runtime policy check failed for {provider}/{model_id}: {exc}")
        return False


class ProviderKernel:
    def __init__(self):
        self.session = requests.Session()

    def call(self, provider: str, model_id: str, messages: list, **kwargs) -> str:
        """Route to the right provider implementation. Returns content string
        (or 'Error: ...' / '<Provider> Error: ...')."""
        provider = (provider or "").strip()
        allow_paid = bool(kwargs.pop("allow_paid", False))
        if not _runtime_model_allowed(provider, model_id, allow_paid=allow_paid):
            return f"Error: blocked by FREE_MODEL_ONLY runtime policy: {provider}/{model_id}"

        api_key = get_credential(provider)
        if not api_key:
            return f"Error: No API key configured for {provider} in /root/credential/api_key.json"

        if provider == "nvidia" and kwargs.pop("parallel_mode", False):
            try:
                from scripts.ilma_nvidia_parallel_kernel import NVIDIAParallelKernel, NVIDIARequest
                req = NVIDIARequest(model_id=model_id, messages=messages, max_tokens=kwargs.get("max_tokens", 4096), temperature=kwargs.get("temperature", 0.7), timeout=kwargs.get("timeout", 90))
                responses = asyncio.run(NVIDIAParallelKernel().execute_parallel([req]))
                r = responses[0]
                return r.content if r.success else f"NVIDIA Parallel Error: {r.error}"
            except Exception as e:
                return f"NVIDIA Parallel Error: {str(e)[:200]}"

        if provider == "openrouter":
            return self._call_openai_compat("https://openrouter.ai/api/v1/chat/completions",
                                            api_key, model_id, messages,
                                            extra_headers={"HTTP-Referer": "http://localhost",
                                                           "X-Title": "ILMA"}, **kwargs)
        elif provider == "nvidia":
            return self._call_openai_compat("https://integrate.api.nvidia.com/v1/chat/completions",
                                            api_key, model_id, messages, **kwargs)
        elif provider == "ollama":
            return self._call_openai_compat("https://ollama.com/v1/chat/completions",
                                            api_key, model_id, messages, **kwargs)
        elif provider == "minimax":
            return self._call_minimax(api_key, model_id, messages, **kwargs)
        elif provider == "blackbox":
            # Phase 71: BlackBox AI — OpenAI-compatible, free, no key needed for basic tier.
            # If no key configured, use anonymous endpoint.
            return self._call_openai_compat("https://api.blackbox.ai/v1/chat/completions",
                                            api_key or "anonymous", model_id, messages, **kwargs)
        else:
            return f"Error: Provider {provider} not supported in Kernel v2.2"

    # ── Generic OpenAI-compatible POST ────────────────────────────────────────
    def _call_openai_compat(self, url: str, api_key: str, model_id: str, messages: list,
                            extra_headers: Optional[dict] = None, **kwargs) -> str:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        # strip provider prefix if present (e.g. "nvidia/qwen/..." -> keep model native id)
        api_model = model_id
        payload = {
            "model": api_model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=kwargs.get("timeout", 90))
            resp.raise_for_status()
            data = resp.json()
            return self._extract_content(data, url)
        except Exception as e:
            return f"{url.split('//')[-1].split('/')[0]} Error: {str(e)[:200]}"

    @staticmethod
    def _extract_content(data: dict, url: str = "") -> str:
        """Robustly extract assistant text from an OpenAI-compatible response.
        Handles reasoning models (reasoning_content), list-form content, and
        missing keys without throwing."""
        try:
            choices = data.get("choices") or []
            if not choices:
                return f"{url.split('//')[-1].split('/')[0]} Error: no choices in response"
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            # content may be a list of parts (some providers)
            if isinstance(content, list):
                content = "".join(
                    (p.get("text", "") if isinstance(p, dict) else str(p)) for p in content
                )
            if content and str(content).strip():
                return content
            # fall back to reasoning_content if the model spent all tokens reasoning
            rc = msg.get("reasoning_content")
            if rc and str(rc).strip():
                return rc
            # some providers put text at choices[0].text
            if choices[0].get("text"):
                return choices[0]["text"]
            return f"{url.split('//')[-1].split('/')[0]} Error: empty content"
        except Exception as e:
            return f"parse Error: {str(e)[:120]}"

    def _call_minimax(self, api_key: str, model_id: str, messages: list, **kwargs) -> str:
        url = "https://api.minimax.io/v1/text/chatcompletion_v2"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model_id.split("/")[-1] if "/" in model_id else model_id,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=kwargs.get("timeout", 90))
            resp.raise_for_status()
            data = resp.json()
            return self._extract_content(data, url)
        except Exception as e:
            return f"MiniMax Error: {str(e)[:200]}"


if __name__ == "__main__":
    print("ProviderKernel v2.2 initialized.")
