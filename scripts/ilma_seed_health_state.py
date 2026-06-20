#!/usr/bin/env python3
"""
ILMA Health State Seeder v1.0
=============================
Seeds ilma_provider_health_state.json dengan:
- All known providers initialized as healthy
- Key nvidia/openrouter/minimax models as available
- All known providers in PROVIDER_INTELLIGENCE_MASTER.json tracked

Run: python3 scripts/ilma_seed_health_state.py
Author: ILMA Core Team
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger("ILMA.HealthSeeder")

ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
PIM_PATH = ILMA_PROFILE / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"
HEALTH_PATH = ILMA_PROFILE / "ilma_provider_health_state.json"
BACKUP_HEALTH = ILMA_PROFILE / "ilma_provider_health_state.json.backup_seeder"

def load_pim_providers() -> dict:
    with open(PIM_PATH) as f:
        return json.load(f)

def create_health_state(pim: dict) -> dict:
    """Create comprehensive health state from PIM."""
    state = {
        "last_updated": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "models": {},
        "providers": {},
    }

    # Key models that should be pre-marked as available (high-quality free models)
    KEY_MODELS = {
        # NVIDIA free models (verified working)
        "nvidia/01-ai/yi-large": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        "nvidia/llama-3.2-90b-vision-instruct": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        "nvidia/deepseek-ai/deepseek-v4-flash": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        "nvidia/mistralai/mistral-large-3-675b-instruct-2512": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        "nvidia/meta/llama-3.3-70b-instruct": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        "nvidia/microsoft/phi-4-mini-instruct": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        # OpenRouter models
        "openrouter/deepseek/deepseek-v4-flash:free": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        "openrouter/nvidia/llama-3.3-70b-instruct:free": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        # Minimax models
        "minimax/MiniMax-M2.7": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        "minimax/MiniMax-M2.7-highspeed": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
        "minimax/MiniMax-M2.5": {"status": "available", "consecutive_failures": 0, "total_failures": 0},
    }

    # Add all free models from PIM as unknown (never tested)
    for pname, pdata in pim.get("providers", {}).items():
        for mid, mdata in pdata.get("models", {}).items():
            full_id = f"{pname}/{mid}".lower()
            if full_id in KEY_MODELS:
                m_state = KEY_MODELS[full_id]
            else:
                m_state = {
                    "status": "unknown",  # unknown = never tested, not unhealthy
                    "consecutive_failures": 0,
                    "total_failures": 0,
                }
            state["models"][full_id] = m_state

    # Provider-level health
    provider_defaults = {
        "nvidia":      {"status": "healthy", "available_models": 74, "total_free": 74},
        "openrouter":  {"status": "healthy", "available_models": 334, "total_free": 334},
        "minimax":     {"status": "healthy", "available_models": 7, "total_free": 7},
        "deepseek":    {"status": "healthy", "available_models": 22, "total_free": 22},
        "google":      {"status": "healthy", "available_models": 85, "total_free": 85},
        "alibaba":     {"status": "healthy", "available_models": 76, "total_free": 76},
        "meta":        {"status": "healthy", "available_models": 17, "total_free": 17},
        "mistral":     {"status": "healthy", "available_models": 31, "total_free": 31},
        "openai":      {"status": "healthy", "available_models": 155, "total_free": 155},
        "anthropic":   {"status": "healthy", "available_models": 27, "total_free": 27},
        "xai":         {"status": "healthy", "available_models": 7, "total_free": 7},
        "cohere":      {"status": "healthy", "available_models": 3, "total_free": 3},
        "ai21-labs":   {"status": "healthy", "available_models": 7, "total_free": 7},
        "amazon":      {"status": "healthy", "available_models": 14, "total_free": 14},
        "microsoft-azure": {"status": "healthy", "available_models": 4, "total_free": 4},
        "useai":       {"status": "healthy", "available_models": 22, "total_free": 22},
        "blackbox":    {"status": "degraded", "available_models": 0, "total_free": 135, "note": "blackbox is banned"},
        "ollama":      {"status": "unknown", "available_models": 3, "total_free": 3},
        "perplexity":  {"status": "degraded", "available_models": 0, "total_free": 0, "note": "perplexity banned (no free tier)"},
    }

    for pname, pdata in pim.get("providers", {}).items():
        if pname in provider_defaults:
            state["providers"][pname] = provider_defaults[pname].copy()
        else:
            state["providers"][pname] = {
                "status": "unknown",
                "available_models": len(pdata.get("models", {})),
                "total_free": sum(1 for m in pdata.get("models", {}).values() if m.get("is_free", False)),
            }
        # Add last_checked
        state["providers"][pname]["last_checked"] = datetime.utcnow().isoformat()

    return state

def main():
    logger.info("🚀 ILMA Health State Seeder starting...")

    # Load PIM
    logger.info("📂 Loading PIM...")
    pim = load_pim_providers()
    total_models = sum(len(p.get("models", {})) for p in pim.get("providers", {}).values())
    logger.info(f"   Found {len(pim.get('providers', {}))} providers, {total_models} models")

    # Backup existing health state
    if HEALTH_PATH.exists():
        import shutil
        logger.info(f"💾 Backing up existing health state to: {BACKUP_HEALTH}")
        shutil.copy(HEALTH_PATH, BACKUP_HEALTH)

    # Create new health state
    logger.info("🔧 Building health state from PIM...")
    state = create_health_state(pim)

    # Save
    logger.info(f"💾 Saving: {HEALTH_PATH}")
    with open(HEALTH_PATH, "w") as f:
        json.dump(state, f, indent=2)

    # Stats
    model_count = len(state["models"])
    provider_count = len(state["providers"])
    available = sum(1 for m in state["models"].values() if m.get("status") == "available")
    unknown = sum(1 for m in state["models"].values() if m.get("status") == "unknown")

    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ HEALTH STATE SEEDED")
    logger.info("=" * 60)
    logger.info(f"  Models tracked:    {model_count}")
    logger.info(f"  Available (pre-seeded): {available}")
    logger.info(f"  Unknown (untested): {unknown}")
    logger.info(f"  Providers tracked: {provider_count}")
    logger.info(f"  Health file: {HEALTH_PATH}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()