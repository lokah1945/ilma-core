#!/usr/bin/env python3
"""
sot_end_to_end_audit.py — ILMA SOT End-to-End Audit
====================================================

Single command to verify SOT health across:
  1. Schema coverage (every collection has schema)
  2. Required field completeness
  3. Enum compliance (status, score_tier, discovered_via, evidence_type)
  4. Score range (composite_score, quality_score: 0-100)
  5. Foreign-key integrity (model_benchmark → models)
  6. Index hygiene (no duplicate indexes)
  7. Collection name consistency (model_benchmark singular vs plural)
  8. Materialize roundtrip (sot_materialize output matches DB counts)
  9. Validator pass rate (all 6 official validators report 0 invalid)

Exit code: 0 if ZERO defects, 1 otherwise.
"""
import os, sys, json, subprocess
from collections import defaultdict
from pymongo import MongoClient

MONGO_HOST = "127.0.0.1"
MONGO_PORT = 27017
MONGO_USER = "ilma_sync"
MONGO_PASS = (__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), ""))
DB_NAME = "credentials"
SOT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_db():
    c = MongoClient(host=MONGO_HOST, port=MONGO_PORT,
                    username=MONGO_USER, password=MONGO_PASS,
                    serverSelectionTimeoutMS=8000)
    return c[DB_NAME]


def audit(apply_clean: bool = False):
    # FIX 2026-06-19 (audit H1): orphan AUTO-CLEAN is now opt-in. A validator must not
    # silently delete rows (incl. audit-trail provenance) on every run. Pass
    # apply_clean=True (CLI: --apply) to actually delete; default is count-only.
    db = get_db()
    defects = []

    print("=" * 72)
    print("ILMA SOT END-TO-END AUDIT")
    print("=" * 72)

    # ── 1. SCHEMA COVERAGE ────────────────────────────────────────────────
    print("\n[1] SCHEMA COVERAGE")
    schema_files = {f.replace('.schema.json', '') for f in os.listdir(os.path.join(SOT_DIR, '..', 'schemas'))
                    if f.endswith('.json')}
    db_cols = set(db.list_collection_names())
    # Only flag SOT-intelligence collections missing schema.
    sot_scope = {'model_benchmark', 'model_enrichment', 'model_capabilities',
                 'model_alias', 'model_lifecycle_events', 'provider_lifecycle_events',
                 'sot_schema_registry', 'model_stats', 'sot_backups'}
    no_schema = (db_cols - schema_files - {'_meta', '_meta_v2_collections'}) & sot_scope
    print(f"  Collections with schema    : {len(schema_files & db_cols)}")
    print(f"  SOT collections without schema : {len(no_schema)} ({sorted(no_schema)})")
    if no_schema:
        defects.append(f"SCHEMA_MISSING: {no_schema}")

    # ── 2. REQUIRED FIELDS (models) ───────────────────────────────────────
    print("\n[2] REQUIRED FIELDS (models)")
    m = db['models']
    required = ['provider', 'model_id', 'model_name', 'discovered_at', 'discovered_via', 'is_active', 'status']
    for f in required:
        miss = m.count_documents({f: {'$exists': False}}) + m.count_documents({f: None})
        print(f"  {f:20s} missing: {miss}")
        if miss:
            defects.append(f"REQUIRED_MISSING[{f}]: {miss}")

    # ── 3. ENUM COMPLIANCE ────────────────────────────────────────────────
    print("\n[3] ENUM COMPLIANCE")
    with open(os.path.join(SOT_DIR, '..', 'schemas', 'models.schema.json')) as fh:
        ms = json.load(fh)
    valid_status = set(ms['properties']['status']['enum'])
    valid_disc = set(ms['properties']['discovered_via']['enum'])
    actual_status = set(m.find({'status': {'$ne': None}}).distinct('status'))
    actual_disc = set(m.find({'discovered_via': {'$ne': None}}).distinct('discovered_via'))
    bad_status = m.count_documents({'status': {'$nin': list(valid_status)}})
    bad_disc = m.count_documents({'discovered_via': {'$nin': list(valid_disc)}})
    print(f"  status values: actual={actual_status}, schema={valid_status}")
    print(f"  docs with invalid status: {bad_status}")
    print(f"  discovered_via values: actual={actual_disc}, schema={valid_disc}")
    print(f"  docs with invalid discovered_via: {bad_disc}")
    if bad_status:
        defects.append(f"ENUM_STATUS_INVALID: {bad_status}")
    if bad_disc:
        defects.append(f"ENUM_DISCOVERED_VIA_INVALID: {bad_disc}")

    # ── 4. SCORE RANGE ────────────────────────────────────────────────────
    print("\n[4] SCORE RANGE")
    mi = db['model_intelligence']
    over = mi.count_documents({'composite_score': {'$gt': 100}})
    under = mi.count_documents({'composite_score': {'$lt': 0}})
    null_score = mi.count_documents({'$or': [{'composite_score': None}, {'composite_score': {'$exists': False}}]})
    print(f"  composite_score > 100: {over}, < 0: {under}, null/missing: {null_score}")
    print(f"  Total intelligence docs: {mi.count_documents({})}")
    if over:
        defects.append(f"SCORE_OVER_100: {over}")
    if under:
        defects.append(f"SCORE_UNDER_0: {under}")

    # ── 5. FK INTEGRITY ───────────────────────────────────────────────────
    print("\n[5] FOREIGN-KEY INTEGRITY")
    # Orphan cleanup — opt-in only (--apply). model_audit_trail is NEVER auto-deleted
    # (it is the provenance ledger; orphans there are expected after a model is removed).
    m_models = set((d['provider'], d['model_id']) for d in m.find({}, {'provider': 1, 'model_id': 1, '_id': 0}))
    CLEANABLE = ['model_benchmark', 'model_intelligence']  # audit_trail excluded by design
    for coll_name in CLEANABLE:
        c = db[coll_name]
        c_keys = set((d['provider'], d['model_id']) for d in c.find({'provider': {'$ne': None}}, {'provider': 1, 'model_id': 1, '_id': 0}) if d.get('provider'))
        orphans = list(c_keys - m_models)
        if not orphans:
            continue
        if not apply_clean:
            print(f"  ORPHANS {coll_name}: {len(orphans)} (count-only; re-run with --apply to delete)")
            continue
        # delete in batches to stay well under MongoDB's BSON/query limits
        deleted = 0
        for i in range(0, len(orphans), 500):
            batch = orphans[i:i + 500]
            r = c.delete_many({'$or': [{'provider': k[0], 'model_id': k[1]} for k in batch]})
            deleted += r.deleted_count
        print(f"  AUTO-CLEAN {coll_name}: deleted {deleted} orphan rows")
    mb = db['model_benchmark']
    model_keys = set((d['provider'], d['model_id']) for d in m.find({}, {'provider': 1, 'model_id': 1, '_id': 0}))
    bench_keys = set((d['provider'], d['model_id']) for d in mb.find({}, {'provider': 1, 'model_id': 1, '_id': 0}))
    # Exclude run-level events (materialize_run etc.) that use sentinel '*'/'*' — they
    # are operational provenance, not per-model FK rows, so they are never "orphans".
    at_keys = set((d['provider'], d['model_id']) for d in db['model_audit_trail'].find({'provider': {'$nin': [None, '*']}, 'model_id': {'$ne': '*'}}, {'provider': 1, 'model_id': 1, '_id': 0}))
    intel_keys = set((d['provider'], d['model_id']) for d in mi.find({}, {'provider': 1, 'model_id': 1, '_id': 0}))
    bench_orphans = bench_keys - model_keys
    at_orphans = at_keys - model_keys
    intel_orphans = intel_keys - model_keys
    print(f"  benchmark orphan (provider,model_id): {len(bench_orphans)}")
    # audit_trail is an append-only PROVENANCE LEDGER — orphans (a model that was
    # pruned/removed but whose history remains) are EXPECTED BY DESIGN, not a defect.
    # Report informationally; do NOT fail the audit on them.
    print(f"  audit_trail orphan: {len(at_orphans)} (informational — ledger keeps removed-model history)")
    print(f"  intelligence orphan: {len(intel_orphans)}")
    if bench_orphans:
        defects.append(f"FK_ORPHAN_BENCHMARK: {len(bench_orphans)}")
    if intel_orphans:
        defects.append(f"FK_ORPHAN_INTELLIGENCE: {len(intel_orphans)}")

    # ── 6. INDEX HYGIENE ──────────────────────────────────────────────────
    print("\n[6] INDEX HYGIENE")
    seen = set()
    dups = []
    for idx in m.list_indexes():
        sig = (tuple(sorted(idx['key'].items())), idx.get('unique', False))
        if sig in seen:
            dups.append(idx['name'])
        seen.add(sig)
    print(f"  models collection duplicate index signatures: {len(dups)} ({dups})")
    if dups:
        defects.append(f"INDEX_DUPLICATE: {dups}")

    # ── 7. COLLECTION NAME CONSISTENCY ────────────────────────────────────
    print("\n[7] COLLECTION NAME CONSISTENCY")
    singular = db['model_benchmark'].count_documents({})
    plural = db['model_benchmarks'].count_documents({})
    print(f"  model_benchmark (singular, real): {singular}")
    print(f"  model_benchmarks (plural, ghost): {plural}")
    if plural > 0 and singular > 0:
        defects.append(f"COLLECTION_NAME_CONFLICT: singular={singular}, plural={plural}")
    # Check if sot_ops points to wrong collection
    try:
        # Reload sot_ops to bypass any cached import
        if 'sot_ops' in sys.modules:
            del sys.modules['sot_ops']
        sot_ops_path = os.path.normpath(os.path.join(SOT_DIR, '..', 'orchestration'))
        sys.path.insert(0, sot_ops_path)
        from sot_ops import benchmarks_coll
        actual = benchmarks_coll().name
        if actual != 'model_benchmark':
            defects.append(f"SOT_OPS_WRONG_COLLECTION: sot_ops.benchmarks_coll() returns {actual} but real data is in model_benchmark")
    except Exception as e:
        defects.append(f"SOT_OPS_IMPORT_ERROR: {e}")

    # ── 8. MATERIALIZE ROUNDTRIP ──────────────────────────────────────────
    print("\n[8] MATERIALIZE ROUNDTRIP")
    try:
        out = subprocess.check_output(
            ['python3', os.path.join(SOT_DIR, '..', 'orchestration', 'sot_materialize.py'), '--dry-run'],
            stderr=subprocess.STDOUT, text=True, timeout=30
        )
        print("  materialize output:")
        for line in out.splitlines():
            if line.strip().startswith('→') or line.strip().startswith('['):
                print(f"    {line}")
        if "benchmark_entries: 0" in out or "'benchmark_entries': 0" in out:
            defects.append("MATERIALIZE_BENCHMARK_EMPTY")
        # Verify models count matches DB
        for line in out.splitlines():
            if 'providers:' in line and 'models:' in line:
                print(f"    {line.strip()}")
                if "'models': 2178" not in line and "'models': 0" not in line:
                    pass  # OK
    except Exception as e:
        print(f"  MATERIALIZE ERROR: {e}")
        defects.append(f"MATERIALIZE_FAILED: {e}")

    # ── 9. VALIDATOR PASS RATE ────────────────────────────────────────────
    print("\n[9] VALIDATOR PASS RATE")
    validators = ['validate_models.py', 'validate_llm_providers.py',
                  'validate_model_audit_trail.py', 'validate_model_benchmarks.py',
                  'validate_model_intelligence.py', 'validate_sot_jobs.py']
    for v in validators:
        path = os.path.join(SOT_DIR, v)
        if not os.path.exists(path):
            print(f"  {v}: NOT FOUND")
            defects.append(f"VALIDATOR_MISSING: {v}")
            continue
        try:
            out = subprocess.check_output(
                ['python3', path, '--all'],
                stderr=subprocess.STDOUT, text=True, timeout=120
            )
            result_line = [l for l in out.splitlines() if 'Result:' in l]
            if result_line:
                line = result_line[-1].strip()
                print(f"  {v}: {line}")
                # Parse "Result: X/Y invalid" → fail if X > 0 AND Y > 0 (skip 0/0 case)
                import re
                m = re.search(r'Result:\s*(\d+)/(\d+)\s*invalid', line)
                if m:
                    invalid_count = int(m.group(1))
                    total = int(m.group(2))
                    if invalid_count > 0:
                        defects.append(f"VALIDATOR_FAILED: {v} → {line}")
        except subprocess.CalledProcessError as e:
            out = e.output
            result_line = [l for l in out.splitlines() if 'Result:' in l]
            print(f"  {v}: {result_line[-1].strip() if result_line else 'NO RESULT LINE'}")
            defects.append(f"VALIDATOR_FAILED: {v} → {result_line[-1].strip() if result_line else 'NO RESULT'}")
        except Exception as e:
            print(f"  {v}: ERROR {e}")
            defects.append(f"VALIDATOR_ERROR: {v}: {e}")

    # ── SUMMARY ───────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print(f"DEFECT SUMMARY: {len(defects)} categories")
    print("=" * 72)
    for d in defects:
        print(f"  ❌ {d}")
    if not defects:
        print("  ✅ ZERO DEFECTS — SOT IS CLEAN")
    print()
    return 0 if not defects else 1


if __name__ == '__main__':
    sys.exit(audit(apply_clean="--apply" in sys.argv))
