#!/usr/bin/env python3
"""
sot_enrich_capabilities_v2.py — Upgrade SOT capability detection (v2)
======================================================================

Bos directive 2026-06-21: need SOT yang LEBIH DETAIL dan tahu capability
setiap model secara komprehensif. v1 hanya regex model_id, ini v2:

NEW vs v1:
  • 30+ capabilities (was 8): chat, instruct, code, reasoning, vision,
    audio, image, video, embedding, rerank, tts, stt, transcription,
    translation, function_calling, tools, json_mode, streaming, safety,
    long_context, multimodal_input/output, image_edit, image_understand,
    fast/lite/quality, music, voice_cloning, etc.
  • Per-provider native metadata harvesting (where API exposes it)
  • Each model gets `endpoint_type` (chat | image | audio | video |
    embedding | rerank | transcription | tts) — runtime knows which
    base URL/payload shape to use
  • `endpoint_suggestion` per model (e.g. /v1/images/generations,
    /v1/audio/speech, /v1/embeddings)
  • Stronger FREE-tier enforcement — `is_free` plus predicted
    `free_tier_score` (0..1) per model (pricing-based)
  • `capabilities_detail` (router vocabulary) on each row, plus
    `primary_cap` (single most-important cap used for routing)
  • Confidently-surfaced modality (input/output)
  • Quality tier added to image / video / audio models (quality=high
    when name signals "ultra"/"pro"/"max"; quality=fast for "fast"/
    "lite"/"mini"; default=standard)

CLI:
  python3 sot_enrich_capabilities_v2.py --full
  python3 sot_enrich_capabilities_v2.py --provider xai --full
  python3 sot_enrich_capabilities_v2.py --dry-run --stats
  python3 sot_enrich_capabilities_v2.py --migrate  # write back to models

Idempotent — re-running only updates existing cols.
"""
from __future__ import annotations
import os, re, sys, json, time, argparse, logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import pymongo

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "orchestration"))
import sot_ops  # evidence_id, audit_coll  # noqa: E402

logger = logging.getLogger("ilma.sot.enrich_v2")

MONGO = dict(
    host="172.16.103.253", port=27017,
    username="quantumtraffic",
    password=(__import__("os").environ.get("ILMA_MONGO_PASS")
              or next((_l.split("=",1)[1].strip()
                       for _l in open("/root/.hermes/.env")
                       if _l.startswith("ILMA_MONGO_PASS=")), "")),
    authSource="admin", directConnection=True,
    serverSelectionTimeoutMS=10000,
)
DB_NAME = "credentials"
ENRICH_VERSION = "capabilities-v2.0"
WRITTEN_COLS = ("models", "model_capabilities", "model_enrichment")


def get_db():
    return pymongo.MongoClient(**MONGO)[DB_NAME]


def now_utc():
    return datetime.now(timezone.utc)


# ── EXTENDED CAPABILITY VOCABULARY (30+) ─────────────────────────────────────
# Order: precedence matters — first match in `tier` lowers collide.
# Each cap: (name, [(pattern, weight)])

_EXTENDED_CAPS: List[Tuple[str, List[Tuple[str, float]]]] = [
    # ── Generative text
    ("chat",               [("chat", 0.9), ("instruct", 0.7), ("assistant", 0.7),
                            ("base", 0.4), ("llm", 0.5), ("it", 0.5)]),
    ("instruct",           [("instruct", 1.0)]),
    ("completion",         [("completion", 1.0), ("completion-model", 0.6)]),

    # ── Reasoning / thinking
    ("reasoning",          [("r1-", 1.0), ("reason", 1.0), ("think", 0.95),
                            ("thinking", 0.95), ("o1", 0.9), ("o3", 0.95),
                            ("o4-mini", 0.95), ("qwq", 1.0), ("cogito", 1.0),
                            ("grok-think", 1.0), ("qwen3-reason", 1.0),
                            ("deepseek-r1", 1.0)]),

    # ── Coding
    ("coding",             [("coder", 1.0), ("code-", 0.9), ("coding", 1.0),
                            ("starcoder", 1.0), ("codegemma", 1.0),
                            ("qwen-coder", 1.0), ("deepseek-coder", 1.0),
                            ("llmcode", 1.0), ("codex", 0.9),
                            ("starcoder2", 1.0), ("wizardcoder", 1.0),
                            ("granite-code", 1.0)]),
    ("code_review",        [("code-review", 1.0), ("reviewer", 0.8)]),
    ("debugging",          [("debug", 0.9), ("bug-hunter", 0.9)]),

    # ── Vision / multimodal
    ("vision",             [("vl-", 1.0), ("vision", 1.0), ("multimodal", 1.0),
                            ("qvq", 1.0), ("glm-v", 1.0), ("gemini-pro-vis", 1.0),
                            ("llava", 1.0), ("qwen-vl", 1.0), ("deepseek-vl", 1.0),
                            ("gpt-4-vision", 1.0), ("-vis-", 0.9), ("vison", 0.9),
                            ("pixtral", 1.0), ("molmo", 1.0), ("llama3.2-vision", 1.0)]),
    ("image_understand",   [("vision", 0.8), ("vl-", 0.7), ("pixtral", 0.7),
                            ("understanding", 0.4), ("-see", 0.5)]),

    # ── Image generation / edit
    ("image",              [("dall-e", 1.0), ("dalle", 1.0), ("image", 0.8),
                            ("stable-diffusion", 1.0), ("sdxl", 1.0),
                            ("midjourney", 1.0), ("flux", 1.0), ("imagen", 1.0),
                            ("sora", 0.85), ("grok-imagine-image", 1.0),
                            ("qwen-image", 1.0), ("wan2.6-image", 1.0),
                            ("juggernaut", 0.95), ("kontext", 0.9),
                            ("recraft", 1.0), ("ideogram", 1.0),
                            ("reve", 1.0), ("playground", 1.0),
                            ("civitai", 1.0), ("minimax-image", 1.0)]),
    ("image_edit",         [("kontext", 1.0), ("edit", 0.7), ("imgedit", 1.0),
                            ("image-edit", 1.0)]),
    ("image_quality",      [("ultra", 0.7), ("max", 0.6), ("pro", 0.5),
                            ("hd", 0.5), ("quality", 1.0), ("xl", 0.4),
                            ("2-dev", 0.3), ("2-pro", 0.5), ("2-max", 0.7),
                            ("1.1-pro", 0.6), ("1-schnell", 0.3)]),

    # ── Video
    ("video",              [("video", 1.0), ("sora", 1.0), ("veo", 1.0),
                            ("kling", 1.0), ("runway", 1.0), ("wan-", 0.95),
                            ("wan2.6", 1.0), ("cogvideo", 1.0), ("mochi", 1.0),
                            ("hunyuan-video", 1.0), ("ltx", 1.0),
                            ("seedance", 1.0), ("dreamina", 1.0),
                            ("pika", 1.0), ("luma", 1.0), ("ray", 0.9),
                            ("minimax-video", 1.0), ("gen-3", 1.0),
                            ("grok-imagine-video", 1.0)]),
    ("video_understand",   [("video-understanding", 1.0)]),

    # ── Audio
    ("audio",              [("whisper", 1.0), ("tts", 0.95), ("audio", 1.0),
                            ("music", 0.85), ("voice", 0.7),
                            ("transcribe", 0.95), ("speech", 0.9),
                            ("sonic", 1.0), ("bark", 1.0), ("eleven", 0.9),
                            ("audiogen", 1.0), ("musicgen", 1.0),
                            ("rvc", 1.0), ("tortoise", 1.0),
                            ("xtts", 1.0), ("styletts", 0.9)]),
    ("tts",                [("tts", 1.0), ("text-to-speech", 1.0), ("speech", 0.85),
                            ("voice", 0.7), ("elevenlabs", 0.9), ("eleven-", 0.9),
                            ("nova", 0.3), ("shimmer", 0.6), ("echo", 0.6),
                            ("onyx", 0.6), ("fable", 0.6), ("alloy", 0.6),
                            ("kore", 0.5), ("aria", 0.5), ("sage", 0.5),
                            ("neurtts", 1.0), ("neutts", 1.0), ("styletts", 1.0),
                            ("gpt-4o-mini-tts", 1.0), ("kokoro", 1.0)]),
    ("stt",                [("whisper", 1.0), ("transcribe", 1.0), ("asr", 1.0),
                            ("stt", 1.0), ("speech-to-text", 1.0),
                            ("voxtral", 1.0), ("scribe", 0.9), ("parakeet", 1.0)]),
    ("music",              [("musicgen", 1.0), ("audiogen", 0.8), ("music", 0.8),
                            ("heartmula", 1.0), ("lyria", 1.0), ("stable-audio", 1.0)]),
    ("voice_cloning",      [("voice-clone", 1.0), ("rvc", 1.0), ("bark", 0.9),
                            ("f5-tts", 1.0)]),

    # ── Embeddings & search
    ("embedding",          [("embed", 1.0), ("embedding", 1.0),
                            ("text-embedding", 1.0), ("ada-002", 1.0),
                            ("nomic-embed", 1.0), ("bge-embed", 1.0),
                            ("cohere-embed", 1.0)]),
    ("rerank",             [("rerank", 1.0), ("reranker", 1.0), ("cross-encoder", 0.9),
                            ("cohere-rerank", 1.0)]),

    # ── Tools / function calling
    ("function_calling",   [("function-call", 1.0), ("tool-call", 1.0),
                            ("tools", 0.85), ("agent", 0.5),
                            ("hermes-function", 1.0)]),
    ("json_mode",          [("json-mode", 1.0), ("json_mode", 1.0),
                            ("structured-output", 1.0), ("json", 0.4)]),
    ("streaming",          [("stream", 0.7), ("sse", 0.7)]),

    # ── Safety / alignment
    ("safety_filter",      [("guard", 1.0), ("content-filter", 1.0),
                            ("moderation", 1.0), ("safe", 0.6)]),

    # ── Long context
    ("long_context",       [("long-context", 1.0), ("1m-context", 1.0),
                            ("200k", 1.0), ("128k", 0.9), ("100k", 0.9),
                            ("1m", 0.9), ("yarn", 1.0)]),

    # ── Speed / size modifier (caps quality tier later)
    ("fast",               [("flash", 1.0), ("fast", 0.95), ("tiny", 1.0),
                            ("mini", 0.9), ("nano", 0.9), ("small", 0.7),
                            ("lite", 0.9), ("quick", 0.95), ("speed", 0.9),
                            ("turbo", 0.9), ("express", 0.9), ("haiku", 0.9)]),
    ("quality",            [("ultra", 1.0), ("max", 0.9), ("pro", 0.7),
                            ("hd", 0.7), ("premium", 1.0), ("opus", 0.9),
                            ("xl", 0.7), ("best", 0.7), ("high", 0.5)]),

    # ── Region / provider specific
    ("minimax_native",     [("minimax", 1.0), ("abab", 1.0)]),
    ("qwen_native",        [("qwen", 1.0), ("qwq", 1.0)]),
    ("deepseek_native",    [("deepseek", 1.0)]),
    ("llama_native",       [("llama", 1.0)]),
    ("mistral_native",     [("mistral", 1.0), ("mixtral", 1.0), ("codestral", 1.0)]),
    ("gemini_native",      [("gemini", 1.0)]),
    ("grok_native",        [("grok", 1.0)]),
    ("claude_native",      [("claude", 1.0)]),
    ("gpt_native",         [("gpt-", 1.0), ("o1", 0.85), ("o3", 0.85)]),
]

# Per-cap endpoint inference: which endpoint does it imply?
_CAP_ENDPOINT = {
    "chat": ("chat-completions", "/v1/chat/completions"),
    "completion": ("chat-completions", "/v1/completions"),
    "reasoning": ("chat-completions", "/v1/chat/completions"),
    "coding": ("chat-completions", "/v1/chat/completions"),
    "code_review": ("chat-completions", "/v1/chat/completions"),
    "debugging": ("chat-completions", "/v1/chat/completions"),
    "vision": ("chat-completions", "/v1/chat/completions"),
    "image_understand": ("chat-completions", "/v1/chat/completions"),
    "instruct": ("chat-completions", "/v1/chat/completions"),
    "function_calling": ("chat-completions", "/v1/chat/completions"),
    "json_mode": ("chat-completions", "/v1/chat/completions"),
    "streaming": ("chat-completions", "/v1/chat/completions"),
    "long_context": ("chat-completions", "/v1/chat/completions"),
    "quality": ("chat-completions", "/v1/chat/completions"),
    "fast": ("chat-completions", "/v1/chat/completions"),
    "safety_filter": ("moderations", "/v1/moderations"),

    "image": ("image-generations", "/v1/images/generations"),
    "image_edit": ("image-edits", "/v1/images/edits"),
    "image_quality": ("image-generations", "/v1/images/generations"),

    "video": ("video-generations", "/v1/video/generations"),
    "video_understand": ("chat-completions", "/v1/chat/completions"),

    "audio": ("audio-speech", "/v1/audio/speech"),
    "tts": ("audio-speech", "/v1/audio/speech"),
    "music": ("audio-speech", "/v1/audio/speech"),
    "voice_cloning": ("audio-speech", "/v1/audio/speech"),

    "stt": ("audio-transcriptions", "/v1/audio/transcriptions"),
    "transcription": ("audio-transcriptions", "/v1/audio/transcriptions"),

    "embedding": ("embeddings", "/v1/embeddings"),
    "rerank": ("rerank", "/v1/rerank"),
}

# Primary (most-decisive) capability per endpoint family — used as `primary_cap`.
_PRIMARY_BY_ENDPOINT_TYPE = {
    "chat-completions": "chat",
    "image-generations": "image",
    "image-edits": "image_edit",
    "video-generations": "video",
    "audio-speech": "tts",
    "audio-transcriptions": "stt",
    "embeddings": "embedding",
    "rerank": "rerank",
    "moderations": "safety_filter",
}

# Modality: input / output
_CAP_MODALITY = {
    "embeddings": ("text", "vector"),
    "image-generations": ("text", "image"),
    "image-edits": ("image+text", "image"),
    "video-generations": ("text", "video"),
    "audio-speech": ("text", "audio"),
    "audio-transcriptions": ("audio", "text"),
    "chat-completions": ("text", "text"),
    "rerank": ("text+text", "ordered"),
    "moderations": ("text", "boolean"),
}


# ── Pricing hint → free_tier_score (0..1) ─────────────────────────────────────
def infer_free_tier_score(model_doc: Dict[str, Any]) -> float:
    """Heuristik FREE likelihood; 1.0 = strongest FREE signal.
    Inputs: is_free, billing_class, is_free, price fields, raw suffix."""
    score = 0.0
    if model_doc.get("is_free") is True: score += 0.6   # single canonical free verdict
    # Pricing signals (input + output both 0 ⇒ free)
    try:
        inp = float(model_doc.get("price_per_m_input") or 0)
        out = float(model_doc.get("price_per_m_output") or 0)
        if inp == 0 and out == 0:
            score += 0.4
        elif (inp + out) < 0.5:
            score += 0.15
    except (TypeError, ValueError):
        pass
    # Suffix signals: ":free", "-free"
    mid = (model_doc.get("model_id") or "").lower()
    if ":free" in mid or "-free" in mid or mid.endswith("/free"):
        score += 0.3
    return min(1.0, round(score, 3))


# ── Quality tier for image / video / audio (helps free-only picker) ──────────
def infer_quality_tier(model_id: str) -> str:
    mid = model_id.lower()
    if any(s in mid for s in ("ultra", "max", "best", "premium", "opus", "1.1-pro")):
        return "high"
    if any(s in mid for s in ("hd", "xl", "quality", "pro", "dev", "2-pro", "2-dev")):
        return "standard"
    if any(s in mid for s in ("flash", "fast", "mini", "nano", "lite", "schnell")):
        return "fast"
    if any(s in mid for s in ("tiny", "-8b", "-4b", "-3b", "-1b")):
        return "tiny"
    return "standard"


# ── Capability detection (regex + provider-mode) ─────────────────────────────
def _detect_caps_extended(model_id: str, raw: Optional[Dict[str, Any]] = None) -> List[str]:
    mid = (model_id or "").lower()
    caps_scores: Dict[str, float] = {}
    for cap, pats in _EXTENDED_CAPS:
        best = 0.0
        for pat, w in pats:
            if pat in mid:
                if w > best:
                    best = w
        if best > 0:
            caps_scores[cap] = max(caps_scores.get(cap, 0.0), best)

    # Augment with provider raw metadata if present (e.g. openrouter supported_params)
    if isinstance(raw, dict):
        sp = raw.get("supported_parameters") or raw.get("parameters") or []
        if isinstance(sp, list):
            tokens = {str(x).lower() for x in sp}
            if "tools" in tokens or "tool_choice" in tokens:
                caps_scores["function_calling"] = max(caps_scores.get("function_calling", 0), 0.95)
            if "json" in tokens or "response_format" in tokens or "structured_outputs" in tokens:
                caps_scores["json_mode"] = max(caps_scores.get("json_mode", 0), 0.9)
            if "stream" in tokens:
                caps_scores["streaming"] = max(caps_scores.get("streaming", 0), 0.85)
        arch = (raw.get("architecture") or {}) if isinstance(raw, dict) else {}
        out_mod = arch.get("output_modalities") or raw.get("output_modalities") or []
        in_mod = arch.get("input_modalities") or raw.get("input_modalities") or []
        if isinstance(out_mod, list):
            for m in (str(x).lower() for x in out_mod):
                if m in ("image", "images"):
                    caps_scores.setdefault("image", 0.6)
                if m in ("video",):
                    caps_scores.setdefault("video", 0.6)
                if m in ("audio",):
                    caps_scores.setdefault("audio", 0.5)
        if isinstance(in_mod, list):
            if any("image" in str(x).lower() for x in in_mod):
                caps_scores.setdefault("vision", max(caps_scores.get("vision", 0), 0.6))
                caps_scores.setdefault("image_understand", max(caps_scores.get("image_understand", 0), 0.5))
            if any("audio" in str(x).lower() for x in in_mod):
                caps_scores.setdefault("stt", max(caps_scores.get("stt", 0), 0.5))

    # Sort: high confidence first, tie-broken by capability name ordering (stable)
    out = sorted(caps_scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [c for c, _ in out]


# ── Endpoint / modality inference ────────────────────────────────────────────
def infer_endpoint_type(caps: List[str]) -> Tuple[str, str]:
    """Return (endpoint_type, suggested_path)."""
    # Priority: chat/image/video/audio-specialized.
    score: Dict[str, int] = {}
    priority = ["image", "image_edit", "video", "stt", "tts", "music",
                "voice_cloning", "embedding", "rerank", "safety_filter",
                "function_calling", "json_mode", "vision", "chat"]
    for i, cap in enumerate(priority):
        if cap in caps:
            score[cap] = len(priority) - i
    if not score:
        return ("chat-completions", "/v1/chat/completions")
    top = max(score.items(), key=lambda kv: kv[1])[0]
    return _CAP_ENDPOINT.get(top, ("chat-completions", "/v1/chat/completions"))


def _modalities(endpoint_type: str) -> Tuple[str, str]:
    return _CAP_MODALITY.get(endpoint_type, ("text", "text"))


# ── Main ingest pass ─────────────────────────────────────────────────────────
def analyze_model(model_doc: Dict[str, Any]) -> Dict[str, Any]:
    mid = model_doc.get("model_id") or ""
    raw = model_doc.get("raw_metadata") or {}
    caps = _detect_caps_extended(mid, raw)
    ep_type, ep_path = infer_endpoint_type(caps)
    primary = _PRIMARY_BY_ENDPOINT_TYPE.get(ep_type, caps[0] if caps else "chat")
    if primary not in caps:
        caps = [primary] + caps
    in_mod, out_mod = _modalities(ep_type)
    return {
        "provider":           model_doc.get("provider"),
        "model_id":           mid,
        "capabilities":       caps,
        "capabilities_count": len(caps),
        "primary_cap":        primary,
        "endpoint_type":      ep_type,
        "endpoint_path":      ep_path,
        "input_modality":     in_mod,
        "output_modality":    out_mod,
        "quality_tier":       infer_quality_tier(mid),
        "free_tier_score":    infer_free_tier_score(model_doc),
        "is_free":      bool(model_doc.get("is_free")),
        "score":              model_doc.get("score"),
        "score_tier":         model_doc.get("score_tier"),
        "status":             model_doc.get("status"),
        "is_active":          bool(model_doc.get("is_active", False)),
        "updated_at":         now_utc(),
        "enrich_version":     ENRICH_VERSION,
    }


# ── Persistence ──────────────────────────────────────────────────────────────
def writeback(db, results: List[Dict[str, Any]], dry_run: bool = False) -> int:
    """Upsert enriched data into model_capabilities + model_enrichment."""
    if dry_run:
        return len(results)
    cap_col = db.model_capabilities
    enr_col = db.model_enrichment
    n = 0
    for r in results:
        key = {"provider": r["provider"], "model_id": r["model_id"]}
        cap_col.update_one(key, {"$set": {
            "provider": r["provider"], "model_id": r["model_id"],
            "capabilities": r["capabilities"],
            "primary_cap": r["primary_cap"],
            "endpoint_type": r["endpoint_type"],
            "endpoint_path": r["endpoint_path"],
            "input_modality": r["input_modality"],
            "output_modality": r["output_modality"],
            "updated_at": r["updated_at"],
        }}, upsert=True)
        enr_col.update_one(key, {"$set": {
            "provider": r["provider"], "model_id": r["model_id"],
            "free_tier_score": r["free_tier_score"],
            "is_free": r["is_free"],
            "quality_tier": r["quality_tier"],
            "score": r["score"],
            "score_tier": r["score_tier"],
            "capabilities_count": r["capabilities_count"],
            "enrich_version": r["enrich_version"],
            "updated_at": r["updated_at"],
        }}, upsert=True)
        # Also reflect endpoint_type + primary_cap into `models` itself so
        # runtime router can read in one hop.
        db.models.update_one(key, {"$set": {
            "endpoint_type": r["endpoint_type"],
            "endpoint_path": r["endpoint_path"],
            "primary_cap": r["primary_cap"],
            "quality_tier": r["quality_tier"],
            "free_tier_score": r["free_tier_score"],
            "input_modality": r["input_modality"],
            "output_modality": r["output_modality"],
            "capabilities": r["capabilities"],
            "capabilities_enriched_at": r["updated_at"],
        }})
        n += 1
    return n


# ── CLI ──────────────────────────────────────────────────────────────────────
def run(provider: str = None, only_missing: bool = False, dry_run: bool = False) -> dict:
    """Programmatic entry (used by the sync pipeline _enrich_provider). Enrich active
    models' capabilities_v2/endpoint_type/primary_cap/quality_tier/free_tier_score."""
    db = get_db()
    q = {"is_active": True}
    if provider:
        q["provider"] = provider
    if only_missing:
        q["capabilities"] = {"$exists": False}
    results = [analyze_model(d) for d in db.models.find(q)]
    written = writeback(db, results, dry_run=dry_run)
    return {"provider": provider or "ALL", "analyzed": len(results), "written": written}


def main():
    ap = argparse.ArgumentParser(description="SOT capabilities v2 enricher")
    ap.add_argument("--full", action="store_true", help="process all active models")
    ap.add_argument("--only-missing", action="store_true", help="only models w/o capabilities_v2")
    ap.add_argument("--provider", default=None, help="restrict to one provider")
    ap.add_argument("--capability", default=None, help="restrict to models with this cap")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    if args.stats:
        db = get_db()
        print("=== STATS ===")
        print(f"models total        : {db.models.count_documents({})}")
        print(f"models active       : {db.models.count_documents({'is_active': True})}")
        print(f"model_capabilities  : {db.model_capabilities.count_documents({})}")
        print(f"model_enrichment    : {db.model_enrichment.count_documents({})}")
        # Capabilities histogram
        pipeline = [
            {"$match": {"endpoint_type": {"$exists": True}}},
            {"$group": {"_id": "$endpoint_type", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
        ]
        print("\nBy endpoint_type:")
        for r in db.models.aggregate(pipeline):
            print(f"  {r['_id']:>25}  {r['n']}")
        # FREE / paid histogram
        pipeline_free = [
            {"$match": {"free_tier_score": {"$exists": True}}},
            {"$group": {"_id": {"$cond": [{"$gte": ["$free_tier_score", 0.7]}, "FREE-signal", "paid"]},
                         "n": {"$sum": 1}}},
        ]
        print("\nBy free signal:")
        for r in db.models.aggregate(pipeline_free):
            print(f"  {r['_id']:>15}  {r['n']}")
        return

    if not (args.full or args.only_missing):
        args.full = True

    db = get_db()
    q: Dict[str, Any] = {"is_active": True}
    if args.provider:
        q["provider"] = args.provider
    cursor = db.models.find(q)
    n_done = 0
    n_total = 0
    t0 = time.time()
    results = []
    for d in cursor:
        n_total += 1
        if args.only_missing and d.get("endpoint_type"):
            continue
        if args.capability and args.capability not in (d.get("capabilities") or []) \
                and args.capability not in (d.get("capabilities") or []):
            continue
        r = analyze_model(d)
        results.append(r)
        n_done += 1
        if n_done % 200 == 0:
            elapsed = time.time() - t0
            print(f"  analyzed {n_done}/{n_total} ({elapsed:.1f}s)")

    n_write = writeback(db, results, dry_run=args.dry_run)
    el = time.time() - t0

    # Aggregate stats for eod report
    endpoint_hist = {}
    free_hist = {"free": 0, "paid": 0}
    cap_hist = {}
    for r in results:
        endpoint_hist[r["endpoint_type"]] = endpoint_hist.get(r["endpoint_type"], 0) + 1
        if r["is_free"]:
            free_hist["free"] += 1
        else:
            free_hist["paid"] += 1
        for c in r["capabilities"]:
            cap_hist[c] = cap_hist.get(c, 0) + 1

    eid = sot_ops.generate_evidence_id(code="ENR2")
    sot_ops.write_audit(
        provider="*",
        model_id=f"capabilities_v2_run_{n_total}",
        event_type="enrich_capabilities_v2",
        actor="sot_enrich_capabilities_v2",
        source_collection="models",
        delta={"analyzed": n_done, "written": n_write, "endpoint_hist": endpoint_hist,
               "free_hist": free_hist, "version": ENRICH_VERSION},
        evidence_id=eid,
    )

    print(f"\n✓ {n_write} capabilities enriched  (idempotent, audit={eid}, version={ENRICH_VERSION}, {el:.1f}s)")
    print(f"  endpoints: {endpoint_hist}")
    print(f"  free/paid: {free_hist}")
    print(f"  caps_top:  {sorted(cap_hist.items(), key=lambda kv: -kv[1])[:12]}")


if __name__ == "__main__":
    main()
