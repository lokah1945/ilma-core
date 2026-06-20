# SOT Skeptical Audit Pattern (Phase 74.1, 2026-06-14)

Bos mandate: "Gunakan paradigma skeptisisme, jangan percaya klaim, audit
komprehensif end-to-end, jika belum 100% bersih iterasi 1000x." This
document captures the audit infrastructure and bug registry that emerged.

## Why a separate document

Phase 74 self-assessment claimed "0/6238 invalid, 6/6 validators pass"
and was technically correct. But Bos's simple example
(`nvidia/nemotron-3-ultra-550b-a55b:free` marked `is_free=False` despite
`:free` suffix) revealed 6+ real bugs the schema validators couldn't see
because the data was internally consistent — it just didn't match reality.

Lesson: schema validation ≠ data correctness. You also need **semantic
checks** (does the data mean what it claims?) and **cross-source
checks** (does data agree with the source it was ported from?).

## Audit script (`sot_audit.py`)

Comprehensive audit covering 4 categories × 15+ checks:

### MongoDB integrity
- `BUG-DUP-1`: duplicate `(provider, model_id)` in models
- `BUG-DUP-2`: duplicate `evidence_id` in audit_trail
- `BUG-DUP-3`: duplicate `job_id` in sot_jobs

### Field consistency
- `BUG-IS_FREE-1`: `:free` suffix must imply `is_free=True`
- `BUG-IS_FREE-2`: price=0/0 should imply `is_free=True`
- `BUG-IS_FREE-3`: `is_free=True` shouldn't have non-zero real price
- `BUG-STATUS-1`: `is_active` must be boolean
- `BUG-STATUS-2`: `status` must be in enum
- `BUG-CAP-1`: model with capability keyword must have capabilities populated
- `BUG-CAP-2`: model with capabilities must have specialization
- `POT-MODEL_ID-WS`: no whitespace in model_id
- `POT-BRIDGE-MISSING`: provider should be in PROVIDER_CONFIGS
- `POT-IS_FREE-NO-PRICE`: `is_free=True` must have price info
- `POT-PRICE-NON-NUMERIC`: string prices must be numeric
- `POT-CTX-0`: no active model with `context_window=0`
- `POT-TIER-INCONSISTENT`: tier must match composite_score
- `POT-APIKEY-SHORT`: api_key must be ≥10 chars
- `POT-ORPHAN-ACTIVE`: no active orphan (no provider_sync coverage)
- `POT-INTEL-NO-SCORE`: score_tier must be backed by score
- `POT-BENCH-STALE`: no stale benchmarks on inactive models
- `POT-CAP-DRIFT`: capabilities consistent between models and intel
- `POT-MASTER-INTEL-DRIFT`: composite_score/score_tier consistent MASTER↔intel

### Cross-collection consistency
- `BUG-INTEL-1`: no orphan model_intelligence (uses aggregation, fast)
- `BUG-IS_FREE-4`: is_free consistent between models and intel
  (uses $lookup, NOT find_one in loop — see P-7)

### Disk cache consistency
- `BUG-MASTER-1`: no duplicate `(provider, model_id)` in MASTER.json
- `BUG-MASTER-2`: `:free` suffix in MASTER must have is_free=True
  (only flag if not disabled)
- `BUG-MASTER-3`: MASTER.json models count matches MongoDB
- `BUG-MASTER-4`: MASTER.json meta fields present
- `BUG-AK-1`: api_key.json llm coverage matches MongoDB
- `BUG-AK-2`: all api_key.json keys are masked
- `BUG-AK-3`: api_key.json preserves 40 non-llm keys

### Schema validation
- Run all 6 validators via subprocess (skip with `--skip-validators`)

## Audit loop script (`sot_audit_loop.py`)

Run `sot_audit.py` N times to detect flakiness/regressions:

```bash
python3 orchestration/sot_audit_loop.py --iterations 1000 \
    --full-disk-check-every 50 \
    --skip-validators
# Output: 1000 iterations, unique bug signatures, flakiness count
```

Key flags:
- `--iterations N`: total runs (default 1000 per Bos mandate)
- `--full-disk-check-every K`: run disk check every K iters (default 10)
- `--skip-validators`: skip 6 validator subprocesses (10x speedup)
- `--break-on-bug`: stop on first bug detection

Output summary includes:
- Total time + per-iter average
- First failure iter + last clean iter
- Unique bug signatures seen
- State changes (flakiness)

## Bug fix registry (`sot_fix.py`)

Idempotent. One function per BUG-* code, registered in `FIXES` dict.

```python
def fix_is_free_1(dry_run: bool = False) -> Dict[str, Any]:
    """BUG-IS_FREE-1: :free suffix but is_free=False → set is_free=True"""
    q = {"model_id": {"$regex": ":free$"}, "is_free": False, "is_active": True}
    affected = 0
    if not dry_run:
        result = models_coll().update_many(
            q,
            {"$set": {"is_free": True, "free_tier": True, "billing": "free",
                      "_sot_fixed_is_free_1": _now()}}
        )
        affected = result.modified_count
    else:
        affected = models_coll().count_documents(q)
    return {"bug": "BUG-IS_FREE-1", "affected": affected}

FIXES = {
    "BUG-IS_FREE-1": fix_is_free_1,
    "BUG-IS_FREE-2": fix_is_free_2,
    "BUG-CAP-1":     fix_cap_1,
    "BUG-INTEL-1":   fix_intel_1,
    "BUG-INTEL-2":   fix_intel_2,
    "BUG-IS_FREE-4": fix_intel_3_is_free_sync,
    "BUG-MASTER-2":  fix_master_2_is_free,
    "BUG-MASTER-3":  fix_master_orphan_sync,
    "POT-ORPHAN-2":  fix_master_orphan_v2_disabled,
}
```

Each fix:
- Takes `dry_run` flag
- Returns `{"bug": str, "affected": int}` (audit trail friendly)
- Uses `$set` with `_sot_fixed_<bug>: now()` marker (idempotency + history)
- Logs to model_audit_trail via `write_audit()`

## The full audit→fix→materialize loop

```bash
# 1. Audit (find what needs fixing)
python3 orchestration/sot_audit.py --json 2>&1 | jq '.bugs[] | .code'

# 2. Dry-run each fix to preview impact
for bug in BUG-IS_FREE-1 BUG-IS_FREE-2 BUG-CAP-1 BUG-INTEL-1 \
           BUG-INTEL-2 BUG-IS_FREE-4 BUG-MASTER-2 BUG-MASTER-3; do
    python3 orchestration/sot_fix.py --bug $bug --dry-run
done

# 3. Apply all fixes
python3 orchestration/sot_fix.py  # applies ALL registered fixes

# 4. Re-materialize MASTER.json from MongoDB
python3 orchestration/sot_materialize.py --target master

# 5. Re-audit (must be 0 bugs)
python3 orchestration/sot_audit.py 2>&1 | tail -5
# Expected: ✅ NO BUGS FOUND. SOT is clean.

# 6. Paranoid mode: 1000x loop
python3 orchestration/sot_audit_loop.py --iterations 1000 \
    --full-disk-check-every 50 --skip-validators
# Expected: ✅ ALL ITERATIONS CLEAN — SOT is stable.
```

## 1000x Audit Loop — Audit-Trail Soft-Fail Recipe (2026-06-14, NEW)

The 1000x audit loop can hit soft fails that look like flakes but are
actually a single bad doc re-validated each iteration. Pattern: large
`M state_changes` with only 1 actual bug → run `--break-on-bug` once to
localize, read the `BUG-VALID-*` code, grep validator with `--all` to
identify the bad doc.

Real example 2026-06-14:
- 1000x loop: 10/1000 iters flagged `(CRITICAL, BUG-VALID-MODEL_AUDIT_TRAIL, 1)`, 20 state changes
- `python3 validators/validate_model_audit_trail.py --all` → 1/404 invalid
- Bad doc `evidence_id=ILMA-EVID-20260614-V2MIGR-38168`, three violations:
  1. `event_type='sot_migration'` — not in schema enum. Use `materialize_run` for migration runs, or `model_updated` for data updates.
  2. `source_collection='_meta'` — not in schema enum. Use `providers` or `model_intelligence`.
  3. Missing required `delta` field.

**Idempotent patch recipe:**
```python
EVIDENCE = "ILMA-EVID-YYYYMMDD-AUDIT-TRAIL-FIX-001"
db['model_audit_trail'].update_one(
    {'evidence_id': '<bad-doc-evidence-id>'},
    {'$set': {
        'event_type': 'materialize_run',           # was 'sot_migration'
        'source_collection': 'providers',          # was '_meta'
        'delta': {                                  # was missing — schema requires it
            'migrated_counts': {'...': N},
            'note': 'normalized by audit-trail fixer'
        },
        'notes': f'normalized by {EVIDENCE}',
        'fix_evidence_id': EVIDENCE,
        'fixed_at': datetime.now(timezone.utc).isoformat(),
    }}
)
```

**Three-step verify (mirrors the audit→fix→re-audit loop):**
1. `python3 validators/validate_model_audit_trail.py --all` → expect `0/404 invalid`
2. `python3 orchestration/sot_audit_loop.py --iterations 20 --break-on-bug` → expect `✅ ALL ITERATIONS CLEAN`
3. Compare loop output: `unique_sigs=1` (just "0 bugs" itself), `state_changes=1` (just the summary oscillation). `unique_sigs≥2` or `state_changes>5` means more bad docs.

**Pitfall P-21 (delta is not strictly a diff):** Schema only requires
`delta: object` — no structural rule disallowing a compliance payload
(e.g. `{'compliance': {'v2_0_compliant': True}}`). The migration
writer that created the bad doc used delta incorrectly (left it empty
or under another key name). Backfill with whatever shapes the
migration meant to log.

## Performance notes

- Single audit (full): 75s (validators dominate)
- Single audit (`--skip-validators`): 2.4s
- Single audit (`--no-materialize-check --skip-validators`): 0.6s
- 1000x loop (`--skip-validators`): ~40 min total

For 1000x loops, always use `--skip-validators` — the schema
validators are deterministic and don't need to be re-run.

## Lessons for the next SOT audit

1. **Schema validation ≠ data correctness.** Need semantic + cross-source checks.
2. **N+1 queries are silent perf killers** — always use aggregation
   for cross-collection work.
3. **`$ifNull` on `$lookup` arrays returns the array, not the value** —
   use `$arrayElemAt` to unwrap.
4. **Known-orphan exemption is necessary** — orphan models are a feature
   (synced from MASTER), not a bug.
5. **Audit loops detect state-dependent bugs** — single-shot audits can
   miss bugs that only manifest under specific iteration timing.
6. **Fix functions are first-class** — idempotent registry, dry-run
   mode, audit trail integration.
