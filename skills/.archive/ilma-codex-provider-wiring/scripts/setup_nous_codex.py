#!/usr/bin/env python3
"""Regenerate ~/.codex/config.toml and model_catalog.json entry for Nous via local proxy.

Reads the live Nous OAuth token from Hermes auth.json (never printed),
writes /root/.codex/config.toml (pointing at the local proxy on :9191) and
clones a schema-complete entry into model_catalog.json.

Re-run after a long gap to resync the catalog; the proxy itself reads a
fresh token per request so it needs no restart on token expiry.
"""
import json
import os
import sys

AUTH = "/root/.hermes/profiles/ilma/auth.json"
CODEX_DIR = "/root/.codex"
CONFIG = os.path.join(CODEX_DIR, "config.toml")
CATALOG = os.path.join(CODEX_DIR, "model_catalog.json")
MODEL = "tencent/hy3:free"


def load_token():
    with open(AUTH) as f:
        d = json.load(f)
    n = d.get("providers", {}).get("nous", {})
    tok = n.get("access_token") or n.get("agent_key")
    if not tok:
        sys.exit("ERROR: no Nous access_token/agent_key found in auth.json")
    return tok


def write_config(tok):
    # Codex v0.144.5 only supports wire_api="responses"; Nous only has
    # chat/completions. Point Codex at the LOCAL proxy (nous_proxy.py :9191).
    lines = [
        f'model = "{MODEL}"',
        'model_reasoning_effort = "medium"',
        'model_provider = "nous"',
        f'model_catalog_json = "{CATALOG}"',
        'approvals_reviewer = "user"',
        "",
        '[model_providers.nous]',
        'name = "Nous Research (local proxy)"',
        'base_url = "http://127.0.0.1:9191"',
        'experimental_bearer_token = "sk-local-proxy"',
        'wire_api = "responses"',
        "",
        '[projects."/"]',
        'trust_level = "trusted"',
        "",
        '[projects."/root"]',
        'trust_level = "trusted"',
        "",
        '[projects."/tmp"]',
        'trust_level = "trusted"',
        "",
        "[tui.model_availability_nux]",
        f'"{MODEL}" = 4',
        "",
        "[notice]",
        "hide_full_access_warning = true",
        "",
    ]
    with open(CONFIG, "w") as f:
        f.write("\n".join(lines))
    print(f"WROTE {CONFIG}")


def update_catalog():
    with open(CATALOG) as f:
        cat = json.load(f)
    models = cat.get("models", [])
    models = [m for m in models if m.get("slug") != MODEL]
    template = dict(models[0]) if models else {}
    entry = dict(template)
    entry["slug"] = MODEL
    entry["display_name"] = "Tencent Hunyuan hy3 (Free) via Nous"
    entry["description"] = "Tencent Hunyuan hy3 free model via Nous Research inference portal."
    models.append(entry)
    cat["models"] = models
    with open(CATALOG, "w") as f:
        json.dump(cat, f, indent=2)
    print(f"UPDATED {CATALOG} (added slug {MODEL})")


if __name__ == "__main__":
    load_token()  # validate presence
    write_config(None)
    update_catalog()
    print("DONE. Codex targets Nous portal (model", MODEL, ") via local proxy :9191")
