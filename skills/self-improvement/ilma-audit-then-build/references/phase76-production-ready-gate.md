# Phase 76 — Production-Ready Gate Pattern

## Origin
Bos mandate 2026-06-15: *"Lakukan perbaikan, patch, dan audit secara
komprehensif end to end. Berhenti hanya jika anda mendapatkan hasil
production ready tanpa cacat atau bug sama sekali."*

This is the consolidated pattern for any "production ready tanpa cacat"
request. It exists because the previous 3 files in the request were
reports (which Bos does not want) — Bos wants the system to actually
be production ready AND a structured report. The deliverable is the
patch + 16/N PASS, not the report.

## When to use
- Bos: "production ready", "100% bersih", "tanpa cacat", "berhenti
  hanya jika", "comprehensive end to end"
- Any time the verdict must be binary (N/N or NOT READY)
- Any time the previous audit was written days ago (P-25)

## The 4-stage pattern

### Stage 1: RE-VERIFY any audit older than 48h

```bash
# Run before acting on any audit
python3 -c "
import pymongo
c = pymongo.MongoClient(host='172.16.103.253', port=27017,
    username='quantumtraffic', password='***REDACTED-SEE-.env***')
db = c['credentials']
for col in sorted(db.list_collection_names()):
    print(f'{col}: {db[col].estimated_document_count()}')
"
```

If the real counts/structure differ from the audit, the audit is
stale. Re-derive the gap analysis from real state.

**Lesson from 2026-06-15:** SOT Final Governance Audit said
47/50 fail, 17 flaws. Real state was 5/16 ready. Re-verification
saved 4+ hours of unnecessary patching.

### Stage 2: BUILD idempotent patcher

`sot_e2e_patcher.py` shape (template):

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix-datetime", action="store_true")
    parser.add_argument("--add-ttl", action="store_true")
    parser.add_argument("--create-collections", action="store_true")
    parser.add_argument("--dedup-collections", action="store_true")
    parser.add_argument("--enforce-immutability", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.all or args.fix_datetime:
        # FL-01: BSON datetime → ISO 8601
        ...
    if args.all or args.add_ttl:
        # FL-10: TTL indexes
        ...
    if args.all or args.create_collections:
        # Missing collections
        ...
    if args.all or args.dedup_collections:
        # Duplicate collection merge/drop
        ...
    if args.all or args.enforce_immutability:
        # Schema validator (Layer 1 of 3)
        ...
    if args.validate:
        # 8/N check dict, printed as score
        results = validate_all()
        total_pass = sum(1 for r in results.values() if r.get("pass"))
        print(f"Score: {total_pass}/{len(results)}")
```

The `--validate` flag is the gate. Bos can run it any time to
verify the system state. It returns N/N where N is fixed.

### Stage 3: BUILD 3-layer enforcement (for Bos #3 immutability)

JSON Schema cannot prevent `$set` on existing valid doc. For
anything marked "IMMUTABLE" by Bos, you need 3 layers:

| Layer | Where | What it stops |
|---|---|---|
| 1. Schema validator | MongoDB | Invalid structure (missing required, bad enum) |
| 2. Python middleware | Application code | `$set api_key` on existing valid doc |
| 3. Audit trail | Change Streams / manual | Detects any mutation (post-mortem) |

```python
# Layer 2 pattern
class APIKeyImmutabilityError(Exception): pass

IMMUTABLE_FIELDS = {"api_key"}

def safe_update_provider(coll, account_email, update):
    if "api_key" in update or "api_key" in update.get("$set", {}):
        raise APIKeyImmutabilityError(
            "Bos #3: api_key is IMMUTABLE. Use rotate_api_key() instead."
        )
    return coll.update_one({"account_email": account_email}, update)

def rotate_api_key(coll, provider, new_key, new_email):
    """Bos #3 pattern: INSERT new + DISABLE old (never $set api_key)."""
    now = datetime.now(timezone.utc).isoformat()
    old = coll.find_one({"provider": provider, "status": "active"})
    if old:
        coll.update_one(
            {"_id": old["_id"]},
            {"$set": {"status": "rotated", "rotated_at": now}},
        )
    return coll.insert_one({
        "provider": provider, "account_email": new_email,
        "api_key": new_key, "status": "active", "added": now,
    })
```

Always include a `__main__` test harness that proves 3/3 pass.

### Stage 4: DELIVER 16/N PASS + 9-file report

**Verdict is binary.** No "mostly ready", no "94%".

```python
passed = sum(1 for _, p, _ in checks if p)
total = len(checks)
verdict = "✅ PRODUCTION READY" if passed == total else "❌ NOT PRODUCTION READY"
```

If anything fails, iterate the patch loop until it passes. If a
blocker is unfixable in this session, document it in
`06_known_issues.md` and accept "not ready" if it's P0. Don't
hide behind partial credit.

**9-file report to /root/upload/report/:**

```
00_INDEX.md              navigation + verdict (1 page)
01_executive_summary.md  TL;DR for Bos (60 lines max)
02_audit_before_after.md per-FL before/after table
03_patches_applied.md    what changed, with commands
04_validation_evidence.md raw validator output
05_middleware_layer.md   Bos #3 enforcement details
06_known_issues.md       what was NOT fixed and why
07_github_sync.md        git commit + push proof
08_appendix_paths.md     file paths, evidence IDs
```

**Git sync (MANDATORY):**
```bash
cd /root/.hermes/profiles/ilma
git add -A
git commit -m "Phase NN: N/N production ready"
git push origin master
```

## Worked example (2026-06-15)

**Before:**
- SOT checks: 4/8 pass
- Production readiness: ~5/16
- 4,800+ datetime fields still BSON
- 0 TTL indexes
- 4 collections missing
- 1 duplicate
- 13 provider status bugs

**After:**
- SOT checks: 8/8 pass
- Production readiness: **16/16 (100%)**
- 10,683 datetime fields → ISO
- 4 TTL indexes
- 4 new collections with seed data
- 0 duplicates
- 13 provider statuses fixed

**Git:** commit `be79760` pushed to `lokah1945/ilma-core@master`.

**Bos command to verify anytime:**
```bash
cd /root/.hermes/profiles/ilma/sot
python3 sot_e2e_patcher.py --validate
# Score: 8/8 checks passed
```

## Pitfalls (new in Phase 76)

- **P-25** Audit may be stale (always re-verify)
- **P-26** BSON datetime vs ISO string silent P0
- **P-27** JSON Schema can't enforce immutability (3 layers needed)
- **P-28** provider.status should derive from models
- **P-29** _meta god-object split into 4 collections

Full pitfall table in
`ilma-sot-migration-mongodb/references/sot-e2e-patcher-phase76-2026-06.md`.
