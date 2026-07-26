#!/usr/bin/env python3
"""
probe_all_providers.py — Re-probe every AI/LLM provider in api_key.json against
the endpoints configured in ilma_model_db_manager.py.

Use this script when:
- A sync run reports a provider failure and you need to distinguish
  endpoint wrong / auth wrong / key invalid / CF block / quota / no key
- You're about to claim a provider is "down" and need ground truth
- You've changed a key or endpoint and need to verify the fix

Output: a table per provider showing current URL, key presence,
        HTTP status, and a one-line diagnosis.

Usage:
    python3 scripts/probe_all_providers.py
    python3 scripts/probe_all_providers.py --provider alibaba
    python3 scripts/probe_all_providers.py --json
    python3 scripts/probe_all_providers.py --all-surfaces   # also probes anthropic-compat

Display-masking note (2026-06-09 pitfall 75): this script uses binary reads to
extract keys, so the keys you see in the script's diagnostic output ARE the
real strings (not Python-display-masked). But if you read api_key.json with
print() or read_file, the middle of any key will be hidden. Trust the
provider API response, not the visual string.
"""

import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple

CREDS_FILE = Path("/root/credential/api_key.json")
MANAGER_FILE = Path("/root/.hermes/profiles/ilma/scripts/ilma_model_db_manager.py")


def get_key(creds: dict, provider: str) -> Optional[str]:
    """Match _get_api_key() in ilma_model_db_manager.py — Shape A/B/C."""
    section = creds.get(provider, {})
    if not isinstance(section, dict):
        return None
    # Shape A: explicit keys list
    keys = section.get("keys", [])
    if keys and isinstance(keys, list):
        return keys[0]
    # Shape B: NVIDIA-style — key is dict key (e.g. 'nvapi-...')
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
    return None


def extract_provider_configs() -> dict:
    """Parse PROVIDER_CONFIGS from ilma_model_db_manager.py."""
    if not MANAGER_FILE.exists():
        return {}
    content = MANAGER_FILE.read_text()
    configs = {}
    # Match: "name": {"url": "...", "fmt": "...", ...}
    pattern = re.compile(
        r'"([a-z_]+)":\s*\{\s*"url":\s*"([^"]+)"[^}]*"fmt":\s*"([^"]+)"'
    )
    for m in pattern.finditer(content):
        configs[m.group(1)] = {"url": m.group(2), "fmt": m.group(3)}
    return configs


def probe(url: str, key: Optional[str], fmt: str = "openai", timeout: int = 15) -> Tuple[str, Optional[int], str]:
    """Probe a provider endpoint. Returns (status_symbol, http_code, message)."""
    try:
        req = urllib.request.Request(url)
        if fmt == "google":
            # Google AI Studio: API key in header, not Bearer
            if key:
                req.add_header("x-goog-api-key", key)
        elif fmt == "minimax-anthropic":
            # minimax Anthropic-compatible surface uses X-Api-Key, not Bearer
            if key:
                req.add_header("X-Api-Key", key)
        elif key and key != "dummy":
            req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            if "data" in data and isinstance(data["data"], list):
                return ("✅", resp.status, f"{len(data['data'])} models")
            if "models" in data and isinstance(data["models"], list):
                return ("✅", resp.status, f"{len(data['models'])} models")
            return ("✅", resp.status, f"keys: {list(data.keys())[:5]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200].replace("\n", " ")
        # Distinguish CF block from auth failure
        if "Error 1010" in body or "Access denied" in body or "blocked your IP" in body:
            return ("🚫", e.code, f"CF 1010 IP-blocked")
        if "quota" in body.lower() or "insufficient_quota" in body:
            return ("💳", e.code, f"quota exhausted")
        if "Incorrect API key" in body or "login fail" in body or "invalid_api_key" in body:
            return ("🔑", e.code, f"invalid key")
        return ("❌", e.code, body[:120])
    except Exception as e:
        return ("💥", None, f"{type(e).__name__}: {e}")


def diagnose(provider: str, key: Optional[str], cfg: dict, creds: dict) -> str:
    """One-line diagnosis for a provider."""
    if not creds.get(provider):
        return "not in registry"
    category = creds[provider].get("category", "?")
    if category != "AI/LLM":
        return f"non-AI/LLM ({category})"
    if not key:
        return "no key detected"
    if not cfg:
        return "no config in manager"
    url = cfg["url"]
    fmt = cfg["fmt"]
    symbol, code, msg = probe(url, key, fmt)
    return f"{symbol} HTTP {code} → {msg}  [{url}]"


def diagnose_minimax_anthropic(key: Optional[str]) -> str:
    """Probe minimax via Anthropic-compatible surface (X-Api-Key)."""
    if not key:
        return "no key"
    symbol, code, msg = probe(
        "https://api.minimax.io/anthropic/v1/models",
        key, fmt="minimax-anthropic"
    )
    return f"{symbol} HTTP {code} → {msg}"


def main():
    args = sys.argv[1:]
    target_provider = None
    json_output = False
    all_surfaces = False
    for i, a in enumerate(args):
        if a == "--provider" and i + 1 < len(args):
            target_provider = args[i + 1]
        elif a == "--json":
            json_output = True
        elif a == "--all-surfaces":
            all_surfaces = True

    if not CREDS_FILE.exists():
        print(f"❌ {CREDS_FILE} not found")
        sys.exit(1)
    if not MANAGER_FILE.exists():
        print(f"❌ {MANAGER_FILE} not found")
        sys.exit(1)

    creds = json.loads(CREDS_FILE.read_text())
    configs = extract_provider_configs()

    # Filter AI/LLM providers
    ai_providers = {
        pid: pdata for pid, pdata in creds.items()
        if isinstance(pdata, dict) and pdata.get("category") == "AI/LLM"
    }

    if target_provider:
        ai_providers = {target_provider: ai_providers.get(target_provider, {})}

    results = {}
    for pid in sorted(ai_providers.keys()):
        key = get_key(creds, pid)
        cfg = configs.get(pid, {})
        diag = diagnose(pid, key, cfg, creds)
        results[pid] = diag
        if not json_output:
            print(f"{pid:<14} {diag}")
            # Also probe anthropic surface for minimax
            if all_surfaces and pid == "minimax" and key:
                anth_diag = diagnose_minimax_anthropic(key)
                print(f"{'':<14} └─ anthropic: {anth_diag}")

    if json_output:
        print(json.dumps(results, indent=2))

    # Exit code: 0 if at least one provider works, 1 if all fail
    if any("✅" in v for v in results.values()):
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
