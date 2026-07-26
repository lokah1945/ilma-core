# Phase R — "Fixes Claimed, File Unchanged" — Case Study (2026-06-17)

## The Incident

Phase 1.2 (`MASTER_PROMPT_PHASE1_2_PERFECT_SOT.md`) was executed on 2026-06-17 with
full authority. It claimed 3 CRITICAL findings (CRITICAL-1 free-model enforcement,
CRITICAL-2 score_tier self-heal, CRITICAL-3 is_free single source) and 5 HIGH
findings were FIXED in `ilma_model_router.py`. JSON reports `01_free_model_enforcement.json`
through `06_cleanup_docs.json` were written. The deliverable directory
`/root/upload/audit16062026/phase1_2/` was populated with 14+ evidence files.

Then Phase R (`MASTER_PROMPT_PHASE_R_REVERSE_ENGINEERING.md`) ran on the same day.
Its first task was to read the actual `ilma_model_router.py` file and trace the
reverse engineering from runtime back to database. The reading revealed:

| Claim from Phase 1.2 report | Actual file content (line 637-755) |
|---|---|
| is_free is single source from llm_providers | `is_free = intel.get('is_free', model_meta.get('is_free', False))` (dual source still present) |
| Loop over model_docs (2,178 visible) | `for intel in intel_docs` (loop still over intel, 2,177 visible) |
| Self-heal removed (DB authoritative) | `intel["score_tier"] = expected_tier` (self-heal still overwriting) |
| 4-query join replaced with $lookup | 4 separate `db.collection.find()` calls (no aggregation) |
| is_free field verified in llm_providers | 0 of 25 llm_providers docs have `is_free` field; actual field is `free_tier` |

**The fixes were never applied to the file.** The JSON reports captured the INTENDED
state, not the actual state.

## Root Cause (Best Guess)

1. **`patch` tool silently failed.** The `patch()` tool's fuzzy matching returned
   "applied" for a near-match, but the file content was unchanged. mtime verification
   would have caught this.
2. **Or: self-improvement cycle reverted the file.** The master-chief profile
   runs an hourly self-improvement cycle (`/root/.hermes/profiles/master-chief/`)
   that may have pulled from git and reverted local edits.
3. **Or: the fixes were written to a different file** (e.g. a `ilma_unified_router.py`
   copy that is not loaded at runtime).

Phase R could not pinpoint the exact mechanism. The fix was to re-apply using
direct Python file write (not the `patch` tool) and verify with `grep` + runtime
test.

## What the Phase R Report Should Have Caught

If the Phase 1.2 reports had included a "verification proof" block (per PITFALL 18
in `ilma-comprehensive-report-writing`):

```bash
$ grep -c "for intel in intel_docs" ilma_model_router.py
1   # ← should be 0 after fix; would have caught the gap
```

The bug would have been caught at write-time, not 2 phases later.

## The Fix That Worked (Phase R)

```python
# Direct Python in-place edit, NOT patch tool
path = "/root/.hermes/profiles/ilma/ilma_model_router.py"
with open(path) as f:
    src = f.read()

old = '''        # Group intel by provider
        master = {"providers": {}, "routing_rules": {}}
        for intel in intel_docs:
            ...'''
new = '''        # Group models by provider (loop over model_docs to ensure 2,178 visible)
        master = {"providers": {}, "routing_rules": {}}
        intel_by_id = {i.get("model_id"): i for i in intel_docs if i.get("model_id")}
        for model in model_docs:
            ...'''

assert src.count(old) == 1, f"Found {src.count(old)} matches, abort"
src = src.replace(old, new, 1)
with open(path, "w") as f:
    f.write(src)

# Verify
with open(path) as f:
    s2 = f.read()
assert s2.count(new) == 1
assert s2.count(old) == 0
```

After the fix, `python3 -c "from ilma_model_router import ILMAUnifiedRouter; ..."` showed
2,178 models (was 2,177).

## The is_free Schema Discovery

Phase R also discovered that `llm_providers.is_free` does NOT exist. The actual
schema field is `llm_providers.free_tier` (16 free_tier=True, 9 free_tier=False).
The Phase 1.2 "is_free single source" fix used the wrong field name and would
have marked all 2,178 models as paid.

**Correct field**: `llm_providers.free_tier` (provider-level) OR
`models.is_free` (per-model, 382 free / 1,796 paid — used as the authoritative
source in Phase R's fix).

## Lessons

1. **Never trust "applied" without verification.** A "fix applied" JSON report
   without `grep` proof and runtime count is a placeholder, not a fix.
2. **Verify field existence before assuming schema.** MongoDB's `find({field: value})`
   returns 0 docs silently when field doesn't exist (PITFALL 22).
3. **Direct file write > patch tool for production code.** The `patch` tool's
   fuzzy matching is great for docs but dangerous for runtime code.
4. **Run a smoke test, not just a unit test.** After applying fixes, run the
   actual production entry point and verify the runtime behavior changed.

## The Final State (After Phase R)

- 6 critical patches re-applied to `ilma_model_router.py`
- 2,178 models visible (was 2,177 before fix)
- is_free distribution: 382 free / 1,796 paid (matches MongoDB)
- Free model enforcement: `route_task` returns `01-ai/yi-large` (nvidia) is_free=True
- All 6 JSON reports + PHASE_R_SUMMARY.txt written to `/root/upload/audit16062026/phase_r/`

## See Also

- `ilma-false-positive-detection` SKILL.md (main skill) — pattern catalogue
- `ilma-comprehensive-report-writing` PITFALL 18 (claim-then-verify), 19 (patch tool silent fail), 20 (is_free schema), 22 (zero-count query bug)
- `ilma-audit-then-build` PITFALL 10 (audit-may-be-stale, 48h window) — same family
