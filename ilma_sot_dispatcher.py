#!/usr/bin/env python3
"""
ilma_sot_dispatcher.py — ILMA SOT Capability Dispatcher (FREE-only semi-strict)
================================================================================

Bos 2026-06-21 directive:
  - ALL capability MUST go through SOT
  - ALL E2E capability routing is FREE-only (priority over PAID)
  - Allow soft fallback (`is_free=True` raw) for capability where SOT
    has not yet final-classified (e.g. image-generation currently 0
    strict FREE models — gap to be closed by SOT enrichment phase)

This is the SINGLE dispatch surface for runtime call sites (image_gen,
llm chat, tts, stt, embedding, rerank, video, music, etc.).

API:
  - sot_dispatch(capability, *, strict=False, allow_paid=False, prefer_score=True,
                 provider=None, quality=None)
      → returns {"provider", "model_id", "endpoint_type", "endpoint_path",
                 "input_modality", "output_modality", "free_signal",
                 "is_free_final", "policy_warning", "alternatives": [...]}
  - sot_dispatch.health()  → DB conn health snapshot
  - sot_dispatch.strict_free_only(capability) → "" | provider/model_id
        (FAST-PATH for call sites that want is_free_final=True only)

CLI test:
  python3 ilma_sot_dispatcher.py --capability image
  python3 ilma_sot_dispatcher.py --capability chat --strict
  python3 ilma_sot_dispatcher.py --health
"""
from __future__ import annotations
import os, sys, json, time, logging, argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

# local imports
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "sot" / "enrichment"))

try:
    from sot_free_model_picker import (
        pick_free_model, pick_free_models, assert_free_choice, get_picker
    )
except Exception as e:
    print(f"[FATAL] cannot import SOT picker: {e}", file=sys.stderr)
    raise

logger = logging.getLogger("ilma.sot.dispatcher")


def sot_dispatch(capability: str,
                 strict: bool = False,
                 allow_paid: bool = False,
                 prefer_score: bool = True,
                 provider: Optional[str] = None,
                 quality: Optional[str] = None,
                 k_alternatives: int = 5) -> Dict[str, Any]:
    """Single-call dispatcher. Returns chosen model + alternatives.

    Args:
      strict: only is_free_final=True & billing_class='free'.
      allow_paid: bypass FREE filter (NOT recommended for ILMA default).
      prefer_score: prefer higher score (else prefer raw free signal).
    """
    if allow_paid and not strict:
        # Allow paid → expand candidates
        p = get_picker()
        models = p.list_models(capability, k=k_alternatives + 1, strict=False,
                                provider=provider, quality=quality)
        # If user paid=True but FREE list short, walk within all candidates via SOT
        # (kept simple here; advanced selector below)
        if not models:
            return {"error": "no_model"}
    else:
        p = get_picker()
        models = p.list_models(capability, k=k_alternatives + 1, strict=strict,
                                provider=provider, quality=quality)

    if not models:
        return {
            "error": "no_free_model",
            "capability": capability,
            "strict": strict,
            "allow_paid": allow_paid,
            "hint": ("No FREE model found in SOT for this capability. "
                     "Either run `sot_billing_classify.py --full` to re-classify, "
                     "or set allow_paid=True (NOT ILMA default)."),
        }

    chosen = models[0]
    return {
        "provider": chosen["provider"],
        "model_id": chosen["model_id"],
        "endpoint_type": chosen["endpoint_type"],
        "endpoint_path": chosen["endpoint_path"],
        "input_modality": chosen["input_modality"],
        "output_modality": chosen["output_modality"],
        "quality_tier": chosen["quality_tier"],
        "is_free_final": chosen.get("is_free_final", False),
        "billing_class": chosen.get("billing_class"),
        "score": chosen.get("score"),
        "score_tier": chosen.get("score_tier"),
        "free_signal": chosen.get("free_tier_score"),
        "policy_warning": chosen.get("policy_warning"),
        "alternatives": models[1:k_alternatives + 1],
    }


def sot_dispatch_strict_free(capability: str) -> Dict[str, Any]:
    """STRICT FREE ONLY (no soft fallback). Returns error if no strict FREE
    candidate exists. Use in production paths with FREE strict policy."""
    p = get_picker()
    models = p.list_models(capability, k=1, strict=True)
    if not models:
        return {"error": "no_strict_free", "capability": capability}
    return models[0]


def health() -> Dict[str, Any]:
    """SOT connectivity + capability count snapshot."""
    db = get_db()
    try:
        # Optional ping (use client scope, not collection)
        from pymongo import MongoClient
        # Re-create a client-level scope to ping without picking collection
        from sot_free_model_picker import MONGO
        client = MongoClient(**MONGO)
        client.admin.command("ping")
        connected = True
    except Exception as e:
        connected = False
        return {"connected": False, "error": str(e)}
    models = db["models"]
    return {
        "connected": connected,
        "total_models": models.count_documents({}),
        "active_models": models.count_documents({"is_active": True}),
        "free_strict": models.count_documents({"is_free_final": True, "is_active": True}),
        "endpoint_types": {r["_id"]: r["n"] for r in
            models.aggregate(
                [{"$match": {"endpoint_type": {"$exists": True}, "is_active": True}},
                 {"$group": {"_id": "$endpoint_type", "n": {"$sum": 1}}},
                 {"$sort": {"n": -1}}])},
    }


def get_db():
    """Re-export from sot_free_model_picker for convenience.
    Returns pymongo Database object (already targeting `credentials`)."""
    from sot_free_model_picker import get_db as _get_db
    return _get_db()


# Attach convenience methods to the dispatch function object
# so callers can use: sot_dispatch.health(), sot_dispatch.strict_free_only(cap)
sot_dispatch.health = health              # type: ignore[attr-defined]
sot_dispatch.strict_free_only = sot_dispatch_strict_free  # type: ignore[attr-defined]
sot_dispatch.get_db = get_db            # type: ignore[attr-defined]


def get_capability_registry() -> Dict[str, Any]:
    """Return the unified capability registry from credentials._meta.

    Single source of truth for the 25 ILMA+Hermes capabilities — keys are
    primary_cap ids (chat, coding, image, tts, stt, embedding, vision, rerank,
    browser, etc.); values carry hermes-default, nous_subscription, ilma_layer,
    modality, sources, and a routable 'ilma_routes_via' hook.
    """
    return get_db()['_meta'].find_one({'_id': 'capability_registry'}) or {}


def lookup_models_by_hermes_cap(hermes_cap: str, strict: bool = True, limit: int = 10) -> list:
    """Find SOT models that satisfy a Hermes handle name (multi-cap aware).

    Args:
        hermes_cap: a Hermes handle from the registry, e.g.
            'vision_analyze', 'text_to_speech', 'image_generate',
            'llm.coding', 'memory_recall', 'vector_search'.
        strict:    limit to is_free_final=True (default True).
        limit:     max number of models to return (default 10).

    Notes:
        The hermes_caps field was added by the enrichment step on 2026-06-21;
        older models may be missing it. Those are excluded by this lookup.
    """
    q: Dict[str, Any] = {"hermes_caps": hermes_cap}
    if strict:
        q["is_free_final"] = True
    q["is_active"] = True
    cursor = get_db().models.find(q).limit(limit)
    out = []
    for d in cursor:
        out.append({
            "model_id": d["model_id"],
            "provider": d["provider"],
            "primary_cap": d.get("primary_cap"),
            "endpoint_type": d.get("endpoint_type"),
            "capabilities_v2": d.get("capabilities_v2", []),
            "hermes_caps": d.get("hermes_caps", []),
            "score": d.get("score"),
        })
    return out


sot_dispatch.get_capability_registry = get_capability_registry  # type: ignore[attr-defined]
sot_dispatch.lookup_models_by_hermes_cap = lookup_models_by_hermes_cap  # type: ignore[attr-defined]


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capability", help="capability to dispatch (chat, image, tts, ...)")
    ap.add_argument("--strict", action="store_true", help="only is_free_final=True")
    ap.add_argument("--allow-paid", action="store_true")
    ap.add_argument("--provider", default=None)
    ap.add_argument("--quality", default=None)
    ap.add_argument("--health", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.health:
        print(json.dumps(health(), indent=2, default=str))
        return

    if not args.capability:
        ap.error("Either --capability or --health required")

    result = sot_dispatch(args.capability, strict=args.strict,
                          allow_paid=args.allow_paid,
                          provider=args.provider, quality=args.quality)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
