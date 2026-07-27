#!/usr/bin/env python3
"""
openhand — OpenHand launcher dengan dynamic model discovery via wrapper-nous.

Mirip pola Codex CLI:
- TIDAK pakai static catalog; fetch live dari wrapper-nous GET /v1/models
- `openhand -m <slug>`          -> pakai model itu (slug dari /v1/models)
- `openhand` (tanpa -m)         -> pakai default (prioritas tinggi dari live list)
- `openhand --list-models`      -> enumerate model dari wrapper-nous
- `openhand --tui`              -> jalankan TUI OpenHand (env injection)
- `openhand ...`                -> forward ke `openhands acp --override-with-envs`

Backend: wrapper-nous @ http://127.0.0.1:9102/v1 (OpenAI Responses -> Nous Chat)

NOTE: manual sys.argv slicing (NOT argparse REMAINDER) so downstream flags like
`-t "task"` forward cleanly to openhands without "unrecognized arguments" errors.
"""
import os
import sys
import json
import shutil
import subprocess

WRAPPER_BASE = "http://127.0.0.1:9102/v1"
WRAPPER_KEY = "wrapper-local-key"
SETTINGS = os.path.expanduser("~/.openhands/settings.json")
DEFAULT_MODEL = "tencent/hy3:free"


def fetch_models():
    """Live fetch model list dari wrapper-nous (dynamic discovery)."""
    try:
        out = subprocess.run(
            ["curl", "-s", "-m", "5", f"{WRAPPER_BASE}/models",
             "-H", f"Authorization: Bearer {WRAPPER_KEY}"],
            capture_output=True, text=True, timeout=8
        )
        data = json.loads(out.stdout)
        return [m["slug"] for m in data.get("data", [])]
    except Exception:
        return []


def list_models():
    models = fetch_models()
    if not models:
        print("! Gagal fetch dari wrapper-nous @", WRAPPER_BASE)
        return 1
    print(f"# Model dari wrapper-nous ({len(models)}):")
    for i, m in enumerate(models, 1):
        mark = " *" if m == DEFAULT_MODEL else ""
        print(f"  {i:2}. {m}{mark}")
    print("\n* = default. Pakai: openhand -m <slug>")
    return 0


def update_settings(model_slug):
    """Tulis model ke settings.json agar mode serve/web/GUI ikut pakai."""
    try:
        cfg = {}
        if os.path.exists(SETTINGS):
            with open(SETTINGS) as f:
                cfg = json.load(f)
        cfg.setdefault("llm", {})
        cfg["llm"]["model"] = f"openai/{model_slug}"
        cfg["llm"]["base_url"] = WRAPPER_BASE
        cfg["llm"]["api_key"] = WRAPPER_KEY
        with open(SETTINGS, "w") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception as e:
        print(f"! Gagal update {SETTINGS}: {e}", file=sys.stderr)
        return False


def resolve_model(arg_model):
    """Tanpa -m -> ambil default dari live list (prioritas). Dengan -m -> validasi."""
    models = fetch_models()
    if arg_model:
        if models and arg_model not in models:
            print(f"! Model '{arg_model}' tidak ada di wrapper-nous.", file=sys.stderr)
            print("  Lihat: openhand --list-models", file=sys.stderr)
            return None
        return arg_model
    if DEFAULT_MODEL in models:
        return DEFAULT_MODEL
    return models[0] if models else DEFAULT_MODEL


def main():
    argv = sys.argv[1:]
    model = None
    tui = False
    list_only = False
    rest = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--list-models":
            list_only = True
            i += 1
        elif a == "--tui":
            tui = True
            i += 1
        elif a in ("-m", "--model"):
            model = argv[i + 1]
            i += 2
        elif a.startswith("--model="):
            model = a.split("=", 1)[1]
            i += 1
        else:
            rest.append(a)
            i += 1

    if list_only:
        return list_models()

    model = resolve_model(model)
    if model is None:
        return 2

    update_settings(model)

    env = os.environ.copy()
    env["LLM_MODEL"] = f"openai/{model}"
    env["LLM_BASE_URL"] = WRAPPER_BASE
    env["LLM_API_KEY"] = WRAPPER_KEY
    env["OPENHANDS_SUPPRESS_BANNER"] = "1"

    openhands_bin = shutil.which("openhands") or "/root/.local/bin/openhands"

    if tui:
        cmd = [openhands_bin] + rest
        print(f"[openhand] TUI -> model=openai/{model} backend=wrapper-nous:9102")
    else:
        cmd = [openhands_bin, "acp", "--override-with-envs"] + rest
        print(f"[openhand] ACP -> model=openai/{model} backend=wrapper-nous:9102")

    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    sys.exit(main())
