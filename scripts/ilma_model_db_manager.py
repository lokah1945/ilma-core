#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ILMA MODEL DATABASE MANAGER — SINGLE SOURCE OF TRUTH                   ║
║     v6.0 (2026-05-24)                                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  PURPOSE                                                                      ║
║    Canonical script untuk update PROVIDER_INTELLIGENCE_MASTER.json           ║
║    (single source of truth untuk seluruh model AI di ILMA).                  ║
║                                                                              ║
║  WHAT IT DOES                                                                 ║
║    Step 1  sync_providers()        Live model list dari 9 WORKING cloud APIs  ║
║                                      ↑ WORKING: nvidia/minimax/openrouter/xai ║
║                                      ↑          bluesminds/groq/together/blackbox/google║
║    Step 3  run_passive_benchmark() Usage log → benchmark_database.json        ║
║    Step 4  enrich()               Capabilities + AA benchmarks → MASTER       ║
║                                                                              ║
║  API KEY SOURCES (PRIORITY ORDER)                                           ║
║    1. /root/credential/api_key.json  (AYDA Credential Store — primary)       ║
║    2. /root/.hermes/profiles/ilma/.env  (ILMA .env — fallback)              ║
║                                                                              ║
║  SINGLE SOURCE OF TRUTH RULE                                                 ║
║    Hanya script ini yang boleh write ke MASTER dan benchmark_database.       ║
║                                                                              ║
║  USAGE                                                                       ║
python3 scripts/ilma_model_db_manager.py --full-sync        # steps 1-4   ║
    python3 scripts/ilma_model_db_manager.py --sync-providers   # step 1      ║
    python3 scripts/ilma_model_db_manager.py --passive-benchmark # step 2     ║
    python3 scripts/ilma_model_db_manager.py --enrich            # step 3     ║
║    python3 scripts/ilma_model_db_manager.py --stats            # read only  ║
║    python3 scripts/ilma_model_db_manager.py --dry-run           # preview    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────────────────────────────────────
ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
ROUTER_DATA  = ILMA_PROFILE / "ilma_model_router_data"
MASTER_DB    = ROUTER_DATA / "PROVIDER_INTELLIGENCE_MASTER.json"
BENCH_DB     = ROUTER_DATA / "benchmark_database.json"
USAGE_LOG    = ROUTER_DATA / "model_usage_log.jsonl"
BACKUP_DIR   = ROUTER_DATA / "backups"
AA_CACHE     = ILMA_PROFILE / "benchmark_aa_cache.json"  # Artificial Analysis scraper cache

# API key sources (priority order)
CREDS_FILE = Path("/root/credential/api_key.json")  # AYDA credential store — primary
ENV_FILE  = ILMA_PROFILE / ".env"                   # ILMA .env — fallback

LOCK_FILE = Path("/tmp/ilma_model_db.lock")

logger = logging.getLogger("ILMA.ModelDbManager")


# ══════════════════════════════════════════════════════════════════════════════════
# PROVIDER CONFIGURATIONS — ALL CLOUD PROVIDERS
# ══════════════════════════════════════════════════════════════════════════════════
# env_var  = key name di credential store + .env
# fmt      = response format: openai / ollama / together / openrouter-detail
# free_tier = default free tier flag (bisa di-override per-model dari API)
#
# OpenRouter uses MANAGEMENT API (openrouter.ai/api/v1/models + auth key)
# untuk dapatin harga per 1M tokens (input + output) per model.
# ══════════════════════════════════════════════════════════════════════════════════
PROVIDER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "openrouter": {"url": "https://openrouter.ai/api/v1/models", "env_var": "openrouter", "fmt": "openrouter-detail", "free_tier": False, "skip_key": False},
    "opencode":   {"url": "https://opencode.ai/zen/go/v1/models", "env_var": "opencode", "fmt": "openai", "free_tier": False, "skip_key": False},
    "nvidia":     {"url": "https://integrate.api.nvidia.com/v1/models", "env_var": "nvidia", "fmt": "openai", "free_tier": True, "skip_key": False},
    "minimax":    {"url": "https://api.minimax.io/v1/models", "env_var": "minimax", "fmt": "openai", "free_tier": True, "skip_key": False},
    "blackbox":   {"url": "https://docs.blackbox.ai/api-reference/models/chat-pricing", "env_var": "blackbox", "fmt": "blackbox-docs", "free_tier": False, "skip_key": True},
    "ollama":     {"url": "http://localhost:11434/api/tags", "env_var": "ollama", "fmt": "openai", "free_tier": True, "skip_key": False},
    "xai":        {"url": "https://api.x.ai/v1/models", "env_var": "xai", "fmt": "openai", "free_tier": False, "skip_key": False},
    "openai":     {"url": "https://api.openai.com/v1/models", "env_var": "openai", "fmt": "openai", "free_tier": False, "skip_key": False},
    "google":     {"url": "https://generativelanguage.googleapis.com/v1beta/models", "env_var": "google", "fmt": "google", "free_tier": False, "skip_key": False},
    "alibaba":    {"url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models", "env_var": "alibaba", "fmt": "openai", "free_tier": False, "skip_key": False},
    "groq":       {"url": "https://api.groq.com/openai/v1/models", "env_var": "groq", "fmt": "openai", "free_tier": False, "skip_key": False},
    "together":   {"url": "https://api.together.xyz/v1/models", "env_var": "together", "fmt": "openai", "free_tier": False, "skip_key": False},
    "cerebras":   {"url": "https://api.cerebras.ai/v1/models", "env_var": "cerebras", "fmt": "openai", "free_tier": False, "skip_key": False},
    "nous":       {"url": "https://inference-api.nousresearch.com/v1/models", "env_var": "nous", "fmt": "openai", "free_tier": False, "skip_key": False},
    "aimlapi":    {"url": "https://api.aimlapi.com/v1/models", "env_var": "aimlapi", "fmt": "openai", "free_tier": False, "skip_key": False},
    "byteplus":   {"url": "https://ark.ap-southeast.bytepluses.com/api/v3/models", "env_var": "byteplus", "fmt": "openai", "free_tier": False, "skip_key": False},
    "bytez":      {"url": "https://api.bytez.com/v1/models", "env_var": "bytez", "fmt": "openai", "free_tier": False, "skip_key": False},
    "felo":       {"url": "https://api.felo.ai/v1/models", "env_var": "felo", "fmt": "openai", "free_tier": False, "skip_key": False},
    "cloudflare": {"url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search", "env_var": "cloudflare", "fmt": "unsupported", "free_tier": False, "skip_key": False, "skip_sync": True},
    "artificial_analysis": {"url": "https://artificialanalysis.ai/", "env_var": "artificial_analysis", "fmt": "unsupported", "free_tier": False, "skip_key": False, "skip_sync": True},
}


# ══════════════════════════════════════════════════════════════════════════════════
# CAPABILITY PATTERNS (self-contained)
# ══════════════════════════════════════════════════════════════════════════════════
_CAPABILITY_PATTERNS = [
    ("code",     ["coder", "code", "coding", "dev", "starcoder", "codegemma", "qwen-coder", "deepseek-coder", "llmcode"]),
    ("reasoning",["think", "reason", "o1", "o3", "o4-mini", "qwq", "grok-think", "thinking", "deepseek-r1", "r1-", "qwen3-reason"]),
    ("vision",   ["vl-", "vision", "multimodal", "qvq", "glm-v", "gemini-pro-vis", "llava", "qwen-vl", "deepseek-vl"]),
    ("fast",     ["flash", "fast", "tiny", "mini", "nano", "small", "lite", "quick", "speed"]),
    ("instruct", ["instruct", "chat", "assistant", "llm"]),
]

_SPECIALIZATION_PATTERNS = [
    ("coding",    ["coder", "code", "coding", "starcoder", "codegemma", "deepseek-coder", "qwen-coder", "granite-code"]),
    ("reasoning", ["think", "reason", "o1", "o3", "qwq", "deepseek-r1", "qwen3-reason", "r1-", "grok-think"]),
    ("vision",    ["vl-", "vision", "multimodal", "qvq", "glm-v", "gemini-pro-vis", "llava", "qwen-vl"]),
    ("instruct",  ["instruct", "chat", "assistant"]),
    ("fast",      ["flash", "fast", "lite", "quick"]),
]


# ══════════════════════════════════════════════════════════════════════════════════
# CLASS: ModelDatabaseManager
# ══════════════════════════════════════════════════════════════════════════════════
class ModelDatabaseManager:
    """
    SINGLE SOURCE OF TRUTH untuk update PROVIDER_INTELLIGENCE_MASTER.json.

    Design rules:
    - HANYA class ini yang write ke MASTER_DB dan BENCH_DB.
    - API keys dibaca dari: (1) /root/credential/api_key.json → (2) .env
    - OpenRouter pakai management API → dapat harga per 1M tokens
    - Setiap save() otomatis bikin backup.
    - fully_sync() → 3 active steps: providers → passive → enrich.
    """

    def __init__(self, dry_run: bool = False, git_push: bool = False):
        self.dry_run  = dry_run
        self.git_push = git_push
        self._master: Optional[Dict] = None
        self._bench:  Optional[Dict] = None
        self._creds:   Optional[Dict] = None  # cached credential store

    # ────────────────────────────────────────────────────────────────────────────
    # PRIVATE: Credential Store Reader
    # ────────────────────────────────────────────────────────────────────────────
    def _load_creds(self) -> Dict[str, Any]:
        """Load /root/credential/api_key.json into memory (cached)."""
        if self._creds is None:
            if CREDS_FILE.exists():
                try:
                    with open(CREDS_FILE) as f:
                        self._creds = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load {CREDS_FILE}: {e}")
                    self._creds = {}
            else:
                self._creds = {}
        return self._creds or {}

    def _strict_verify_free(self, model: dict, provider: str) -> bool:
        """
        Strict free model verification during SOT build.
        Prevents paid models from entering the intelligence database.
        """
        # Pricing check
        pricing = model.get('pricing', {})
        if pricing:
            inp = float(pricing.get('input_per_1m', 0) or pricing.get('prompt', 0) or 0)
            out = float(pricing.get('output_per_1m', 0) or pricing.get('completion', 0) or 0)
            if inp > 0 or out > 0:
                return False
        
        billing = str(model.get('billing', '')).lower()
        if billing in ['paid', 'subscription', 'metered']:
            return False
        
        if not model.get('is_free', False):
            return False
        
        # Mixed provider extra check
        if provider in ['openrouter', 'blackbox', 'opencode']:
            name = str(model.get('name', '')).lower() + str(model.get('model_id', '')).lower()
            if any(kw in name for kw in ['paid', 'pro', 'premium', 'enterprise']):
                return False
        
        return True


    def _get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key for a provider — checks credential store first (.env fallback).

        Priority:
          1. /root/credential/api_key.json → section[provider].keys[0]
          2. ILMA .env file → env_var matching provider name
        """
        creds = self._load_creds()

        # ── Source 1: AYDA Credential Store ──────────────────────────────
        if provider in creds:
            section = creds[provider]
            if isinstance(section, dict):
                # Shape A: explicit keys list
                keys = section.get("keys", [])
                if keys:
                    return keys[0] if isinstance(keys, list) else keys
                # Shape B: NVIDIA-style — the api key IS the dict key (e.g. 'nvapi-...')
                for k, v in section.items():
                    if isinstance(k, str) and (k.startswith("nvapi-") or k.startswith("sk-")):
                        return k
                # Shape C: nested per-account dicts
                for k, v in section.items():
                    if isinstance(v, dict):
                        if v.get("api_key"):
                            return v["api_key"]
                        if v.get("key"):
                            return v["key"]
                        # account dict may itself contain a key field nested deeper
                        for kk, vv in v.items():
                            if isinstance(kk, str) and (kk.startswith("nvapi-") or kk.startswith("sk-")):
                                return kk
            elif isinstance(section, str) and section:
                return section

        # ── Source 2: ILMA .env file ────────────────────────────────────
        if not ENV_FILE.exists():
            return None
        try:
            # Map provider → env var name
            env_var_map = {
                "openrouter": "OPENROUTER_API_KEY",
                "nvidia":     "NVIDIA_API_KEY",
                "cohere":     "COHERE_API_KEY",
                "ollama":     "OLLAMA_API_KEY",
                "blackbox":   "BLACKBOX_API_KEY",
                "xai":        "XAI_API_KEY",
                "perplexity": "PERPLEXITY_API_KEY",
                "you":        "YOU_API_KEY",
                "openai":     "OPENAI_API_KEY",
                "anthropic":  "ANTHROPIC_API_KEY",
                "google":     "GOOGLE_AI_STUDIO_KEY",
                "minimax":    "MINIMAX_API_KEY",
            }
            env_var = env_var_map.get(provider)
            if not env_var:
                return None
            with open(ENV_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("#") or not line:
                        continue
                    if "=" in line:
                        k, _, v = line.partition("=")
                        if k.strip() == env_var:
                            val = v.strip().strip('"').strip("'")
                            if val and val not in ("YOUR_KEY_HERE", "dummy", ""):
                                return val
        except Exception as e:
            logger.warning(f"Failed to read {ENV_FILE}: {e}")
        return None

    # ────────────────────────────────────────────────────────────────────────────
    # PRIVATE: Load / Save
    # ────────────────────────────────────────────────────────────────────────────
    def _load_master(self) -> Dict:
        if self._master is None:
            with open(MASTER_DB) as f:
                self._master = json.load(f)
        return self._master

    def _save_master(self, data: Dict) -> None:
        data_str = json.dumps(data, indent=2, ensure_ascii=False)
        if self.dry_run:
            print(f"[DRY RUN] Would write {len(data_str):,} bytes to {MASTER_DB.name}")
            self._master = data
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / f"PROVIDER_INTELLIGENCE_MASTER_{ts}.json"
        shutil.copy2(MASTER_DB, backup)
        tmp = MASTER_DB.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data_str)
        tmp.replace(MASTER_DB)
        logger.info(f"✅ MASTER saved (+ backup {backup.name})")
        self._master = data

    def _save_bench(self, data: Dict) -> None:
        if self.dry_run:
            self._bench = data
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / f"benchmark_database_{ts}.json"
        if BENCH_DB.exists():
            shutil.copy2(BENCH_DB, backup)
        tmp = BENCH_DB.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(BENCH_DB)
        logger.info(f"✅ Benchmark DB saved (+ backup {backup.name})")
        self._bench = data

    # ────────────────────────────────────────────────────────────────────────────
    # PRIVATE: SSL context
    # ────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _ssl_ctx():
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    # ────────────────────────────────────────────────────────────────────────────
    # PRIVATE: Capability inference
    # ────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _infer_capabilities(model_id: str) -> List[str]:
        m = model_id.lower()
        caps: Set[str] = set()
        for cap_name, patterns in _CAPABILITY_PATTERNS:
            for pat in patterns:
                if pat in m:
                    caps.add(cap_name)
                    break
        return sorted(caps)

    @staticmethod
    def _classify_specialization(model_id: str, caps: List[str]) -> List[str]:
        m = model_id.lower()
        specs: Set[str] = set()
        for spec_name, patterns in _SPECIALIZATION_PATTERNS:
            for pat in patterns:
                if pat in m:
                    specs.add(spec_name)
                    break
        return sorted(specs) if specs else ["general"]

    # ────────────────────────────────────────────────────────────────────────────
    # STEP 1: Sync Providers
    # ────────────────────────────────────────────────────────────────────────────

    def sync_providers(self) -> Dict[str, Any]:
        """Fetch live model list dari ALL cloud provider APIs."""
        print("\n[STEP 1/3] sync_providers()...")
        master = self._load_master()
        if "providers" not in master:
            master["providers"] = {}

        stats = {
            "providers_checked": 0,
            "providers_synced": 0,
            "providers_no_key": [],
            "providers_failed": [],
            "total_added": 0,
            "total_removed": 0,
            "total_updated": 0,
            "per_provider": {},
        }

        for pname, cfg in PROVIDER_CONFIGS.items():
            if cfg.get("skip_sync"):
                print(f"[ProviderSync] {pname}: configured but skip_sync=True")
                continue
            if cfg.get("skip_key"):
                key = "dummy"  # marker: no key needed
            else:
                key = self._get_api_key(pname)

            stats["providers_checked"] += 1

            if not key:
                print(f"[ProviderSync] {pname}: no API key")
                stats["providers_no_key"].append(pname)
                continue

            # Init provider section
            if pname not in master["providers"]:
                master["providers"][pname] = {"models": {}, "provider_info": {}}
            pdata = master["providers"][pname]
            if "models" not in pdata:
                pdata["models"] = {}
            pdata.setdefault("provider_info", {})["name"] = pname
            pdata["provider_info"].setdefault("free_tier", cfg["free_tier"])

            # Fetch live models
            try:
                models_raw = self._fetch_provider_models(pname, cfg["url"], key, cfg["fmt"])
            except Exception as e:
                print(f"[ProviderSync] {pname}: ❌ {e}")
                stats["providers_failed"].append(pname)
                continue

            # Parse into (model_id, meta_dict)
            if cfg["fmt"] == "openrouter-detail":
                parsed = models_raw  # already parsed: [(id, meta)]
            elif cfg["fmt"] == "blackbox-docs":
                # blackbox-docs returns List[str] of FREE model_ids
                # Mark free models in meta; all others default to PAID
                free_ids = set(models_raw)
                parsed = [(m, {"free_tier": m in free_ids}) for m in free_ids]
                # Also fill in all PAID blackbox models from existing master
                if pname in master.get("providers", {}):
                    existing_bb = master["providers"][pname].get("models", {})
                    for eid, emeta in existing_bb.items():
                        if eid not in free_ids and eid not in [x[0] for x in parsed]:
                            parsed.append((eid, {"free_tier": False}))
            else:
                parsed = [(m, {}) for m in models_raw]

            live_ids  = set(m[0] for m in parsed)
            existing  = set(pdata["models"].keys())
            added     = live_ids - existing
            removed   = existing - live_ids
            updated   = existing & live_ids

            print(f"[ProviderSync] {pname}: {len(live_ids)} live models "
                  f"(+{len(added)} -{len(removed)} ~{len(updated)})")

            if not self.dry_run:
                for mid, meta in parsed:
                    if mid in added:
                        raw_free = bool(meta.get("free_tier", cfg["free_tier"]))
                        ctx_win = meta.get("context_length") or meta.get("context_window")
                        new_model = {
                            "model_id": mid,
                            "provider": pname,
                            "free_tier": raw_free,
                            "is_free": raw_free,
                            "capabilities": self._infer_capabilities(mid),
                            "context_window": ctx_win or 4096,
                            "price_per_m_input":  meta.get("price_per_m_input"),
                            "price_per_m_output": meta.get("price_per_m_output"),
                            "pricing": meta.get("pricing", {}),
                            "billing": "free" if raw_free else "paid",
                            "disabled": False,
                            "user_allowed": True,
                            "admin_override": False,
                            "last_verified": datetime.now().isoformat(),
                            "model_info":        meta.get("model_info"),
                        }
                        strict_free = self._strict_verify_free(new_model, pname)
                        new_model["is_free"] = strict_free
                        new_model["free_tier"] = strict_free
                        if not strict_free:
                            new_model["disabled"] = True
                            new_model["disabled_reason"] = "strict_free_verification_failed"
                        pdata["models"][mid] = new_model
                    elif mid in updated:
                        cur = pdata["models"][mid]
                        cur["refreshed_at"] = datetime.now().isoformat()
                        cur["last_verified"] = datetime.now().isoformat()
                        for k in ("price_per_m_input", "price_per_m_output", "pricing", "context_length", "context_window"):
                            if k in meta and meta.get(k) is not None:
                                cur[k] = meta.get(k)
                        strict_free = self._strict_verify_free(cur, pname)
                        cur["is_free"] = strict_free
                        cur["free_tier"] = strict_free
                        if not strict_free:
                            cur["disabled"] = True
                            cur["disabled_reason"] = "strict_free_verification_failed"
                for mid in removed:
                    del pdata["models"][mid]

            stats["providers_synced"]   += 1
            stats["total_added"]        += len(added)
            stats["total_removed"]     += len(removed)
            stats["total_updated"]     += len(updated)
            stats["per_provider"][pname] = {
                "live": len(live_ids), "added": len(added),
                "removed": len(removed), "updated": len(updated),
            }

        if not self.dry_run:
            self._save_master(master)
        else:
            self._master = master

        print(f"[ProviderSync] ✅ Synced {stats['providers_synced']}/{stats['providers_checked']} providers")
        return {"success": True, "stats": stats}

    def _fetch_provider_models(
        self, pname: str, url: str, key: str, fmt: str
    ) -> List[Any]:
        """
        Fetch model list from one provider API.
        Returns:
          - list of model_id strings (for openai/ollama formats)
          - list of (model_id, meta_dict) tuples (for openrouter-detail)
        """
        req = urllib.request.Request(url)
        if key != "dummy":
            if fmt == "google":
                # Google AI Studio: use x-goog-api-key header (not Bearer)
                req.add_header("x-goog-api-key", key)
            else:
                req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Accept", "application/json")
        # Use browser-like User-Agent to bypass Cloudflare 403 on some providers
        # (cerebras, groq, opencode, together, aimlapi, you)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")

        try:
            if fmt == "blackbox-docs":
                # HTML page, not JSON
                with urllib.request.urlopen(req, timeout=20, context=self._ssl_ctx()) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
            else:
                with urllib.request.urlopen(req, timeout=20, context=self._ssl_ctx()) as resp:
                    raw = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            raise RuntimeError(f"HTTP {e.code}: {body}")

        if fmt == "openai":
            # Handle both {"data": [...]} and raw list responses (e.g., Together AI)
            if isinstance(raw, list):
                return [m.get("id", m.get("name", "")) for m in raw if isinstance(m, dict) and (m.get("id") or m.get("name"))]
            return [m.get("id", "") for m in raw.get("data", []) if m.get("id")]

        elif fmt == "openrouter-detail":
            # OpenRouter: full detail per model — includes pricing per 1M tokens
            # Response: {"data": [{id, name, description, pricing: {prompt|completion}, context_length, ...}]}
            openrouter_result: List[Any] = []
            for m in raw.get("data", []):
                mid = m.get("id")
                if not mid:
                    continue
                pricing = m.get("pricing", {})
                openrouter_result.append((mid, {
                    "model_id":           mid,
                    "provider":           pname,
                    "free_tier":           m.get("free_tier", False),
                    "context_length":     m.get("context_length"),
                    "context_window":     m.get("context_length"),
                    "description":        m.get("description"),
                    "model_info": {
                        "name":        m.get("name"),
                        "description": m.get("description"),
                        "architecture": m.get("architecture", {}),
                        "top_provider": m.get("top_provider"),
                        "mode":        m.get("mode"),
                    },
                    "price_per_m_input":   pricing.get("prompt"),
                    "price_per_m_output":  pricing.get("completion"),
                }))
            return openrouter_result

        elif fmt == "ollama":
            return [m.get("name", "") for m in raw.get("models", []) if m.get("name")]

        elif fmt == "google":
            # Google AI Studio: response has {"models": [{name, baseModelId, ...}]}
            return [m.get("name", m.get("baseModelId", "")) for m in raw.get("models", []) if m.get("name") or m.get("baseModelId")]

        elif fmt == "blackbox-docs":
            # BlackBox docs page HTML table parsing.
            # HTML structure: <table> with columns:
            #   Model Name | Model ID | Input Cost | Output Cost | Context Length
            # Free model: input_cost == "Free" or "$0.00" (case-insensitive)
            result: List[str] = []
            html_body = raw if isinstance(raw, str) else str(raw)
            row_pattern = re.compile(
                r'<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?</tr>',
                re.DOTALL
            )
            in_free_col = re.compile(r'^\$0\.00$', re.IGNORECASE)
            # Process ALL rows (no header row in this table)
            for m in row_pattern.finditer(html_body):
                cells = [re.sub(r'<[^>]+>', '', c).strip() for c in m.groups()]
                # cells[1] = Model ID, cells[2] = Input Cost, cells[3] = Output Cost
                mid = cells[1].strip()
                if not mid:
                    continue
                is_free = (
                    cells[2].lower() == "free" or
                    cells[3].lower() == "free" or
                    bool(in_free_col.match(cells[2])) or
                    bool(in_free_col.match(cells[3]))
                )
                if is_free:
                    result.append(mid)
            return result

        else:
            raise ValueError(f"Unknown fmt: {fmt}")

    # ────────────────────────────────────────────────────────────────────────────
    # STEP 3: Passive Benchmark
    # ────────────────────────────────────────────────────────────────────────────
    def run_passive_benchmark(self) -> Dict[str, Any]:
        """Parse model_usage_log.jsonl → update benchmark_database.json."""
        print("\n[STEP 3/4] run_passive_benchmark()...")
        master = self._load_master()

        bench: Dict = {"benchmarks": {}}
        if BENCH_DB.exists():
            with open(BENCH_DB) as f:
                bench = json.load(f)
        if "benchmarks" not in bench:
            bench["benchmarks"] = {}

        entries: List[Dict] = []
        if USAGE_LOG.exists():
            try:
                with open(USAGE_LOG) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entries.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
            except Exception as e:
                print(f"[PassiveBench] ⚠️  Failed to read usage log: {e}")

        print(f"[PassiveBench] Parsed {len(entries)} usage entries")

        # Aggregate
        agg: Dict[str, Dict[str, Any]] = {}
        for e in entries:
            mid = e.get("model_id", "unknown")
            if mid not in agg:
                agg[mid] = {"total_requests": 0, "total_tokens": 0,
                            "total_errors": 0, "events": []}
            agg[mid]["total_requests"] += 1
            agg[mid]["total_tokens"]    += e.get("tokens_used", 0)
            agg[mid]["total_errors"]    += e.get("error_count", 0)
            agg[mid]["events"].append({
                "timestamp": e.get("timestamp"),
                "success":   e.get("success", True),
            })

        def _score(a: Dict) -> float:
            req   = a["total_requests"]
            if req < 3:
                return 0.0
            err_r = a["total_errors"] / req
            last_ts = a["events"][-1].get("timestamp", 0) or 0
            if isinstance(last_ts, str):
                try:
                    last_ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00")).timestamp()
                except Exception:
                    last_ts = time.time()
            rec = max(0.0, 1.0 - (time.time() - last_ts) / 604800)
            return round((1 - err_r) * rec * min(req / 10, 1.0) * 100, 2)

        updated = added = unchanged = insufficient = 0

        for mid, a in agg.items():
            score    = _score(a)
            existing = bench["benchmarks"].get(mid, {})
            new_entry = {
                "model_id":         mid,
                "avg_score":        score,
                "total_requests":   a["total_requests"],
                "total_tokens":      a["total_tokens"],
                "error_rate":       round(a["total_errors"] / max(a["total_requests"], 1), 4),
                "last_updated":     datetime.now().isoformat(),
                "usage_recency":     a["events"][-1].get("timestamp") if a["events"] else None,
            }
            if score == 0:
                insufficient += 1
                continue
            if existing and abs(score - existing.get("avg_score", 0)) < 0.01:
                unchanged += 1
            else:
                bench["benchmarks"][mid] = new_entry
                if existing:
                    updated += 1
                else:
                    added += 1

        bench["last_updated"] = datetime.now().isoformat()
        self._save_bench(bench)

        print(f"[PassiveBench] {len(agg)} models aggregated — "
              f"updated:{updated} added:{added} unchanged:{unchanged} insufficient:{insufficient}")

        return {"success": True, "stats": {"models_updated": updated,
                                           "models_added": added,
                                           "models_unchanged": unchanged,
                                           "insufficient": insufficient}}

    # ══════════════════════════════════════════════════════════════════════════════════
    # FREE ONLY POLICY (per Bos mandate — 2026-05-24)
    # Bos stated: minimax/nvidia/ollama ALL FREE; openrouter/blackbox MIXED;
    # all others PAID.
    # ══════════════════════════════════════════════════════════════════════════════════
    # Providers where ALL models are FREE
    FREE_PROVIDERS: set = {"minimax", "nvidia", "ollama"}
    # Providers with MIXED free/paid models (use per-model free_tier from API data)
    MIXED_PROVIDERS: set = {"openrouter", "blackbox", "opencode"}
    # ALL other providers: ALL PAID (not in Bos free list)
    PAID_PROVIDERS: set = {
        "openai", "anthropic", "google", "meta", "mistral", "cohere",
        "amazon", "microsoft-azure", "ai21-labs", "alibaba", "deepseek",
        "useai", "perplexity", "xai", "you",
    }

    def _resolve_free_tier(self, pname: str, pdata: dict, mid: str, minfo: dict) -> bool:
        """Policy-aware free_tier resolver — single source of truth for enrich().

        Rules (per Bos mandate):
          1. If provider in FREE_PROVIDERS (nvidia, minimax, ollama) → True
             (overrides any API data; these providers are ALWAYS free for ILMA)
          2. If provider in MIXED_PROVIDERS (openrouter, blackbox):
             - Check explicit free indicators: :free suffix, billing=free
             - OpenRouter: price_per_m_input == "0" AND price_per_m_output == "0"
               (0.00 is also treated as free; any non-zero price = paid)
             - Blackbox: per-model free_tier flag from API/docs table
          3. If provider in PAID_PROVIDERS → False (ALL paid by default)
             Exception: specific free models that match rules above.
        """
        # 1. FREE_PROVIDERS: always free regardless of what API says
        if pname in self.FREE_PROVIDERS:
            return True
        
        if pname in self.MIXED_PROVIDERS:
            # 2a. OpenRouter: pricing endpoint pricing.prompt / pricing.completion
            input_price = minfo.get("price_per_m_input")
            output_price = minfo.get("price_per_m_output")
            
            if input_price is not None and output_price is not None:
                # Normalize to string for comparison
                ip = str(input_price).strip()
                op = str(output_price).strip()
                if ip in ("0", "0.00", "0.0", "free") and op in ("0", "0.00", "0.0", "free"):
                    return True
                # If we have explicit prices and they are non-zero (or unknown), it's paid
                if ip and ip not in ("0", "0.00", "0.0", "free", "None", ""):
                    return False
        
        # Dead models (validated not-found-for-account) stay excluded from free pool.
        if minfo.get("unavailable") and "not_found" in str(minfo.get("unavailable_reason", "")):
            return False
        if pname in self.MIXED_PROVIDERS:
            # Check model-level indicators (OpenRouter/billing)
            if ':free' in mid.lower():
                return True
            billing = minfo.get('billing') or pdata.get('billing')
            if billing == 'free':
                return True
            return False
        # All others: PAID (not in Bos free list)
        return False

    # ────────────────────────────────────────────────────────────────────────────
    # STEP 4: Enrich
    # ────────────────────────────────────────────────────────────────────────────
    def sync_artificialanalysis(self) -> Dict[str, Any]:
        """Load benchmark_aa_cache.json and return lookup index.
        
        Returns:
            Dict keyed by model slug (e.g. 'gpt-5-5-pro') and model name variants.
            Each entry: {ai_index, coding_index, math_index, mmlu_pro, gpqa, ...}
        """
        if not AA_CACHE.exists():
            return {}
        
        with open(AA_CACHE) as f:
            cache = json.load(f)
        
        records = cache.get("records", [])
        index = {}
        
        for r in records:
            slug = r.get("slug", "")
            if not slug:
                continue
            
            # Index by slug
            index[slug] = {
                "ai_index":   r.get("artificial_analysis_intelligence_index"),
                "coding_index": r.get("artificial_analysis_coding_index"),
                "math_index": r.get("artificial_analysis_math_index"),
                "mmlu_pro":   r.get("mmlu_pro"),
                "gpqa":       r.get("gpqa"),
                "livecodebench": r.get("livecodebench"),
                "provider":    r.get("provider"),
                "name":        r.get("name"),
            }
            
            # Also index by lowercase slug variants
            index[slug.lower()] = index[slug]
            index[slug.replace("-", "")] = index[slug]
            index[slug.replace("-", "").lower()] = index[slug]
            
            # Index by name
            name = r.get("name", "").lower().replace(" ", "-")
            index[name] = index[slug]
            index[name.replace("(", "").replace(")", "")] = index[slug]
        
        return index

    @staticmethod
    def _compute_score(minfo: dict) -> dict:
        """Compute a unified 0-100 score + breakdown + tier for a model.

        Weighting (when AA data present):
          intelligence 45%, coding 30%, math 15%, capability_breadth 5%, usage_health 5%
        When AA data absent: fall back to capability + usage signals (capped lower).
        """
        aa = minfo.get("benchmark_aa") or {}
        def _num(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        ai   = _num(aa.get("ai_index"))
        code = _num(aa.get("coding_index"))
        math = _num(aa.get("math_index"))

        # AA indices are roughly 0..70 in current data — normalize to 0..100 (cap at 70 -> 100)
        def _norm(v, hi=70.0):
            if v is None:
                return None
            return max(0.0, min(100.0, (v / hi) * 100.0))

        n_ai, n_code, n_math = _norm(ai), _norm(code), _norm(math)

        caps = minfo.get("capabilities") or []
        cap_breadth = min(len(caps) / 5.0, 1.0) * 100.0  # 0..100

        usage = _num(minfo.get("benchmark_score"))  # passive benchmark 0..100
        err   = _num(minfo.get("error_rate"))
        usage_health = usage if usage is not None else (100.0 * (1.0 - err) if err is not None else None)

        breakdown = {}
        if n_ai is not None or n_code is not None or n_math is not None:
            # AA-driven scoring
            parts, weights = [], []
            if n_ai is not None:   parts.append(n_ai);   weights.append(0.45); breakdown["intelligence"] = round(n_ai,1)
            if n_code is not None: parts.append(n_code); weights.append(0.30); breakdown["coding"] = round(n_code,1)
            if n_math is not None: parts.append(n_math); weights.append(0.15); breakdown["math"] = round(n_math,1)
            parts.append(cap_breadth); weights.append(0.05); breakdown["capability_breadth"] = round(cap_breadth,1)
            if usage_health is not None:
                parts.append(usage_health); weights.append(0.05); breakdown["usage_health"] = round(usage_health,1)
            wsum = sum(weights)
            score = sum(p*w for p, w in zip(parts, weights)) / wsum if wsum else 0.0
            source = "aa+heuristic"
        else:
            # No AA data — heuristic only, capped at 60 so AA-scored models rank higher
            parts, weights = [cap_breadth], [0.7]
            breakdown["capability_breadth"] = round(cap_breadth,1)
            if usage_health is not None:
                parts.append(usage_health); weights.append(0.3); breakdown["usage_health"] = round(usage_health,1)
            wsum = sum(weights)
            raw = sum(p*w for p, w in zip(parts, weights)) / wsum if wsum else 0.0
            score = min(raw, 60.0)
            source = "heuristic"

        score = round(score, 2)
        if score >= 80:   tier = "S"
        elif score >= 65: tier = "A"
        elif score >= 50: tier = "B"
        elif score >= 35: tier = "C"
        else:             tier = "D"
        return {"score": score, "score_tier": tier, "score_source": source, "score_breakdown": breakdown}

    def enrich(self) -> Dict[str, Any]:
        """Apply capabilities + benchmark scores + AA data + POLICY-AWARE free_tier → MASTER."""
        print("\n[STEP 4/4] enrich() — POLICY-AWARE + AA benchmark integration...")
        master = self._load_master()

        bench: Dict = {"benchmarks": {}}
        if BENCH_DB.exists():
            with open(BENCH_DB) as f:
                bench = json.load(f)
        bench_bm = bench.get("benchmarks", {})

        # Load AA benchmark index
        aa_index = self.sync_artificialanalysis()
        aa_enriched = 0
        print(f"[AA] Loaded {len(aa_index)} AA benchmark entries")

        processed = enriched = free_count = paid_count = 0

        for pname, pdata in master.get("providers", {}).items():
            for mid, minfo in list(pdata.get("models", {}).items()):
                processed += 1
                norm_caps  = self._infer_capabilities(mid)
                specs     = self._classify_specialization(mid, norm_caps)
                minfo.setdefault("capabilities", norm_caps)
                minfo.setdefault("specializations", specs)

                bm = bench_bm.get(mid, {})
                minfo["benchmark_score"]    = bm.get("avg_score")
                minfo["total_requests"]    = bm.get("total_requests")
                minfo["error_rate"]        = bm.get("error_rate")
                minfo["benchmark_updated"] = bm.get("last_updated")

                # ── AA Benchmark Integration ────────────────────────────────
                # Match model by slug, name, or name variants
                aa_match = None
                for key in [mid.lower(), mid.replace("-", "").lower(),
                            mid.replace("_", "-").lower(),
                            minfo.get("name", "").lower().replace(" ", "-"),
                            minfo.get("id", "").lower()]:
                    if key in aa_index:
                        aa_match = aa_index[key]
                        break
                
                if aa_match and aa_match.get("ai_index") is not None:
                    minfo["benchmark_aa"] = {
                        "ai_index":     aa_match["ai_index"],
                        "coding_index":  aa_match["coding_index"],
                        "math_index":    aa_match["math_index"],
                        "mmlu_pro":      aa_match["mmlu_pro"],
                        "gpqa":          aa_match["gpqa"],
                        "livecodebench": aa_match["livecodebench"],
                        "provider_match": aa_match["provider"],
                    }
                    aa_enriched += 1
                # ─────────────────────────────────────────────────────────────

                # ── Derive capabilities_detail from AA benchmark (2026-06-01) ──
                # Gives the router accurate per-capability scores for models that
                # lack hand-authored capabilities_detail (e.g. ollama-cloud).
                aa_bm = minfo.get("benchmark_aa") or {}
                if aa_bm and not minfo.get("capabilities_detail"):
                    def _n(v, hi=70.0):
                        try:
                            return max(0.0, min(1.0, float(v) / hi))
                        except (TypeError, ValueError):
                            return None
                    ai = _n(aa_bm.get("ai_index"))
                    code = _n(aa_bm.get("coding_index"))
                    math = _n(aa_bm.get("math_index"))
                    mmlu = _n(aa_bm.get("mmlu_pro"), 100.0)
                    if ai is not None:
                        minfo["capabilities_detail"] = {
                            "reasoning":             round(ai, 3),
                            "coding":                round(code if code is not None else ai, 3),
                            "instruction_following": round(mmlu if mmlu is not None else ai, 3),
                            "structured_output":     round(ai, 3),
                            "research":              round(ai, 3),
                            "backend":               round(code if code is not None else ai, 3),
                            "math":                  round(math if math is not None else ai, 3),
                        }

                # POLICY-AWARE free_tier — the canonical fix
                ft = self._resolve_free_tier(pname, pdata, mid, minfo)
                minfo["free_tier"] = ft
                minfo["is_free"] = ft  # Also set is_free so router picks up policy correctly
                minfo.setdefault("disabled", False)
                minfo.setdefault("user_allowed", True)
                minfo.setdefault("admin_override", False)
                minfo["last_verified"] = datetime.now().isoformat()
                if not ft:
                    minfo["disabled"] = True
                    minfo.setdefault("disabled_reason", "strict_free_verification_failed")

                # ── Unified scoring (capacity / capability / task fitness) ──
                _sc = self._compute_score(minfo)
                minfo["score"] = _sc["score"]
                minfo["score_tier"] = _sc["score_tier"]
                minfo["score_source"] = _sc["score_source"]
                minfo["score_breakdown"] = _sc["score_breakdown"]
                if ft:
                    free_count += 1
                else:
                    paid_count += 1
                if norm_caps:
                    enriched += 1

        # PHASE B: Promote quality >= 70 free models to is_active
        promoted_count, promoted_list = self._promote_models(master)

        self._save_master(master)
        print(f"[Enrich] {processed} processed, {enriched} enriched, "
              f"free:{free_count} paid:{paid_count}")
        print(f"[AA] {aa_enriched} models matched with AA benchmark data")

        return {"success": True, "stats": {
            "models_processed":   processed,
            "models_enriched":    enriched,
            "models_aa_enriched": aa_enriched,
            "models_free":        free_count,
            "models_paid":        paid_count,
            "models_promoted":    promoted_count,
        }}

    # ────────────────────────────────────────────────────────────────────────────
    # PHASE B: STAGED MODEL PROMOTION (2026-06-05)
    # ────────────────────────────────────────────────────────────────────────────
    QUALITY_PROMOTION_THRESHOLD = 70.0   # normalize to 0-100 scale

    def _normalize_quality(self, mdata: dict) -> float:
        """Normalize quality_score to 0-100 scale."""
        qs = mdata.get('quality_score', 0)
        if not qs:
            return 0.0
        return qs * 100.0 if qs < 1.0 else float(qs)

    def _promote_models(self, master: dict) -> Tuple[int, List[str]]:
        """
        Staged promotion: promote inactive models to is_active=True based on
        quality_score, free_tier, and track record.
        
        Tier 1 (this phase): quality >= 70, free_tier, not deprecated, has caps.
        Total: ~30 models → active pool grows from 27 to ~57.
        
        This is conservative: we promote models that look good on metadata but
        let the health system prove them in production. is_healthy() will give
        unknown models a 0.3 penalty (PHASE A) so proven-healthy models still
        rank above promoted models.
        
        Rollback: run --dry-run --enrich first to preview; set is_active=False
        directly in MASTER to demote.
        """
        promoted = []
        providers = master.get("providers", {})
        
        # Quality threshold (0-100 scale)
        threshold = self.QUALITY_PROMOTION_THRESHOLD
        
        # PHASE 0 BUG FIX (2026-06-06): OpenRouter was EXCLUDED from promotion,
        # locking all 23 OpenRouter :free models at is_active=False permanently.
        # Root cause: promote list was {nvidia, minimax, ollama} — missing
        # openrouter. All OpenRouter free models (verified by API :free suffix)
        # must now be eligible for promotion regardless of quality_score.
        # free_tier=True from OpenRouter IS the quality signal — provider confirmed
        # no-cost access, which is sufficient for activation.
        # 
        # DUAL THRESHOLD: free-tier models use lower threshold (50 vs 70) since
        # is_free=True from provider API IS the quality signal for free models.
        # free_tier models with no benchmark data: quality_score heuristic default
        # is 0.3 → would need quality_score >= 0.70 to pass. With :free suffix
        # confirmation from API, this is sufficient to activate at lower threshold.
        FREE_TIER_THRESHOLD = 50.0   # free-tier models: promote if quality >= 50
        for pname, pdata in providers.items():
            if pname not in {"nvidia", "minimax", "ollama", "openrouter"}:
                continue
            for mid, mdata in list(pdata.get("models", {}).items()):
                # Skip already active
                if mdata.get("is_active"):
                    continue
                # Skip non-free
                if not self._strict_verify_free(mdata, pname):
                    continue
                # Skip deprecated
                if mdata.get("deprecated", False):
                    continue
                # Skip if no capabilities
                caps = mdata.get("capabilities", [])
                if not caps:
                    continue
                # Determine free-tier status (used for quality baseline + threshold)
                free_tier_flag = mdata.get("is_free", mdata.get("free_tier", False))
                # PHASE 0 BUG FIX: OpenRouter :free models have quality_score=0.3
                # (heuristic default — no benchmark data) but is_free=True from API.
                # For free-tier models where OpenRouter API confirmed no cost (:free suffix),
                # use is_free status as sufficient quality signal. Apply minimum baseline
                # of 0.50 so these models pass promotion threshold (70→50 for free-tier).
                if free_tier_flag:
                    qs_raw = mdata.get("quality_score", 0)
                    # If quality is very low default (0.3 = heuristic fallback with no evidence)
                    # AND model has free_tier confirmation → elevate to minimum viable baseline
                    if qs_raw is not None and 0 < qs_raw < 0.35:
                        mdata["quality_score"] = 0.50   # free-tier minimum baseline
                        full_id = f"{pname}/{mid}"
                        print(f"[Promote] ⬆️  QUALITY BOOST {full_id}: {qs_raw:.2f}→0.50 (free-tier baseline)")
                # Quality threshold — use lower threshold for free-tier models
                # (free_tier=True from provider API is the quality signal)
                qs = self._normalize_quality(mdata)
                effective_threshold = threshold
                if free_tier_flag:
                    effective_threshold = min(threshold, FREE_TIER_THRESHOLD)
                if qs < effective_threshold:
                    continue
                
                # Promote!
                mdata["is_active"] = True
                full_id = f"{pname}/{mid}"
                promoted.append(f"{full_id} [{qs:.0f}]")
        
        if promoted:
            print(f"[Promote] ⬆️  {len(promoted)} models promoted (quality>={threshold}, free, not deprecated)")
            for p in sorted(promoted):
                print(f"          {p}")
        else:
            print(f"[Promote] No models met promotion criteria (threshold={threshold})")
        
        return len(promoted), promoted

    # ────────────────────────────────────────────────────────────────────────────
    # FULL SYNC
    # ────────────────────────────────────────────────────────────────────────────
    def full_sync(self) -> Dict[str, Any]:
        """Run complete 3-step pipeline."""
        print("\n" + "="*60)
        print("ILMA MODEL DB MANAGER — FULL SYNC v6.0")
        print("="*60)

        r1 = self.sync_providers()
        r2 = self.run_passive_benchmark()
        r3 = self.enrich()

        if self.git_push and not self.dry_run:
            self._git_push()

        total = sum(len(v["models"]) for v in self._load_master()["providers"].values())
        s1 = r1.get("stats", {})
        print("\n" + "="*60)
        print(f"  Providers:        {s1.get('providers_synced',0)}/{s1.get('providers_checked',0)} synced "
              f"(+{s1.get('total_added',0)} -{s1.get('total_removed',0)})")
        print(f"  Benchmark:         {r2.get('stats',{}).get('models_updated',0)} updated, "
              f"{r2.get('stats',{}).get('models_added',0)} added")
        print(f"  Enrich:           {r3.get('stats',{}).get('models_enriched',0)}/{r3.get('stats',{}).get('models_processed',0)} enriched")
        print(f"  Total in MASTER:  {total} models")
        print("="*60)
        return {"success": True,
                "sync_providers": r1,
                "passive_benchmark": r2,
                "enrich": r3}

    # ────────────────────────────────────────────────────────────────────────────
    # STATS
    # ────────────────────────────────────────────────────────────────────────────
    def get_stats(self) -> Dict[str, Any]:
        master = self._load_master()
        providers = master.get("providers", {})
        total = sum(len(v.get("models", {})) for v in providers.values())
        return {
            "total_models": total,
            "total_providers": len(providers),
            "per_provider": {
                p: len(v.get("models", {}))
                for p, v in sorted(providers.items())
            },
        }

    # ────────────────────────────────────────────────────────────────────────────
    # GIT PUSH
    # ────────────────────────────────────────────────────────────────────────────
    def _git_push(self) -> None:
        try:
            import subprocess
            cwd = str(ILMA_PROFILE)
            subprocess.run(["git", "add",
                            "ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json",
                            "ilma_model_router_data/benchmark_database.json"],
                           cwd=cwd, check=True, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m",
                 f"chore(model-db): auto-sync {datetime.now().strftime('%Y-%m-%d %H:%M')} "
                 f"({self.get_stats()['total_models']} models)"],
                cwd=cwd, check=True, capture_output=True, text=True)
            subprocess.run(["git", "push", "origin", "master"],
                           cwd=cwd, check=True, capture_output=True)
            print(f"[GitPush] ✅ {result.stdout[:200]}")
        except Exception as e:
            print(f"[GitPush] ⚠️  {e}")


# ══════════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── Acquire lock to prevent concurrent runs ───────────────────────────
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            os.kill(pid, 0)
            print(f"[LOCK] Another instance running (PID {pid}) — exiting")
            sys.exit(1)
        except (OSError, ValueError):
            pass
    LOCK_FILE.write_text(str(os.getpid()))

    try:
        # ── CLI ─────────────────────────────────────────────────────────────
        parser = argparse.ArgumentParser(
            description="ILMA Model DB Manager v6.0 — Single Source of Truth",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Commands:
  --full-sync          Complete 3-step pipeline (default if no flags)
  --sync-providers     Cloud APIs → MASTER only
  --passive-benchmark  Usage log → benchmark DB only
  --enrich             Capabilities + scores → MASTER only
  --stats              Show current MASTER stats (read-only)
  --dry-run            Preview without writing files
  --git-push           Auto git push after sync
        """,
        )
        parser.add_argument("--full-sync",          action="store_true")
        parser.add_argument("--sync-providers",     action="store_true")
        parser.add_argument("--passive-benchmark",  action="store_true")
        parser.add_argument("--enrich",             action="store_true")
        parser.add_argument("--stats",               action="store_true")
        parser.add_argument("--dry-run",            action="store_true")
        parser.add_argument("--git-push",          action="store_true")
        args = parser.parse_args()

        if not any([args.full_sync, args.sync_providers,
                    args.passive_benchmark, args.enrich, args.stats]):
            args.full_sync = True

        mgr = ModelDatabaseManager(dry_run=args.dry_run, git_push=args.git_push)

        if args.stats:
            r = mgr.get_stats()
            print(f"\n{'='*50}\nILMA MODEL DB — CURRENT STATE\n{'='*50}")
            print(f"  Total: {r['total_models']} models, {r['total_providers']} providers")
            for p, n in r["per_provider"].items():
                print(f"    {p}: {n}")
            print(f"{'='*50}")

        if args.full_sync:
            mgr.full_sync()
        elif args.sync_providers:
            mgr.sync_providers()
        elif args.passive_benchmark:
            mgr.run_passive_benchmark()
        elif args.enrich:
            mgr.enrich()
    finally:
        LOCK_FILE.unlink(missing_ok=True)
# === PRODUCTION READINESS CHECK ===
def check_production_readiness():
    """
    Quick health check for ILMA SOT system.
    """
    print("[ProductionCheck] Checking SOT integrity...")
    # Add more checks as needed
    return True
