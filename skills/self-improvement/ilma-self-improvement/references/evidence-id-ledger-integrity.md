# Evidence ID Ledger Integrity — Critical Pattern

**Logged:** 2026-05-10
**Status:** resolved
**Area:** tests, evidence, capability_registry

---

## Summary

Evidence IDs must have corresponding ledger entries. Missing ledger backing = fabrication = Judge v4 FAIL.

---

## Root Cause

Phase 53 added 56 `evidence_id` entries to capability registry without creating ledger entries. This created a gap that Judge v4 would flag as `fabrication`.

---

## Resolution

Downgraded all 108 capabilities from VERIFIED to STRONGLY_SUPPORTED. Removed orphaned `evidence_id` fields. Gap = 0.

---

## Prevention Rule

When adding `evidence_id` to any capability:
1. Create ledger entry first
2. Then add evidence_id to capability registry
3. Verify both exist before moving on

---

## Related

- Judge v4 `fabrication` criterion: evidence ID not in ledger = FAIL
- Evidence ID pattern bug: `[A-Z]+` should be `[A-Z0-9]+` to match alphanumeric IDs like `P54J`
- Pre-existing test failure: `test_judge_good_artifact` failed because evidence ID `ILMA-EVID-20260510-JUDGE-001` didn't exist in ledger. Fixed by changing to `ILMA-EVID-20260509-P30-QA_CRITIC-001` (exists in ledger).