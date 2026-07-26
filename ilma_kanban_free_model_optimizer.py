#!/usr/bin/env python3
"""
ilma_kanban_free_model_optimizer.py — ILMA Canonical Free Model Optimizer for Hermes Kanban Workers
====================================================================================================

SSS Tier — End-to-end FREE ONLY routing for all kanban workers.
All workers spawned by the ilma profile use ONLY free models (minimax, nvidia, openrouter, blackbox).

How it works:
1. ILMA Model Registry provides canonical FREE model pool (163 models)
2. This module exposes task-type → best FREE model mapping
3. Works with config.yaml model: + fallback_providers (no modification needed)
4. Can set HERMES_MODEL env var for workers that need explicit routing

Free providers:
  - minimax   : 6 FREE (M2.7, M2.5, M2.1, etc.)
  - nvidia    : 131 FREE (DeepSeek-R1, Llama, Qwen, etc.)
  - openrouter: 25 FREE (o3-mini-high, etc.)
  - blackbox  : 1 FREE (GPT-4o-mini)

Usage:
    from ilma_kanban_free_model_optimizer import get_best_free_for_task, sync_worker_model_env

    # Get best free model for a task type
    model_id = get_best_free_for_task("coding")  # nvidia/DeepSeek-R1

    # Sync env var for current process (for cron jobs, etc.)
    sync_worker_model_env()
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# ILMA Profile Paths
# ============================================================================

ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE_PATH", "/root/.hermes/profiles/ilma"))
DASHBOARD_DB = ILMA_PROFILE / "data/ilma_dashboard.db"
MASTER_JSON = ILMA_PROFILE / "ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json"

# ============================================================================
# Task Type → Model Mapping (canonical free models per task category)
# ============================================================================

# Primary model per task type (provider/model_id)
TASK_TYPE_PRIMARY: Dict[str, Tuple[str, str]] = {
    # Heavy reasoning / analysis
    "reasoning_xhigh":  ("nvidia",    "DeepSeek-R1"),
    "reasoning_high":   ("nvidia",    "DeepSeek-R1"),
    "research":        ("nvidia",    "DeepSeek-R1"),

    # Coding tasks
    "super_heavy":      ("nvidia",    "DeepSeek-R1"),
    "heavy_coding":     ("nvidia",    "qwen2.5-coder-32b-instruct"),
    "medium_coding":    ("nvidia",    "qwen2.5-coder-32b-instruct"),
    "fast_coding":     ("minimax",   "minimax-m2.7"),

    # General tasks
    "general":         ("minimax",   "minimax-m2.7"),
    "fast_tasks":      ("minimax",   "minimax-m2.7"),

    # Multimodal / vision — use nvidia's free vision models (openrouter gpt-4o-mini:free unavailable)
    "vision":          ("nvidia",   "llama-3.2-11b-vision-instruct"),

    # Writing / creative
    "writing":         ("minimax",   "minimax-m2.7"),

    # Default fallback
    "default":         ("minimax",   "minimax-m2.7"),
}

# Fallback chain per task type (in case primary fails)
TASK_TYPE_FALLBACKS: Dict[str, List[Tuple[str, str]]] = {
    "reasoning_xhigh":  [
        ("openrouter",  "openai/o3-mini-high:free"),
        ("minimax",     "minimax-m2.7"),
        ("openrouter",  "anthropic/claude-3.5-haiku:free"),
    ],
    "reasoning_high":   [
        ("openrouter",  "openai/o3-mini-high:free"),
        ("minimax",     "minimax-m2.7"),
    ],
    "research":        [
        ("openrouter",  "openai/o3-mini-high:free"),
        ("minimax",     "minimax-m2.7"),
    ],
    "super_heavy":      [
        ("openrouter",  "openai/o3-mini-high:free"),
        ("minimax",     "minimax-m2.7"),
    ],
    "heavy_coding":     [
        ("minimax",     "minimax-m2.7"),
        ("openrouter",  "openai/o3-mini-high:free"),
    ],
    "medium_coding":    [
        ("minimax",     "minimax-m2.7"),
        ("nvidia",      "Qwen2.5-Coder-32B"),
    ],
    "fast_coding":      [
        ("minimax",     "minimax-m2.7"),
    ],
    "general":          [
        ("nvidia",      "Qwen2.5-72B-Instruct"),
        ("minimax",     "minimax-m2.5"),
    ],
    "fast_tasks":       [
        ("minimax",     "minimax-m2.7"),
        ("minimax",     "minimax-m2.5"),
    ],
    "vision":           [
        ("openrouter",  "google/gemini-2.0-flash:free"),
        ("openrouter",  "openai/gpt-4o-mini:free"),
    ],
    "writing":          [
        ("minimax",     "minimax-m2.7"),
        ("minimax",     "minimax-m2.5"),
    ],
    "default":          [
        ("minimax",     "minimax-m2.7"),
        ("nvidia",      "Qwen2.5-72B-Instruct"),
    ],
}

# ============================================================================
# Cache (avoid DB hit every dispatch tick)
# ============================================================================

_cache: Dict[str, any] = {
    "last_sync": 0,
    "cache_ttl": 300,  # 5 minutes
    "model_by_provider": {},  # provider -> list of free model_ids
    "sync_verified": False,
}


def _get_dashboard_db() -> Optional[Path]:
    """Return path to ilma dashboard DB."""
    if DASHBOARD_DB.exists():
        return DASHBOARD_DB
    return None


def _sync_free_models_from_db() -> bool:
    """Sync free model list from ilma dashboard DB. Returns True if successful."""
    db_path = _get_dashboard_db()
    if not db_path:
        logger.warning("Dashboard DB not found at %s", DASHBOARD_DB)
        return False

    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("""
            SELECT provider, provider_model_id, free_or_paid
            FROM model_ids
            WHERE free_or_paid = 'FREE'
            ORDER BY provider, provider_model_id
        """)
        rows = c.fetchall()
        conn.close()

        by_provider: Dict[str, List[str]] = {}
        for provider, model_id, _ in rows:
            by_provider.setdefault(provider, []).append(model_id)

        _cache["model_by_provider"] = by_provider
        _cache["last_sync"] = time.time()
        _cache["sync_verified"] = True

        total = sum(len(v) for v in by_provider.values())
        logger.info("Synced %d FREE models from DB across %d providers", total, len(by_provider))
        return True
    except Exception as e:
        logger.error("Failed to sync free models from DB: %s", e)
        return False


def _is_model_free(provider: str, model_id: str) -> bool:
    """Check if a specific model is free (from cache or DB)."""
    # Check cache first
    now = time.time()
    if now - _cache["last_sync"] > _cache["cache_ttl"]:
        _sync_free_models_from_db()

    by_provider = _cache.get("model_by_provider", {})
    free_list = by_provider.get(provider, [])

    # DB stores full canonical IDs like "nvidia/DeepSeek-R1"
    # Normalize both to lowercase for comparison
    model_lower = model_id.lower()
    canonical_lower = f"{provider}/{model_id}".lower()

    for free_model in free_list:
        fl = free_model.lower()
        # Match: bare model_id, canonical form, or any case variation
        if model_lower in fl or fl in canonical_lower:
            return True

    return False


# ============================================================================
# Public API
# ============================================================================

def _router_pick(task_type: str):
    """Use the live ILMA router (callability + AA score, free-only) to pick a model.
    Returns 'provider/model_id' or None on any failure (router optional)."""
    try:
        import os, sys
        _d = os.path.dirname(__file__)
        if _d not in sys.path:
            sys.path.insert(0, _d)
        from ilma_model_router import ILMAUnifiedRouter
        r = ILMAUnifiedRouter(allow_paid=False)
        res = r.get_best_model(task_type, allow_paid=False)
        if res and res.get("is_free") and res.get("provider") and res.get("model_id"):
            return f"{res['provider']}/{res['model_id']}"
    except Exception:
        pass
    return None


def get_best_free_for_task(task_type: str) -> str:
    """
    Return canonical model_id for a task type.

    Priority: live router (callable + AA-scored, free-only)
              → TASK_TYPE_PRIMARY → TASK_TYPE_FALLBACKS → "minimax/minimax-m2.7"
    """
    # Priority 0 (2026-06-01): live router — callability-gated + score-ranked
    picked = _router_pick(task_type)
    if picked:
        return picked

    # Try primary
    if task_type in TASK_TYPE_PRIMARY:
        provider, model_id = TASK_TYPE_PRIMARY[task_type]
        canonical = f"{provider}/{model_id}"
        # Verify it's actually free
        if _is_model_free(provider, model_id):
            return canonical

    # Try fallbacks
    if task_type in TASK_TYPE_FALLBACKS:
        for provider, model_id in TASK_TYPE_FALLBACKS[task_type]:
            if _is_model_free(provider, model_id):
                return f"{provider}/{model_id}"

    # Universal fallback — always use minimax-m2.7 (verified free)
    return "minimax/minimax-m2.7"


def get_all_free_model_ids() -> List[str]:
    """Return all free model IDs as provider/model_id strings."""
    now = time.time()
    if now - _cache["last_sync"] > _cache["cache_ttl"]:
        _sync_free_models_from_db()

    result = []
    by_provider = _cache.get("model_by_provider", {})
    for provider, model_ids in by_provider.items():
        for model_id in model_ids:
            result.append(f"{provider}/{model_id}")
    return sorted(result)


def get_free_models_by_provider(provider: str) -> List[str]:
    """Return free model IDs for a specific provider."""
    now = time.time()
    if now - _cache["last_sync"] > _cache["cache_ttl"]:
        _sync_free_models_from_db()

    by_provider = _cache.get("model_by_provider", {})
    return by_provider.get(provider, [])


def get_fallback_chain(task_type: str) -> List[str]:
    """Return ordered fallback chain for a task type."""
    chain = []

    if task_type in TASK_TYPE_PRIMARY:
        provider, model_id = TASK_TYPE_PRIMARY[task_type]
        chain.append(f"{provider}/{model_id}")

    if task_type in TASK_TYPE_FALLBACKS:
        for provider, model_id in TASK_TYPE_FALLBACKS[task_type]:
            candidate = f"{provider}/{model_id}"
            if candidate not in chain:
                chain.append(candidate)

    # Always end with universal fallback
    universal = "minimax/minimax-m2.7"
    if universal not in chain:
        chain.append(universal)

    return chain


def sync_worker_model_env() -> None:
    """
    Sync free model list and set HERMES_MODEL env var for the current process.
    Use this in cron jobs / daemon loops to keep env fresh.
    """
    _sync_free_models_from_db()
    # Set HERMES_MODEL to best general model
    best = get_best_free_for_task("general")
    os.environ["HERMES_MODEL"] = best
    logger.info("Set HERMES_MODEL=%s", best)


def get_kanban_stats() -> Dict:
    """Return free model statistics for kanban workers."""
    now = time.time()
    if now - _cache["last_sync"] > _cache["cache_ttl"]:
        _sync_free_models_from_db()

    by_provider = _cache.get("model_by_provider", {})
    total = sum(len(v) for v in by_provider.values())

    return {
        "total_free_models": total,
        "by_provider": {p: len(models) for p, models in by_provider.items()},
        "last_sync_ts": _cache.get("last_sync", 0),
        "cache_ttl": _cache.get("cache_ttl", 300),
        "sync_verified": _cache.get("sync_verified", False),
        "default_model": "minimax/minimax-m2.7",
        "primary_models": TASK_TYPE_PRIMARY,
    }


def force_refresh() -> bool:
    """Force-refresh free model cache from DB. Returns success."""
    return _sync_free_models_from_db()


def get_model_for_task_body(task_body: str) -> str:
    """
    Infer task type from task body text, then return best free model.
    Simple heuristic-based routing.
    """
    body_lower = task_body.lower()

    # Coding
    if any(kw in body_lower for kw in ["code", "coding", "build", "debug", "fix bug", "function", "api", "endpoint", "frontend", "backend"]):
        if any(kw in body_lower for kw in ["heavy", "complex", "fullstack", "platform", "system"]):
            return get_best_free_for_task("heavy_coding")
        return get_best_free_for_task("medium_coding")

    # Research
    if any(kw in body_lower for kw in ["research", "riset", "analisis", "study", "paper", "akademik"]):
        return get_best_free_for_task("research")

    # Reasoning
    if any(kw in body_lower for kw in ["reasoning", "strategi", "planning", "analisis", "evaluasi"]):
        return get_best_free_for_task("reasoning_high")

    # Vision
    if any(kw in body_lower for kw in ["image", "screenshot", "visual", "foto", "gambar", "vision"]):
        return get_best_free_for_task("vision")

    # Writing
    if any(kw in body_lower for kw in ["write", "blog", "article", "document", "tulis", "artikel"]):
        return get_best_free_for_task("writing")

    # Fast task
    if any(kw in body_lower for kw in ["fast", "quick", "ringkas", "cepat", "simple"]):
        return get_best_free_for_task("fast_tasks")

    return get_best_free_for_task("default")


if __name__ == "__main__":
    # CLI test
    print("=== ILMA Kanban Free Model Optimizer ===")
    stats = get_kanban_stats()
    print(f"Total FREE models: {stats['total_free_models']}")
    for p, cnt in stats['by_provider'].items():
        print(f"  {p}: {cnt}")
    print(f"\nDefault model: {stats['default_model']}")
    print(f"\nTask type → Model mapping:")
    for tt, model in stats['primary_models'].items():
        print(f"  {tt}: {model}")