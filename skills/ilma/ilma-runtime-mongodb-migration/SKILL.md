---
name: ilma-runtime-mongodb-migration
description: "Migrate ILMA runtime code from JSON/file-based reads to 100% MongoDB-driven. Class-level skill for converting legacy file-based hot paths in `ilma_model_router.py` / `ilma_subagent_router.py` / `ilma_orchestrator.py` to direct MongoDB queries. Covers: backward-compat shape preservation (rebuild legacy dict from MongoDB joins), multi-write-path discovery (find all `MASTER_DB`/`open(.*json)` writes — load, flush, auto-disable, audit), score-tier auto-validation in-memory, JSON-grep verification (filter comments/docstrings/constant refs), 30s TTL cache with auto-invalidation, ZERO JSON fallback policy (RuntimeError on MongoDB failure per v7.0 spec), pymongo kwargs-vs-URI pitfall, and 5/5+12/12 test patterns. v7.0 verified 2026-06-16: 17/17 smoke + 1000x loop clean + idempotency 3x. Distinct from `ilma-sot-migration-mongodb` (which is data-plane only — never touches runtime code per Bos rule 2)."
triggers:
  - "migrate runtime to mongodb"
  - "json to mongodb migration"
  - "runtime mongodb driven"
  - "remove json from runtime"
  - "100% mongodb"
  - "zero json runtime"
  - "ilma_model_router.py mongodb"
  - "MASTER_DB mongodb"
  - "PROVIDER_INTELLIGENCE_MASTER mongodb"
  - "runtime mongodb"
  - "no json fallback"
  - "json to mongodb runtime"
  - "v7.0 mongodb"
  - "mongodb driven runtime"
---

# ILMA Runtime → MongoDB Migration (v7.0)

## When to use

- Bos says: "100% MongoDB-driven", "zero JSON runtime reads", "JSON to MongoDB",
  "remove JSON dependency", "migrate runtime to MongoDB", "runtime is reading JSON
  remove it", "no JSON fallback"
- Converting any file-based hot path in `ilma_*.py` runtime code to MongoDB
- `MASTER_DB`, `PROVIDER_INTELLIGENCE_MASTER.json`, `model_health_state.json`,
  `model_usage.jsonl` (writes), or any `.json` file referenced from runtime
- You just discovered (e.g. via Runtime Discovery) that a runtime file reads JSON
  for decision-making
- The SOT is already MongoDB-driven (data plane done) and now the runtime
  hot path must catch up

## CRITICAL distinction from SOT data-plane migration

**`ilma-sot-migration-mongodb`** covers migrating the **data plane** —
collections, indexes, validators, materializers, audit-trail schema. It
never touches `ilma_*.py` runtime code (Bos rule 2: "Jangan sentuh runtime").

**This skill** covers the **opposite direction** — migrating **runtime
hot paths** (`ilma_model_router.py`, etc.) from JSON to MongoDB while
SOT is already canonical. The data plane is already done; the runtime
hot path was lagging and now needs to catch up.

The two skills are complementary, not overlapping:
- SOT migration = collections get filled correctly
- Runtime migration = code reads from those collections, not JSON

If you find yourself writing `pymongo` for `models`/`providers` sync
purposes, that's still SOT (use `ilma-sot-migration-mongodb`).
If you find yourself replacing `open(MASTER_DB)` with `db.find()` for
routing decisions, that's runtime migration (use this skill).

## The migration pattern (5 phases, v7.0 verified)

### Phase 1: Discover ALL JSON touch points in runtime

```bash
# Active code reads (NOT comments/docstrings)
grep -n "json.load\|json.loads\|open(.*\.json" runtime_files

# Active code references to file-based constants
grep -n "MASTER_DB\|HEALTH_FILE\|USAGE_LOG\|TRACE_FILE" runtime_files

# ALL writes to JSON (more important than reads!)
grep -n "json.dump\|open(.*\.json.*'w'\|MASTER_DB.*w" runtime_files
```

Then read each match line by line. Distinguish:
- **Active read**: `with open(...) as f: x = json.load(f)` — must migrate
- **Active write**: `with open(MASTER_DB, "w") as f: json.dump(...)` — must migrate
- **Constant def**: `MASTER_DB = ROUTER_DATA / "MASTER.json"` — leave as ref, won't break
- **Docstring/comment**: `"""Loads MASTER.json"""` — leave alone

**Critical pitfall (P-66)**: `MASTER_DB` referenced in comments and in
docstrings will show up in any grep. The `MASTER_DB` constant itself is
fine to keep (just becomes a fallback or unused). The 4 active USES that
matter are: `MASTER_DB.stat()`, `open(MASTER_DB, "r")`, `open(MASTER_DB, "w")`,
`MASTER_DB.parent.mkdir()`. Count those specifically.

### Phase 2: Build MongoDB-equivalent shape

The runtime expects a specific dict shape (the legacy JSON file's shape).
Build it via 4-collection query and join:

```python
def _load_master_from_mongodb(self) -> Dict:
    """Join 4 collections, return dict matching JSON legacy shape."""
    db = self._mongo_client["credentials"]
    intel_docs = list(db["model_intelligence"].find({}, {"_id": 0}))
    model_docs = list(db["models"].find({}, {"_id": 0}))
    provider_docs = list(db["providers"].find({}, {"_id": 0}))
    llm_provider_docs = list(db["llm_providers"].find({}, {"_id": 0}))

    # Build lookups (1:1 maps)
    models_by_id = {m["model_id"]: m for m in model_docs}
    providers_by_name = {p["provider"]: p for p in provider_docs}
    llm_by_name = {p["provider"]: p for p in llm_provider_docs}

    # Group intel by provider, attach model + provider context
    master = {"providers": {}}
    for intel in intel_docs:
        mid = intel["model_id"]
        pname = intel["provider"]
        model_meta = models_by_id.get(mid, {})
        prov_meta = providers_by_name.get(pname, {})
        llm_meta = llm_by_name.get(pname, {})

        # Build record (subset of fields actually used by router)
        record = {
            "model_id": mid,
            "normalized_model": intel.get("normalized_model") or model_meta.get("normalized_model", ""),
            "provider": pname,
            "composite_score": intel.get("composite_score", 0.0),
            "score_tier": intel.get("score_tier", ""),
            "is_active": intel.get("is_active", True),
            "is_free": intel.get("is_free", False),
            "capabilities": intel.get("capabilities", []),
            "context_window": intel.get("context_window", 4096),
            "free_tier": prov_meta.get("free_tier", False),
            "api_key": llm_meta.get("api_key", ""),
            ...
        }
        master["providers"].setdefault(pname, {
            "models": {},  # CRITICAL: dict keyed by model_id, not list
            "free_tier": record["free_tier"],
            "base_url": llm_meta.get("base_url") or prov_meta.get("base_url", ""),
        })
        master["providers"][pname]["models"][mid] = record
    return master
```

**Critical pitfall (P-67)**: The shape expected by downstream code is
`{providers: {name: {models: {model_id: record}}}}` — **dict keyed by
model_id, not list of records**. The legacy JSON had it as a dict
(`pdata["models"][mid]`); if you build it as a list, downstream
`for mid, mdata in pdata.get("models", {}).items()` raises
`AttributeError: 'list' object has no attribute 'items'`.

### Phase 3: Replace load + ALL writes

For EACH of these patterns in runtime, replace with MongoDB:

| Pattern | Replacement |
|---|---|
| `with open(MASTER_DB) as f: x = json.load(f)` | `x = self._load_master_from_mongodb()` (cached) |
| `with open(MASTER_DB, "w") as f: json.dump(master, f)` | `mongo_db["model_intelligence"].update_many(..., {"$set": ...})` |
| `with open(HEALTH_FILE) as f: x = json.load(f)` | `x = list(mongo_db["model_intelligence"].find({...}))` or keep (health is ephemeral, not canonical) |
| `USAGE_LOG = ROUTER_DATA / "model_usage.jsonl"` writes | `mongo_db["model_audit_trail"].insert_one({...})` |

**Critical pitfall (P-68)**: Audit ALL `MASTER_DB` usages. There are typically
3-4 write sites, not 1. In v7.0, the runtime had:
- L643 `open(MASTER_DB) as f: master = json.load(f)` (read in `_load_master`)
- L788 `open(HEALTH_FILE) as f: self._health_cache = json.load(f)` (read health)
- L2164 `open(MASTER_DB, "w") as f: json.dump(master, f)` (write in `_auto_disable`)
- L2250 `open(MASTER_DB, "w") as f: json.dump(master, f)` (write in `flush_usage_updates`)

All 4 need replacement. Missing one = silent inconsistency (one path updates MongoDB, another path updates JSON, downstream code reads from a different source).

### Phase 4: 30s TTL cache with auto-invalidation

```python
def _load_master(self) -> Dict:
    with self._lock:
        now = time.time()
        if (self._master_cache is not None
                and self._master_mtime is not None
                and (now - self._master_mtime) < 30):
            return self._master_cache
        try:
            master = self._load_master_from_mongodb()
            self._master_cache = master
            self._master_mtime = now
            self._master_source = "mongodb"
        except Exception as e:
            # v7.0 spec: ZERO JSON FALLBACK
            raise RuntimeError(
                f"v7.0: 100% MongoDB-driven — cannot fall back to JSON. Error: {e}"
            ) from e
        return self._master_cache
```

**Critical pitfall (P-69)**: When writes happen (e.g. `flush_usage_updates` updates
`reliability_score`), the cache must be invalidated or the next read sees stale
data. Pattern: call `self._invalidate_candidate_cache()` after every MongoDB write,
OR use a shorter TTL (30s) and accept eventual consistency.

**Critical pitfall (P-70 — the v7.0 ZERO FALLBACK rule)**: Spec mandates
"no fallback to JSON if MongoDB fails". Don't add a `try/except` that
silently loads JSON when MongoDB raises. **Raise** the error. The
operator needs to KNOW that MongoDB is down — silent fallback creates
the exact stale-data problem the migration was supposed to solve.

### Phase 5: Verify with grep + tests

```bash
# Verification 1: 0 active JSON reads in runtime
grep -n "json.load\|json.loads\|PROVIDER_INTELLIGENCE_MASTER" runtime_files

# Filter false positives:
#   - Lines starting with "#" (comments)
#   - Docstring lines (inside """...""" or '''...''')
#   - Constant definition (`MASTER_DB = ...`)
# Real hits: `with open(MASTER_DB) as f: json.load(f)` should be 0
```

**Critical pitfall (P-71)**: The grep will return many matches in comments
and docstrings. Filter to ACTIVE CODE only:

```python
# False-positive filter
def is_active_code_line(line):
    s = line.strip()
    if s.startswith("#"): return False
    if s.startswith('"""') or s.startswith("'''"): return False
    if '"""' in s and s.count('"""') == 2: return False  # single-line docstring
    return True
```

Then run the 5+12 test pattern (5 forward + 12 from v6.0 smoke, but
add 1-2 new tests for the migrated path):
- 6.1-6.4 best_free_* (forward)
- 6.5 alias_resolves
- 6.6-6.7 chain/api_key (forward)
- 6.8 cascade_status (forward, may need to carve out by-design inactive like P-50/P-65)
- 6.9 tier_accuracy
- 6.10 fallback_robustness
- 6.11-6.17 reverse chains

In v7.0, all 17/17 passed.

## Migration recipe (copy-paste safe for v7.0+)

```python
# Inside your runtime class (e.g. ILMAUnifiedRouter):

from pymongo import MongoClient

# pymongo kwargs form — URI form auth-glitches (P-36 from sot-migration)
self._mongo_client = MongoClient(
    host="172.16.103.253", port=27017,
    username="quantumtraffic", password="***REDACTED-SEE-.env***",
    authSource="admin", directConnection=True,
    serverSelectionTimeoutMS=5000,
)

def _load_master(self) -> Dict:
    """v7.0: 100% MongoDB-driven, 30s TTL, ZERO JSON fallback."""
    with self._lock:
        now = time.time()
        if (self._master_cache is not None
                and self._master_mtime is not None
                and (now - self._master_mtime) < 30):
            return self._master_cache
        try:
            master = self._load_master_from_mongodb()
            self._master_cache = master
            self._master_mtime = now
            self._master_source = "mongodb"
        except Exception as e:
            raise RuntimeError(
                f"v7.0: 100% MongoDB-driven — no JSON fallback. Error: {e}"
            ) from e
        return self._master_cache

def _load_master_from_mongodb(self) -> Dict:
    db = self._mongo_client["credentials"]
    intel_docs = list(db["model_intelligence"].find({}, {"_id": 0}))
    model_docs = list(db["models"].find({}, {"_id": 0}))
    provider_docs = list(db["providers"].find({}, {"_id": 0}))
    llm_provider_docs = list(db["llm_providers"].find({}, {"_id": 0}))

    models_by_id = {m["model_id"]: m for m in model_docs if m.get("model_id")}
    providers_by_name = {p["provider"]: p for p in provider_docs if p.get("provider")}
    llm_by_name = {p["provider"]: p for p in llm_provider_docs if p.get("provider")}

    master = {"providers": {}, "routing_rules": {}}
    for intel in intel_docs:
        mid = intel.get("model_id")
        pname = intel.get("provider")
        if not mid or not pname:
            continue
        model_meta = models_by_id.get(mid, {})
        prov_meta = providers_by_name.get(pname, {})
        llm_meta = llm_by_name.get(pname, {})

        # Score tier auto-validation (A>=60, B>=45, C>=35, D<35)
        score = intel.get("composite_score", 0.0) or 0.0
        expected_tier = (
            "A" if score >= 60 else
            "B" if score >= 45 else
            "C" if score >= 35 else "D"
        )
        if intel.get("score_tier") != expected_tier:
            intel["score_tier"] = expected_tier  # in-memory fix

        record = {
            "model_id": mid,
            "normalized_model": intel.get("normalized_model") or model_meta.get("normalized_model", ""),
            "provider": pname,
            "composite_score": score,
            "score_tier": intel["score_tier"],
            "is_active": intel.get("is_active", True),
            "is_free": intel.get("is_free", False),
            "capabilities": intel.get("capabilities", model_meta.get("capabilities", [])),
            "context_window": intel.get("context_window", model_meta.get("context_window", 4096)),
            "free_tier": prov_meta.get("free_tier", False),
            "api_key": llm_meta.get("api_key", ""),
            "base_url": llm_meta.get("base_url") or prov_meta.get("base_url", ""),
        }
        master["providers"].setdefault(pname, {
            "models": {}, "free_tier": record["free_tier"],
            "base_url": record["base_url"],
        })
        master["providers"][pname]["models"][mid] = record
    return master
```

## Pitfalls (P-66..P-72)

- **P-66** `MASTER_DB` constant + `MASTER_DB.stat()` are different things.
  The constant is harmless. `MASTER_DB.stat()` and `open(MASTER_DB)` are
  active uses. Grep for the latter two specifically.
- **P-67** Shape must be `{providers: {name: {models: {model_id: record}}}}`
  not `{providers: {name: {models: [records]}}}`. Downstream code does
  `pdata["models"][mid]`. List-shaped breaks the lookup pattern.
- **P-68** Multi-write-path: 3-4 `open(MASTER_DB, "w")` sites in typical
  runtime. Audit all of them. Missed one = silent data divergence.
- **P-69** Cache invalidation after writes. `flush_usage_updates()` updates
  `reliability_score` — cache must invalidate or next read sees stale.
  Use 30s TTL OR call `self._invalidate_candidate_cache()` after writes.
- **P-70** ZERO JSON FALLBACK per v7.0 spec. Don't add `try/except` that
  loads JSON when MongoDB fails. Raise RuntimeError. Operator must know.
- **P-71** Grep verification false positives: comments, docstrings,
  constant defs. Filter to active code only before counting.
- **P-72** pymongo URI form can auth-glitch (already documented as P-36 in
  `ilma-sot-migration-mongodb`). Use **kwargs form** for `MongoClient()`.
- **P-73** (Phase R, 2026-06-17) "Single source of truth" must verify the
  field actually exists in the source collection. The Phase 1.2 fix
  assumed `llm_providers.is_free` exists; the actual field is
  `llm_providers.free_tier`. The fix used the wrong field, silently
  defaulting all models to paid. **Rule**: before writing a single-source
  fix, run a presence check on the target collection:
  ```python
  has = sum(1 for d in db.coll.find({}, {target_field: 1})
            if target_field in d)
  total = db.coll.estimated_document_count()
  print(f'{target_field}: {has}/{total} docs have it')
  # If <80% have it, the field is not "the source of truth" — find another
  ```
  See `ilma-comprehensive-report-writing` PITFALL 20 for the full pattern.
- **P-74** (Phase R, 2026-06-17) Verify count claims with the actual field
  name. A `db.coll.find({is_free: True}).count() == 0` when the field
  doesn't exist in the collection silently returns 0, not an error. A
  "0 free providers" report based on this query is meaningless. **Rule**:
  always do `find_one({})` first and inspect actual keys before counting
  on a field. See PITFALL 22 in `ilma-comprehensive-report-writing`.

## Cross-references

- `ilma-sot-migration-mongodb` — complementary skill (data-plane only,
  never touches runtime). Use when migrating collections, not code.
- `ilma-runtime-readiness-audit` — verifies the router can use SOT data.
  After migration, run the audit to confirm 17/17 smoke + 1000x loop.
- `ilma-comprehensive-report-writing` — for the report deliverable
  (10+ files in /root/upload/vXX/)
- `references/runtime-mongodb-migration-v70-2026-06.md` — v7.0 detailed
  session log with code diffs, all 17 smoke results, 1000x loop
  performance, idempotency verification

## Verified status

**v7.0 (2026-06-16)** — `ilma_model_router.py` migrated to 100% MongoDB-driven:
- `_load_master()` → queries 4 collections, 30s TTL, ZERO JSON fallback
- `flush_usage_updates()` → writes to MongoDB (reliability_score, avg_latency_ms)
- `_auto_disable_exploration` → persists to MongoDB (is_active=False)
- 17/17 smoke tests PASS
- 1000x loop CLEAN (539ms/iter avg)
- Idempotency 3x identical
- Git commit `02c06a6` pushed to `origin/master`
- DB FROZEN v2.0

**Subsequent audit/verify (v6.0 + v7.0)**: The "0 JSON runtime reads" classification
(P-61, P-64) was updated to include v7.0 migration status. Audit/Report
files (`ilma_health_check.py`, `ilma_model_status.py`,
`ilma_passive_benchmark_enricher.py`) still use JSON per spec 3.4 — allowed.
