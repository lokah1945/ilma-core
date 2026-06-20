#!/usr/bin/env python3
"""
sot_ops.py — ILMA SOT Core Operations Library
================================================

Central library used by ALL SOT writers (provider_sync,
enricher, materializer). Provides:

  • MongoDB connection helpers
  • Evidence-ID generator (ILMA-EVID-YYYYMMDD-CCODE-XXXXX)
  • Audit-trail writer (called by every mutation)
  • Score computation (port of ilma_model_db_manager._compute_score)
  • Capability / specialization inference (port from provider_sync)
  • Idempotency lock helper for sot_jobs
  • BSON → JSON-safe normalizer

This is the single import surface for SOT consumers.
Runtime (ilma.py, ilma_model_router.py, etc.) does NOT import this module
directly — runtime reads the materialized MASTER.json / api_key.json cache.
"""
import os, sys, json, re, hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import pymongo
from bson import ObjectId

# ── MongoDB connection ────────────────────────────────────────────────────────
MONGO_HOST = "172.16.103.253"
MONGO_PORT = 27017
MONGO_USER = "quantumtraffic"
MONGO_PASS = (__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), ""))
MONGO_AUTH = "admin"
DB_NAME = "credentials"

def get_client() -> pymongo.MongoClient:
    return pymongo.MongoClient(
        host=MONGO_HOST, port=MONGO_PORT,
        username=MONGO_USER, password=MONGO_PASS,
        authSource=MONGO_AUTH,
        serverSelectionTimeoutMS=10000,
    )

def get_db():
    return get_client()[DB_NAME]

# Collection shortcuts
def models_coll():
    return get_db()["models"]
def benchmarks_coll():
    # FIX 2026-06-17: real collection is singular "model_benchmark" (3721 docs)
    # was plural "model_benchmarks" (0 docs / ghost collection)
    return get_db()["model_benchmark"]  # was plural (ghost collection)
def intelligence_coll():
    return get_db()["model_intelligence"]
def llm_providers_coll():
    return get_db()["llm_providers"]
def providers_coll():
    return get_db()["providers"]
def audit_coll():
    return get_db()["model_audit_trail"]
def jobs_coll():
    return get_db()["sot_jobs"]

# ── BSON → JSON-safe normalizer ───────────────────────────────────────────────
def normalize(value: Any, key: Optional[str] = None,
              numeric_fields: Optional[set] = None,
              integer_fields: Optional[set] = None) -> Any:
    """Recursively convert BSON types and coerce numeric strings."""
    nf = numeric_fields or set()
    intf = integer_fields or set()
    if key in nf and isinstance(value, str):
        s = value.strip()
        if s:
            try:
                if key in intf:
                    return int(s)
                return float(s)
            except (ValueError, TypeError):
                pass
    if isinstance(value, datetime):
        return value.isoformat() + ("" if value.tzinfo else "Z")
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: normalize(v, key=k, numeric_fields=nf, integer_fields=intf)
                for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v, numeric_fields=nf, integer_fields=intf) for v in value]
    return value

# ── Evidence-ID generator ─────────────────────────────────────────────────────
_EVIDENCE_COUNTERS: Dict[str, int] = {}
_EVIDENCE_USED: set = set()
_EVIDENCE_DB_SEEDED: set = set()  # day_keys whose counter has been seeded from DB max


def _claim_evidence_id(eid: str) -> bool:
    """Atomically check + claim an evidence_id. Returns True if claimed."""
    if eid in _EVIDENCE_USED:
        return False
    _EVIDENCE_USED.add(eid)
    return True


def generate_evidence_id(code: str = "SOT", salt: str = "") -> str:
    """Generate ILMA-EVID-YYYYMMDD-CCODE-XXXXX evidence id.

    CCODE: short domain tag (SOT, SOT-SYNC, SOT-ENRICH, SOT-MAT, etc.)
    XXXXX: 5-digit monotonic counter, with salt-derived offset to ensure
    uniqueness across separate script runs in the same day.

    If the generated id already exists in MongoDB or in-memory cache,
    increment until fresh.
    """
    from pymongo.errors import CollectionInvalid
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d")
    # Salt-based offset: hash of (date+code+salt) mod 100000
    salt_offset = 0
    if salt:
        h = hashlib.md5(f"{date_part}-{code}-{salt}".encode()).hexdigest()
        salt_offset = int(h[:8], 16) % 99999
    day_key = f"{date_part}-{code}"
    # FIX 2026-06-20: seed the per-day counter from the DB's current max ONCE per
    # process. Previously a fresh process restarted at 0 and collided with the
    # thousands of ids already written today, exhausting the 1000-retry loop and
    # making sync/enrich raise "Could not generate unique evidence_id".
    if day_key not in _EVIDENCE_DB_SEEDED:
        _EVIDENCE_DB_SEEDED.add(day_key)
        try:
            prefix = f"ILMA-EVID-{date_part}-{code}-"
            top = get_db()["model_audit_trail"].find_one(
                {"evidence_id": {"$regex": f"^{prefix}"}},
                sort=[("evidence_id", -1)], projection={"evidence_id": 1})
            if top and top.get("evidence_id"):
                maxn = int(top["evidence_id"].rsplit("-", 1)[-1])
                _EVIDENCE_COUNTERS[day_key] = max(
                    _EVIDENCE_COUNTERS.get(day_key, 0), maxn + salt_offset)
        except Exception:
            pass
    _EVIDENCE_COUNTERS.setdefault(day_key, salt_offset)
    _EVIDENCE_COUNTERS[day_key] += 1
    counter = _EVIDENCE_COUNTERS[day_key] % 100000
    eid = f"ILMA-EVID-{date_part}-{code}-{counter:05d}"
    # Ensure unique
    attempts = 0
    while attempts < 1000:
        if _claim_evidence_id(eid):
            # Cross-check with MongoDB
            try:
                coll = get_db()["model_audit_trail"]
                if coll.find_one({"evidence_id": eid}, {"_id": 1}):
                        # Already in DB, increment and retry
                        _EVIDENCE_COUNTERS[day_key] += 1
                        counter = _EVIDENCE_COUNTERS[day_key] % 100000
                        eid = f"ILMA-EVID-{date_part}-{code}-{counter:05d}"
                        attempts += 1
                        continue
            except Exception:
                pass
            return eid
        _EVIDENCE_COUNTERS[day_key] += 1
        counter = _EVIDENCE_COUNTERS[day_key] % 100000
        eid = f"ILMA-EVID-{date_part}-{code}-{counter:05d}"
        attempts += 1
    raise RuntimeError(f"Could not generate unique evidence_id after 1000 attempts (code={code})")

# ── Audit trail writer ────────────────────────────────────────────────────────
def write_audit(
    provider: str,
    model_id: str,
    event_type: str,
    actor: str,
    source_collection: str,
    delta: Dict[str, Any],
    evidence_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """Append an audit record. Returns the evidence_id used."""
    eid = evidence_id or generate_evidence_id(code="SOT")
    doc = {
        "provider": provider,
        "model_id": model_id,
        "event_type": event_type,
        "event_at": datetime.now(timezone.utc),
        "actor": actor,
        "source_collection": source_collection,
        "delta": delta,
        "evidence_id": eid,
    }
    if notes:
        doc["notes"] = notes
    audit_coll().insert_one(doc)
    return eid

# ── Capability & specialization inference (port from provider_sync.py) ──────
_CAPABILITY_PATTERNS = [
    ("code",       ["coder", "code", "coding", "dev", "starcoder", "codegemma",
                    "qwen-coder", "deepseek-coder", "llmcode", "codex",
                    "starcoder2", "wizardcoder"]),
    ("reasoning",  ["think", "reason", "o1", "o3", "o4-mini", "qwq",
                    "grok-think", "thinking", "deepseek-r1", "r1-",
                    "qwen3-reason", "reasoning", "cogito"]),
    ("vision",     ["vl-", "vision", "multimodal", "qvq", "glm-v",
                    "gemini-pro-vis", "llava", "qwen-vl", "deepseek-vl",
                    "gpt-4-vision", "-vis-", "vison"]),
    ("fast",       ["flash", "fast", "tiny", "mini", "nano", "small",
                    "lite", "quick", "speed", "turbo", "express"]),
    ("instruct",   ["instruct", "chat", "assistant", "llm", "it",
                    "base", "rlhf"]),
    ("embedding",  ["embed", "embedding", "text-embedding", "ada"]),
    ("audio",      ["whisper", "tts", "audio", "music", "voice",
                    "transcribe", "speech"]),
    ("image",      ["dall-e", "dalle", "image", "stable-diffusion", "sdxl",
                    "midjourney", "flux", "imagen", "sora"]),
]
_SPECIALIZATION_PATTERNS = [
    ("coding",    ["coder", "code", "coding", "starcoder", "codegemma",
                   "deepseek-coder", "qwen-coder", "granite-code", "codex"]),
    ("reasoning", ["think", "reason", "o1", "o3", "qwq", "deepseek-r1",
                   "qwen3-reason", "r1-", "grok-think", "cogito"]),
    ("vision",    ["vl-", "vision", "multimodal", "qvq", "glm-v",
                   "gemini-pro-vis", "llava", "qwen-vl"]),
    ("instruct",  ["instruct", "chat", "assistant"]),
    ("fast",      ["flash", "fast", "lite", "quick", "turbo", "express"]),
    ("embedding", ["embed", "embedding", "text-embedding"]),
]

def infer_capabilities(model_id: str) -> List[str]:
    caps = set()
    mid = model_id.lower()
    for cap, pats in _CAPABILITY_PATTERNS:
        if any(p in mid for p in pats):
            caps.add(cap)
    return sorted(caps)

def infer_specialization(model_id: str) -> str:
    mid = model_id.lower()
    for spec, pats in _SPECIALIZATION_PATTERNS:
        if any(p in mid for p in pats):
            return spec
    return "general"

# ── Score computation (port of _compute_score from ilma_model_db_manager) ────
def compute_score(minfo: Dict[str, Any]) -> Dict[str, Any]:
    """Compute unified 0-100 score + tier + breakdown for a model.

    Weighting (with AA data): intelligence 45%, coding 30%, math 15%,
    capability_breadth 5%, usage_health 5%.
    Without AA: heuristic only, capped at 60.
    """
    aa = minfo.get("benchmark_aa") or {}
    def _num(v):
        try: return float(v)
        except (TypeError, ValueError): return None

    ai   = _num(aa.get("ai_index"))
    code = _num(aa.get("coding_index"))
    math = _num(aa.get("math_index"))

    # AA indices roughly 0..70 — normalize to 0..100
    def _norm(v, hi=70.0):
        if v is None: return None
        return max(0.0, min(100.0, (v / hi) * 100.0))

    n_ai, n_code, n_math = _norm(ai), _norm(code), _norm(math)

    caps = minfo.get("capabilities") or []
    cap_breadth = min(len(caps) / 5.0, 1.0) * 100.0

    usage = _num(minfo.get("benchmark_score"))  # passive 0..100
    err   = _num(minfo.get("error_rate"))
    usage_health = usage if usage is not None else (
        100.0 * (1.0 - err) if err is not None else None
    )

    breakdown: Dict[str, Any] = {}
    if n_ai is not None or n_code is not None or n_math is not None:
        parts, weights = [], []
        if n_ai   is not None: parts.append(n_ai);   weights.append(0.45); breakdown["intelligence"] = round(n_ai,1)
        if n_code is not None: parts.append(n_code); weights.append(0.30); breakdown["coding"]        = round(n_code,1)
        if n_math is not None: parts.append(n_math); weights.append(0.15); breakdown["math"]          = round(n_math,1)
        parts.append(cap_breadth); weights.append(0.05); breakdown["capability_breadth"] = round(cap_breadth,1)
        if usage_health is not None:
            parts.append(usage_health); weights.append(0.05); breakdown["usage_health"] = round(usage_health,1)
        wsum = sum(weights)
        score = sum(p*w for p, w in zip(parts, weights)) / wsum if wsum else 0.0
        source = "aa+heuristic"
    else:
        parts, weights = [cap_breadth], [0.7]
        breakdown["capability_breadth"] = round(cap_breadth,1)
        if usage_health is not None:
            parts.append(usage_health); weights.append(0.3); breakdown["usage_health"] = round(usage_health,1)
        wsum = sum(weights)
        raw = sum(p*w for p, w in zip(parts, weights)) / wsum if wsum else 0.0
        score = min(raw, 60.0)
        source = "heuristic"

    score = round(score, 2)
    if score >= 80:   tier = "S"
    elif score >= 65: tier = "A"
    elif score >= 50: tier = "B"
    elif score >= 35: tier = "C"
    else:             tier = "D"
    return {"score": score, "score_tier": tier, "score_source": source, "score_breakdown": breakdown}

# ── Idempotency lock for sot_jobs ────────────────────────────────────────────
def acquire_job_lock(job_id: str, job_type: str, actor: str,
                     idempotency_key: Optional[str] = None,
                     evidence_id: Optional[str] = None) -> Optional[Dict]:
    """Insert a new job in 'running' state. Returns None if a running job
    with the same idempotency_key already exists (caller should skip)."""
    eid = evidence_id or generate_evidence_id(code="JOB")
    ikey = idempotency_key or job_id
    # FIX 2026-06-19 (audit M3): the idempotency_key index is non-unique and job_id
    # embeds a timestamp, so the DuplicateKeyError path alone never deduped across
    # script runs (history shows 9 collided keys). Enforce dedup in code: if a job
    # with the same idempotency_key already exists in a running/recent-terminal state,
    # skip. This is the intended window — idempotency_key encodes a date/hour bucket.
    existing = jobs_coll().find_one({"idempotency_key": ikey,
                                     "status": {"$in": ["running", "success"]}})
    if existing is not None:
        return None
    doc = {
        "job_id": job_id,
        "job_type": job_type,
        "status": "running",
        "started_at": datetime.now(timezone.utc),
        "actor": actor,
        "idempotency_key": ikey,
        "evidence_id": eid,
    }
    try:
        jobs_coll().insert_one(doc)
        return doc
    except pymongo.errors.DuplicateKeyError:
        return None

def finish_job(job_id: str, status: str, result: Optional[Dict] = None,
               error: Optional[str] = None) -> None:
    update = {
        "status": status,
        "finished_at": datetime.now(timezone.utc),
    }
    if result is not None: update["result"] = result
    if error is not None: update["error"] = error
    jobs_coll().update_one({"job_id": job_id}, {"$set": update})

# ── Indexes bootstrap ────────────────────────────────────────────────────────
ENSURED_INDEXES = False


def _ensure_unique_index(coll, keys, name):
    """Create a unique index by name, but if an index with same keys already
    exists under a different name (or the same name with different options),
    skip silently. Prevents IndexOptionsConflict on re-runs."""
    target_key = dict(keys)
    for idx in coll.list_indexes():
        if dict(idx.get("key")) == target_key:
            # Index already exists with these keys; nothing to do
            return
    try:
        coll.create_index(keys, unique=True, name=name)
    except pymongo.errors.OperationFailure as e:
        if getattr(e, "code", None) == 85:  # IndexOptionsConflict
            return  # already exists under different name
        raise

def ensure_indexes(force: bool = False) -> None:
    """Create all required SOT indexes (idempotent)."""
    global ENSURED_INDEXES
    if ENSURED_INDEXES and not force:
        return
    audit_coll().create_index([("provider", 1), ("model_id", 1)])
    audit_coll().create_index([("event_at", -1)])
    audit_coll().create_index([("evidence_id", 1)], unique=True)
    jobs_coll().create_index([("job_id", 1)], unique=True)
    jobs_coll().create_index([("idempotency_key", 1)])
    jobs_coll().create_index([("started_at", -1)])
    # FIX 2026-06-19 (audit M-1): models must have unique (provider, model_id) to prevent drift duplicates
    _ensure_unique_index(
        models_coll(),
        [("provider", 1), ("model_id", 1)],
        "models_provider_model_id_unique"
    )
    # Benchmarks unique per (provider, model_id, source) — handle existing
    _ensure_unique_index(
        benchmarks_coll(),
        [("provider", 1), ("model_id", 1), ("benchmark_source", 1)],
        "bm_provider_model_source_unique"
    )
    # Intelligence unique per (provider, model_id) — handle existing
    _ensure_unique_index(
        intelligence_coll(),
        [("provider", 1), ("model_id", 1)],
        "intel_provider_model_unique"
    )
    ENSURED_INDEXES = True

if __name__ == "__main__":
    # CLI: bootstrap indexes + print state
    ensure_indexes(force=True)
    print("SOT indexes ensured.")
    for name, coll in [
        ("models", models_coll()),
        ("model_benchmarks", benchmarks_coll()),
        ("model_intelligence", intelligence_coll()),
        ("model_audit_trail", audit_coll()),
        ("sot_jobs", jobs_coll()),
        ("llm_providers", llm_providers_coll()),
    ]:
        print(f"  {name}: {coll.count_documents({})} docs, indexes:")
        for idx in coll.list_indexes():
            print(f"    {idx['name']}: {dict(idx['key'])}")
