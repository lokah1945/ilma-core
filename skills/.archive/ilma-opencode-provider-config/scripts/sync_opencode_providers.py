#!/usr/bin/env python3
"""Sync all /root/wrapper LLM proxies into OpenCode as custom providers.

Usage:
    python3 sync_opencode_providers.py

Fetches GET /v1/models from each live wrapper, ensures the
@ai-sdk/openai-compatible npm dep is installed, and writes
~/.config/opencode/opencode.jsonc with every model listed (OpenCode does
NOT auto-fetch models for custom providers).

Run this after any wrapper pull/restart to keep the model list in sync.
"""
import json
import os
import subprocess
import urllib.request

OC_CONFIG_DIR = os.path.expanduser("~/.config/opencode")
OC_JSONC = os.path.join(OC_CONFIG_DIR, "opencode.jsonc")
API_KEY = "wrapper-local-key"

# (provider_key, display_name, port, context_limit, output_limit)
WRAPPERS = [
    ("wrapper-nvidia",   "Wrapper NVIDIA (NIM)",        9101, 30000,  4096),
    ("wrapper-nous",     "Wrapper Nous (free)",         9102, 200000, 8192),
    ("wrapper-opencode", "Wrapper OpenCode Zen (free)", 9103, 200000, 8192),
    ("wrapper-blackbox", "Wrapper BlackBox (free)",     9104, 200000, 8192),
    ("wrapper-vercel",   "Wrapper Vercel (free)",       9105, 200000, 8192),
]


def fetch_models(port: int):
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/models",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
        return [m["id"] for m in data.get("data", [])]
    except Exception as e:
        print(f"  WARN port {port}: {e}")
        return []


def ensure_npm_dep():
    node_modules = os.path.join(OC_CONFIG_DIR, "node_modules", "@ai-sdk", "openai-compatible")
    if os.path.isdir(node_modules):
        print("npm dep @ai-sdk/openai-compatible: present")
        return
    print("installing @ai-sdk/openai-compatible ...")
    subprocess.run(["npm", "install", "@ai-sdk/openai-compatible"],
                   cwd=OC_CONFIG_DIR, check=True)


def main():
    ensure_npm_dep()
    provider_cfg = {}
    total = 0
    for key, display, port, ctx, out in WRAPPERS:
        ids = fetch_models(port)
        models = {
            mid: {"name": mid, "limit": {"context": ctx, "output": out}}
            for mid in ids
        }
        provider_cfg[key] = {
            "npm": "@ai-sdk/openai-compatible",
            "name": display,
            "options": {
                "baseURL": f"http://localhost:{port}/v1",
                "apiKey": API_KEY,
            },
            "models": models,
        }
        print(f"  {key}: {len(ids)} models")
        total += len(ids)

    config = {"$schema": "https://opencode.ai/config.json", "provider": provider_cfg}
    text = json.dumps(config, indent=2)
    header = (
        '{\n'
        '  "$schema": "https://opencode.ai/config.json",\n'
        '  // ILMA-managed: all /root/wrapper LLM proxies as custom OpenAI-compatible providers.\n'
        '  // Auth: Bearer wrapper-local-key. Models synced by sync_opencode_providers.py.\n'
    )
    with open(OC_JSONC, "w") as f:
        f.write(header + text[1:])
    print(f"WROTE {OC_JSONC} ({len(provider_cfg)} providers, {total} models)")


if __name__ == "__main__":
    main()
