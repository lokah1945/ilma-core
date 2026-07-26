#!/usr/bin/env python3
"""
sot_free_model_picker.py — FREE-only SOT picker (single source of truth)
=========================================================================

Bos directive 2026-06-21:
  ALL capability wajib lewat SOT dan hanya gunakan model FREE
  (`is_free_final=True` atau `free_tier_score >= 0.7`).

This module is the SOT-backed FREE-only resolver used by image_gen, llm,
tts, stt, embedding, rerank, and capability dispatch in ilma_*.py.

API:
  - pick_free_model(capability=..., endpoint_type=None, prefer_score=True,
      provider=None, quality=None)
  - pick_free_models(capability=..., k=5, ...)
  - list_by_capability(capability=...)  → all matching free models
  - cache 60s (configurable)

Uses cached MongoDB collection `models` (provider/model_id/...).

CLI:
  python3 sot_free_model_picker.py --capability image
  python3 sot_free_model_picker.py --capability tts --k 5
  python3 sot_free_model_picker.py --capability image --provider together
"""
from __future__ import annotations
import os, re, sys, json, time, argparse, logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pymongo

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "orchestration"))
import sot_ops  # noqa: E402

logger = logging.getLogger("ilma.sot.free_picker")

DB_NAME = "credentials"
MONGO = dict(
    host="127.0.0.1", port=27017,
    username="ilma_sync",
    password=(__import__("os").environ.get("ILMA_MONGO_LOCAL_PASS")),
    authSource="admin", directConnection=True,
    serverSelectionTimeoutMS=5000,
)

# endpoint_type → (path, input_modality, output_modality) — single source so the
# derivable fields (endpoint_path/input_modality/output_modality) need not be stored.
_ENDPOINT_DERIVE = {
    "chat-completions":     ("/v1/chat/completions", "text", "text"),
    "image-generations":    ("/v1/images/generations", "text", "image"),
    "image-edits":          ("/v1/images/edits", "image+text", "image"),
    "video-generations":    ("/v1/video/generations", "text", "video"),
    "audio-speech":         ("/v1/audio/speech", "text", "audio"),
    "audio-transcriptions": ("/v1/audio/transcriptions", "audio", "text"),
    "embeddings":           ("/v1/embeddings", "text", "vector"),
    "rerank":               ("/v1/rerank", "text+text", "ordered"),
    "moderations":          ("/v1/moderations", "text", "boolean"),
}

# Capability → endpoint_type (matches sot_enrich_capabilities_v2)
_CAP_TO_ENDPOINT = {
    "chat": "chat-completions",
    "coding": "chat-completions",
    "reasoning": "chat-completions",
    "vision": "chat-completions",
    "image_understand": "chat-completions",
    "image": "image-generations",
    "image_edit": "image-edits",
    "video": "video-generations",
    "tts": "audio-speech",
    "stt": "audio-transcriptions",
    "music": "audio-speech",
    "embedding": "embeddings",
    "rerank": "rerank",
    "safety_filter": "moderations",
}


def _now():
    return datetime.now(timezone.utc)


def get_db():
    return pymongo.MongoClient(**MONGO)[DB_NAME]


# ── Query: free candidate for capability ──────────────────────────────────────
def _query_free(db, capability: str, provider: Optional[str] = None,
                endpoint_type: Optional[str] = None,
                quality: Optional[str] = None,
                k: int = 5, min_score: float = 1.0,
                strict: bool = False) -> List[Dict[str, Any]]:

    # Map capability → endpoint_type if not provided
    ep = endpoint_type or _CAP_TO_ENDPOINT.get(capability, "chat-completions")

    # SINGLE canonical billing field: `is_free` (the trap-safe verdict; free_tier +
    # is_free_final consolidated into it 2026-06-22). is_free alone is the free gate.
    q_or = {"is_free": True}
    base_q: Dict[str, Any] = {
        "is_active": True,
        "status": "active",
        "$and": [
            q_or,
            {"$or": [
                {"capabilities": capability},
                {"endpoint_type": ep},
            ]},
        ],
    }
    if provider:
        base_q["provider"] = provider
    if quality:
        base_q["quality_tier"] = quality

    cur = db.models.find(base_q).sort(
        [("score", -1), ("free_tier_score", -1), ("last_verified", -1)]
    ).limit(max(k * 4, 20))

    out: List[Dict[str, Any]] = []
    for d in cur:
        sc = d.get("score") or 0
        try:
            if float(sc) < min_score:
                continue
        except (TypeError, ValueError):
            pass
        out.append(d)
        if len(out) >= k:
            break
    return out


# ── Cached facade ────────────────────────────────────────────────────────────
class SOTFreePicker:
    """Singleton FREE picker with TTL cache."""

    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._cache: Dict[Tuple[Any, ...], Tuple[float, List[Dict[str, Any]]]] = {}

    def _cache_key(self, **kw) -> Tuple[Any, ...]:
        return tuple(sorted(kw.items()))

    def _get_cached(self, key) -> Optional[List[Dict[str, Any]]]:
        if key in self._cache:
            t, v = self._cache[key]
            if time.time() - t < self.ttl:
                return v
            self._cache.pop(key, None)
        return None

    def pick(self, capability: str, **filters) -> Dict[str, Any]:
        """Return ONE best free model (or {} if none)."""
        models = self.list_models(capability, k=1, **filters)
        if models:
            return models[0]
        return {}

    def list_models(self, capability: str, k: int = 5, strict: bool = False,
                    **filters) -> List[Dict[str, Any]]:
        """Return list of free-capable models.
        Free gate = single canonical is_free=True (free_tier/is_free_final consolidated).
        `strict` retained for API compat; is_free is already the trap-safe verdict."""
        key = self._cache_key(capability=capability, k=k, strict=strict, **filters)
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        db = get_db()
        try:
            results = _query_free(db, capability, k=k, strict=strict, **filters)
        except Exception as e:
            logger.error(f"SOT free query failed: {e}")
            results = []
        # Trim to dict essentials (not full BSON ObjectId)
        clean = []
        for d in results:
            clean.append({
                "provider": d.get("provider"),
                "model_id": d.get("model_id"),
                "endpoint_type": d.get("endpoint_type"),
                # derived from endpoint_type (fields dropped 2026-06-22 — fully determined)
                "endpoint_path": _ENDPOINT_DERIVE.get(d.get("endpoint_type"), (d.get("endpoint_path") or "/v1/chat/completions", "text", "text"))[0],
                "input_modality": _ENDPOINT_DERIVE.get(d.get("endpoint_type"), ("", "text", "text"))[1],
                "output_modality": _ENDPOINT_DERIVE.get(d.get("endpoint_type"), ("", "text", "text"))[2],
                "primary_cap": d.get("primary_cap"),
                "quality_tier": d.get("quality_tier"),
                "is_free_final": d.get("is_free"),  # back-compat alias → canonical is_free
                # derived from is_free_final (billing_class field dropped 2026-06-22)
                "billing_class": ("free" if d.get("is_free") else "paid"),
                "free_tier_score": d.get("free_tier_score"),
                "score": d.get("score"),
                "score_tier": d.get("score_tier"),
                "capabilities": d.get("capabilities"),
                # policy warning if model isn't strictly classified FREE
                "policy_warning": (None
                                   if d.get("is_free")
                                   else "soft_free_ungated_strict_required_for_production"),
            })
        self._cache[key] = (time.time(), clean)
        return clean


# Module-level singleton
_PICKER = None
def get_picker(ttl_seconds: int = 60) -> SOTFreePicker:
    global _PICKER
    if _PICKER is None:
        _PICKER = SOTFreePicker(ttl_seconds=ttl_seconds)
    return _PICKER


# ── Convenience functions (used directly from runtime) ──────────────────────
def pick_free_model(capability: str, provider: Optional[str] = None,
                    endpoint_type: Optional[str] = None,
                    quality: Optional[str] = None) -> Dict[str, Any]:
    p = get_picker()
    return p.pick(capability, provider=provider, endpoint_type=endpoint_type,
                  quality=quality)


def pick_free_models(capability: str, k: int = 5, **filters) -> List[Dict[str, Any]]:
    p = get_picker()
    return p.list_models(capability, k=k, **filters)


# ── Health gate (sanity: refuse to return paid when strict) ─────────────────
def assert_free_choice(model: Dict[str, Any], strict: bool = True) -> None:
    """Raise if model isn't FREE (use this guard at runtime call sites)."""
    if not model:
        raise RuntimeError("SOT FREE picker returned empty model — no provider met the FREE+capability filter")
    if strict and not (model.get("is_free") or
                       (model.get("free_tier_score") or 0) >= 0.7):
        raise RuntimeError(f"SOT FREE picker violated policy: {model.get('provider')}/{model.get('model_id')} is not FREE")


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capability", required=True)
    ap.add_argument("--provider", default=None)
    ap.add_argument("--quality", default=None)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--list-all", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.list_all:
        ms = pick_free_models(args.capability, k=20, provider=args.provider, quality=args.quality)
    else:
        m = pick_free_model(args.capability, provider=args.provider, quality=args.quality)
        ms = [m] if m else []
    print(json.dumps(ms, indent=2, default=str))
    print(f"\n[top-1={ms[0]['provider']}/{ms[0]['model_id']}]" if ms else "\n[no free model — try different filter]")


if __name__ == "__main__":
    main()
