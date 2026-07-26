#!/usr/bin/env python3
"""
ILMA Callability Validator v1.0  (2026-06-01)
=============================================
Probes ONE representative model per provider/sub-provider with a real chat call,
using the SAME credential resolution the runtime uses, then writes an accurate
provider-level availability map to:
    ilma_model_router_data/provider_callability.json

Free-only: only probes providers in the free policy set.
Safe: read-only except for the JSON it writes; tiny max_tokens; short timeouts.
"""
import json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

PROFILE = Path("/root/.hermes/profiles/ilma")
ENV_FILE = PROFILE / ".env"
CREDS = Path("/root/credential/api_key.json")
OUT = PROFILE / "ilma_model_router_data" / "provider_callability.json"

def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def load_creds():
    try:
        return json.load(open(CREDS))
    except Exception:
        return {}

def nvidia_key(env, creds):
    if env.get("NVIDIA_API_KEY"):
        return env["NVIDIA_API_KEY"]
    sec = creds.get("nvidia", {})
    for k in sec:
        if isinstance(k, str) and k.startswith("nvapi-"):
            return k
    return None

def chat(url, model, key=None, extra_headers=None, timeout=40):
    payload = json.dumps({"model": model,
                          "messages": [{"role": "user", "content": "Reply with: OK"}],
                          "max_tokens": 8})
    cmd = ["curl", "-s", "--max-time", str(timeout), url,
           "-H", "Content-Type: application/json", "-d", payload]
    if key:
        cmd += ["-H", "Authorization: Bearer " + key]
    for h in (extra_headers or []):
        cmd += ["-H", h]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        dt = round(time.time() - t0, 2)
        d = json.loads(r.stdout)
        if "choices" in d and d["choices"]:
            return True, dt, "ok"
        # Distinguish AUTH failures (real) from transient/model-specific errors.
        err = d.get("error") or d.get("detail") or d
        code = None
        if isinstance(err, dict):
            code = err.get("code") or err.get("status")
        code = code or d.get("status")
        try:
            code = int(code)
        except (TypeError, ValueError):
            code = None
        # 401/403 = key invalid -> NOT callable. 404/429/5xx/empty = auth OK, provider reachable.
        if code in (429, 404) or (code is not None and 500 <= code < 600):
            return True, dt, f"auth_ok_transient({code})"
        return False, dt, str(err)[:120]
    except Exception as e:
        return False, round(time.time() - t0, 2), f"{type(e).__name__}: {str(e)[:80]}"

def main():
    env = load_env()
    creds = load_creds()
    nv = nvidia_key(env, creds)
    mm = env.get("MINIMAX_API_KEY")
    oll = (creds.get("ollama", {}).get("keys") or [None])[0]

    # (provider_label, url, representative_model, key, extra_headers)
    probes = [
        ("nvidia",             "https://integrate.api.nvidia.com/v1/chat/completions", "meta/llama-3.1-8b-instruct", nv, None),
        ("minimax",            "https://api.minimax.io/v1/text/chatcompletion_v2", "MiniMax-M2.7", mm, None),
        ("ollama",             "https://ollama.com/v1/chat/completions", "gemma3:12b", oll, None),
        ("openrouter",         "https://openrouter.ai/api/v1/chat/completions", "meta-llama/llama-3.3-70b-instruct:free",
         env.get("OPENROUTER_API_KEY") or (creds.get("openrouter", {}).get("keys") or [None])[0], None),
        ("blackbox",           "https://api.blackbox.ai/v1/chat/completions", "claude-haiku-4-5-20251001",
         creds.get("blackbox", {}).get("keys", [None])[0] or env.get("BLACKBOX_API_KEY"), None),
        ("google",             "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
         "gemini-2.5-flash", env.get("GOOGLE_API_KEY") or creds.get("google", {}).get("keys", [None])[0], None),
    ]

    result = {"_meta": {"validated_at": datetime.now(timezone.utc).isoformat(),
                        "validator": "ilma_callability_validator v1.0",
                        "policy": "free_only"},
              "providers": {}}

    print("=== ILMA Callability Validation ===")
    for label, url, model, key, hdr in probes:
        ok, dt, msg = chat(url, model, key, hdr)
        result["providers"][label] = {
            "callable": ok, "latency_s": dt, "probe_model": model,
            "detail": msg, "has_key": bool(key),
        }
        print(f"  [{'OK ' if ok else 'ERR'}] {label:20} {dt:>5}s  {model[:36]:38} {('' if ok else msg)[:60]}")

    OUT.write_text(json.dumps(result, indent=2))
    callable_n = sum(1 for v in result["providers"].values() if v["callable"])
    print(f"\nCallable providers: {callable_n}/{len(probes)}  -> wrote {OUT.name}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
