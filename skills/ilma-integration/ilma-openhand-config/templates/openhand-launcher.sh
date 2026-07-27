#!/usr/bin/env python3
"""openhand — OpenHand launcher with dynamic model discovery via wrapper-nous.

Mirrors Codex CLI: no static catalog; fetches live from wrapper-nous GET /v1/models.
  openhand --list-models                 # list live models
  openhand -m <slug> <args>             # use a specific model (validated)
  openhand <args>                        # default model (tencent/hy3:free)
  openhand --tui                         # TUI-style env injection (non-ACP)
Forwards remaining args to `openhands acp --override-with-envs` (proven env path).
"""
import os, sys, json, shutil, subprocess

WRAPPER_BASE = "http://127.0.0.1:9102/v1"   # VERIFY port before relying on this
WRAPPER_KEY = "wrapper-local-key"
SETTINGS = os.path.expanduser("~/.openhands/settings.json")
DEFAULT_MODEL = "tencent/hy3:free"

def fetch_models():
    try:
        out = subprocess.run(["curl","-s","-m","5",f"{WRAPPER_BASE}/models",
            "-H",f"Authorization: Bearer {WRAPPER_KEY}"], capture_output=True, text=True, timeout=8)
        return [m["slug"] for m in json.loads(out.stdout).get("data", [])]
    except Exception:
        return []

def list_models():
    models = fetch_models()
    if not models:
        print("! Gagal fetch dari wrapper-nous @", WRAPPER_BASE); return 1
    print(f"# Model dari wrapper-nous ({len(models)}):")
    for i, m in enumerate(models, 1):
        print(f"  {i:2}. {m}{' *' if m==DEFAULT_MODEL else ''}")
    print("\n* = default. Pakai: openhand -m <slug>")
    return 0

def update_settings(model_slug):
    try:
        cfg = json.load(open(SETTINGS)) if os.path.exists(SETTINGS) else {}
        cfg.setdefault("llm", {})
        cfg["llm"].update(model=f"openai/{model_slug}", base_url=WRAPPER_BASE, api_key=WRAPPER_KEY)
        json.dump(cfg, open(SETTINGS,"w"), indent=2)
        return True
    except Exception as e:
        print(f"! Gagal update {SETTINGS}: {e}", file=sys.stderr); return False

def resolve_model(arg):
    models = fetch_models()
    if arg:
        if models and arg not in models:
            print(f"! Model '{arg}' tidak ada di wrapper-nous.", file=sys.stderr)
            print("  Lihat: openhand --list-models", file=sys.stderr); return None
        return arg
    return DEFAULT_MODEL if DEFAULT_MODEL in models else (models[0] if models else DEFAULT_MODEL)

def main():
    argv = sys.argv[1:]; model=None; tui=False; list_only=False; rest=[]
    i=0
    while i < len(argv):
        a=argv[i]
        if a=="--list-models": list_only=True; i+=1
        elif a=="--tui": tui=True; i+=1
        elif a in ("-m","--model"): model=argv[i+1]; i+=2
        elif a.startswith("--model="): model=a.split("=",1)[1]; i+=1
        else: rest.append(a); i+=1
    if list_only: return list_models()
    model = resolve_model(model)
    if model is None: return 2
    update_settings(model)
    env = os.environ.copy()
    env.update(LLM_MODEL=f"openai/{model}", LLM_BASE_URL=WRAPPER_BASE,
               LLM_API_KEY=WRAPPER_KEY, OPENHANDS_SUPPRESS_BANNER="1")
    bin_ = shutil.which("openhands") or "/root/.local/bin/openhands"
    cmd = [bin_, "acp", "--override-with-envs"] + rest if not tui else [bin_] + rest
    print(f"[openhand] {'ACP' if not tui else 'TUI'} -> model=openai/{model} backend=wrapper-nous:9102")
    return subprocess.call(cmd, env=env)

if __name__ == "__main__":
    sys.exit(main())
