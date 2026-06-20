# SOT E2E Patcher Pattern (Phase 76 — 2026-06-15)

## Origin
After Phase 75 SOT MASTER RULE v2.0 compliance, the final 16/16
production-ready gate required a single end-to-end patcher that
collapses the audit + repair + verify cycle into one runnable script.
This is the consolidation of every pattern from Phases 73-75 into a
production deployable.

Bos mandate 2026-06-15: "Lakukan perbaikan, patch, dan audit secara
komprehensif end to end. Berhenti hanya jika anda mendapatkan hasil
production ready tanpa cacat atau bug sama sekali."

## When to use this pattern
- A new "production ready" gate is requested (any time Bos says
  "production ready" or "100% bersih")
- Multiple small P0/P1 issues need a coordinated patch, not ad-hoc fixes
- The audit loop and the patcher must run together (idempotent)
- You need ONE script that Bos can re-run to verify the gate
- The result must be expressable as N/N checks pass (not a vague
  "looks good")

## The 4-pillar structure of `sot_e2e_patcher.py`

```
PILLAR 1: fix_datetime_fields(coll, fields, dry_run)
  →  FL-01: BSON datetime → ISO 8601 string for ALL datetime fields
  →  Stats: {total, converted, skipped_null, errors}
  →  Use $type:"date" cursor, batch update

PILLAR 2: add_ttl_indexes(dry_run)
  →  FL-10: 4 TTL indexes (1y benchmark, 90d audit, 30d jobs, 180d enrichment)
  →  create_index([(field, 1)], expireAfterSeconds=N, name=...)

PILLAR 3: create_missing_collections(dry_run)
  →  sot_schema_registry, model_lifecycle_events,
     provider_lifecycle_events, sot_backups
  →  Seed with initial state from `models` and `providers`

PILLAR 4: validate_all()
  →  8 checks: topology, datetime, status enum, collections,
     TTL, unique index, no-dup, counts
  →  Returns dict of {name: {pass, detail}}
  →  Score: N/8
```

## CLI surface (idempotent, safe to re-run)

```bash
python3 sot_e2e_patcher.py --all          # run all 4 pillars
python3 sot_e2e_patcher.py --fix-datetime # FL-01 only
python3 sot_e2e_patcher.py --add-ttl      # FL-10 only
python3 sot_e2e_patcher.py --create-collections
python3 sot_e2e_patcher.py --dedup-collections
python3 sot_e2e_patcher.py --enforce-immutability
python3 sot_e2e_patcher.py --validate     # read-only gate
python3 sot_e2e_patcher.py --all --dry-run  # preview, no writes
```

The `--validate` flag runs `validate_all()` and is the only command
Bos needs to verify the gate.

## Critical Pitfalls (P-25..P-29, NEW from Phase 76)

### P-25: Audit-may-be-stale (FATAL: leads to wrong scope)

The SOT Final Governance Audit (2026-06-11) reported "47/50 criteria
fail, 17 flaws, ETA 8-15 sessions". Phase 76 (2026-06-15) discovered
that **Phase 73-75 auto-fixed most of those blockers** between
2026-06-10 and 2026-06-14. Re-verifying the audit claims showed:
- FL-09 (status enum): already fixed by Schema v2
- FL-10 (TTL): not fixed → still need patch
- FL-01 (datetime): not fixed → still need patch
- collections missing: not all missing (most were created)
- topology: NEVER checked by audit (assumed "unknown")

**Rule:** Any audit older than 48h should be re-verified before
acting on its findings. The real state often diverges from the
documented state due to async pipeline runs.

**Verify-first recipe:**
```python
# Run before accepting any audit's verdict
total_models = db["models"].count_documents({})
print(f"  models: {total_models}")  # If audit said 1353 and real is 2400, audit is stale
```

### P-26: BSON datetime in JSON Schema is the silent P0

The schema says `"format": "date-time"` (string), but pymongo writes
`datetime.now()` (BSON). Validator passes schema check (it doesn't
strict-check BSON type), but consumers (JS, JSON viewers, copy-out)
fail.

**Fix:** Always include `fl01_datetime_iso` in your validator:
```python
total_bad = sum(
    db[coll].count_documents({f: {"$type": "date"}})
    for coll in colls
    for f in datetime_fields
)
```

After fix, every doc's datetime field must be:
`"2026-06-14T22:51:53.123456+00:00"` (ISO with TZ, microsecond)
NOT `datetime.datetime(2026, 6, 14, 22, 51, 53, 123456)`.

### P-27: JSON Schema CANNOT prevent $set on existing valid doc

When you set a `validationLevel: "moderate"` + `validationAction: "error"`
on a collection, MongoDB will REJECT new inserts that don't match.
But it will NOT reject an updateOne that `$set`s a field on an
existing valid doc, because the new document still matches schema.

**Bos Decision #3 (api_key IMMUTABLE) cannot be enforced by schema
alone. Required:**

| Layer | Where | What it stops |
|---|---|---|
| 1. Schema validator | MongoDB | Invalid structure (missing required, bad enum) |
| 2. Python middleware | Application code | `$set api_key` on existing valid doc |
| 3. Audit trail | Change Streams / manual | Detects any mutation (post-mortem) |

Layer 2 is `sot_api_key_middleware.py` — `safe_update_provider()`
and `rotate_api_key()`. **Mandatory wrap all llm_providers writes.**

### P-28: Master.json self-healing — provider.status is derived

When you have N models under provider X, `provider.status` should
be DERIVED from model statuses, not independently set. This avoids
the "provider says disabled but has 220 active models" inconsistency
that bit us in MASTER.json pre-Phase 76.

**Rule for any `providers`-style collection:**
```python
for prov_name, prov in master["providers"].items():
    models = prov.get("models", {})
    n_active = sum(1 for m in models.values() if m.get("status") == "active")
    prov["status"] = "active" if n_active > 0 else "disabled"
```

Apply this rule on every materialize step. Otherwise inconsistencies
accumulate.

### P-29: 4-Collection split from `_meta` god-object (FL-11 fix)

`_meta` collection with 13+ sections in one doc is a "god object" that
fights atomic updates. Fix by SPLITTING into 4:

| Sub-collection | Contents |
|---|---|
| `_meta` (small) | Just SOT instance state (version, last_updated) |
| `sot_schema_registry` | Versioned schema definitions + migrations[] |
| `sot_jobs` | Async job tracking + idempotency |
| `sot_backups` | DR metadata manifest |

`FL-11` audit finding from 2026-06-11. Phase 76 implements this split
via `create_missing_collections()`.

## Middleware pattern: `sot_api_key_middleware.py`

```python
class APIKeyImmutabilityError(Exception): pass

IMMUTABLE_FIELDS = {"api_key"}

def safe_update_provider(coll, account_email, update):
    if "api_key" in update:
        raise APIKeyImmutabilityError("Bos #3: api_key is IMMUTABLE")
    if "$set" in update and "api_key" in update["$set"]:
        raise APIKeyImmutabilityError("Bos #3: $set api_key forbidden")
    return coll.update_one({"account_email": account_email}, update)

def rotate_api_key(coll, provider, new_key, new_email, added_by="system"):
    """Bos #3 pattern: INSERT new + DISABLE old (never $set api_key)."""
    now = datetime.now(timezone.utc).isoformat()
    old = coll.find_one({"provider": provider, "status": "active"})
    if old:
        coll.update_one(
            {"_id": old["_id"]},
            {"$set": {"status": "rotated", "rotated_at": now}},
            # NOTE: api_key NOT in $set
        )
    new_doc = {
        "provider": provider, "account_email": new_email,
        "api_key": new_key, "status": "active",
        "added": now, "added_by": added_by,
    }
    return coll.insert_one(new_doc)
```

**Test harness output (3/3 pass):**
```
Test 1: $set api_key → REJECTED ✅
Test 2: $set key_status → ALLOWED ✅
Test 3: rotate_api_key → new_id inserted, old disabled ✅
```

## Worked example (2026-06-15 E2E run)

**Before:**
- SOT checks: 4/8 pass
- Production readiness: ~5/16 (per stale audit)
- 4,800+ datetime fields still BSON
- 0 TTL indexes
- 4 collections missing
- 1 duplicate (model_benchmarks)
- 13 provider status bugs in MASTER.json

**After (`--all` then `--validate`):**
- SOT checks: 8/8 pass
- Production readiness: **16/16 (100%)**
- 10,683 datetime fields converted to ISO
- 4 TTL indexes
- 4 new collections with seed data
- 0 duplicates
- 13 provider statuses fixed

**Git:** commit `be79760` pushed to `lokah1945/ilma-core@master`.

**Validation command Bos can run anytime:**
```bash
cd /root/.hermes/profiles/ilma/sot
python3 sot_e2e_patcher.py --validate
# Score: 8/8 checks passed
```

## Final report structure (9 files in /root/upload/report/)

Bos's standing requirement: every production-ready session ends
with a 9-file structured report in `/root/upload/report/`. Template:

```
00_INDEX.md              — navigation + verdict
01_executive_summary.md  — TL;DR (60 lines max)
02_audit_before_after.md — per-FL before/after table
03_patches_applied.md    — what was changed, with commands
04_validation_evidence.md— raw validator output
05_middleware_layer.md   — Bos #3 enforcement details
06_known_issues.md       — what was NOT fixed and why
07_github_sync.md        — git commit + push proof
08_appendix_paths.md     — file paths, evidence IDs
```

Each file: concrete, no hand-waving, with tool output and evidence IDs.

## Cross-references

- `ilma-audit-then-build` — the parent methodology (this skill is
  the SOT-specific implementation)
- `ilma-sot-migration-mongodb` (this skill) — main SKILL.md
- `references/sot-pitfalls-phase74-75-2026-06.md` — P-1..P-24
  (the new P-25..P-29 are added here)
- `sot_e2e_patcher.py` — the script (800+ lines, idempotent)
- `sot_api_key_middleware.py` — middleware (200+ lines)
