#!/usr/bin/env python3
"""
ILMA DATABASE OPTIMIZER v3.0
===========================
Implements Steps 1-4 of the optimization plan.
Robust casting to avoid NoneType errors.
"""

import json
import requests
from pathlib import Path
from datetime import datetime

PROFILE_DIR = Path("/root/.hermes/profiles/ilma")
MASTER_DB_PATH = PROFILE_DIR / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"
AA_CACHE_PATH = PROFILE_DIR / "benchmark_aa_cache.json"

BENCHMARK_BASE = {
    "deepseek-r1": 80.0, "llama-3.1-405b": 85.0, "llama-3.1-70b": 75.0,
    "qwen-2.5-72b": 78.0, "minimax-m2-7": 50.0, "muse-spark": 52.0,
    "gemma-2-27b": 68.0, "mistral-large": 70.0,
}

CAPABILITY_MAP = {
    "coding": ["coder", "code", "programming", "starcoder", "deepseek-coder"],
    "reasoning": ["r1", "reasoning", "thinking", "think", "logic"],
    "research": ["research", "search", "deepsearch", "web"],
    "creative": ["creative", "muse", "poem", "story", "writing"],
    "long_doc": ["long", "1m", "128k", "context", "doc"],
    "quick_answer": ["small", "fast", "gemma-2b", "llama-8b", "4b"],
}

def fetch_openrouter_free():
    print("Fetching free models from OpenRouter...")
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
        if resp.status_code == 200:
            return [m for m in resp.json().get("data", []) 
                    if m.get("id", "").endswith(":free") or m.get("pricing", {}).get("prompt") == "0"]
    except Exception as e:
        print(f"OpenRouter fetch failed: {e}")
    return []

def load_json(path: Path):
    if not path.exists(): return {}
    try:
        with open(path, 'r') as f: return json.load(f)
    except: return {}

def optimize():
    db = load_json(MASTER_DB_PATH)
    aa_cache = load_json(AA_CACHE_PATH)
    if not db: db = {"version": "2.0", "providers": {}}

    or_models = fetch_openrouter_free()
    if or_models:
        if "openrouter" not in db["providers"]:
            db["providers"]["openrouter"] = {"name": "OpenRouter", "models": {}}
        or_prov = db["providers"]["openrouter"]
        for m in or_models:
            mid = m["id"]
            or_prov["models"][mid] = {
                "name": m.get("name"),
                "is_free": True,
                "context_window": m.get("context_length", 0) or 0,
                "benchmark_score": 0.0,
                "short_id": mid.split("/")[-1]
            }

    for prov_id, prov_data in db["providers"].items():
        models = prov_data.get("models", {})
        for mid, mdata in models.items():
            # Safe Benchmark Score
            score = 0.0
            for aa_key, aa_val in aa_cache.items():
                if mid.lower() in aa_key.lower() or aa_key.lower() in mid.lower():
                    score = aa_val.get("overall", aa_val.get("score", 0.0))
                    break
            if score == 0.0:
                for bk, bs in BENCHMARK_BASE.items():
                    if bk in mid.lower():
                        score = bs
                        break
            
            mdata["benchmark_score"] = float(score if score is not None else 0.0)

            # Safe Context Window
            ctx = mdata.get("context_window")
            mdata["context_window"] = int(ctx) if ctx is not None else 0

            # Safe Capabilities
            caps = [cap for cap, kws in CAPABILITY_MAP.items() if any(kw in mid.lower() for kw in kws)]
            mdata["capabilities"] = caps if caps else ["general"]
            
            base = float(mdata.get("benchmark_score", 0.0))
            mdata["scores"] = {
                "reasoning": base * 1.3 if "reasoning" in caps else base * 0.7,
                "coding": base * 1.2 if "coding" in caps else base * 0.8,
                "creative": base * 1.1 if "creative" in caps else base * 0.9,
                "general": base
            }
            mdata["capacity"] = "High" if mdata["context_window"] >= 128000 else "Medium"
            mdata["role"] = "Specialist" if len(caps) > 2 else "Generalist"

    db["last_updated"] = datetime.utcnow().isoformat() + "Z"
    MASTER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MASTER_DB_PATH, "w") as f:
        json.dump(db, f, indent=2)
    print(f"Optimization complete. DB saved to {MASTER_DB_PATH}")

if __name__ == "__main__":
    optimize()
