#!/usr/bin/env python3
"""Regenerate ~/.config/opencode/opencode.jsonc with all /root/wrapper LLM proxies
as custom OpenAI-compatible providers.

- Scrapes live model lists from each wrapper's /v1/models (Bearer wrapper-local-key).
- Emits jsonc with one entry per wrapper, each containing the REQUIRED
  "npm": "@ai-sdk/openai-compatible" field and a manually-registered model list.

Idempotent: overwrites the provider block only. Run after any wrapper model change.

Usage:
  python3 scripts/build_oc_config.py
"""
import json
import urllib.request
import os

KEY = "wrapper-local-key"
CONFIG_DIR = os.path.expanduser("~/.config/opencode")
OUT = os.path.join(CONFIG_DIR, "opencode.jsonc")

WRAPPERS = {
    "wrapper-nvidia":   {"port": 9101, "display": "Wrapper NVIDIA (NIM)",        "ctx": 30000,  "out": 4096},
    "wrapper-nous":     {"port": 9102, "display": "Wrapper Nous (free)",         "ctx": 200000, "out": 8192},
    "wrapper-opencode": {"port": 9103, "display": "Wrapper OpenCode Zen (free)", "ctx": 200000, "out": 8192},
    "wrapper-blackbox": {"port": 9104, "display": "Wrapper BlackBox (free)",     "ctx": 200000, "out": 8192},
}


def fetch_models(port):
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/models",
            headers={"Authorization": f"Bearer {KEY}"},
        )
        data = json.load(urllib.request.urlopen(req, timeout=8))
        return [m["id"] for m in data.get("data", [])]
    except Exception as e:
        print(f"  WARN port {port}: {e}")
        return []


def models_block(ids, ctx, out):
    return {mid: {"name": mid, "limit": {"context": ctx, "output": out}} for mid in ids}


def main():
    provider_cfg = {}
    for name, meta in WRAPPERS.items():
        ids = fetch_models(meta["port"])
        provider_cfg[name] = {
            "npm": "@ai-sdk/openai-compatible",
            "name": meta["display"],
            "options": {
                "baseURL": f"http://localhost:{meta['port']}/v1",
                "apiKey": KEY,
            },
            "models": models_block(ids, meta["ctx"], meta["out"]),
        }
        print(f"  {name}: {len(ids)} models")

    provider_cfg["nous-portal"] = {
        "id": "nous",
        "name": "Nous Portal (cloud)",
        "options": {
            "baseURL": "https://inference-api.nousresearch.com/v1",
            "apiKey": "«redacted:sk-…»",
        },
        "models": {},
    }

    config = {"$schema": "https://opencode.ai/config.json", "provider": provider_cfg}
    text = json.dumps(config, indent=2)
    header = (
        '{\n'
        '  "$schema": "https://opencode.ai/config.json",\n'
        '  // ILMA-managed: all /root/wrapper LLM proxies as custom OpenAI-compatible providers.\n'
        '  // Auth: Bearer wrapper-local-key. Models synced from /v1/models by build_oc_config.py.\n'
    )
    final = header + text[1:]
    with open(OUT, "w") as f:
        f.write(final)
    print(f"WROTE {OUT} ({sum(len(v) for v in provider_cfg.values()) - 0} provider entries)")


if __name__ == "__main__":
    main()
