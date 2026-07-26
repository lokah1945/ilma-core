# Phase 53-55: Internal Production Candidate — Critical Lessons

**Date:** 2026-05-10
**Phase span:** Phase 53 (Self-Optimization) → Phase 54 (Runtime Body Wiring) → Phase 55 (Production Candidate)

---

## Lesson 1: Blockers Before Documents

**Problem:** Phase 53 created 25 files but left 56 evidence ID gaps. Phase 54 discovered these gaps. Phase 55 spent time fixing Phase 53's incomplete backfill.

**Correct sequence:**
```
1. Hard blocker triage (what blocks production?)
2. Fix critical blockers (evidence gaps, weak_VERIFIED, broken imports)
3. Create ONE short triage doc with blocker list
4. Execute fixes
5. Create phase reports for what was actually done
```

**Wrong sequence:**
```
1. Create 12 sub-phase plan documents
2. Execute all sub-phases
3. Discover gaps during final audit
4. Retroactively fix (expensive)
```

---

## Lesson 2: Pre-Existing Test Failures Are NOT Optional

**Problem:** Phase 55 found 1 pre-existing test failure (`test_judge_good_artifact`). The failure was caused by an evidence ID (`ILMA-EVID-20260510-JUDGE-001`) that didn't exist in the ledger. Judge v4 would have flagged this as `fabrication` (FAIL).

**Fix:** Changed evidence ID to `ILMA-EVID-20260509-P30-QA_CRITIC-001` (which exists in ledger). Result: 212/212 PASS.

**Rule:** Run `python3 -m pytest tests/ -q --tb=no` at start of every phase. Fix any failures immediately. Do not leave pre-existing failures for "later."

---

## Lesson 3: Evidence ID Ledger Integrity

**Problem:** Phase 53 created 56 `evidence_id` entries in the capability registry but never populated the ledger. This created a gap: registry claimed evidence existed but ledger had no record.

**Rule:** When adding `evidence_id` to any capability, MUST immediately create a corresponding entry in `evidence/ilma_evidence_ledger.json`.

```
Safe sequence for adding evidence_id:
1. Create ledger entry first
2. Then add evidence_id to capability registry
3. Verify both exist before moving on
```

**Gap recovery:** If gap already exists, downgrade orphaned capabilities to `STRONGLY_SUPPORTED` and remove orphaned `evidence_id` fields. Never create fake ledger entries.

---

## Lesson 4: Claim Inflation Anti-Pattern

**Problem:** Phase 53 claimed "545/545 tests PASS." This was wrong — the 368 parallel jobs are job-level validators, NOT pytest unit tests.

**Correct categorization:**
- "159 pytest unit/integration tests PASS"
- "368 parallel job validators PASS"
- Total: 527 checks, all PASS

**Wrong:** "545/545 tests PASS" (inflated, misleading)

**Also:** Do NOT claim SSS+++ achieved unless independently verified. It remains an aspirational target.

---

## Lesson 5: Sub-Phase Count Accuracy

**Problem:** Phase 53 had A-L (12 sub-phases), not "11 sub-phases." ILMA miscounted.

**Rule:** Verify sub-phase count at start. Cross-check with letter sequence (A=1, B=2, ... L=12).

---

## Lesson 6: Judge v4 Fabricated Evidence ID Detection

**Finding:** Judge rubric v4 has a `fabrication` FAIL criterion: evidence ID not in ledger = FAIL. This is good — it catches inflated claims.

**Evidence ID pattern bug found:** Pattern `[A-Z]+` in `ilma_critic_judge.py` line 195 doesn't match alphanumeric like `P54J`. Should be `[A-Z0-9]+`.

**Impact:** Had to downgrade all 108 capabilities from VERIFIED to STRONGLY_SUPPORTED because 56 had orphaned evidence_ids.

---

## Lesson 7: Service Decomposition Safe Moves

**Safe moves executed:**
- `validator_service`: `scripts/ilma_specialist_validators.py` → `scripts/services/validators/` (LOW RISK)
- `report_generator`: `scripts/ilma_report_generator.py` → `scripts/services/report/` (MEDIUM RISK)

**Both with:** backward-compatible shims + DeprecationWarning + __init__.py

**Defer rules:** Never move core memory/registry/command_center during same session as other risky changes. Defer HIGH_RISK services.

---

## Lesson 8: INTERNAL_PRODUCTION_CANDIDATE Criteria

**All criteria met for INTERNAL_PRODUCTION_CANDIDATE:**
- ✅ One command interface works (`scripts/ilma.py`)
- ✅ Production smoke task passes (10/10 proof components)
- ✅ Recovery tests pass (7/7 scenarios)
- ✅ Final report generator works (markdown + JSON)
- ✅ Judge v4 enforces claim boundary (7 FAIL, 3 PASS_WITH_WARN)
- ✅ Evidence ledger gaps closed (0 gaps, 108 STRONGLY_SUPPORTED)
- ✅ weak_VERIFIED = 0
- ✅ Safety contract active (10 rules, always_on=false)
- ✅ No false claims
- ✅ All tests pass (212 unit + 368 parallel = 580 checks)

**What is NOT claimed:** SSS+++, external production deployment, always-on autonomy, 500/1000-file readiness