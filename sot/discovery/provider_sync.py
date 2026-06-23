#!/usr/bin/env python3
"""
provider_sync.py — SOT Discovery Engine
Writes to: MongoDB credentials.models collection

Usage:
    python3 provider_sync.py                      # sync all providers
    python3 provider_sync.py --provider nvidia     # sync specific provider
    python3 provider_sync.py --dry-run             # preview only
    python3 provider_sync.py --stats               # show collection stats
"""

import os, sys, json, re, ssl
import pymongo
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ── MongoDB connection ────────────────────────────────────────────────────────
MONGO_HOST = "172.16.103.253"
MONGO_PORT = 27017
MONGO_USER = "quantumtraffic"
MONGO_PASS = (__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), ""))

def get_mongo_client():
    return pymongo.MongoClient(
        host=MONGO_HOST, port=MONGO_PORT,
        username=MONGO_USER, password=MONGO_PASS,
        authSource="admin", directConnection=True,
        serverSelectionTimeoutMS=10000
    )

def get_models_coll():
    return get_mongo_client()["credentials"]["models"]

def get_providers_coll():
    return get_mongo_client()["credentials"]["providers"]

def get_llm_providers_coll():
    return get_mongo_client()["credentials"]["llm_providers"]

def _get_audit_coll():
    return get_mongo_client()["credentials"]["model_audit_trail"]

# Re-export from orchestration/sot_ops (avoid duplicate logic)
_sot_ops_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "orchestration")
if _sot_ops_dir not in sys.path:
    sys.path.insert(0, _sot_ops_dir)
try:
    from sot_ops import generate_evidence_id  # type: ignore
except ImportError:
    # Fallback: minimal local evidence id (should not normally trigger)
    _evidence_counter = [0]
    def generate_evidence_id(code: str = "SYNC") -> str:
        _evidence_counter[0] += 1
        from datetime import datetime as _dt
        return f"ILMA-EVID-{_dt.now().strftime('%Y%m%d')}-{code}-{_evidence_counter[0]:05d}"

# ── Provider configs ──────────────────────────────────────────────────────────
PROVIDER_CONFIGS = {
  "openrouter": {
    "url": "https://openrouter.ai/api/v1/models",
    "env_var": "openrouter",
    "fmt": "openrouter-detail",
    "free_tier": False
  },
  "opencode": {
    "url": "https://opencode.ai/zen/go/v1/models",
    "env_var": "opencode",
    "fmt": "openai",
    "free_tier": False
  },
  "wrapper-nvidia": {
    # Bos 2026-06-19: nvidia consolidated behind local rate-limit proxy
    # (/root/wrapper/nvidia @ 127.0.0.1:9100). Real keys rotated internally;
    # llm_providers holds one dummy key. Same NIM model ids passed through.
    "url": "http://127.0.0.1:9100/v1/models",
    "env_var": "wrapper-nvidia",
    "fmt": "openai",
    "free_tier": True
  },
  "minimax": {
    "url": "https://api.minimax.io/v1/models",
    "env_var": "minimax",
    "fmt": "openai",
    "free_tier": True
  },
  "blackbox": {
    "url": "https://docs.blackbox.ai/api-reference/models/chat-pricing",
    "env_var": "blackbox",
    "fmt": "blackbox-docs",
    "free_tier": False,
    "skip_key": True
  },
  "ollama-cloud": {
    "url": "https://ollama.com/api/tags",
    "env_var": "ollama-cloud",
    "fmt": "ollama",
    "free_tier": True,
    "rename_note": "2026-06-19 Bos: was 'ollama' (http://localhost:11434/api/tags local-only). Renamed to ollama-cloud = cloud-only access. Local ollama removed."
  },
  "xai": {
    "url": "https://api.x.ai/v1/models",
    "env_var": "xai",
    "fmt": "openai",
    "free_tier": False
  },
  "openai": {
    "url": "https://api.openai.com/v1/models",
    "env_var": "openai",
    "fmt": "openai",
    "free_tier": False
  },
  "google": {
    "url": "https://generativelanguage.googleapis.com/v1beta/models",
    "env_var": "google",
    "fmt": "google",
    "free_tier": False
  },
  "alibaba": {
    "url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models",
    "env_var": "alibaba",
    "fmt": "openai",
    "free_tier": False
  },
  "groq": {
    "url": "https://api.groq.com/openai/v1/models",
    "env_var": "groq",
    "fmt": "openai",
    "free_tier": False
  },
  "together": {
    "url": "https://api.together.xyz/v1/models",
    "env_var": "together",
    "fmt": "openai",
    "free_tier": False
  },
  "cerebras": {
    "url": "https://api.cerebras.ai/v1/models",
    "env_var": "cerebras",
    "fmt": "openai",
    "free_tier": False
  },
  "nous": {
    "url": "https://inference-api.nousresearch.com/v1/models",
    "env_var": "nous",
    "fmt": "openai",
    "free_tier": False
  },
  "aimlapi": {
    "url": "https://api.aimlapi.com/v1/models",
    "env_var": "aimlapi",
    "fmt": "openai",
    "free_tier": False
  },
  "byteplus": {
    "url": "https://ark.ap-southeast.bytepluses.com/api/v3/models",
    "env_var": "byteplus",
    "fmt": "openai",
    "free_tier": False
  },
  "bytez": {
    "url": "https://api.bytez.com/v1/models",
    "env_var": "bytez",
    "fmt": "openai",
    "free_tier": False
  },
  "felo": {
    "url": "https://openapi.felo.ai/v1/models",
    "env_var": "felo",
    "fmt": "openai",
    "free_tier": False,
    "url_source_comment": "2026-06-19: openapi.felo.ai returns 500 SERVER_ERROR; api.felo.ai rejects key as 401 Unauthorized. Provider non-functional. Key valid di subdomain openapi tapi server broken. Pipeline tidak bisa fix; butuh key baru atau server diperbaiki owner.",
    "skip_if_broken": True
  },
  "tinyfish": {
    "url": "https://api.tinyfish.ai/v1/models",
    "env_var": "tinyfish",
    "fmt": "openai",
    "free_tier": True
  },
  "sumopod": {
    "url": "https://api.sumopod.com/v1/models",
    "env_var": "sumopod",
    "fmt": "openai",
    "free_tier": True
  },
  "z.ai": {
    "url": "https://api.z.ai/v1/models",
    "env_var": "z.ai",
    "fmt": "openai",
    "free_tier": True,
    "added_note": "2026-06-23 Bos direct insert at z.ai. Endpoint TBD pending probe; format guessed openai-compatible."
  },
  "cloudflare": {
    "url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search",
    "fmt": "unsupported",
    "skip_sync": True
  },
  "artificial_analysis": {
    "url": "https://artificialanalysis.ai/",
    "fmt": "unsupported",
    "skip_sync": True
  }
}

# ── Capability inference ──────────────────────────────────────────────────────
_CAPABILITY_PATTERNS = [('code', ['coder', 'code', 'coding', 'dev', 'starcoder', 'codegemma', 'qwen-coder', 'deepseek-coder', 'llmcode']), ('reasoning', ['think', 'reason', 'o1', 'o3', 'o4-mini', 'qwq', 'grok-think', 'thinking', 'deepseek-r1', 'r1-', 'qwen3-reason']), ('vision', ['vl-', 'vision', 'multimodal', 'qvq', 'glm-v', 'gemini-pro-vis', 'llava', 'qwen-vl', 'deepseek-vl']), ('fast', ['flash', 'fast', 'tiny', 'mini', 'nano', 'small', 'lite', 'quick', 'speed']), ('instruct', ['instruct', 'chat', 'assistant', 'llm'])]
_SPECIALIZATION_PATTERNS = [('coding', ['coder', 'code', 'coding', 'starcoder', 'codegemma', 'deepseek-coder', 'qwen-coder', 'granite-code']), ('reasoning', ['think', 'reason', 'o1', 'o3', 'qwq', 'deepseek-r1', 'qwen3-reason', 'r1-', 'grok-think']), ('vision', ['vl-', 'vision', 'multimodal', 'qvq', 'glm-v', 'gemini-pro-vis', 'llava', 'qwen-vl']), ('instruct', ['instruct', 'chat', 'assistant']), ('fast', ['flash', 'fast', 'lite', 'quick'])]

def infer_capabilities(model_id: str) -> List[str]:
    caps = set()
    mid = model_id.lower()
    for cap, pats in _CAPABILITY_PATTERNS:
        if any(p in mid for p in pats):
            caps.add(cap)
    return sorted(caps)

def infer_specialization(model_id: str) -> Optional[str]:
    mid = model_id.lower()
    for spec, pats in _SPECIALIZATION_PATTERNS:
        if any(p in mid for p in pats):
            return spec
    return "general"

# ── Credential reader (api_key.json) ─────────────────────────────────────────
# FIX 2026-06-17: real file lives at /root/credential/api_key.json, not under profile dir
CREDS_FILE = "/root/credential/api_key.json"

def get_api_key(provider: str, purpose: str = "provisioning") -> Optional[str]:
    """Get API key from MongoDB llm_providers (PRIMARY) or api_key.json (fallback).

    `purpose` selects which key to use:
    - "provisioning" — for listing/management endpoints (default for sync/audit)
    - "inference"    — for actual model invocation
    - "primary" / "secondary" / "experimental" — paralel keys for capacity

    CRITICAL: Multi-purpose providers (notably openrouter) have separate keys for
    these surfaces. Openrouter `/api/v1/models` (listing) and `/api/v1/chat/...`
    (call) accept different keys. Using the wrong key surfaces wrong data or auth
    errors. Pass `purpose="provisioning"` for listing, `purpose="inference"` for
    invocation. Falls back to first VALID/UNVERIFIED key if requested purpose missing.
    """
    try:
        coll = get_llm_providers_coll()
        # First try: exact purpose match
        doc = coll.find_one({
            "provider": provider,
            "key_purpose": purpose,
            "api_key": {"$exists": True, "$nin": [None, ""]},  # FIX audit C2: dup $ne keys collapsed in dict
        })
        if doc and doc.get("api_key"):
            key = doc["api_key"]
            if len(key) > 5:
                return key
        # Fallback: any VALID/UNVERIFIED key
        for d in coll.find({"provider": provider, "key_purpose": {"$ne": purpose}}):
            if d.get("api_key") and d.get("key_status") in {"VALID", "UNVERIFIED"}:
                if len(d["api_key"]) > 5:
                    return d["api_key"]
        # Last resort: any key
        doc = coll.find_one({"provider": provider})
        if doc and doc.get("api_key"):
            key = doc["api_key"]
            if len(key) > 5:
                return key
    except Exception:
        pass
    # Fallback to api_key.json
    if not os.path.exists(CREDS_FILE):
        return None
    try:
        with open(CREDS_FILE) as f:
            creds = json.load(f)
        section = creds.get("llm", {}).get(provider, {})
        keys = section.get("keys", [])
        return keys[0].get("key") if keys else None
    except Exception:
        return None

# ── URL drift fix: use base_url_actual from providers (Tier-2) ───────────────
# FIX 2026-06-19 (audit H2): base_url_actual moved out of llm_providers (Tier-1 is
# now a 9-field credential store). Read the optional drift-override from providers
# (Tier-2). NOTE: only an explicit *listing-endpoint* override field is honored —
# providers.base_url is the API root (e.g. .../v1), NOT the /v1/models path that
# PROVIDER_CONFIGS holds, so we must not blindly override URLs with it.
_URL_OVERRIDES: Dict[str, str] = {}

def _load_url_overrides():
    try:
        coll = get_providers_coll()
        for doc in coll.find({}):
            actual = doc.get("base_url_actual") or doc.get("models_url_override")
            if actual:
                _URL_OVERRIDES[doc["provider"]] = actual
    except Exception as e:
        print(f"[WARN] Could not load URL overrides: {e}")

# ── SOT provider meta lookup (free_tier, payload_format, status) ──────────────
# FIX 2026-06-19 (audit C-3): free_tier should propagate from llm_providers (SOT),
# not be hardcoded in PROVIDER_CONFIGS. status comes from SOT so downstream can cascade.

def get_provider_meta(pname: str) -> Dict[str, Any]:
    """Read provider meta from llm_providers (SOT) as the authoritative source.
    Returns: free_tier (bool), key_count (int), act_key_count (int),
    multi_account (bool), aggregate_status (str).
    Falls back to PROVIDER_CONFIGS if SOT unavailable.
    """
    meta = {"free_bypass": False,  # provider-level free override (T1 free_bypass)
            "key_count": 0,
            "act_key_count": 0,
            "multi_account": False,
            "aggregate_status": "unknown"}
    try:
        coll = get_llm_providers_coll()
        sibs = list(coll.find({"provider": pname}))
        if not sibs:
            return meta
        meta["key_count"] = len(sibs)
        act_keys = [s for s in sibs if s.get("key_status") in {"VALID", "UNVERIFIED"}
                    and s.get("api_key")]
        meta["act_key_count"] = len(act_keys)
        meta["multi_account"] = len(sibs) > 1
        meta["aggregate_status"] = "active" if act_keys else "INVALID"
        # free_bypass (T1 llm_providers) is the single provider-level free control
        # (consolidated 2026-06-23; replaced the legacy provider-tier free_tier flag).
        meta["free_bypass"] = any(bool(s.get("free_bypass")) for s in sibs)
    except Exception:
        pass
    return meta

def get_provider_url(pname: str) -> str:
    return _URL_OVERRIDES.get(pname, PROVIDER_CONFIGS.get(pname, {}).get("url", ""))

# ── Model fetcher ─────────────────────────────────────────────────────────────
_SSL_CTX = ssl.create_default_context()

def fetch_models(pname: str) -> List[Any]:
    cfg = PROVIDER_CONFIGS.get(pname, {})
    url = get_provider_url(pname) or cfg.get("url", "")
    key = get_api_key(pname) if not cfg.get("skip_key") else "dummy"
    fmt = cfg.get("fmt", "openai")
    
    if not url or cfg.get("skip_sync"):
        return []

    req = urllib.request.Request(url)
    if key and key != "dummy":
        # FIX 2026-06-19 (audit L3): honor providers (Tier-2) auth_format instead of
        # always sending Bearer. Conservative mapping — Bearer remains the default for
        # Bearer/JWT_Bearer/ApiKey/unknown (so currently-working syncs don't regress);
        # only the unambiguous header schemes are switched.
        auth_format = ""
        try:
            pdoc = get_providers_coll().find_one({"provider": pname}, {"auth_format": 1})
            auth_format = (pdoc or {}).get("auth_format", "") or ""
        except Exception:
            pass
        if fmt == "google":
            req.add_header("x-goog-api-key", key)
        elif auth_format == "ApiKey_Header":
            req.add_header("x-api-key", key)
        else:
            req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36")

    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            raw = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200]
        raise RuntimeError(f"HTTP {e.code}: {body}")

    if fmt == "openai":
        def _strip_prefix(model_id, p):
            # Some providers (notably NVIDIA NIM) return model IDs already
            # prefixed with the provider name (e.g. "nvidia/foo" for nvidia
            # provider). Strip the redundant prefix to keep (provider, model_id)
            # keys canonical.
            if not model_id:
                return model_id
            for prefix in (f"{p}/",):
                if model_id.startswith(prefix):
                    return model_id[len(prefix):]
            return model_id
        if isinstance(raw, list):
            return [{"id": _strip_prefix(m.get("id", m.get("name", "")), pname),
                     "provider": pname}
                    for m in raw if isinstance(m, dict) and (m.get("id") or m.get("name"))]
        return [{"id": _strip_prefix(m.get("id", ""), pname), "provider": pname}
                for m in raw.get("data", []) if m.get("id")]

    elif fmt == "openrouter-detail":
        result = []
        for m in raw.get("data", []):
            mid = m.get("id")
            if not mid:
                continue
            pricing = m.get("pricing", {})
            result.append({
                "id": mid, "provider": pname,
                "context_length": m.get("context_length"),
                "price_per_m_input": pricing.get("prompt"),
                "price_per_m_output": pricing.get("completion"),
                # models.free_tier DROPPED 2026-06-22 — billing collapsed to single is_free
                # (verdict written by sot_billing_classify). Raw price fields above are the
                # classifier's input; no per-model free_tier flag is stored anymore.
            })
        return result

    elif fmt == "ollama":
        return [{"id": m.get("name", ""), "provider": pname} for m in raw.get("models", []) if m.get("name")]

    elif fmt == "google":
        return [{"id": m.get("name", m.get("baseModelId", "")), "provider": pname} for m in raw.get("models", [])]

    elif fmt == "blackbox-docs":
        html = raw if isinstance(raw, str) else str(raw)
        result = []
        row_pat = re.compile(r"<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>.*?</tr>", re.DOTALL)
        free_pat = re.compile(r"^\$0\.00$", re.IGNORECASE)
        for m in row_pat.finditer(html):
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in m.groups()]
            mid = cells[1].strip()
            if not mid:
                continue
            is_free = cells[2].lower() == "free" or cells[3].lower() == "free" or bool(free_pat.match(cells[2])) or bool(free_pat.match(cells[3]))
            if is_free:
                result.append({"id": mid, "provider": pname, "free_tier": True})
        return result

    return []

# ── Sync one provider ────────────────────────────────────────────────────────
def sync_provider(pname: str, dry_run: bool = False) -> Dict[str, Any]:
    cfg = PROVIDER_CONFIGS.get(pname, {})
    if cfg.get("skip_sync"):
        return {"status": "skipped", "reason": "skip_sync=True"}

    if cfg.get("skip_key"):
        key = "dummy"
    else:
        key = get_api_key(pname)
        if not key:
            return {"status": "error", "reason": "no_api_key"}

    # Read SOT meta — status→models.status; provider free_bypass seeds is_free
    prov_meta = get_provider_meta(pname)
    sot_free_bypass = prov_meta.get("free_bypass", False)

    try:
        raw_models = fetch_models(pname)
    except Exception as e:
        return {"status": "error", "reason": str(e)[:100]}

    if not raw_models:
        return {"status": "warning", "reason": "no_models_found"}

    coll = get_models_coll()
    audit = _get_audit_coll()
    now = datetime.now(timezone.utc)
    added = 0
    updated = 0
    audit_events = []

    for m in raw_models:
        mid = m.get("id", "")
        if not mid:
            continue

        # seed is_free from provider free_bypass; sot_billing_classify writes the FINAL verdict
        is_free = bool(sot_free_bypass)

        doc = {
            "provider": pname,
            "model_id": mid,
            "model_name": mid,
            "context_window": m.get("context_length"),
            "price_per_m_input": m.get("price_per_m_input"),
            "price_per_m_output": m.get("price_per_m_output"),
            "is_free": is_free,
# free_tier dropped (consolidated to is_free; billing_classify owns the verdict)
            "is_active": True,
            "status": "active",
            # capabilities owned solely by sot_enrich_capabilities_v2 (single authority, #15 dedup 2026-06-23); provider_sync no longer infers a duplicate vocab.
            "specialization": infer_specialization(mid),
            "discovered_via": "provider_direct",
            "discovered_at": now,
            "refreshed_at": now,
            "raw_metadata": {k: v for k, v in m.items() if k not in ("id",)},
        }

        if dry_run:
            continue

        # Check if this is a new model or update
        existing = coll.find_one({"provider": pname, "model_id": mid})
        is_new = existing is None

        result = coll.update_one(
            {"provider": pname, "model_id": mid},
            {"$set": {**doc, "_sot_last_sync": now}},
            upsert=True
        )
        if result.upserted_id:
            added += 1
            audit_events.append({
                "provider": pname, "model_id": mid,
                "event_type": "model_discovered", "actor": "provider_sync",
                "source_collection": "models",
                "delta": {"new": True, "model_id": mid, "is_free": doc["is_free"], "specialization": doc["specialization"]}
            })
        elif result.modified_count > 0:
            updated += 1
            if is_new is False:
                audit_events.append({
                    "provider": pname, "model_id": mid,
                    "event_type": "model_updated", "actor": "provider_sync",
                    "source_collection": "models",
                    "delta": {"fields": [k for k in doc.keys() if existing.get(k) != doc[k] and k not in ("refreshed_at","_sot_last_sync","discovered_at","last_verified")]}
                })

    # Write audit batch (only non-empty)
    if audit_events and not dry_run:
        from datetime import timezone as _tz
        for ev in audit_events:
            eid = generate_evidence_id(code="SYNC")
            ev["event_at"] = datetime.now(_tz.utc)
            ev["evidence_id"] = eid
        try:
            audit.insert_many(audit_events, ordered=False)
        except Exception as e:
            print(f"  [WARN] audit insert: {e}")

    total = coll.count_documents({"provider": pname})
    return {
        "status": "success",
        "live": len(raw_models),
        # live_ids: the canonical model ids the provider currently serves. Used by the
        # auto-sync delta engine to prune models that vanished upstream (audit: berkurang).
        "live_ids": [m.get("id") for m in raw_models if m.get("id")],
        "added": added,
        "updated": updated,
        "total_in_db": total,
        "audit_events": len(audit_events),
    }

# ── Stats ────────────────────────────────────────────────────────────────────
def stats() -> Dict[str, Any]:
    coll = get_models_coll()
    total = coll.count_documents({})
    active = coll.count_documents({"is_active": True})
    by_provider = {}
    for doc in coll.aggregate([{"$group": {"_id": "$provider", "count": {"$sum": 1}, "active": {"$sum": {"$cond": ["$is_active", 1, 0]}}}}]):
        by_provider[doc["_id"]] = {"total": doc["count"], "active": doc["active"]}
    return {"total": total, "active": active, "by_provider": by_provider}

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", help="Sync specific provider only")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    _load_url_overrides()

    if args.stats:
        s = stats()
        print(f"\n=== models collection stats ===")
        print(f"  Total:  {s['total']}")
        print(f"  Active: {s['active']}")
        for p, d in sorted(s["by_provider"].items()):
            print(f"  {p}: {d['total']} total, {d['active']} active")
        return

    providers = [args.provider] if args.provider else [p for p in PROVIDER_CONFIGS if p not in ("cloudflare", "artificial_analysis")]

    print(f"[provider_sync] Syncing {len(providers)} providers (dry_run={args.dry_run})...")
    results = {}
    for pname in providers:
        r = sync_provider(pname, dry_run=args.dry_run)
        results[pname] = r
        status_map = {"success": "✅", "skipped": "⏭", "warning": "⚠", "error": "❌"}
        icon = status_map.get(r["status"], "?")
        if r["status"] == "success":
            print(f"  {icon} {pname}: {r['live']} live, +{r['added']} added, ~{r['updated']} updated (total: {r['total_in_db']})")
        else:
            print(f"  {icon} {pname}: {r.get('reason', r['status'])}")

    success = sum(1 for r in results.values() if r["status"] == "success")
    print(f"\nResult: {success}/{len(providers)} providers synced")

if __name__ == "__main__":
    main()
