# SOT End-to-End Audit Pattern (2026-06-17)

## Origin

Phase 76 (2026-06-15) declared SOT "production ready" with 16/16
hardening gates PASS and 0/2400 invalid docs. Two days later
(2026-06-17), an end-to-end audit run found **11 defect categories**
the Phase 76 audit missed:

| Defect category | Impact |
|---|---|
| 1. Schema missing for 9 SOT-intelligence collections | No governance, drift inevitable |
| 2. `status: "inactive"` (222 docs) not in enum | 10.2% models fail schema |
| 3. `composite_score` schema `maximum: 1` but data 0-100 | 100% (2177/2177) invalid |
| 4. `event_type: "runtime_audit"` (2 docs) not in enum | |
| 5. `benchmark_source: "stub_runtime_audit"` (1730 docs) not in enum | 46.5% invalid |
| 6. `evidence_type: "STUB"` (1730 docs) not in enum | 46.5% invalid |
| 7. Duplicate (provider, model_id) index on `models` | One unique, one non-unique |
| 8. 1014 FK orphans in `model_benchmark` (1519 rows) | Wasted I/O, misleading cache |
| 9. 46 FK orphans in `model_audit_trail` (180 rows) | |
| 10. `sot_ops.benchmarks_coll()` → ghost `model_benchmarks` (0 docs) | Materialize always 0 entries |
| 11. `provider_sync.py` CREDS_FILE wrong relative path | Mitigated by MongoDB PRIMARY |

**Lesson**: schema + index + validator audits alone are NOT enough.
You need the roundtrip check (materialize dry-run) AND the FK
integrity check (orphan rows) AND the collection-name consistency
check (ghost collections).

## The 9-Section Audit

```bash
cd /root/.hermes/profiles/ilma/sot
python3 validators/sot_end_to_end_audit.py
```

Output is a structured report. Exit 0 = clean, exit 1 = defects
found (cron-friendly).

| # | Section | Detection logic |
|---|---|---|
| 1 | **Schema coverage** | For each collection in DB, check `sot/schemas/<name>.schema.json` exists |
| 2 | **Required field completeness** | For each schema, count docs with `null` or missing for required fields |
| 3 | **Enum compliance** | For each enum field, count docs with value not in enum |
| 4 | **Score range** | `$bucket` aggregation on `composite_score` — anything in [1,100] when max=1 = scale wrong |
| 5 | **FK integrity** | `aggregate $group` on `(provider, model_id)` for each child collection, intersect with models keys |
| 6 | **Index hygiene** | Hash `(key_signature, unique_flag)` for each index, report duplicates |
| 7 | **Collection name consistency** | Import `sot_ops`, call each `*_coll()` function, verify name matches `db.<name>.count() > 0` |
| 8 | **Materialize roundtrip** | `sot_materialize.py --dry-run`, parse output, verify `benchmark_entries > 0` if `db.model_benchmark.count() > 0` |
| 9 | **Validator pass rate** | Subprocess each `validate_*.py --all`, parse "Result: X/Y invalid", report any with X > 0 (and Y > 0) |

Each section auto-fixes where safe (FK orphan cleanup) and reports
where manual review is needed (schema scale mismatch — could be
schema wrong OR data wrong).

## What Each Section Caught (2026-06-17)

### Section 1: Schema coverage

**Caught**: 9 SOT-intelligence collections without schemas:
`model_benchmark`, `model_enrichment`, `model_capabilities`,
`model_alias`, `model_lifecycle_events`, `provider_lifecycle_events`,
`sot_schema_registry`, `model_stats`, `sot_backups`.

**Fix**: Generate minimal schema from real doc shape:
```bash
python3 -c "
from pymongo import MongoClient
c = MongoClient(host='172.16.103.253', port=27017,
    username='quantumtraffic', password='***REDACTED-SEE-.env***', authSource='admin')
db = c['credentials']
for coll in ['model_benchmark', 'model_enrichment', ...]:
    docs = list(db[coll].find().limit(20))
    keys = sorted(set().union(*[set(d.keys()) for d in docs]) - {'_id'})
    print(f'{coll}: {keys}')"
```

Then hand-write schema with required fields + type constraints.
Place at `sot/schemas/<coll>.schema.json`.

### Section 3: Enum compliance

**Caught**: 4 enum mismatches across 3 collections. Validator
output is sufficient — `grep "FAIL"` + `awk -F"'"` to extract the
bad value, then add to enum.

```bash
python3 validate_models.py --all 2>&1 | grep "FAIL" | awk -F"'" '{print $2}' | sort -u
# Output: 'inactive'
```

### Section 5: FK integrity

**Caught**: 1014 benchmark + 46 audit_trail orphans.

**Fix** (auto-clean in audit script):
```python
m_models = set((d['provider'], d['model_id']) for d in m.find({}, {'provider':1,'model_id':1,'_id':0}))
for coll_name in ['model_benchmark', 'model_audit_trail', 'model_intelligence']:
    c = db[coll_name]
    c_keys = set((d['provider'], d['model_id']) for d in c.find({'provider': {'$ne': None}}, {'provider':1,'model_id':1,'_id':0}))
    orphans = list(c_keys - m_models)
    if orphans:
        r = c.delete_many({'$or': [{'provider': k[0], 'model_id': k[1]} for k in orphans]})
        print(f"  AUTO-CLEAN {coll_name}: deleted {r.deleted_count} orphan rows")
```

### Section 7: Collection name consistency

**Caught**: `sot_ops.benchmarks_coll()` returns `model_benchmarks`
(plural, 0 docs) but real data in `model_benchmark` (singular,
3721 docs). This is the **silent killer** — materialize ran without
error but produced 0 entries.

**Detection recipe**:
```python
# Compare collection count vs sot_ops function output
singular = db['model_benchmark'].count_documents({})
plural = db['model_benchmarks'].count_documents({})

sys.path.insert(0, '../orchestration')
if 'sot_ops' in sys.modules: del sys.modules['sot_ops']  # reload
from sot_ops import benchmarks_coll
actual = benchmarks_coll().name
if actual != 'model_benchmark':
    print(f"SOT_OPS_WRONG_COLLECTION: got {actual}, expected model_benchmark")
```

### Section 8: Materialize roundtrip

**Caught**: `sot_materialize.py --dry-run` reported
`benchmark_entries: 0` even though `model_benchmark` had 3721 docs.

**Detection recipe**:
```python
out = subprocess.check_output(
    ['python3', '../orchestration/sot_materialize.py', '--dry-run'],
    stderr=subprocess.STDOUT, text=True, timeout=30)
if "'benchmark_entries': 0" in out:
    defects.append("MATERIALIZE_BENCHMARK_EMPTY")
```

**Why this is critical**: every other section passed. The defect
was ONLY visible through materialize roundtrip. Validator said
`0/0 invalid` (because it was reading the ghost plural collection).
The data was in singular collection, validator wasn't seeing it,
materialize wasn't reading it. Triple-blind failure mode.

### Section 9: Validator pass rate

**Caught**: After schema fixes, all 6 validators report 0/N
invalid. Before fixes, breakdown was:

| Validator | Before | After |
|---|---|---|
| validate_models | 222/2178 | 0/2178 |
| validate_model_intelligence | 2177/2177 | 0/2177 |
| validate_model_benchmarks | 0/0 (ghost) | 0/2202 |
| validate_model_audit_trail | 2/408 | 0/228 |
| validate_llm_providers | 0/25 | 0/25 |
| validate_sot_jobs | 0/40 | 0/51 |

## Code: The Audit Tool Itself

Located at `sot/validators/sot_end_to_end_audit.py`. Standalone —
no external dependencies beyond `pymongo` and stdlib.

Key features:
- Single command exit code (0 = clean, 1 = defects)
- Auto-clean FK orphans (safe — data is unrecoverable)
- Reports defect categories by severity code
- Cron-friendly (set `CRON_AUDIT=1` to suppress audit trail writes)

## The Cascade Strategy Decision

When models are removed but FK orphans accumulate, three options:

| Option | Effect | When to use |
|---|---|---|
| **CASCADE-DELETE** | Drop orphans permanently | Default. 1519 unrecoverable refs gone. |
| **ARCHIVE** | Keep with `archived: true`, filter at materialize | Compliance requires audit trail preservation |
| **REMAP** | Remap orphans to closest valid model | Risky — semantic mapping may be wrong |

The audit tool implements cascade-delete by default (P-39). If
compliance is needed, set `AUDIT_FK_STRATEGY=archive` env var.

## When to Run

1. **After any schema migration** — verify enums match new data shape
2. **After any provider sync** — verify FK integrity (new models added, may create orphans)
3. **Before declaring production-ready** — the final gate after Phase 76 patcher
4. **Daily via cron** — catches drift introduced by enrichment runs
5. **On audit-trail write storms** — when `sot_jobs` activity is high, FK orphan risk increases

Cron template:
```bash
0 3 * * * cd /root/.hermes/profiles/ilma/sot && python3 validators/sot_end_to_end_audit.py 2>&1 | tee -a /var/log/sot_audit.log
```

If exit code != 0, alert Bos via Telegram (per SOUL.md sync rules).

## Pitfall Index Update

P-37: Collection name conflict (singular vs plural) — `sot_ops.X()`
may point to ghost collection with 0 docs while real data is
elsewhere. Detect by counting both singular and plural variants.

P-38: Score scale mismatch hides in 100% of docs — schema
`maximum: 1` but data is 0-100. Use `$bucket` aggregation to detect.

P-39: FK orphans accumulate when models are removed without
cascade. Default fix: cascade-delete (audit tool does this).

P-40: Wildcard FK (`provider: "*", model_id: "*"`) in audit_trail
confuses FK validation. Delete or move to dedicated `sot_system_events`.

P-41: Materialize roundtrip check is the only section that
catches data-flow disconnects where validators all pass but the
output is wrong.

## Reference

- **Audit tool**: `sot/validators/sot_end_to_end_audit.py` (300 lines)
- **Phase 76 patcher**: `sot/sot_e2e_patcher.py` (8/N gate, runs BEFORE this audit)
- **Phase 76 runtime audit**: `sot/sot_runtime_audit.py` (12 logic checks, runs BEFORE this audit)
- **This audit**: 9 sections, runs AFTER Phase 76, FINAL gate
