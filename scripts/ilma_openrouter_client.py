#!/usr/bin/env python3
"""
ILMA OpenRouter Direct Client v1.0

- Uses /root/credential/api_key.json as the FIRST source for OPENROUTER_API_KEY.
- Fallback order: OPENROUTER_API_KEY env -> api_key.json call_key -> api_key.json keys[0]
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
ROUTER_DATA = ILMA_PROFILE / "ilma_model_router_data"
MASTER_DB = ROUTER_DATA / "PROVIDER_INTELLIGENCE_MASTER.json"
HEALTH_FILE = ILMA_PROFILE / "ilma_provider_health_state.json"

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT = f"{OPENROUTER_BASE}/chat/completions"
OPENROUTER_MODELS = f"{OPENROUTER_BASE}/models"
CREDENTIAL_FILE = Path("/root/credential/api_key.json")


def _load_openrouter_api_key() -> Optional[str]:
    """Prio 1: api_key.json, prio 2: OPENROUTER_API_KEY env."""
    try:
        data = json.loads(CREDENTIAL_FILE.read_text())
        section = data.get("openrouter") or {}
        key = section.get("call_key") or (section.get("keys") or [None])[0]
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("OPENROUTER_API_KEY")


class OpenRouterClient:
    def __init__(self, api_key: Optional[str] = None):
        # kalau argumen diberikan, pakai itu; kalau tidak, muat dari wiring.
        self.api_key = api_key or _load_openrouter_api_key() or ""
        self._master: Dict[str, Any] = {}
        self._health: Dict[str, Any] = {}
        self._load_databases()

    def _load_databases(self) -> None:
        try:
            self._master = json.loads(MASTER_DB.read_text())
        except Exception as e:
            print(f"[OpenRouter] Failed to load master db: {e}")
            self._master = {"providers": {}}

        try:
            self._health = json.loads(HEALTH_FILE.read_text())
        except Exception as e:
            print(f"[OpenRouter] Failed to load health state: {e}")
            self._health = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def health_check(self, model: str, timeout: int = 10) -> Dict[str, Any]:
        if not self.is_configured:
            return {"status": "unconfigured", "error": "No OPENROUTER_API_KEY"}

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "pong"}],
            "max_tokens": 5,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            import requests as req_lib
            resp = req_lib.post(OPENROUTER_CHAT, json=payload, headers=headers, timeout=timeout)
            data = resp.json()
            return {
                "status": "available",
                "model": model,
                "http_status": resp.status_code,
                "content": ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "",
            }
        except Exception as e:
            return {"status": "error", "model": model, "error": str(e)}

    def chat(
        self,
        message: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        thinking: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        if not self.is_configured:
            return {"success": False, "content": "", "model": "", "error": "OPENROUTER_API_KEY not set"}

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        if not model:
            top = self.get_top_free_models(limit=1)
            if not top:
                return {"success": False, "content": "", "model": "", "error": "No free models available"}
            model = top[0]["model_id"]

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if thinking and thinking.lower() in {"thinking", "deep", "high"}:
            payload["thinking"] = {"max_tokens": 4096, "budget_tokens": 8192}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ilma-hermes.local",
            "X-Title": "ILMA Hermes Agent",
        }

        try:
            import requests as req_lib
            resp = req_lib.post(OPENROUTER_CHAT, json=payload, headers=headers, timeout=timeout)
            data = resp.json()
            content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            return {
                "success": True,
                "content": content,
                "model": model,
                "usage": data.get("usage", {}),
            }
        except Exception as e:
            return {"success": False, "content": "", "model": model, "error": str(e)}

    def get_free_models(self) -> List[Dict[str, Any]]:
        provider = (self._master.get("providers") or {}).get("openrouter", {})
        models = provider.get("models", {})
        out = []
        for mid, mdata in models.items():
            if mdata.get("is_free") or mdata.get("billing") == "free":
                out.append(
                    {
                        "model_id": mid,
                        "name": mdata.get("name", mid),
                        "quality_score": mdata.get("quality_score", 0),
                    }
                )
        return sorted(out, key=lambda x: x["quality_score"], reverse=True)

    def get_top_free_models(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.get_free_models()[:limit]


def _build_client() -> OpenRouterClient:
    return OpenRouterClient()
